import os
import shutil
import tempfile
import unittest

from mongoengine import disconnect

from app import create_app
from app.models.entity import Entity
from app.models.funding import FundingSource
from app.models.initiative import FileAttachment, Initiative
from app.models.log import ActivityLog
from app.models.user import User


class TenantIsolationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upload_dir = tempfile.mkdtemp(prefix='sigiplan-test-uploads-')
        cls.app = create_app('test')
        cls.app.config['UPLOAD_FOLDER'] = cls.upload_dir
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.upload_dir, ignore_errors=True)
        disconnect()

    def setUp(self):
        self._clear_database()
        self.data = self._seed_tenants()

    def tearDown(self):
        self.client.get('/auth/logout')
        self._clear_database()

    def _clear_database(self):
        ActivityLog.objects.delete()
        Initiative.objects.delete()
        FundingSource.objects.delete()
        User.objects.delete()
        Entity.objects.delete()

    def _make_user(self, entity, role, email):
        user = User(
            entity=entity,
            role=role,
            email=email,
            first_name=role.title().split('_')[0],
            last_name=entity.name,
            is_active=True,
        )
        user.set_password('password123')
        user.save()
        return user

    def _make_initiative(self, entity, code, director, leader=None, formulators=None, sources=None):
        initiative = Initiative(
            entity=entity,
            code=code,
            title=f'Iniciativa {code}',
            description='Descripcion de prueba',
            planning_director=director,
            formulation_leader=leader,
            assigned_formulators=formulators or [],
            funding_sources=sources or [],
            estimated_cost=1000,
            status='IN_PROGRESS',
        )
        initiative.save()
        return initiative

    def _seed_tenants(self):
        entity_a = Entity(name='Entidad A', tax_id='76.111.111-1', is_active=True).save()
        entity_b = Entity(name='Entidad B', tax_id='76.222.222-2', is_active=True).save()

        admin_a = self._make_user(entity_a, 'ENTITY_ADMIN', 'admin.a@test.local')
        director_a = self._make_user(entity_a, 'PLANNING_DIRECTOR', 'director.a@test.local')
        leader_a = self._make_user(entity_a, 'FORMULATION_LEADER', 'leader.a@test.local')
        formulator_a = self._make_user(entity_a, 'TECHNICAL_FORMULATOR', 'formulator.a@test.local')

        admin_b = self._make_user(entity_b, 'ENTITY_ADMIN', 'admin.b@test.local')
        director_b = self._make_user(entity_b, 'PLANNING_DIRECTOR', 'director.b@test.local')
        leader_b = self._make_user(entity_b, 'FORMULATION_LEADER', 'leader.b@test.local')
        formulator_b = self._make_user(entity_b, 'TECHNICAL_FORMULATOR', 'formulator.b@test.local')

        source_a = FundingSource(
            entity=entity_a,
            name='Fuente A',
            code='F-A',
            total_budget=100000,
            is_active=True,
        ).save()
        source_b = FundingSource(
            entity=entity_b,
            name='Fuente B',
            code='F-B',
            total_budget=100000,
            is_active=True,
        ).save()

        initiative_a = self._make_initiative(
            entity_a,
            'A-001',
            director_a,
            leader=leader_a,
            formulators=[formulator_a],
            sources=[source_a],
        )
        initiative_b = self._make_initiative(
            entity_b,
            'B-001',
            director_b,
            leader=leader_b,
            formulators=[formulator_b],
            sources=[source_b],
        )

        attachment_id = 'tenant-b-file'
        attachment_path = os.path.join(str(entity_b.id), str(initiative_b.id), f'{attachment_id}_acta.txt')
        full_dir = os.path.join(self.app.config['UPLOAD_FOLDER'], str(entity_b.id), str(initiative_b.id))
        os.makedirs(full_dir, exist_ok=True)
        with open(os.path.join(full_dir, f'{attachment_id}_acta.txt'), 'w', encoding='utf-8') as handle:
            handle.write('archivo privado de entidad B')
        initiative_b.attachments.append(FileAttachment(
            file_id=attachment_id,
            name='acta.txt',
            file_path=attachment_path.replace(os.sep, '/'),
            size_bytes=27,
            uploaded_by=formulator_b,
        ))
        initiative_b.save()

        return {
            'entity_a': entity_a,
            'entity_b': entity_b,
            'admin_a': admin_a,
            'admin_b': admin_b,
            'director_a': director_a,
            'director_b': director_b,
            'formulator_a': formulator_a,
            'formulator_b': formulator_b,
            'source_a': source_a,
            'source_b': source_b,
            'initiative_a': initiative_a,
            'initiative_b': initiative_b,
            'attachment_id': attachment_id,
        }

    def _login(self, email, password='password123'):
        return self.client.post('/auth/login', data={
            'email': email,
            'password': password,
        })

    def test_user_cannot_open_other_tenant_initiative_by_direct_url(self):
        self._login('director.a@test.local')

        response = self.client.get(f'/planning/initiative/{self.data["initiative_b"].id}')

        self.assertEqual(response.status_code, 404)

    def test_formulator_cannot_download_other_tenant_attachment(self):
        self._login('formulator.a@test.local')

        response = self.client.get(
            f'/formulation/initiative/{self.data["initiative_b"].id}'
            f'/attachment/{self.data["attachment_id"]}/download'
        )

        self.assertEqual(response.status_code, 404)

    def test_entity_admin_cannot_edit_other_tenant_user(self):
        self._login('admin.a@test.local')

        response = self.client.get(f'/admin/users/{self.data["admin_b"].id}/edit')

        self.assertEqual(response.status_code, 404)

    def test_other_tenant_funding_source_cannot_be_assigned_to_initiative(self):
        self._login('director.a@test.local')
        initiative = self.data['initiative_a']

        response = self.client.post(f'/planning/initiative/{initiative.id}/edit', data={
            'code': initiative.code,
            'title': initiative.title,
            'description': initiative.description,
            'planning_director': str(self.data['director_a'].id),
            'formulation_leader': '',
            'assigned_formulators': [],
            'funding_sources': [str(self.data['source_b'].id)],
            'estimated_cost': '1000',
            'deadline': '',
        })

        self.assertEqual(response.status_code, 302)
        initiative.reload()
        self.assertNotIn(self.data['source_b'].id, [source.id for source in initiative.funding_sources])
        self.assertEqual(initiative.funding_sources, [])

    def test_inactive_entity_cannot_login_or_continue_operating_existing_session(self):
        self.data['entity_a'].is_active = False
        self.data['entity_a'].save()

        login_response = self._login('admin.a@test.local')

        self.assertEqual(login_response.status_code, 200)
        self.assertIsNone(User.objects(email='admin.a@test.local').first().last_login)

        self.data['entity_a'].is_active = True
        self.data['entity_a'].save()
        active_login = self._login('admin.a@test.local')
        self.assertEqual(active_login.status_code, 302)

        self.data['entity_a'].is_active = False
        self.data['entity_a'].save()
        operating_response = self.client.get('/admin/users')

        self.assertEqual(operating_response.status_code, 302)
        self.assertIn('/auth/login', operating_response.location)


if __name__ == '__main__':
    unittest.main()
