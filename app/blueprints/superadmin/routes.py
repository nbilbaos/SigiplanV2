from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required
from app.blueprints.superadmin import superadmin_bp
from app.utils.decorators import role_required

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
]


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
            'users_count': User.objects(entity=entity).count(),
            'initiatives_count': Initiative.objects(entity=entity, is_deleted=False).count(),
            'initiatives_approved': Initiative.objects(entity=entity, is_deleted=False, status='APPROVED').count(),
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
    from app.models.user import User
    from app.models.initiative import Initiative

    all_entities = Entity.objects.order_by('name')
    entities_stats = []
    for entity in all_entities:
        entities_stats.append({
            'entity': entity,
            'users_count': User.objects(entity=entity).count(),
            'initiatives_count': Initiative.objects(entity=entity, is_deleted=False).count(),
        })

    return render_template('superadmin/entities.html', entities_stats=entities_stats)


@superadmin_bp.route('/entities/create', methods=['GET', 'POST'])
@login_required
@role_required('SUPER_ADMIN')
def entity_create():
    from app.models.entity import Entity

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
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

        if errors:
            for err in errors:
                flash(err, 'danger')
            data = {'name': name, 'tax_id': tax_id, 'address': address, 'subscription_plan': subscription_plan}
            return render_template('superadmin/entity_form.html', action='create', data=data)

        Entity(name=name, tax_id=tax_id, address=address,
               subscription_plan=subscription_plan, is_active=True).save()
        flash(f'Entidad "{name}" creada exitosamente.', 'success')
        return redirect(url_for('superadmin.entities'))

    data = {'name': '', 'tax_id': '', 'address': '', 'subscription_plan': 'Standard'}
    return render_template('superadmin/entity_form.html', action='create', data=data)


@superadmin_bp.route('/entities/<entity_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('SUPER_ADMIN')
def entity_edit(entity_id):
    from app.models.entity import Entity

    try:
        entity = Entity.objects(id=entity_id).first()
    except Exception:
        entity = None
    if not entity:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
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

        if errors:
            for err in errors:
                flash(err, 'danger')
            data = {'name': name, 'tax_id': tax_id, 'address': address, 'subscription_plan': subscription_plan}
            return render_template('superadmin/entity_form.html', action='edit', entity=entity, data=data)

        entity.name = name
        entity.tax_id = tax_id
        entity.address = address
        entity.subscription_plan = subscription_plan
        entity.save()
        flash(f'Entidad "{name}" actualizada correctamente.', 'success')
        return redirect(url_for('superadmin.entities'))

    data = {
        'name': entity.name,
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

    entity.is_active = not entity.is_active
    entity.save()
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
    from flask_login import current_user

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
    from flask_login import current_user

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
    from app.models.initiative import Initiative

    entity_id    = request.args.get('entity_id', '').strip()
    action_filter = request.args.get('action', '').strip()
    date_from    = request.args.get('date_from', '').strip()
    date_to      = request.args.get('date_to', '').strip()

    init_query = Initiative.objects
    if entity_id:
        try:
            entity_obj = Entity.objects(id=entity_id).first()
            if entity_obj:
                init_query = init_query.filter(entity=entity_obj)
        except Exception:
            pass

    # Convertir fechas de filtro
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

    # Aplanar audit_trail de todas las iniciativas
    entries = []
    for initiative in init_query:
        for entry in initiative.audit_trail:
            if action_filter and entry.action != action_filter:
                continue
            if dt_from and entry.timestamp < dt_from:
                continue
            if dt_to and entry.timestamp > dt_to:
                continue
            entries.append({
                'timestamp':        entry.timestamp,
                'user':             entry.user,
                'action':           entry.action,
                'details':          entry.details or '',
                'initiative_code':  initiative.code,
                'initiative_title': initiative.title,
                'initiative_id':    str(initiative.id),
                'entity':           initiative.entity,
            })

    entries.sort(key=lambda x: x['timestamp'], reverse=True)
    total = len(entries)
    entries = entries[:200]  # Limitar a 200 entradas más recientes

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
