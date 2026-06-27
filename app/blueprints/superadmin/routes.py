from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required
from app.blueprints.superadmin import superadmin_bp
from app.services.audit import log_event
from app.utils.decorators import role_required
from app.utils.executive import STATUS_LABELS, STATUS_ORDER
from app.utils.tenant import (
    tenant_funding_sources,
    tenant_initiatives,
    tenant_users,
)

ROLES = [
    'SUPER_ADMIN',
    'ENTITY_ADMIN',
    'PLANNING_DIRECTOR',
    'FORMULATION_LEADER',
    'TECHNICAL_FORMULATOR',
]

AUDIT_ACTIONS = [
    'CREATE',
    'UPDATE',
    'SUBMIT_FOR_REVIEW',
    'APPROVE',
    'REJECT',
    'SOFT_DELETE',
    'RESTORE',
    'ENTITY_CREATE',
    'ENTITY_UPDATE',
    'ENTITY_TOGGLE',
    'ENTITY_RESTORE',
    'LOGIN',
    'LOGIN_FAILED',
    'LOGOUT',
    'USER_CREATE',
    'USER_UPDATE',
    'USER_TOGGLE',
    'FUNDING_SOURCE_CREATE',
    'FUNDING_SOURCE_UPDATE',
    'FUNDING_SOURCE_TOGGLE',
]


def _get_entity(entity_id):
    from app.models.entity import Entity

    try:
        entity = Entity.objects(id=entity_id).first()
    except Exception:
        entity = None
    if not entity:
        abort(404)
    return entity


def _audit_entries_for(initiatives, limit=10):
    from datetime import datetime

    entries = []
    for initiative in initiatives:
        for entry in initiative.audit_trail:
            entries.append({
                'timestamp': entry.timestamp,
                'user': entry.user,
                'action': entry.action,
                'details': entry.details or '',
                'initiative': initiative,
                'entity': initiative.entity,
            })
    entries.sort(key=lambda item: item['timestamp'] or datetime.min, reverse=True)
    return entries[:limit]


# ─── Dashboard ───────────────────────────────────────────────────────────────

@superadmin_bp.route('/')
@login_required
@role_required('SUPER_ADMIN')
def index():
    from app.models.entity import Entity
    from app.models.user import User
    from app.models.initiative import Initiative

    metrics = {
        'entities_total': Entity.objects.count(),
        'entities_active': Entity.objects(is_active=True).count(),
        'users_total': User.objects.count(),
        'users_active': User.objects(is_active=True).count(),
        'initiatives_total': Initiative.objects(is_deleted=False).count(),
        'initiatives_draft': Initiative.objects(is_deleted=False, status='DRAFT').count(),
        'initiatives_progress': Initiative.objects(is_deleted=False, status='IN_PROGRESS').count(),
        'initiatives_review': Initiative.objects(is_deleted=False, status='UNDER_REVIEW').count(),
        'initiatives_approved': Initiative.objects(is_deleted=False, status='APPROVED').count(),
        'initiatives_rejected': Initiative.objects(is_deleted=False, status='REJECTED').count(),
    }

    entities = Entity.objects.order_by('-created_at')
    entities_stats = []
    for entity in entities:
        entities_stats.append({
            'entity': entity,
            'users_count': tenant_users(entity=entity).count(),
            'initiatives_count': tenant_initiatives(entity=entity).count(),
            'initiatives_approved': tenant_initiatives(entity=entity, status='APPROVED').count(),
        })

    recent_users = User.objects.order_by('-created_at')[:8]

    return render_template('superadmin/dashboard.html',
                           metrics=metrics,
                           entities_stats=entities_stats,
                           recent_users=recent_users)


# ─── Entidades ────────────────────────────────────────────────────────────────

