from datetime import datetime
from mongoengine import Document, StringField, ReferenceField, DateTimeField
from app.models.user import User
from app.models.entity import Entity

class ActivityLog(Document):
    meta = {
        'collection': 'activity_logs',
        'ordering': ['-timestamp']
    }
    
    user = ReferenceField(User, reverse_delete_rule=4)
    entity = ReferenceField(Entity, reverse_delete_rule=4)
    action = StringField(required=True)  # E.g., "LOGIN", "LOGOUT", "BACKUP_DB", "USER_CREATE", "USER_DELETE", "INITIATIVE_PURGE"
    details = StringField()
    ip_address = StringField()
    timestamp = DateTimeField(default=datetime.utcnow)
    
    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.user.full_name if self.user else 'System'} - {self.action}: {self.details}"
