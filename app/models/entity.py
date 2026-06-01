from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, EmbeddedDocumentListField, EmbeddedDocument, BooleanField, FloatField

class PaymentRecord(EmbeddedDocument):
    amount = FloatField(required=True)
    payment_date = DateTimeField(default=datetime.utcnow)
    status = StringField(choices=('Paid', 'Pending', 'Failed'), default='Paid')
    transaction_id = StringField()

class Entity(Document):
    meta = {'collection': 'entities'}
    
    name = StringField(required=True, unique=True, max_length=150)
    tax_id = StringField(required=True, unique=True)  # Rut / RFC / Tax ID
    address = StringField()
    is_active = BooleanField(default=True)
    subscription_plan = StringField(choices=('Standard', 'Premium', 'Enterprise'), default='Standard')
    payment_history = EmbeddedDocumentListField(PaymentRecord)
    created_at = DateTimeField(default=datetime.utcnow)
    
    def __str__(self):
        return self.name