@superadmin_bp.route('/entities')
@login_required
@role_required('SUPER_ADMIN')
def entities():
    from app.models.entity import Entity

    all_entities = Entity.objects.order_by('name')
    entities_stats = []
    for entity in all_entities:
        entities_stats.append({
            'entity': entity,
            'users_count': tenant_users(entity=entity).count(),
            'initiatives_count': tenant_initiatives(entity=entity).count(),
        })

    return render_template('superadmin/entities.html', entities_stats=entities_stats)


@superadmin_bp.route('/entities/<entity_id>')
@login_required
@role_required('SUPER_ADMIN')
def entity_detail(entity_id):
    entity = _get_entity(entity_id)
    users = list(tenant_users(entity=entity).order_by('role', 'last_name', 'first_name'))
    initiatives = list(tenant_initiatives(entity=entity).order_by('-updated_at'))
    sources = list(tenant_funding_sources(entity=entity).order_by('name'))

    status_counts = {
        status: sum(1 for item in initiatives if item.status == status)
        for status in STATUS_ORDER
    }
    role_counts = {role: sum(1 for user in users if user.role == role) for role in ROLES}
    budget_total = sum(source.total_budget or 0 for source in sources)
    budget_allocated = sum(source.allocated_budget or 0 for source in sources)
    estimated_total = sum(item.estimated_cost or 0 for item in initiatives)
    active_work = [item for item in initiatives if item.status not in ('APPROVED', 'ARCHIVED')]

    metrics = {
        'users_total': len(users),
        'users_active': sum(1 for user in users if user.is_active),
        'initiatives_total': len(initiatives),
        'initiatives_active': len(active_work),
        'initiatives_approved': status_counts.get('APPROVED', 0),
        'estimated_total': estimated_total,
        'budget_total': budget_total,
        'budget_allocated': budget_allocated,
        'budget_available': max(0, budget_total - budget_allocated),
        'sources_total': len(sources),
    }

    critical = [
        item for item in initiatives
        if item.status == 'REJECTED'
        or (not [f for f in item.assigned_formulators if f] and item.status not in ('APPROVED', 'ARCHIVED'))
        or (not [s for s in item.funding_sources if s] and item.status not in ('APPROVED', 'ARCHIVED'))
    ][:8]

    return render_template(
        'superadmin/entity_detail.html',
        entity=entity,
        metrics=metrics,
        status_counts=status_counts,
        status_labels=STATUS_LABELS,
        status_order=STATUS_ORDER,
        role_counts=role_counts,
        users=users,
        initiatives=initiatives[:10],
        top_initiatives=sorted(initiatives, key=lambda item: item.estimated_cost or 0, reverse=True)[:6],
        critical=critical,
        sources=sources,
        recent_audit=_audit_entries_for(initiatives, limit=10),
    )


