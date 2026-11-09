from datetime import datetime, timedelta
from typing import Dict, Any, List

from sqlalchemy import select, func
from sqlmodel import Session

from app.db.database import engine
from app.models.report import Report, ReportStatusEnum, ReportPriorityEnum
from app.models.specialty import Specialty
from app.models.user import User


# ---------------------------------------------------------------------------
# SLA dinámico por prioridad (HU-22) — sin columna due_date en BD
# ---------------------------------------------------------------------------
SLA_POR_PRIORIDAD: Dict[str, int] = {
    ReportPriorityEnum.ALTA.value:  24,   # Alta:  24 horas
    ReportPriorityEnum.MEDIA.value: 48,   # Media: 48 horas
    ReportPriorityEnum.BAJA.value:  72,   # Baja:  72 horas
    # Sin prioridad asignada → mismo SLA que media (48 h)
}
SLA_DEFAULT_HORAS = 48


def _sla_horas(prioridad: str | None) -> int:
    """Devuelve el límite de horas SLA según la prioridad de la incidencia."""
    if prioridad is None:
        return SLA_DEFAULT_HORAS
    return SLA_POR_PRIORIDAD.get(str(prioridad).lower(), SLA_DEFAULT_HORAS)


def _esta_vencida(report: Report, ahora: datetime) -> bool:
    """True si la incidencia superó su SLA calculado desde su fecha de creación."""
    sla = timedelta(hours=_sla_horas(report.priority))
    # Normalizar created_at: puede venir con o sin tzinfo
    created = report.created_at.replace(tzinfo=None) if report.created_at.tzinfo else report.created_at
    return (ahora - created) > sla


def _horas_vencida(report: Report, ahora: datetime) -> int:
    """Horas de retraso respecto al SLA (siempre ≥ 1 cuando vencida)."""
    sla = timedelta(hours=_sla_horas(report.priority))
    created = report.created_at.replace(tzinfo=None) if report.created_at.tzinfo else report.created_at
    exceso = (ahora - created) - sla
    return max(1, int(exceso.total_seconds() / 3600))


# ---------------------------------------------------------------------------
# Función principal del dashboard
# ---------------------------------------------------------------------------

def obtener_resumen_dashboard() -> Dict[str, Any]:
    """
    Genera el resumen operativo para el Dashboard (HU-22 / HU-23).

    Incluye:
    - KPIs globales: total activas, en progreso, bloqueadas, vencidas, resueltas.
    - Desglose por área / especialidad: total, bloqueadas y vencidas.
    - Alertas de incidencias vencidas: lista ordenada por horas de retraso.
    """
    with Session(engine) as db:
        activos_estados = [
            ReportStatusEnum.REPORTADA.value,
            ReportStatusEnum.VALIDADA.value,
            ReportStatusEnum.ASIGNADA.value,
            ReportStatusEnum.EN_PROGRESO.value,
            ReportStatusEnum.BLOQUEADA.value,
            ReportStatusEnum.REABIERTA.value,
        ]
        resueltos_estados = [
            ReportStatusEnum.RESUELTA.value,
            ReportStatusEnum.CERRADA.value,
        ]
        ahora = datetime.utcnow()

        # ------------------------------------------------------------------
        # 1. Cargar todas las incidencias activas en memoria para aplicar SLA
        # ------------------------------------------------------------------
        reportes_activos: List[Report] = db.scalars(
            select(Report).where(
                func.lower(Report.status).in_(activos_estados)
            )
        ).all()

        # ------------------------------------------------------------------
        # 2. Separar vencidas del total
        # ------------------------------------------------------------------
        vencidas_set = [r for r in reportes_activos if _esta_vencida(r, ahora)]

        # ------------------------------------------------------------------
        # 3. KPIs generales
        # ------------------------------------------------------------------
        total_activas = len(reportes_activos)
        en_progreso   = sum(1 for r in reportes_activos if r.status == ReportStatusEnum.EN_PROGRESO)
        bloqueadas    = sum(1 for r in reportes_activos if r.status == ReportStatusEnum.BLOQUEADA)
        vencidas_kpi  = len(vencidas_set)
        resueltas     = db.scalar(
            select(func.count(Report.id)).where(
                func.lower(Report.status).in_(resueltos_estados)
            )
        ) or 0

        # ------------------------------------------------------------------
        # 4. Desglose por Área / Especialidad
        # ------------------------------------------------------------------
        specialties: List[Specialty] = db.scalars(select(Specialty)).all()
        # Índice rápido por specialty_id
        reporte_by_esp: Dict[int, List[Report]] = {}
        for r in reportes_activos:
            if r.specialty_id is not None:
                reporte_by_esp.setdefault(r.specialty_id, []).append(r)

        areas_data: List[Dict[str, Any]] = []
        for esp in specialties:
            reportes_esp = reporte_by_esp.get(esp.id, [])
            total_esp = len(reportes_esp)
            bloq_esp  = sum(1 for r in reportes_esp if r.status == ReportStatusEnum.BLOQUEADA)
            venc_esp  = sum(1 for r in reportes_esp if _esta_vencida(r, ahora))

            if total_esp > 0:
                areas_data.append({
                    "area_id":          esp.id,
                    "area_nombre":      esp.name,
                    "total_incidencias": total_esp,
                    "bloqueadas":       bloq_esp,
                    "vencidas":         venc_esp,
                })

        # ------------------------------------------------------------------
        # 5. Alertas de incidencias vencidas (HU-22)
        # ------------------------------------------------------------------
        # Cargar usuarios y especialidades en dicts para lookup O(1)
        users_map: Dict[int, str] = {
            u.id: u.name
            for u in db.scalars(select(User)).all()
        }
        esp_map: Dict[int, str] = {
            esp.id: esp.name for esp in specialties
        }

        alertas: List[Dict[str, Any]] = []
        for r in vencidas_set:
            tecnico_nombre = (
                users_map.get(r.assignee_id, "Sin asignar")
                if r.assignee_id else "Sin asignar"
            )
            area_nombre = esp_map.get(r.specialty_id, "Sin área") if r.specialty_id else "Sin área"

            alertas.append({
                "id":             r.id,
                "folio":          r.folio,
                "titulo":         r.title,
                "estado":         r.status.value if hasattr(r.status, 'value') else str(r.status),
                "prioridad":      r.priority.value if r.priority and hasattr(r.priority, 'value') else (str(r.priority) if r.priority else "sin prioridad"),
                "area_nombre":    area_nombre,
                "tecnico_nombre": tecnico_nombre,
                "horas_vencida":  _horas_vencida(r, ahora),
            })

        # Ordenar de mayor a menor retraso
        alertas.sort(key=lambda a: a["horas_vencida"], reverse=True)

        # ------------------------------------------------------------------
        # 6. Respuesta final
        # ------------------------------------------------------------------
        return {
            "kpis": {
                "total_activas": total_activas,
                "en_progreso":   en_progreso,
                "bloqueadas":    bloqueadas,
                "vencidas":      vencidas_kpi,
                "resueltas":     resueltas,
            },
            "areas":           areas_data,
            "alertas_vencidas": alertas,
        }
