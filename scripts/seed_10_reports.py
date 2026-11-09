"""
Script para generar 10 reportes de incidencias completas con imágenes dependientes.
Cada reporte corresponde a una categoría y problemática real en campus universitario (BUAP),
con imágenes reales descargadas de URLs públicas (Unsplash CDN) y almacenadas en uploads/reports/.

Uso:
  docker compose exec api python -m scripts.seed_10_reports
"""

import os
import json
import secrets
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlmodel import select

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.campus import Campus
from app.models.evidence import EvidenceStageEnum, ReportEvidence
from app.models.faculty import Faculty
from app.models.location import Location
from app.models.report import Report, ReportPriorityEnum, ReportStatusEnum
from app.models.report_assignment import ReportAssignment
from app.models.report_status_event import ReportStatusEvent
from app.models.role import RoleEnum
from app.models.specialty import IncidentCategoryEnum, Specialty
from app.models.user import User
from app.models.user_role import UserRole
from app.core.security import hash_password

REPORTS_DATA = [
    {
        "index": 1,
        "title": "Cortocircuito y sobrecalentamiento en tomacorriente de pared",
        "description": "El contacto eléctrico del módulo 4 en el laboratorio presentó chisporroteo y olor a quemado tras conectar equipo de cómputo. La tapa plástica quedó carbonizada y la línea perdió energía.",
        "category": IncidentCategoryEnum.ELECTRICIDAD,
        "priority": ReportPriorityEnum.ALTA,
        "status": ReportStatusEnum.EN_PROGRESO,
        "campus_code": "CU",
        "campus_name": "CU",
        "faculty_name": "Facultad de Ciencias de la Computación",
        "location_name": "Laboratorio de Cómputo 1",
        "image_filename": "incidencia_01_electricidad_contacto_quemado.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&auto=format&fit=crop&q=80",
        "caption": "Tomacorriente carbonizado y cableado expuesto en módulo norte",
        "work_note": "Se aisló el circuito en el centro de carga; en espera de reemplazo de placa y pastilla termomagnética.",
    },
    {
        "index": 2,
        "title": "Fuga continua en tubería de suministro de agua en sanitarios",
        "description": "Se detectó fuga constante en la válvula y cople de la tubería principal bajo los lavamanos, generando encharcamiento en piso y riesgo de filtración al piso inferior.",
        "category": IncidentCategoryEnum.AGUA,
        "priority": ReportPriorityEnum.ALTA,
        "status": ReportStatusEnum.ASIGNADA,
        "campus_code": "CU",
        "campus_name": "CU",
        "faculty_name": "Facultad de Ingeniería",
        "location_name": "Cafetería FI",
        "image_filename": "incidencia_02_agua_tuberia_fuga.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1585704032915-c3400ca199e7?w=800&auto=format&fit=crop&q=80",
        "caption": "Fuga de agua activa en tubería y llave de paso sanitaria",
        "work_note": "Se cerró la llave de paso temporal. Se requiere cambio de niple y empaque de presión.",
    },
    {
        "index": 3,
        "title": "Proyector interactivo no responde ni emite señal de video",
        "description": "El proyector montado en el plafón del aula parpadea con indicador LED en rojo indicando falla en la lámpara óptica y no detecta entradas HDMI ni VGA.",
        "category": IncidentCategoryEnum.TI,
        "priority": ReportPriorityEnum.MEDIA,
        "status": ReportStatusEnum.EN_VALIDACION,
        "campus_code": "CU",
        "campus_name": "CU",
        "faculty_name": "Facultad de Ciencias de la Computación",
        "location_name": "Aula Magna FCC",
        "image_filename": "incidencia_03_ti_proyector_falla.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=800&auto=format&fit=crop&q=80",
        "caption": "Proyector de techo con indicador de error de lámpara óptica",
        "work_note": "Se reemplazó lámpara de prueba; el equipo enciende y se encuentra en validación de horas de uso.",
    },
    {
        "index": 4,
        "title": "Butacas universitarias fracturadas y respaldos vencidos",
        "description": "Ocho butacas en las filas traseras tienen el respaldo vencido y las paletas de escritura rotas con bordes filosos, representando riesgo de lesiones a estudiantes.",
        "category": IncidentCategoryEnum.MOBILIARIO,
        "priority": ReportPriorityEnum.BAJA,
        "status": ReportStatusEnum.REPORTADA,
        "campus_code": "CU",
        "campus_name": "CU",
        "faculty_name": "Facultad de Ciencias Físico Matemáticas",
        "location_name": "Aula 101 FCFM",
        "image_filename": "incidencia_04_mobiliario_butacas_rotas.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1580582932707-520aed937b7b?w=800&auto=format&fit=crop&q=80",
        "caption": "Conjunto de butacas con herrajes sueltos y paletas dañadas",
        "work_note": "Incidencia recibida y pendiente de catalogación por el área de almacén y carpintería.",
    },
    {
        "index": 5,
        "title": "Goteo constante y condensación en equipo minisplit",
        "description": "La unidad interior de aire acondicionado drena agua directamente sobre los escritorios de los docentes debido a posible obstrucción en la manguera de condensados.",
        "category": IncidentCategoryEnum.CLIMATIZACION,
        "priority": ReportPriorityEnum.MEDIA,
        "status": ReportStatusEnum.EN_PROGRESO,
        "campus_code": "CU",
        "campus_name": "CU",
        "faculty_name": "Facultad de Ciencias de la Computación",
        "location_name": "Sala de Maestros",
        "image_filename": "incidencia_05_climatizacion_minisplit_goteo.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?w=800&auto=format&fit=crop&q=80",
        "caption": "Unidad de climatización evaporadora con escurrimiento en carcasa",
        "work_note": "Técnico realizando purga y desazolve de línea de desagüe de condensado.",
    },
    {
        "index": 6,
        "title": "Desprendimiento de plafón y humedad en techo por lluvias",
        "description": "Filtración pluvial en la azotea reblandeció los paneles de cielo falso en el pasillo norte, provocando la caída de material y exponiendo cableado de luminarias.",
        "category": IncidentCategoryEnum.INFRAESTRUCTURA,
        "priority": ReportPriorityEnum.ALTA,
        "status": ReportStatusEnum.VALIDADA,
        "campus_code": "CAPU",
        "campus_name": "Campus Norte CAPU",
        "faculty_name": "Facultad de Derecho y Ciencias Sociales",
        "location_name": "Biblioteca FDCS",
        "image_filename": "incidencia_06_infraestructura_plafon_humedad.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=800&auto=format&fit=crop&q=80",
        "caption": "Plafón desprendido con manchas de humedad y estructura metálica a la vista",
        "work_note": "Validada por infraestructura. Se acordonó la zona y se programó impermeabilización previa al remozamiento.",
    },
    {
        "index": 7,
        "title": "Cerradura digital y pestillo trabado en puerta de laboratorio",
        "description": "La chapa de alta seguridad del laboratorio de física quedó atascada mecánicamente; no acciona con la tarjeta RFID ni con la llave maestra, impidiendo el ingreso seguro.",
        "category": IncidentCategoryEnum.SEGURIDAD,
        "priority": ReportPriorityEnum.ALTA,
        "status": ReportStatusEnum.EN_PROGRESO,
        "campus_code": "CU",
        "campus_name": "CU",
        "faculty_name": "Facultad de Ciencias Físico Matemáticas",
        "location_name": "Laboratorio de Física",
        "image_filename": "incidencia_07_seguridad_chapa_cerradura.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1558002038-1055907df827?w=800&auto=format&fit=crop&q=80",
        "caption": "Cerradura de acceso y herraje de seguridad trabados",
        "work_note": "Personal técnico desarmó la caja del pestillo para sustituir el mecanismo cilíndrico averiado.",
    },
    {
        "index": 8,
        "title": "Derrame de sustancia viscosa y acumulación de residuos",
        "description": "Derrame accidental de aceite/lubricante en el corredor peatonal adyacente a la cafetería, creando un área resbalosa sin señalamientos de precaución.",
        "category": IncidentCategoryEnum.LIMPIEZA,
        "priority": ReportPriorityEnum.MEDIA,
        "status": ReportStatusEnum.RESUELTA,
        "campus_code": "CU",
        "campus_name": "CU",
        "faculty_name": "Facultad de Ingeniería",
        "location_name": "Cafetería FI",
        "image_filename": "incidencia_08_limpieza_derrame_piso.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800&auto=format&fit=crop&q=80",
        "caption": "Área de piso intervenida con señalización preventiva y desengrasante",
        "work_note": "Se aplicó material absorbente, desengrasante industrial y lavado con agua a presión. Zona segura y habilitada.",
    },
    {
        "index": 9,
        "title": "Punto de acceso WiFi (Access Point) sin sincronización de red",
        "description": "El Access Point Cisco del área de cubículos parpadea en color ámbar y los usuarios no obtienen dirección IP por DHCP, dejando sin señal WiFi a docentes y alumnos.",
        "category": IncidentCategoryEnum.TI,
        "priority": ReportPriorityEnum.MEDIA,
        "status": ReportStatusEnum.ASIGNADA,
        "campus_code": "CU",
        "campus_name": "CU",
        "faculty_name": "Facultad de Ciencias de la Computación",
        "location_name": "Cubículos FCC",
        "image_filename": "incidencia_09_ti_access_point_wifi.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=800&auto=format&fit=crop&q=80",
        "caption": "Dispositivo inalámbrico AP montado en techo con cableado de parcheo UTP",
        "work_note": "Asignado a soporte de telecomunicaciones para revisión de puerto PoE en el switch de distribución.",
    },
    {
        "index": 10,
        "title": "Balastro magnético defectuoso y luminarias fluorescentes parpadeando",
        "description": "Tres lámparas lineales en el taller de electrónica parpadean estroboscópicamente con zumbido constante y olor a barniz caliente, impidiendo el trabajo de precisión.",
        "category": IncidentCategoryEnum.ELECTRICIDAD,
        "priority": ReportPriorityEnum.BAJA,
        "status": ReportStatusEnum.CERRADA,
        "campus_code": "CU",
        "campus_name": "CU",
        "faculty_name": "Facultad de Ingeniería",
        "location_name": "Taller de Electrónica",
        "image_filename": "incidencia_10_electricidad_luminaria_balastro.jpg",
        "public_image_url": "https://images.unsplash.com/photo-1507499739999-097706ad8914?w=800&auto=format&fit=crop&q=80",
        "caption": "Luminarias de techo reemplazadas y reconvertidas a tecnología LED",
        "work_note": "Se retiró balastro quemado y se instalaron 3 tubos LED de encendido directo. Reporte cerrado con visto bueno del docente.",
    },
]