@superadmin_bp.route('/statistics')
@login_required
@role_required('SUPER_ADMIN')
def statistics():
    from app.models.entity import Entity
    from app.models.user import User
    from app.models.initiative import Initiative
    from app.models.funding import FundingSource

    entities = list(Entity.objects.order_by('name'))
    initiatives = list(Initiative.objects(is_deleted=False))
    sources = list(FundingSource.objects)

    status_counts = {
        status: sum(1 for item in initiatives if item.status == status)
        for status in STATUS_ORDER
    }
    plan_counts = {
        plan: sum(1 for entity in entities if entity.subscription_plan == plan)
        for plan in ('Standard', 'Premium', 'Enterprise')
    }
    budget_total = sum(source.total_budget or 0 for source in sources)
    budget_allocated = sum(source.allocated_budget or 0 for source in sources)
    estimated_total = sum(item.estimated_cost or 0 for item in initiatives)

    entity_rows = []
    for entity in entities:
        entity_inits = [item for item in initiatives if item.entity and item.entity.id == entity.id]
        entity_sources = [source for source in sources if source.entity and source.entity.id == entity.id]
        row_estimated = sum(item.estimated_cost or 0 for item in entity_inits)
        row_budget = sum(source.total_budget or 0 for source in entity_sources)
        entity_rows.append({
            'entity': entity,
            'users': tenant_users(entity=entity).count(),
            'initiatives': len(entity_inits),
            'approved': sum(1 for item in entity_inits if item.status == 'APPROVED'),
            'rejected': sum(1 for item in entity_inits if item.status == 'REJECTED'),
            'estimated_total': row_estimated,
            'budget_total': row_budget,
            'execution_pressure': (row_estimated / row_budget * 100) if row_budget else 0,
        })
    entity_rows.sort(key=lambda item: item['estimated_total'], reverse=True)

    platform = {
        'entities_total': len(entities),
        'entities_active': sum(1 for entity in entities if entity.is_active),
        'users_total': User.objects.count(),
        'users_active': User.objects(is_active=True).count(),
        'initiatives_total': len(initiatives),
        'estimated_total': estimated_total,
        'budget_total': budget_total,
        'budget_allocated': budget_allocated,
        'budget_available': max(0, budget_total - budget_allocated),
        'approval_rate': (status_counts.get('APPROVED', 0) / len(initiatives) * 100) if initiatives else 0,
        'review_load': status_counts.get('UNDER_REVIEW', 0),
        'rejected_load': status_counts.get('REJECTED', 0),
    }

    return render_template(
        'superadmin/statistics.html',
        platform=platform,
        status_counts=status_counts,
        status_labels=STATUS_LABELS,
        status_order=STATUS_ORDER,
        plan_counts=plan_counts,
        entity_rows=entity_rows,
        recent_audit=_audit_entries_for(initiatives, limit=12),
    )


