from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlmodel import select

from app.models.report import Report, ReportStatusEnum
from app.models.report_assignment import ReportAssignment
from app.models.report_status_event import ReportStatusEvent
from app.models.role import RoleEnum
from app.models.specialty import Specialty
from app.models.user import User
from app.schemas.report import ReportRead
from app.schemas.workflow import (
    AssignmentCreate,
    AssignmentRead,
    CategorizeReport,
    SpecialtyRead,
    StatusChange,
    StatusEventRead,
)
from app.services.report import serialize_report

_ASSIGNABLE_FROM = {
    ReportStatusEnum.VALIDADA,
    ReportStatusEnum.ASIGNADA,
    ReportStatusEnum.REABIERTA,
    ReportStatusEnum.BLOQUEADA,
}
_CATEGORIZABLE = {
    ReportStatusEnum.REPORTADA,
    ReportStatusEnum.VALIDADA,
    ReportStatusEnum.REABIERTA,
}
_INTAKE_ROLES = {
    RoleEnum.RESPONSABLE_AREA,
    RoleEnum.COORDINADOR,
    RoleEnum.ADMINISTRADOR,
}
_ASSIGN_ROLES = _INTAKE_ROLES
_BLOCK_SOURCES = {ReportStatusEnum.ASIGNADA, ReportStatusEnum.EN_PROGRESO}
_REOPEN_SOURCES = {
    ReportStatusEnum.EN_VALIDACION,
    ReportStatusEnum.RESUELTA,
    ReportStatusEnum.CERRADA,
}


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _get_report(db: Session, folio: str) -> Report:
    report = db.scalar(select(Report).where(Report.folio == folio))
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe un reporte con ese folio",
        )
    return report


def _read(db: Session, report: Report) -> ReportRead:
    author = db.get(User, report.author_id)
    return serialize_report(report, author)


def _is_assignee(report: Report, actor: User) -> bool:
    return report.assignee_id is not None and report.assignee_id == actor.id


def _is_author(report: Report, actor: User) -> bool:
    return report.author_id == actor.id


def _record_status(
    db: Session,
    report: Report,
    actor: User,
    target: ReportStatusEnum,
    comment: str | None,
) -> None:
    db.add(
        ReportStatusEvent(
            report_id=report.id,
            from_status=report.status,
            to_status=target,
            actor_id=actor.id,
            comment=comment,
        )
    )
    report.status = target
    report.awaiting_validation = target == ReportStatusEnum.EN_VALIDACION
    report.updated_at = datetime.now(timezone.utc)


def list_specialties(db: Session) -> list[SpecialtyRead]:
    specialties = list(db.scalars(select(Specialty).order_by(Specialty.id)).all())
    return [SpecialtyRead.model_validate(specialty) for specialty in specialties]


def categorize_report(
    db: Session,
    folio: str,
    payload: CategorizeReport,
    _actor: User,
) -> ReportRead:
    report = _get_report(db, folio)
    if report.status not in _CATEGORIZABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se puede categorizar una incidencia reportada, validada o reabierta",
        )

    specialty = db.scalar(select(Specialty).where(Specialty.category == payload.category))
    if specialty is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay especialidad vinculada a esa categoría",
        )

    report.category = payload.category
    report.specialty_id = specialty.id
    report.priority = payload.priority
    report.classified = True
    report.updated_at = datetime.now(timezone.utc)
    db.add(report)
    _commit(db)
    db.refresh(report)
    return _read(db, report)


def assign_report(
    db: Session,
    folio: str,
    payload: AssignmentCreate,
    actor: User,
) -> ReportRead:
    report = _get_report(db, folio)
    if report.status not in _ASSIGNABLE_FROM:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La incidencia no está en un estado asignable",
        )
    if report.specialty_id is None or report.category is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La incidencia debe estar categorizada antes de asignarse",
        )
    if report.assignee_id == payload.assignee_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El técnico ya es el responsable actual",
        )

    assignee = db.scalar(
        select(User)
        .options(selectinload(User.user_roles))
        .where(User.id == payload.assignee_id)
    )
    if assignee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe el usuario a asignar",
        )
    if not assignee.is_active or not assignee.has_any_role(RoleEnum.TECNICO):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se puede asignar a un usuario activo con rol de técnico",
        )

    assigned_at = datetime.now(timezone.utc)
    db.add(
        ReportAssignment(
            report_id=report.id,
            assignee_id=assignee.id,
            assigned_by_id=actor.id,
            assigned_at=assigned_at,
            status=ReportStatusEnum.ASIGNADA,
            specialty_id=report.specialty_id,
        )
    )
    if report.status != ReportStatusEnum.BLOQUEADA:
        _record_status(db, report, actor, ReportStatusEnum.ASIGNADA, None)
    report.assignee_id = assignee.id
    report.assigned_at = assigned_at
    report.updated_at = assigned_at
    db.add(report)
    _commit(db)
    db.refresh(report)
    return _read(db, report)


