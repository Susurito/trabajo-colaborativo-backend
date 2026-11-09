import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.models.report import Report, ReportStatusEnum as Status
from app.models.report_assignment import ReportAssignment
from app.models.report_status_event import ReportStatusEvent
from app.models.user import User
from app.models.user_role import UserRole
from app.models.role import RoleEnum
from app.models.specialty import IncidentCategoryEnum
from app.schemas.workflow import AssignmentCreate
from app.services import workflow

class UnblockingTests(unittest.TestCase):
    def actor(self, uid=2, role=RoleEnum.TECNICO):
        user = User(id=uid, name='Test', email='test@example.com', password_hash='unused')
        user.user_roles = [UserRole(user_id=uid, role=role)]
        return user

    def report(self):
        return Report(id=1, folio='test', title='Test', description='Test', campus_label='Test',
                      space_label='Test', author_id=1, assignee_id=2, specialty_id=1,
                      category=list(IncidentCategoryEnum)[0], status=Status.BLOQUEADA)

    def test_restore_both_sources_and_permissions(self):
        for source in [Status.ASIGNADA, Status.EN_PROGRESO]:
            with patch.object(workflow, '_latest_block', return_value=MagicMock(from_status=source)):
                workflow._assert_transition(None, self.report(), self.actor(), source)
                workflow._assert_transition(None, self.report(), self.actor(3, RoleEnum.RESPONSABLE_AREA), source)
                with self.assertRaises(HTTPException) as caught:
                    workflow._assert_transition(None, self.report(), self.actor(4), source)
                self.assertEqual(caught.exception.status_code, 403)
                other = Status.EN_PROGRESO if source == Status.ASIGNADA else Status.ASIGNADA
                with self.assertRaises(HTTPException) as caught:
                    workflow._assert_transition(None, self.report(), self.actor(), other)
                self.assertEqual(caught.exception.status_code, 409)

    def test_ordinary_status_change_cannot_assign(self):
        report = self.report()
        report.status = Status.VALIDADA
        with self.assertRaises(HTTPException):
            workflow._assert_transition(None, report, self.actor(), Status.ASIGNADA)

    def test_reassignment_preserves_block_and_transfers_permission(self):
        report = self.report()
        db = MagicMock()
        db.scalar.return_value = self.actor(4)
        with patch.object(workflow, '_get_report', return_value=report), patch.object(workflow, '_read', return_value=report):
            workflow.assign_report(db, report.folio, AssignmentCreate(assignee_id=4), self.actor(3, RoleEnum.RESPONSABLE_AREA))
        self.assertEqual(report.status, Status.BLOQUEADA)
        self.assertEqual(report.assignee_id, 4)
        added = [call.args[0] for call in db.add.call_args_list]
        self.assertTrue(any(isinstance(row, ReportAssignment) for row in added))
        self.assertFalse(any(isinstance(row, ReportStatusEvent) for row in added))
        with patch.object(workflow, '_latest_block', return_value=MagicMock(from_status=Status.ASIGNADA)):
            workflow._assert_transition(db, report, self.actor(4), Status.ASIGNADA)
            with self.assertRaises(HTTPException):
                workflow._assert_transition(db, report, self.actor(2), Status.ASIGNADA)

    def test_latest_block_determines_resume_after_multiple_cycles(self):
        from sqlmodel import Session, create_engine
        engine = create_engine('sqlite://')
        ReportStatusEvent.__table__.create(engine)
        with Session(engine) as db:
            for source, target in [(Status.ASIGNADA, Status.BLOQUEADA),
                                   (Status.BLOQUEADA, Status.ASIGNADA),
                                   (Status.EN_PROGRESO, Status.BLOQUEADA)]:
                db.add(ReportStatusEvent(report_id=1, actor_id=2, from_status=source,
                                        to_status=target, comment='Motivo'))
            db.commit()
            workflow._assert_transition(db, self.report(), self.actor(), Status.EN_PROGRESO)
            with self.assertRaises(HTTPException):
                workflow._assert_transition(db, self.report(), self.actor(), Status.ASIGNADA)
        engine.dispose()


if __name__ == '__main__':
    unittest.main(verbosity=2)
