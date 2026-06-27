from datetime import datetime
from mongoengine import DENY, NULLIFY, Document, StringField, ReferenceField, DateTimeField
from app.models.user import User
from app.models.entity import Entity

class ActivityLog(Document):
    meta = {
        'collection': 'activity_logs',
        'ordering': ['-timestamp'],
        'indexes': [
            ('entity', '-timestamp'),
            ('actor', '-timestamp'),
            ('target_type', 'target_id'),
            ('action', '-timestamp'),
        ],
    }
    
    actor = ReferenceField(User, reverse_delete_rule=NULLIFY)
    user = ReferenceField(User, reverse_delete_rule=NULLIFY)
    entity = ReferenceField(Entity, reverse_delete_rule=DENY)
    target_type = StringField()
    target_id = StringField()
    action = StringField(required=True)  # E.g., "LOGIN", "LOGOUT", "BACKUP_DB", "USER_CREATE", "USER_DELETE", "INITIATIVE_PURGE"
    details = StringField()
    ip_address = StringField()
    user_agent = StringField()
    timestamp = DateTimeField(default=datetime.utcnow)
    
    def __str__(self):
        actor = self.actor or self.user
        actor_name = actor.full_name if actor else 'System'
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {actor_name} - {self.action}: {self.details}"
