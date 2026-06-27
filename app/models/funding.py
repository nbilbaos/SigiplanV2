from mongoengine import DENY, Document, StringField, FloatField, ReferenceField, BooleanField
from app.models.entity import Entity

class FundingSource(Document):
    meta = {
        'collection': 'funding_sources',
        'indexes': [
            ('entity', 'is_active'),
        ],
    }
    
    # DENY: las fuentes quedan preservadas; el tenant se desactiva/soft-deletea.
    entity = ReferenceField(Entity, required=True, reverse_delete_rule=DENY)
    name = StringField(required=True, max_length=100)
    code = StringField(required=True, unique_with='entity')  # Código presupuestario (Ej. FNDR-2026, Municipal, Canon)
    total_budget = FloatField(default=0.0)
    allocated_budget = FloatField(default=0.0)
    is_active = BooleanField(default=True)
    
    @property
    def remaining_budget(self):
        return max(0.0, self.total_budget - self.allocated_budget)
        
    def __str__(self):
        return f"{self.code} - {self.name}"