@superadmin_bp.route('/entities/create', methods=['GET', 'POST'])
@login_required
@role_required('SUPER_ADMIN')
def entity_create():
    from app.models.entity import Entity
    from app.utils.slug import slugify

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        slug = request.form.get('slug', '').strip()
        tax_id = request.form.get('tax_id', '').strip()
        address = request.form.get('address', '').strip()
        subscription_plan = request.form.get('subscription_plan', 'Standard')

        errors = []
        if not name:
            errors.append('El nombre de la entidad es obligatorio.')
        if not tax_id:
            errors.append('El RUT / Tax ID es obligatorio.')
        if subscription_plan not in ('Standard', 'Premium', 'Enterprise'):
            errors.append('Plan de suscripción inválido.')
        if name and Entity.objects(name=name).first():
            errors.append('Ya existe una entidad registrada con ese nombre.')
        if tax_id and Entity.objects(tax_id=tax_id).first():
            errors.append('Ya existe una entidad registrada con ese RUT / Tax ID.')
        normalized_slug = slugify(slug) if slug else ''
        if slug and not normalized_slug:
            errors.append('El slug debe contener letras o números.')
        if normalized_slug and Entity.objects(slug=normalized_slug).first():
            errors.append('Ya existe una entidad registrada con ese slug.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            data = {'name': name, 'slug': slug, 'tax_id': tax_id, 'address': address, 'subscription_plan': subscription_plan}
            return render_template('superadmin/entity_form.html', action='create', data=data)

        entity = Entity(name=name, tax_id=tax_id, address=address,
                        slug=normalized_slug,
                        subscription_plan=subscription_plan, is_active=True)
        entity.save()
        log_event(
            actor=current_user,
            entity=entity,
            action='ENTITY_CREATE',
            target=entity,
            target_type='Entity',
            details=f'Entidad creada: {entity.name}.',
        )
        flash(f'Entidad "{name}" creada exitosamente.', 'success')
        return redirect(url_for('superadmin.entities'))

    data = {'name': '', 'slug': '', 'tax_id': '', 'address': '', 'subscription_plan': 'Standard'}
    return render_template('superadmin/entity_form.html', action='create', data=data)


@superadmin_bp.route('/entities/<entity_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('SUPER_ADMIN')
def entity_edit(entity_id):
    from app.models.entity import Entity
    from app.utils.slug import slugify

    try:
        entity = Entity.objects(id=entity_id).first()
    except Exception:
        entity = None
    if not entity:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        slug = request.form.get('slug', '').strip()
        tax_id = request.form.get('tax_id', '').strip()
        address = request.form.get('address', '').strip()
        subscription_plan = request.form.get('subscription_plan', 'Standard')

        errors = []
        if not name:
            errors.append('El nombre de la entidad es obligatorio.')
        if not tax_id:
            errors.append('El RUT / Tax ID es obligatorio.')
        if subscription_plan not in ('Standard', 'Premium', 'Enterprise'):
            errors.append('Plan de suscripción inválido.')
        if name and Entity.objects(name=name, id__ne=entity.id).first():
            errors.append('Ya existe otra entidad con ese nombre.')
        if tax_id and Entity.objects(tax_id=tax_id, id__ne=entity.id).first():
            errors.append('Ya existe otra entidad con ese RUT / Tax ID.')
        normalized_slug = slugify(slug) if slug else ''
        if slug and not normalized_slug:
            errors.append('El slug debe contener letras o números.')
        if normalized_slug and Entity.objects(slug=normalized_slug, id__ne=entity.id).first():
            errors.append('Ya existe otra entidad con ese slug.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            data = {'name': name, 'slug': slug, 'tax_id': tax_id, 'address': address, 'subscription_plan': subscription_plan}
            return render_template('superadmin/entity_form.html', action='edit', entity=entity, data=data)

        entity.name = name
        entity.slug = normalized_slug
        entity.tax_id = tax_id
        entity.address = address
        entity.subscription_plan = subscription_plan
        entity.save()
        log_event(
            actor=current_user,
            entity=entity,
            action='ENTITY_UPDATE',
            target=entity,
            target_type='Entity',
            details=f'Entidad actualizada: {entity.name}.',
        )
        flash(f'Entidad "{name}" actualizada correctamente.', 'success')
        return redirect(url_for('superadmin.entities'))

    data = {
        'name': entity.name,
        'slug': entity.slug or '',
        'tax_id': entity.tax_id,
        'address': entity.address or '',
        'subscription_plan': entity.subscription_plan,
    }
    return render_template('superadmin/entity_form.html', action='edit', entity=entity, data=data)


@superadmin_bp.route('/entities/<entity_id>/toggle', methods=['POST'])
@login_required
@role_required('SUPER_ADMIN')
def entity_toggle(entity_id):
    from app.models.entity import Entity

    try:
        entity = Entity.objects(id=entity_id).first()
    except Exception:
        entity = None
    if not entity:
        abort(404)

    if entity.is_deleted:
        entity.restore()
        log_event(
            actor=current_user,
            entity=entity,
            action='ENTITY_RESTORE',
            target=entity,
            target_type='Entity',
            details=f'Entidad restaurada: {entity.name}.',
        )
        flash(f'Entidad "{entity.name}" restaurada y activada correctamente.', 'success')
        return redirect(url_for('superadmin.entities'))

    entity.is_active = not entity.is_active
    entity.save()
    log_event(
        actor=current_user,
        entity=entity,
        action='ENTITY_TOGGLE',
        target=entity,
        target_type='Entity',
        details=f'Entidad {"activada" if entity.is_active else "desactivada"}: {entity.name}.',
    )
    estado = 'activada' if entity.is_active else 'desactivada'
    flash(f'Entidad "{entity.name}" {estado} correctamente.', 'success')
    return redirect(url_for('superadmin.entities'))


# ─── Usuarios ─────────────────────────────────────────────────────────────────

@superadmin_bp.route('/users')
@login_required
@role_required('SUPER_ADMIN')
def users():
    from app.models.user import User
    from app.models.entity import Entity

    entity_id = request.args.get('entity_id', '').strip()
    role_filter = request.args.get('role', '').strip()

    query = User.objects
    selected_entity = None
    if entity_id:
        try:
            selected_entity = Entity.objects(id=entity_id).first()
            if selected_entity:
                query = query.filter(entity=selected_entity)
        except Exception:
            pass
    if role_filter and role_filter in ROLES:
        query = query.filter(role=role_filter)

    all_users = query.order_by('last_name', 'first_name')
    all_entities = Entity.objects.order_by('name')

    return render_template('superadmin/users.html',
                           users=all_users,
                           all_entities=all_entities,
                           roles=ROLES,
                           selected_entity_id=entity_id,
                           selected_role=role_filter)


@superadmin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@role_required('SUPER_ADMIN')
def user_create():
    from app.models.user import User
    from app.models.entity import Entity

    all_entities = Entity.objects(is_active=True).order_by('name')

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', '')
        entity_id = request.form.get('entity_id', '').strip()
        password = request.form.get('password', '')

        errors = []
        if not first_name:
            errors.append('El nombre es obligatorio.')
        if not last_name:
            errors.append('El apellido es obligatorio.')
        if not email:
            errors.append('El email es obligatorio.')
        if role not in ROLES:
            errors.append('El rol seleccionado es inválido.')
        if not password:
            errors.append('La contraseña es obligatoria.')
        elif len(password) < 8:
            errors.append('La contraseña debe tener al menos 8 caracteres.')
        if email and User.objects(email=email).first():
            errors.append('Ya existe un usuario registrado con ese email.')

        entity = None
        if role != 'SUPER_ADMIN':
            if not entity_id:
                errors.append('Debe seleccionar una entidad para este rol.')
            else:
                try:
                    entity = Entity.objects(id=entity_id).first()
                    if not entity:
                        errors.append('La entidad seleccionada no existe.')
                except Exception:
                    errors.append('Entidad inválida.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            data = {'first_name': first_name, 'last_name': last_name,
                    'email': email, 'role': role, 'entity_id': entity_id}
            return render_template('superadmin/user_form.html',
                                   action='create', data=data,
                                   all_entities=all_entities, roles=ROLES)

        user = User(first_name=first_name, last_name=last_name,
                    email=email, role=role, entity=entity, is_active=True)
        user.set_password(password)
        user.save()
        log_event(
            actor=current_user,
            entity=user.entity,
            action='USER_CREATE',
            target=user,
            target_type='User',
            details=f'Usuario creado: {user.email}.',
        )
        flash(f'Usuario "{user.full_name}" creado exitosamente.', 'success')
        return redirect(url_for('superadmin.users'))

    data = {'first_name': '', 'last_name': '', 'email': '',
            'role': 'ENTITY_ADMIN', 'entity_id': ''}
    return render_template('superadmin/user_form.html',
                           action='create', data=data,
                           all_entities=all_entities, roles=ROLES)


@superadmin_bp.route('/users/<user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('SUPER_ADMIN')
def user_edit(user_id):
    from app.models.user import User
    from app.models.entity import Entity

    try:
        user = User.objects(id=user_id).first()
    except Exception:
        user = None
    if not user:
        abort(404)

    all_entities = Entity.objects(is_active=True).order_by('name')

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', '')
        entity_id = request.form.get('entity_id', '').strip()
        password = request.form.get('password', '')
        is_active = request.form.get('is_active') == 'on'

        errors = []
        if not first_name:
            errors.append('El nombre es obligatorio.')
        if not last_name:
            errors.append('El apellido es obligatorio.')
        if not email:
            errors.append('El email es obligatorio.')
        if role not in ROLES:
            errors.append('El rol seleccionado es inválido.')
        if password and len(password) < 8:
            errors.append('La contraseña debe tener al menos 8 caracteres.')
        if email and User.objects(email=email, id__ne=user.id).first():
            errors.append('Ya existe otro usuario con ese email.')

        entity = None
        if role != 'SUPER_ADMIN':
            if not entity_id:
                errors.append('Debe seleccionar una entidad para este rol.')
            else:
                try:
                    entity = Entity.objects(id=entity_id).first()
                    if not entity:
                        errors.append('La entidad seleccionada no existe.')
                except Exception:
                    errors.append('Entidad inválida.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            data = {'first_name': first_name, 'last_name': last_name,
                    'email': email, 'role': role, 'entity_id': entity_id,
                    'is_active': is_active}
            return render_template('superadmin/user_form.html',
                                   action='edit', data=data, user=user,
                                   all_entities=all_entities, roles=ROLES)

        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.role = role
        user.entity = entity
        user.is_active = is_active
        if password:
            user.set_password(password)
        user.save()
        log_event(
            actor=current_user,
            entity=user.entity,
            action='USER_UPDATE',
            target=user,
            target_type='User',
            details=f'Usuario actualizado: {user.email}.',
        )
        flash(f'Usuario "{user.full_name}" actualizado correctamente.', 'success')
        return redirect(url_for('superadmin.users'))

    data = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'role': user.role,
        'entity_id': str(user.entity.id) if user.entity else '',
        'is_active': user.is_active,
    }
    return render_template('superadmin/user_form.html',
                           action='edit', data=data, user=user,
                           all_entities=all_entities, roles=ROLES)


@superadmin_bp.route('/users/<user_id>/toggle', methods=['POST'])
@login_required
@role_required('SUPER_ADMIN')
def user_toggle(user_id):
    from app.models.user import User
    try:
        user = User.objects(id=user_id).first()
    except Exception:
        user = None
    if not user:
        abort(404)

    if str(user.id) == str(current_user.id):
        flash('No puedes desactivar tu propia cuenta.', 'warning')
        return redirect(url_for('superadmin.users'))

    user.is_active = not user.is_active
    user.save()
    log_event(
        actor=current_user,
        entity=user.entity,
        action='USER_TOGGLE',
        target=user,
        target_type='User',
        details=f'Usuario {"activado" if user.is_active else "desactivado"}: {user.email}.',
    )
    estado = 'activado' if user.is_active else 'desactivado'
    flash(f'Usuario "{user.full_name}" {estado} correctamente.', 'success')
    return redirect(url_for('superadmin.users'))


# ─── Logs de Auditoría ────────────────────────────────────────────────────────

@superadmin_bp.route('/logs')
@login_required
@role_required('SUPER_ADMIN')
def logs():
    from datetime import datetime
    from app.models.entity import Entity
    from app.models.log import ActivityLog

    entity_id = request.args.get('entity_id', '').strip()
    action_filter = request.args.get('action', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    query = ActivityLog.objects
    if entity_id:
        try:
            entity_obj = Entity.objects(id=entity_id).first()
            if entity_obj:
                query = query.filter(entity=entity_obj)
        except Exception:
            pass

    dt_from = dt_to = None
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    if action_filter:
        query = query.filter(action=action_filter)
    if dt_from:
        query = query.filter(timestamp__gte=dt_from)
    if dt_to:
        query = query.filter(timestamp__lte=dt_to)

    total = query.count()
    entries = []
    for event in query.order_by('-timestamp')[:200]:
        details = event.details or ''
        if event.ip_address:
            details = f'{details} IP: {event.ip_address}'.strip()
        entries.append({
            'timestamp': event.timestamp,
            'user': event.actor or event.user,
            'action': event.action,
            'details': details,
            'object_type': event.target_type or 'Evento',
            'object_id': event.target_id or '',
            'entity': event.entity,
            'user_agent': event.user_agent or '',
        })

    all_entities = Entity.objects.order_by('name')

    return render_template('superadmin/logs.html',
                           entries=entries,
                           total=total,
                           all_entities=all_entities,
                           audit_actions=AUDIT_ACTIONS,
                           selected_entity_id=entity_id,
                           selected_action=action_filter,
                           date_from=date_from,
                           date_to=date_to)
