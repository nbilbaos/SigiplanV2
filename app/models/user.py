from datetime import datetime
from mongoengine import (
    DENY, Document, StringField, EmailField, ReferenceField, BooleanField,
    DateTimeField
)
from flask_login import UserMixin
from app.models.entity import Entity

class User(Document, UserMixin):
    meta = {
        'collection': 'users',
        'indexes': [
            ('entity', 'role', 'is_active'),
        ],
    }
    
    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)
    first_name = StringField(required=True, max_length=50)
    last_name = StringField(required=True, max_length=50)
    role = StringField(choices=(
        ('SUPER_ADMIN', 'Super Administrador de Plataforma'),       # Administrador Global de la Plataforma
        ('ENTITY_ADMIN', 'Administrador de la Entidad'),            # Administrador Local de la Entidad
        ('PLANNING_DIRECTOR', 'Director de Planificación y Desarrollo'),
        ('FORMULATION_LEADER', 'Coordinador de Formulación'),
        ('TECHNICAL_FORMULATOR', 'Formulador Técnico / Analista'),
    ), required=True)
    # DENY: los tenants se desactivan o marcan como eliminados; no se borran en cascada.
    entity = ReferenceField(Entity, reverse_delete_rule=DENY)  # None para SUPER_ADMIN
    is_active = BooleanField(default=True)
    last_login = DateTimeField()
    created_at = DateTimeField(default=datetime.utcnow)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
        
    def set_password(self, password):
        from app import bcrypt
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        
    def check_password(self, password):
        from app import bcrypt
        return bcrypt.check_password_hash(self.password_hash, password)

    # NOTA: get_role_display() lo genera MongoEngine a partir de las choices
    # (valor, etiqueta) del campo `role`. No definir un método propio con ese
    # nombre: el autogenerado lo eclipsa a nivel de instancia.

    def __str__(self):
        return f"{self.full_name} ({self.role})"
