"""Crea/actualiza datos demo para validar SIGIPLAN sin borrar datos existentes.

Uso en producción (dentro del contenedor):
  DEMO_PASSWORD='...' python scripts/ensure_demo_data.py

El script es idempotente: actualiza los registros demo por email/código, pero no
elimina documentos ni modifica usuarios fuera del conjunto demo.
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.entity import Entity, PaymentRecord
from app.models.funding import FundingSource
from app.models.initiative import AuditTrailEntry, Initiative
from app.models.user import User


ENTITY_NAME = "Ilustre Municipalidad de Santiago"
ENTITY_TAX_ID = "69.070.300-K"

DEMO_USERS = [
    ("admin@santiago.cl", "Ignacio", "Carrasco", "ENTITY_ADMIN"),
    ("director@santiago.cl", "Beatriz", "Mendoza", "PLANNING_DIRECTOR"),
    ("coordinador@santiago.cl", "Nemesio", "Bilbao", "FORMULATION_LEADER"),
    ("formulador@santiago.cl", "Camila", "Rojas", "TECHNICAL_FORMULATOR"),
]


def upsert_entity():
    entity = Entity.objects(tax_id=ENTITY_TAX_ID).first() or Entity.objects(name=ENTITY_NAME).first()
    if not entity:
        entity = Entity(name=ENTITY_NAME, tax_id=ENTITY_TAX_ID)

    entity.name = ENTITY_NAME
    entity.tax_id = ENTITY_TAX_ID
    entity.address = "Plaza de Armas s/n, Santiago Centro"
    entity.subscription_plan = "Enterprise"
    entity.is_active = True
    if not entity.payment_history:
        entity.payment_history = [
            PaymentRecord(amount=1200000.0, status="Paid", transaction_id="DEMO-2026-001"),
            PaymentRecord(amount=1200000.0, status="Paid", transaction_id="DEMO-2026-002"),
        ]
    entity.save()
    return entity


def upsert_user(entity, email, first_name, last_name, role, password):
    user = User.objects(email=email).first()
    if not user:
        user = User(email=email)

    user.first_name = first_name
    user.last_name = last_name
    user.role = role
    user.entity = entity
    user.is_active = True
    user.set_password(password)
    user.save()
    return user


def upsert_funding(entity, code, name, total_budget, allocated_budget, active=True):
    source = FundingSource.objects(entity=entity, code=code).first()
    if not source:
        source = FundingSource(entity=entity, code=code)

    source.name = name
    source.total_budget = total_budget
    source.allocated_budget = allocated_budget
    source.is_active = active
    source.save()
    return source


def upsert_initiative(entity, code, payload, actor):
    initiative = Initiative.objects(entity=entity, code=code).first()
    created = False
    if not initiative:
        initiative = Initiative(entity=entity, code=code)
        created = True

    for key, value in payload.items():
        setattr(initiative, key, value)

    initiative.is_deleted = False
    now = datetime.utcnow()
    if created:
        initiative.created_at = now
        initiative.audit_trail = [
            AuditTrailEntry(
                user=actor,
                action="CREATE",
                timestamp=now,
                details="Iniciativa demo creada para validación comercial y QA.",
            )
        ]
    initiative.updated_at = now
    initiative.save()
    if not created:
        initiative.log_action(actor, "UPDATE", "Datos demo actualizados para QA.")
    return initiative


def main():
    create_app(os.environ.get("FLASK_ENV", "prod"))

    password = os.environ.get("DEMO_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Define DEMO_PASSWORD con al menos 12 caracteres.")

    entity = upsert_entity()
    users = {
        role: upsert_user(entity, email, first, last, role, password)
        for email, first, last, role in DEMO_USERS
    }

    fndr = upsert_funding(
        entity,
        "FNDR-2026",
        "Fondo Nacional de Desarrollo Regional",
        1250000000.0,
        640000000.0,
    )
    municipal = upsert_funding(
        entity,
        "MUNI-2026",
        "Presupuesto Ordinario Municipal",
        360000000.0,
        210000000.0,
    )
    salud = upsert_funding(
        entity,
        "SALUD-APS-2026",
        "Programa de Atención Primaria de Salud",
        480000000.0,
        180000000.0,
    )
    seguridad = upsert_funding(
        entity,
        "SEG-PUB-2026",
        "Fondo de Seguridad Pública",
        220000000.0,
        0.0,
    )

    director = users["PLANNING_DIRECTOR"]
    leader = users["FORMULATION_LEADER"]
    formulator = users["TECHNICAL_FORMULATOR"]

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    initiatives = [
        (
            "INIT-CESFAM-01",
            {
                "title": "Reposición CESFAM Comunal y Equipamiento Clínico",
                "description": "Reposición de infraestructura APS, box clínicos, equipamiento dental y mejora de acceso universal.",
                "planning_director": director,
                "formulation_leader": leader,
                "assigned_formulators": [formulator],
                "funding_sources": [fndr, salud],
                "estimated_cost": 640000000.0,
                "status": "IN_PROGRESS",
                "deadline": today + timedelta(days=24),
            },
        ),
        (
            "INIT-CICLO-02",
            {
                "title": "Red de Ciclovías e Iluminación Sustentable",
                "description": "Habilitación de ciclovías de estándar urbano con luminarias solares y cruces seguros.",
                "planning_director": director,
                "formulation_leader": leader,
                "assigned_formulators": [formulator],
                "funding_sources": [municipal],
                "estimated_cost": 210000000.0,
                "status": "UNDER_REVIEW",
                "deadline": today + timedelta(days=42),
            },
        ),
        (
            "INIT-SEG-03",
            {
                "title": "Sistema Integrado de Cámaras y Central de Monitoreo",
                "description": "Implementación de puntos de televigilancia, analítica básica y sala de monitoreo municipal.",
                "planning_director": director,
                "formulation_leader": leader,
                "assigned_formulators": [],
                "funding_sources": [seguridad],
                "estimated_cost": 180000000.0,
                "status": "REJECTED",
                "deadline": today - timedelta(days=8),
            },
        ),
        (
            "INIT-PLAZA-04",
            {
                "title": "Recuperación de Plaza Barrial y Áreas Verdes",
                "description": "Mejoramiento de pavimentos, mobiliario urbano, arbolado, riego eficiente y juegos inclusivos.",
                "planning_director": director,
                "formulation_leader": leader,
                "assigned_formulators": [],
                "funding_sources": [],
                "estimated_cost": 95000000.0,
                "status": "DRAFT",
                "deadline": today + timedelta(days=75),
            },
        ),
        (
            "INIT-ESCUELA-05",
            {
                "title": "Normalización Eléctrica de Escuela Pública",
                "description": "Actualización de tableros, canalizaciones, certificación SEC y eficiencia energética.",
                "planning_director": director,
                "formulation_leader": leader,
                "assigned_formulators": [formulator],
                "funding_sources": [municipal],
                "estimated_cost": 125000000.0,
                "status": "APPROVED",
                "deadline": today + timedelta(days=120),
            },
        ),
        (
            "INIT-ARCH-06",
            {
                "title": "Archivo Histórico Digital Comunal",
                "description": "Digitalización documental, catálogo público y equipamiento básico de conservación.",
                "planning_director": director,
                "formulation_leader": leader,
                "assigned_formulators": [formulator],
                "funding_sources": [municipal],
                "estimated_cost": 45000000.0,
                "status": "ARCHIVED",
                "deadline": today - timedelta(days=45),
            },
        ),
    ]

    saved = [upsert_initiative(entity, code, payload, director) for code, payload in initiatives]

    rejected = Initiative.objects(entity=entity, code="INIT-SEG-03").first()
    if rejected and not any(entry.action == "REJECT" for entry in rejected.audit_trail):
        rejected.log_action(
            director,
            "REJECT",
            "Falta complementar matriz de costos, permisos de instalación y plan de operación.",
        )

    print("DEMO_ENTITY", entity.name)
    print("DEMO_USERS", ", ".join(email for email, *_ in DEMO_USERS))
    print("DEMO_FUNDING", FundingSource.objects(entity=entity).count())
    print("DEMO_INITIATIVES", len(saved))
    print("DEMO_PASSWORD_SET", True)


if __name__ == "__main__":
    main()
