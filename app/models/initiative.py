from datetime import datetime
from mongoengine import (
    DENY, Document, StringField, ReferenceField, ListField, DateTimeField,
    BooleanField, EmbeddedDocument, EmbeddedDocumentField, FloatField, IntField,
    ValidationError
)
from app.models.entity import Entity
from app.models.user import User
from app.models.funding import FundingSource

class FileAttachment(EmbeddedDocument):
    file_id = StringField(required=True)  # Hash único del archivo para evitar duplicaciones
    name = StringField(required=True)
    file_path = StringField(required=True)
    size_bytes = IntField()
    uploaded_by = ReferenceField(User)
    uploaded_at = DateTimeField(default=datetime.utcnow)

class AuditTrailEntry(EmbeddedDocument):
    user = ReferenceField(User)
    action = StringField(required=True)  # "CREATE", "UPDATE", "SUBMIT_FOR_REVIEW", "APPROVE", "REJECT", "SOFT_DELETE", "RESTORE"
    timestamp = DateTimeField(default=datetime.utcnow)
    details = StringField()

class Initiative(Document):
    meta = {
        'collection': 'initiatives',
        'indexes': [
            ('entity', 'is_deleted', 'status'),
        ],
    }
    
    # DENY: las iniciativas se conservan; los tenants no se eliminan en cascada.
    entity = ReferenceField(Entity, required=True, reverse_delete_rule=DENY)
    code = StringField(required=True, unique_with='entity')  # Código único de inversión pública por entidad
    title = StringField(required=True, max_length=255)
    description = StringField(required=True)
    
    # Asignaciones y Responsables
    # NULLIFY (1) en referencias simples: al borrar el User referenciado, el campo
    # queda en None. PULL (4) solo es válido sobre ListField (ver assigned_formulators).
    planning_director = ReferenceField(User, reverse_delete_rule=1)
    formulation_leader = ReferenceField(User, reverse_delete_rule=1)
    assigned_formulators = ListField(ReferenceField(User, reverse_delete_rule=4))  # PULL: quita el User de la lista
    
    # Financiamiento
    funding_sources = ListField(ReferenceField(FundingSource))
    estimated_cost = FloatField(default=0.0)
    
    # Flujo de Estado
    status = StringField(choices=(
        ('DRAFT', 'Borrador'),                       # Borrador inicial
        ('IN_PROGRESS', 'En Formulación'),           # En formulación técnica y carga de archivos
        ('UNDER_REVIEW', 'En Revisión'),             # Enviado para revisión y aprobación
        ('APPROVED', 'Aprobada'),                    # Aprobado por el Director
        ('REJECTED', 'Devuelta con Observaciones'),  # Devuelto con observaciones
        ('ARCHIVED', 'Archivada')                    # Archivado/Finalizado
    ), default='DRAFT')
    
    # Plazos
    deadline = DateTimeField()
    
    # Documentos y Bitácora de Auditoría
    attachments = ListField(EmbeddedDocumentField(FileAttachment))
    audit_trail = ListField(EmbeddedDocumentField(AuditTrailEntry))
    
    # Control de Borrado Lógico
    is_deleted = BooleanField(default=False)
    
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def _validate_user_reference(self, user, field_name, expected_role=None):
        if not user:
            return
        if not user.entity or user.entity.id != self.entity.id:
            raise ValidationError(
                f'{field_name} debe pertenecer a la misma entidad que la iniciativa.'
            )
        if expected_role and user.role != expected_role:
            raise ValidationError(
                f'{field_name} debe tener rol {expected_role}.'
            )

    def _validate_funding_reference(self, source, field_name):
        if not source:
            return
        if not source.entity or source.entity.id != self.entity.id:
            raise ValidationError(
                f'{field_name} debe pertenecer a la misma entidad que la iniciativa.'
            )

    def clean(self):
        if not self.entity:
            raise ValidationError('La iniciativa debe tener una entidad asociada.')

        self._validate_user_reference(
            self.planning_director,
            'planning_director',
            'PLANNING_DIRECTOR',
        )
        self._validate_user_reference(
            self.formulation_leader,
            'formulation_leader',
            'FORMULATION_LEADER',
        )
        for formulator in self.assigned_formulators:
            self._validate_user_reference(
                formulator,
                'assigned_formulators',
                'TECHNICAL_FORMULATOR',
            )
        for source in self.funding_sources:
            self._validate_funding_reference(source, 'funding_sources')
    
    def log_action(self, user, action, details=""):
        entry = AuditTrailEntry(user=user, action=action, details=details, timestamp=datetime.utcnow())
        self.audit_trail.append(entry)
        self.updated_at = datetime.utcnow()
        self.save()
        from app.services.audit import log_event
        log_event(
            actor=user,
            entity=self.entity,
            action=action,
            target=self,
            target_type='Initiative',
            details=details,
        )

    # NOTA: get_status_display() lo genera MongoEngine automáticamente a partir de
    # las choices (valor, etiqueta) del campo `status`. No definir un método propio
    # con ese nombre: el autogenerado lo eclipsa a nivel de instancia.

    def get_status_color(self):
        color_dict = {
            'DRAFT': 'bg-secondary',
            'IN_PROGRESS': 'bg-primary',
            'UNDER_REVIEW': 'bg-warning',
            'APPROVED': 'bg-success',
            'REJECTED': 'bg-danger',
            'ARCHIVED': 'bg-dark'
        }
        return color_dict.get(self.status, 'bg-secondary')

    def __str__(self):
        return f"{self.code} - {self.title}"
