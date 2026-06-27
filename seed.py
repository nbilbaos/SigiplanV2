import os
from datetime import datetime, timedelta
from mongoengine import connect
from app.models.entity import Entity, PaymentRecord
from app.models.user import User
from app.models.funding import FundingSource
from app.models.initiative import Initiative, FileAttachment, AuditTrailEntry
from app.models.log import ActivityLog
from app import bcrypt

def seed_database():
    print("--- Iniciando Inicialización de Base de Datos SIGIPLAN ---")
    
    # Cargar configuraciones de desarrollo
    os.environ['FLASK_ENV'] = 'dev'
    from config import config_by_name
    db_settings = config_by_name['dev'].MONGODB_SETTINGS
    
    # Conectarse a MongoDB
    print(f"Conectando a base de datos: {db_settings['db']}...")
    connect(db=db_settings['db'], host=db_settings['host'])
    
    # Limpiar base de datos previa para evitar duplicaciones.
    # IMPORTANTE: borrar los documentos hijos ANTES que los padres. Si se borran
    # los User mientras existen Initiative que los referencian, MongoEngine intenta
    # aplicar el reverse_delete_rule (PULL) sobre planning_director/formulation_leader
    # —que son referencias simples, no listas— y falla con "$pull to a non-array value".
    print("Limpiando registros antiguos...")
    ActivityLog.objects.delete()
    Initiative.objects.delete()
    FundingSource.objects.delete()
    User.objects.delete()
    Entity.objects.delete()
    
    # 1. Crear Entidad Gubernamental
    print("Creando Entidad de Demostración...")
    santiago_entity = Entity(
        name="Ilustre Municipalidad de Santiago",
        slug="municipalidad-santiago",
        tax_id="69.070.300-K",
        address="Plaza de Armas s/n, Santiago Centro",
        subscription_plan="Enterprise",
        payment_history=[
            PaymentRecord(amount=1200000.0, status="Paid", transaction_id="TXN-2026-001"),
            PaymentRecord(amount=1200000.0, status="Paid", transaction_id="TXN-2026-002")
        ]
    )
    santiago_entity.save()
    
    # 2. Crear Usuarios (Roles Completos)
    print("Creando Cuentas de Usuario de Demostración...")
    
    # Super Admin de la Plataforma
    super_admin = User(
        email="superadmin@sigiplan.cl",
        first_name="Rodrigo",
        last_name="Valenzuela",
        role="SUPER_ADMIN",
        is_active=True
    )
    super_admin.set_password("password123")
    super_admin.save()
    
    # Administrador de la Entidad
    entity_admin = User(
        email="admin@santiago.cl",
        first_name="Ignacio",
        last_name="Carrasco",
        role="ENTITY_ADMIN",
        entity=santiago_entity,
        is_active=True
    )
    entity_admin.set_password("password123")
    entity_admin.save()
    
    # Director de Planificación
    planning_director = User(
        email="director@santiago.cl",
        first_name="Beatriz",
        last_name="Mendoza",
        role="PLANNING_DIRECTOR",
        entity=santiago_entity,
        is_active=True
    )
    planning_director.set_password("password123")
    planning_director.save()
    
    # Coordinador de Formulación
    formulation_leader = User(
        email="coordinador@santiago.cl",
        first_name="Nemesio",
        last_name="Bilbao",
        role="FORMULATION_LEADER",
        entity=santiago_entity,
        is_active=True
    )
    formulation_leader.set_password("password123")
    formulation_leader.save()
    
    # Formulador Técnico
    technical_formulator = User(
        email="formulador@santiago.cl",
        first_name="Camila",
        last_name="Rojas",
        role="TECHNICAL_FORMULATOR",
        entity=santiago_entity,
        is_active=True
    )
    technical_formulator.set_password("password123")
    technical_formulator.save()
    
    # 3. Crear Fuentes de Financiamiento
    print("Creando Fuentes de Financiamiento...")
    fndr_fund = FundingSource(
        entity=santiago_entity,
        name="Fondo Nacional de Desarrollo Regional (FNDR)",
        code="FNDR-2026",
        total_budget=850000000.0,
        allocated_budget=340000000.0
    )
    fndr_fund.save()
    
    municipal_fund = FundingSource(
        entity=santiago_entity,
        name="Presupuesto Ordinario Municipal",
        code="MUNICIPAL-2026",
        total_budget=200000000.0,
        allocated_budget=850000000.0
    )
    municipal_fund.save()
    
    # 4. Crear Iniciativas de Inversión
    print("Creando Iniciativas de Inversión de Demostración...")
    
    # Iniciativa 1 (En formulación activa)
    init_1 = Initiative(
        entity=santiago_entity,
        code="INIT-CESFAM-01",
        title="Reposición CESFAM Comunal y Equipamiento Clínico",
        description="Proyecto integral de reconstrucción de la infraestructura del centro de salud familiar, incluyendo la compra de 12 nuevos sillones dentales y habilitación de salas de urgencia (SAPU).",
        planning_director=planning_director,
        formulation_leader=formulation_leader,
        assigned_formulators=[technical_formulator],
        funding_sources=[fndr_fund],
        estimated_cost=340000000.0,
        status="IN_PROGRESS",
        deadline=datetime.utcnow() + timedelta(days=120)
    )
    # Registrar bitácora inicial
    init_1.audit_trail = [
        AuditTrailEntry(user=planning_director, action="CREATE", details="Iniciativa creada y asignada al Coordinador de Formulación."),
        AuditTrailEntry(user=formulation_leader, action="UPDATE", details="Asignación de la formuladora técnica Camila Rojas.")
    ]
    init_1.save()
    
    # Iniciativa 2 (Borrador inicial)
    init_2 = Initiative(
        entity=santiago_entity,
        code="INIT-CICLO-02",
        title="Habilitación de Ciclovías y Iluminación Sustentable",
        description="Creación de 5.2 kilómetros de ciclovías de alto estándar en el sector sur de la comuna, complementado con luminarias solares inteligentes para la reducción del consumo eléctrico municipal.",
        planning_director=planning_director,
        formulation_leader=formulation_leader,
        assigned_formulators=[technical_formulator],
        funding_sources=[municipal_fund],
        estimated_cost=85000000.0,
        status="DRAFT",
        deadline=datetime.utcnow() + timedelta(days=60)
    )
    init_2.audit_trail = [
        AuditTrailEntry(user=planning_director, action="CREATE", details="Borrador de proyecto vial e iluminación creado.")
    ]
    init_2.save()
    
    print("\n--- ¡Semillado Finalizado Exitosamente! ---")
    print("Cuentas listas para pruebas de inicio de sesión:")
    print("  1. Super Admin:       superadmin@sigiplan.cl / password123")
    print("  2. Admin Entidad:     admin@santiago.cl / password123")
    print("  3. Director Plan:     director@santiago.cl / password123")
    print("  4. Coordinador Form:  coordinador@santiago.cl / password123")
    print("  5. Formulador Técnico: formulador@santiago.cl / password123")
    print("---------------------------------------------")

if __name__ == '__main__':
    seed_database()