def list_assignments(db: Session, folio: str) -> list[AssignmentRead]:
    report = _get_report(db, folio)
    rows = db.scalars(
        select(ReportAssignment)
        .where(ReportAssignment.report_id == report.id)
        .order_by(ReportAssignment.id.desc())
    ).all()
    return [AssignmentRead.model_validate(row) for row in rows]


def _latest_block(db: Session, report_id: int) -> ReportStatusEvent | None:
    return db.scalar(
        select(ReportStatusEvent)
        .where(
            ReportStatusEvent.report_id == report_id,
            ReportStatusEvent.to_status == ReportStatusEnum.BLOQUEADA,
        )
        .order_by(ReportStatusEvent.id.desc())
    )


def _forbid() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permiso para esta transición",
    )


def _conflict(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _assert_transition(db: Session, report: Report, actor: User, target: ReportStatusEnum) -> None:
    current = report.status
    if target == current:
        _conflict("La incidencia ya está en ese estado")

    if current == ReportStatusEnum.BLOQUEADA:
        blocked = _latest_block(db, report.id)
        if blocked is None or target != blocked.from_status:
            _conflict("Desde Bloqueada solo se puede volver al estado previo al bloqueo")
        if not (_is_assignee(report, actor) or actor.has_any_role(RoleEnum.RESPONSABLE_AREA)):
            _forbid()
        return

    if target == ReportStatusEnum.ASIGNADA:
        _conflict("El estado Asignada solo se alcanza mediante la asignación de un técnico")

    if target == ReportStatusEnum.VALIDADA:
        if current != ReportStatusEnum.REPORTADA:
            _conflict("Solo una incidencia reportada puede validarse")
        if not actor.has_any_role(*_INTAKE_ROLES):
            _forbid()
        return

    if target == ReportStatusEnum.EN_PROGRESO:
        if current not in {ReportStatusEnum.ASIGNADA, ReportStatusEnum.REABIERTA}:
            _conflict("Solo se puede pasar a En progreso desde Asignada o Reabierta")
        if not _is_assignee(report, actor):
            _forbid()
        return

    if target == ReportStatusEnum.EN_VALIDACION:
        if current != ReportStatusEnum.EN_PROGRESO:
            _conflict("Solo se puede enviar a validación desde En progreso")
        if not _is_assignee(report, actor):
            _forbid()
        return

    if target == ReportStatusEnum.RESUELTA:
        if current != ReportStatusEnum.EN_VALIDACION:
            _conflict("Solo se puede resolver desde En validación")
        if not _is_assignee(report, actor):
            _forbid()
        return

    if target == ReportStatusEnum.CERRADA:
        if current != ReportStatusEnum.RESUELTA:
            _conflict("Solo se puede cerrar una incidencia resuelta")
        if not (_is_author(report, actor) or actor.has_any_role(RoleEnum.VALIDADOR)):
            _forbid()
        return

    if target == ReportStatusEnum.BLOQUEADA:
        if current not in _BLOCK_SOURCES:
            _conflict("Solo se puede bloquear una incidencia asignada o en progreso")
        if not (_is_assignee(report, actor) or actor.has_any_role(RoleEnum.RESPONSABLE_AREA)):
            _forbid()
        return

    if target == ReportStatusEnum.REABIERTA:
        if current not in _REOPEN_SOURCES:
            _conflict("Solo se puede reabrir desde En validación, Resuelta o Cerrada")
        if current == ReportStatusEnum.CERRADA and not actor.has_any_role(RoleEnum.VALIDADOR):
            _forbid()
        if not (_is_author(report, actor) or actor.has_any_role(RoleEnum.VALIDADOR)):
            _forbid()
        return

    _conflict("Transición de estado no permitida")


def change_status(
    db: Session,
    folio: str,
    payload: StatusChange,
    actor: User,
) -> ReportRead:
    report = _get_report(db, folio)
    _assert_transition(db, report, actor, payload.status)
    _record_status(db, report, actor, payload.status, payload.comment)
    db.add(report)
    _commit(db)
    db.refresh(report)
    return _read(db, report)


def list_status_events(db: Session, folio: str) -> list[StatusEventRead]:
    report = _get_report(db, folio)
    rows = db.scalars(
        select(ReportStatusEvent)
        .where(ReportStatusEvent.report_id == report.id)
        .order_by(ReportStatusEvent.id.desc())
    ).all()
    return [StatusEventRead.model_validate(row) for row in rows]

