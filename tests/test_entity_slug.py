import unittest

from mongoengine import ValidationError, disconnect

from app import create_app
from app.models.entity import Entity


class EntitySlugTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('test')

    @classmethod
    def tearDownClass(cls):
        disconnect()

    def setUp(self):
        Entity.objects.delete()

    def tearDown(self):
        Entity.objects.delete()

    def test_slug_is_generated_from_entity_name(self):
        entity = Entity(
            name='Ilustre Municipalidad de Ñuñoa',
            tax_id='69.111.111-1',
        )
        entity.save()

        self.assertEqual(entity.slug, 'ilustre-municipalidad-de-nunoa')

    def test_manual_slug_is_normalized(self):
        entity = Entity(
            name='Municipalidad de Santiago',
            slug='  Municipalidad Santiago!!!  ',
            tax_id='69.222.222-2',
        )
        entity.save()

        self.assertEqual(entity.slug, 'municipalidad-santiago')

    def test_auto_slug_adds_suffix_on_collision(self):
        Entity(name='Municipalidad Santiago', tax_id='69.333.333-3').save()
        entity = Entity(name='Municipalidad-Santiago', tax_id='69.444.444-4')
        entity.save()

        self.assertEqual(entity.slug, 'municipalidad-santiago-2')

    def test_manual_slug_must_be_unique(self):
        Entity(
            name='Entidad A',
            slug='municipalidad-santiago',
            tax_id='69.555.555-5',
        ).save()
        duplicate = Entity(
            name='Entidad B',
            slug='Municipalidad Santiago',
            tax_id='69.666.666-6',
        )

        with self.assertRaises(ValidationError):
            duplicate.save()


if __name__ == '__main__':
    unittest.main()
