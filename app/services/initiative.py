from datetime import datetime

from app.services.exceptions import ServiceError


class InitiativeService:
    EDITABLE_STATUSES = ('DRAFT', 'IN_PROGRESS', 'REJECTED')

    @staticmethod
    def _actor(actor):
        return actor._get_current_object() if hasattr(actor, '_get_current_object') else actor

    @staticmethod
    def create(
        *,
        entity,
        actor,
        code,
        title,
        description,
        planning_director=None,
        formulation_leader=None,
        assigned_formulators=None,
        funding_sources=None,
        estimated_cost=0.0,
        deadline=None,
    ):
        from app.models.initiative import Initiative

        if Initiative.objects(entity=entity, code=code).first():
            raise ServiceError(f'Ya existe una iniciativa con el codigo "{code}".')

        init = Initiative(
            entity=entity,
            code=code,
            title=title,
            description=description,
            planning_director=planning_director or InitiativeService._actor(actor),
            formulation_leader=formulation_leader,
            assigned_formulators=assigned_formulators or [],
            funding_sources=funding_sources or [],
            estimated_cost=estimated_cost,
            deadline=deadline,
            status='DRAFT',
        )
        init.save()
        init.log_action(
            actor,
            'CREATE',
            f'Iniciativa "{init.title}" creada en estado Borrador.',
        )
        return init

    @staticmethod
    def update_details(
        init,
        *,
        actor,
        code,
        title,
        description,
        planning_director=None,
        formulation_leader=None,
        assigned_formulators=None,
        funding_sources=None,
        estimated_cost=0.0,
        deadline=None,
    ):
        from app.models.initiative import Initiative

        if init.status not in InitiativeService.EDITABLE_STATUSES:
            raise ServiceError('Solo se pueden editar iniciativas en estados editables.')
        if Initiative.objects(entity=init.entity, code=code, id__ne=init.id).first():
            raise ServiceError(f'Ya existe otra iniciativa con el codigo "{code}".')

        init.code = code
        init.title = title
        init.description = description
        init.planning_director = planning_director
        init.formulation_leader = formulation_leader
        init.assigned_formulators = assigned_formulators or []
        init.funding_sources = funding_sources or []
        init.estimated_cost = estimated_cost
        init.deadline = deadline
        init.updated_at = datetime.utcnow()
        init.save()
        init.log_action(actor, 'UPDATE', 'Datos de la iniciativa actualizados.')
        return init

    @staticmethod
    def update_technical(init, *, actor, title, description, estimated_cost):
        if init.status not in InitiativeService.EDITABLE_STATUSES:
            raise ServiceError('Esta iniciativa no admite cambios en su estado actual.')

        init.title = title
        init.description = description
        init.estimated_cost = estimated_cost
        init.updated_at = datetime.utcnow()
        init.save()
        init.log_action(actor, 'UPDATE', 'Ficha tecnica actualizada.')
        return init

    @staticmethod
    def assign_formulators(init, *, actor, users):
        init.assigned_formulators = users or []
        init.updated_at = datetime.utcnow()
        init.save()
        names = ', '.join(u.full_name for u in init.assigned_formulators) if init.assigned_formulators else 'ninguno'
        init.log_action(actor, 'UPDATE', f'Formuladores asignados: {names}.')
        return init

    @staticmethod
    def assign_funding(init, *, actor, funding_sources):
        init.funding_sources = funding_sources or []
        init.updated_at = datetime.utcnow()
        init.save()
        init.log_action(actor, 'UPDATE', 'Fuentes de financiamiento actualizadas.')
        return init

    @staticmethod
    def transition_status(init, *, actor, target_status, action, details, allowed_from):
        if init.status not in allowed_from:
            raise ServiceError('Transicion de estado no permitida.')

        init.status = target_status
        init.updated_at = datetime.utcnow()
        init.save()
        init.log_action(actor, action, details)
        return init

    @staticmethod
    def soft_delete(init, *, actor):
        init.is_deleted = True
        init.updated_at = datetime.utcnow()
        init.save()
        init.log_action(actor, 'SOFT_DELETE', 'Iniciativa enviada a la papelera.')
        return init

    @staticmethod
    def restore(init, *, actor):
        init.is_deleted = False
        init.updated_at = datetime.utcnow()
        init.save()
        init.log_action(actor, 'RESTORE', 'Iniciativa restaurada desde la papelera.')
        return init
