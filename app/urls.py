from fastapi import FastAPI

from app.routers import auth as auth_router
from app.routers import catalog as catalog_router
from app.routers import collaboration as collaboration_router
from app.routers import comment as comment_router
from app.routers import evidence as evidence_router
from app.routers import history as history_router
from app.routers import report as report_router
from app.routers import technical as technical_router
from app.routers import user as user_router
from app.routers import workflow as workflow_router


from app.routers import workload as workload_router
from app.routers import dashboard as dashboard_router


def register_routers(app: FastAPI) -> None:
    """
    Archivo central de rutas.
    Todos los routers del sistema se registran aqui.
    Para agregar un nuevo modulo: importarlo y anadir su include_router.
    """

    app.include_router(workload_router.router, prefix="/workload", tags=["Workload"])

    app.include_router(
        dashboard_router.router,
        prefix="/api/dashboard",
        tags=["Dashboard"],
    )

    app.include_router(
        auth_router.router,
        prefix="/auth",
        tags=["Auth"],
    )

    app.include_router(
        user_router.router,
        prefix="/users",
        tags=["Users"],
    )

    app.include_router(
        report_router.router,
        prefix="/reports",
        tags=["Reports"],
    )

    app.include_router(
        workflow_router.router,
        prefix="/reports",
        tags=["Workflow"],
    )

    app.include_router(
        technical_router.router,
        prefix="/reports",
        tags=["Technical"],
    )

    app.include_router(
        workflow_router.specialty_router,
        prefix="/specialties",
        tags=["Specialties"],
    )

    app.include_router(
        catalog_router.campus_router,
        prefix="/campuses",
        tags=["Campuses"],
    )

    app.include_router(
        catalog_router.faculty_router,
        prefix="/faculties",
        tags=["Faculties"],
    )

    app.include_router(
        catalog_router.location_router,
        prefix="/locations",
        tags=["Locations"],
    )

    app.include_router(
        comment_router.router,
        tags=["Comments"],
    )

    app.include_router(
        evidence_router.router,
        prefix="/reports",
        tags=["Evidences"],
    )

    app.include_router(
        collaboration_router.router,
        prefix="/reports",
        tags=["Collaborations"],
    )

    app.include_router(
        collaboration_router.collaboration_router,
        prefix="/collaborations",
        tags=["Collaborations"],
    )

    app.include_router(
        history_router.router,
        prefix="/reports",
        tags=["History"],
    )

    app.include_router(
        history_router.location_router,
        prefix="/history",
        tags=["History"],
    )

    app.include_router(
        history_router.activity_router,
        prefix="/activity",
        tags=["Activity"],
    )