def ensure_fallback_image(file_path: Path, title: str, category: str):
    """Genera una imagen JPEG válida en caso de fallo de conexión a Internet."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (800, 600), color=(41, 53, 72))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 780, 580], outline=(79, 142, 247), width=4)
        draw.text((50, 100), f"REPORTE: {category.upper()}", fill=(255, 255, 255))
        draw.text((50, 160), title[:60], fill=(200, 220, 255))
        draw.text((50, 220), title[60:120], fill=(200, 220, 255))
        draw.text((50, 300), "Evidencia fotografica de incidencia universitaria", fill=(160, 175, 200))
        img.save(file_path, "JPEG", quality=85)
    except Exception:
        # Minimalist valid 1x1 JPEG fallback
        tiny_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4"
            b"\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
            b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )
        file_path.write_bytes(tiny_jpeg)


def download_or_get_image(upload_reports_dir: Path, filename: str, public_url: str, title: str, category: str) -> Path:
    destination = upload_reports_dir / filename
    if destination.exists() and destination.stat().st_size > 500:
        return destination

    print(f"  [↓] Descargando imagen para: '{title[:40]}...'")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrabajoColaborativo/1.0"}
    try:
        req = urllib.request.Request(public_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read()
            if content and len(content) > 1000:
                destination.write_bytes(content)
                print(f"      OK ({len(content):,} bytes guardados en {filename})")
                return destination
            else:
                raise ValueError("Contenido vacío o demasiado pequeño")
    except Exception as e:
        print(f"      [!] Falló descarga ({e}). Generando imagen de respaldo local...")
        ensure_fallback_image(destination, title, category)
        return destination


def seed_10_reports():
    print("=" * 70)
    print(" INICIANDO CARGA DE 10 REPORTES CON IMÁGENES ASOCIADAS ")
    print("=" * 70)

    # 1. Configurar directorios de uploads
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_reports_dir = upload_dir / "reports"
    upload_evidences_dir = upload_dir / "evidences"
    upload_reports_dir.mkdir(parents=True, exist_ok=True)
    upload_evidences_dir.mkdir(parents=True, exist_ok=True)

    base_url = settings.PUBLIC_BASE_URL.rstrip("/")
    json_output_list = []

    with SessionLocal() as db:
        # 2. Asegurar que existan especialidades
        for category in IncidentCategoryEnum:
            spec = db.scalar(select(Specialty).where(Specialty.category == category))
            if not spec:
                spec = Specialty(code=category.value, name=category.value.capitalize(), category=category)
                db.add(spec)
        db.flush()

        specialties_map = {s.category: s for s in db.scalars(select(Specialty)).all()}

        # 3. Obtener o crear usuarios base
        reporter = db.scalar(select(User).where(User.email == "dar@gmail.com"))
        if not reporter:
            reporter = db.scalar(select(User).where(User.email == "reportante@buap.mx"))
        if not reporter:
            reporter = User(
                name="Dariana Reportante",
                email="reportante@buap.mx",
                password_hash=hash_password("DemoLocal2026!"),
            )
            db.add(reporter)
            db.flush()
            db.add(UserRole(user_id=reporter.id, role=RoleEnum.REPORTANTE))

        technician = db.scalar(select(User).where(User.email == "al@gmail.com"))
        if not technician:
            technician = db.scalar(select(User).where(User.email == "tecnico@buap.mx"))
        if not technician:
            technician = User(
                name="Alan Técnico",
                email="tecnico@buap.mx",
                password_hash=hash_password("DemoLocal2026!"),
            )
            db.add(technician)
            db.flush()
            db.add(UserRole(user_id=technician.id, role=RoleEnum.TECNICO))

        coordinator = db.scalar(select(User).where(User.email == "Jr@gmail.com"))
        if not coordinator:
            coordinator = db.scalar(select(User).where(User.email == "coordinador@buap.mx"))
        if not coordinator:
            coordinator = User(
                name="Jorge Coordinador",
                email="coordinador@buap.mx",
                password_hash=hash_password("DemoLocal2026!"),
            )
            db.add(coordinator)
            db.flush()
            db.add(UserRole(user_id=coordinator.id, role=RoleEnum.COORDINADOR))

        db.commit()

        # 4. Procesar cada uno de los 10 reportes
        for data in REPORTS_DATA:
            idx = data["index"]
            title = data["title"]
            desc = data["description"]
            cat = data["category"]
            prio = data["priority"]
            status = data["status"]
            campus_name = data["campus_name"]
            campus_code = data["campus_code"]
            faculty_name = data["faculty_name"]
            location_name = data["location_name"]
            filename = data["image_filename"]
            public_url = data["public_image_url"]
            caption = data["caption"]

            print(f"\n[Reporte {idx:02d}/10] {title}")

            # Descargar o asegurar imagen dependiente
            local_img_path = download_or_get_image(
                upload_reports_dir,
                filename,
                public_url,
                title,
                cat.value,
            )
            image_url = f"{base_url}/uploads/reports/{filename}"

            # Resolver Campus
            campus = db.scalar(select(Campus).where(Campus.code == campus_code))
            if not campus:
                campus = Campus(code=campus_code, name=campus_name)
                db.add(campus)
                db.flush()

            # Resolver Facultad
            faculty = db.scalar(
                select(Faculty).where(
                    Faculty.campus_id == campus.id,
                    Faculty.name == faculty_name,
                )
            )
            if not faculty:
                faculty = Faculty(campus_id=campus.id, name=faculty_name)
                db.add(faculty)
                db.flush()

            # Resolver Ubicación
            location = db.scalar(
                select(Location).where(
                    Location.faculty_id == faculty.id,
                    Location.name == location_name,
                )
            )
            if not location:
                location = Location(faculty_id=faculty.id, name=location_name)
                db.add(location)
                db.flush()

            specialty = specialties_map.get(cat)

            # Verificar si ya existe un reporte con este título
            existing_report = db.scalar(select(Report).where(Report.title == title))

            if existing_report:
                report = existing_report
                print(f"  [i] Reporte existente encontrado (ID {report.id}, Folio {report.folio}). Actualizando imagen...")
                report.image_url = image_url
                report.category = cat
                report.specialty_id = specialty.id if specialty else None
                report.priority = prio
                report.status = status
                report.classified = True
                report.campus_label = campus.name
                report.faculty_label = faculty.name
                report.space_label = location.name
                report.campus_id = campus.id
                report.faculty_id = faculty.id
                report.location_id = location.id
            else:
                folio = f"reporte-{secrets.token_hex(4)}"
                report = Report(
                    folio=folio,
                    title=title,
                    description=desc,
                    campus_label=campus.name,
                    faculty_label=faculty.name,
                    space_label=location.name,
                    campus_id=campus.id,
                    faculty_id=faculty.id,
                    location_id=location.id,
                    status=status,
                    category=cat,
                    specialty_id=specialty.id if specialty else None,
                    assignee_id=technician.id if status in [ReportStatusEnum.ASIGNADA, ReportStatusEnum.EN_PROGRESO, ReportStatusEnum.EN_VALIDACION, ReportStatusEnum.RESUELTA, ReportStatusEnum.CERRADA] else None,
                    assigned_at=datetime.now(timezone.utc) if status in [ReportStatusEnum.ASIGNADA, ReportStatusEnum.EN_PROGRESO, ReportStatusEnum.EN_VALIDACION, ReportStatusEnum.RESUELTA, ReportStatusEnum.CERRADA] else None,
                    image_url=image_url,
                    author_id=reporter.id,
                    classified=True,
                    priority=prio,
                    awaiting_validation=(status == ReportStatusEnum.EN_VALIDACION),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(report)
                db.flush()
                print(f"  [+] Creado nuevo reporte (ID {report.id}, Folio {report.folio})")

            # Asignación formal
            if report.assignee_id:
                assignment = db.scalar(
                    select(ReportAssignment).where(
                        ReportAssignment.report_id == report.id,
                        ReportAssignment.assignee_id == report.assignee_id,
                    )
                )
                if not assignment:
                    db.add(
                        ReportAssignment(
                            report_id=report.id,
                            assignee_id=report.assignee_id,
                            assigned_by_id=coordinator.id,
                            status=report.status,
                            specialty_id=report.specialty_id,
                            assigned_at=datetime.now(timezone.utc),
                        )
                    )

            # Registrar evidencia fotográfica dependiente
            evidence = db.scalar(
                select(ReportEvidence).where(
                    ReportEvidence.report_id == report.id,
                    ReportEvidence.file_url == image_url,
                )
            )
            if not evidence:
                db.add(
                    ReportEvidence(
                        report_id=report.id,
                        uploader_id=reporter.id,
                        file_url=image_url,
                        caption=caption,
                        stage=EvidenceStageEnum.ANTES,
                        created_at=datetime.now(timezone.utc),
                    )
                )

            # Historial de eventos de estado
            event = db.scalar(
                select(ReportStatusEvent).where(
                    ReportStatusEvent.report_id == report.id,
                    ReportStatusEvent.to_status == status,
                )
            )
            if not event:
                db.add(
                    ReportStatusEvent(
                        report_id=report.id,
                        from_status=ReportStatusEnum.REPORTADA,
                        to_status=status,
                        actor_id=coordinator.id if status != ReportStatusEnum.REPORTADA else reporter.id,
                        comment=f"Transición a {status.value}: {data['work_note']}",
                        created_at=datetime.now(timezone.utc),
                    )
                )

            # Agregar a lista JSON estructurada
            json_output_list.append({
                "id": report.id,
                "folio": report.folio,
                "title": report.title,
                "description": report.description,
                "category": cat.value,
                "priority": prio.value,
                "status": status.value,
                "campus": campus.name,
                "faculty": faculty.name,
                "location": location.name,
                "author": {"id": reporter.id, "name": reporter.name, "email": reporter.email},
                "assignee": {"id": technician.id, "name": technician.name, "email": technician.email} if report.assignee_id else None,
                "image": {
                    "local_filename": filename,
                    "local_url": image_url,
                    "public_cdn_url": public_url,
                    "caption": caption,
                    "stage": "antes",
                },
                "work_note": data["work_note"],
            })

        db.commit()

    # 5. Guardar archivo JSON estructurado de acompañamiento
    json_path = Path(__file__).resolve().parent / "reportes_10_con_imagenes.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_output_list, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(" ¡CARGA COMPLETADA CON ÉXITO!")
    print(f" • 10 reportes listos en la base de datos.")
    print(f" • 10 imágenes guardadas en: {upload_reports_dir.resolve()}")
    print(f" • Archivo JSON exportado en: {json_path.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    seed_10_reports()
