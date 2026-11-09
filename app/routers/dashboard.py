from fastapi import APIRouter, Depends

from app.dependencies.auth import require_roles
from app.models.role import RoleEnum
from app.services.dashboard import obtener_resumen_dashboard

# ---------------------------------------------------------------------------
# Router — Dashboard Operativo (HU-22 / HU-23)
# Acceso restringido a: Coordinador, Responsable de Área y Administrador
# ---------------------------------------------------------------------------
router = APIRouter(
    dependencies=[
        Depends(
            require_roles(
                RoleEnum.COORDINADOR,
                RoleEnum.RESPONSABLE_AREA,
                RoleEnum.ADMINISTRADOR,
            )
        )
    ]
)


@router.get("/operativo", summary="Resumen operativo global")
def get_dashboard_operativo():
    """
    Devuelve métricas en tiempo real para el Dashboard Operativo (HU-23):
    - KPIs globales (activas, en progreso, bloqueadas, vencidas, resueltas).
    - Desglose por área / especialidad.
    - Alertas de incidencias que superaron su SLA (HU-22), ordenadas por retraso.

    Roles permitidos: coordinador, responsable_area, administrador.
    """
    return obtener_resumen_dashboard()