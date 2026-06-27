from datetime import datetime
from mongoengine import (
    Document, StringField, DateTimeField, EmbeddedDocumentListField,
    EmbeddedDocument, BooleanField, FloatField, ValidationError
)
from app.utils.slug import slugify

class PaymentRecord(EmbeddedDocument):
    amount = FloatField(required=True)
    payment_date = DateTimeField(default=datetime.utcnow)
    status = StringField(choices=('Paid', 'Pending', 'Failed'), default='Paid')
    transaction_id = StringField()

class Entity(Document):
    meta = {'collection': 'entities'}
    
    name = StringField(required=True, unique=True, max_length=150)
    slug = StringField(unique=True, sparse=True, max_length=80)
    tax_id = StringField(required=True, unique=True)  # Rut / RFC / Tax ID
    address = StringField()
    is_active = BooleanField(default=True)
    is_deleted = BooleanField(default=False)
    deleted_at = DateTimeField()
    subscription_plan = StringField(choices=('Standard', 'Premium', 'Enterprise'), default='Standard')
    payment_history = EmbeddedDocumentListField(PaymentRecord)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def soft_delete(self):
        self.is_active = False
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.save()

    def restore(self):
        self.is_active = True
        self.is_deleted = False
        self.deleted_at = None
        self.updated_at = datetime.utcnow()
        self.save()

    def _slug_exists(self, slug):
        query = Entity.objects(slug=slug)
        if self.id:
            query = query.filter(id__ne=self.id)
        return query.first() is not None

    def _next_available_slug(self, base_slug):
        candidate = base_slug
        suffix = 2
        while self._slug_exists(candidate):
            suffix_text = f'-{suffix}'
            candidate = f'{base_slug[:80 - len(suffix_text)]}{suffix_text}'
            suffix += 1
        return candidate

    def clean(self):
        base_slug = slugify(self.slug or self.name)
        if not base_slug:
            raise ValidationError('La entidad debe tener un slug valido.')

        if self.slug:
            if self._slug_exists(base_slug):
                raise ValidationError('Ya existe una entidad con ese slug.')
            self.slug = base_slug
            return

        self.slug = self._next_available_slug(base_slug)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
