from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.blueprints.admin import admin_bp
from app.utils.decorators import role_required

# Roles que el Entity Admin puede crear/asignar (no SUPER_ADMIN ni ENTITY_ADMIN)
ALLOWED_ROLES = [
    'PLANNING_DIRECTOR',
    'FORMULATION_LEADER',
    'TECHNICAL_FORMULATOR',
]

ROLE_LABELS = {
    'PLANNING_DIRECTOR':    'Director de Planificación',
    'FORMULATION_LEADER':   'Coordinador de Formulación',
    'TECHNICAL_FORMULATOR': 'Formulador Técnico / Analista',
}

AUDIT_ACTIONS = ['CREATE', 'UPDATE', 'SUBMIT_FOR_REVIEW', 'APPROVE', 'REJECT', 'SOFT_DELETE', 'RESTORE']


# ─── Dashboard ────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
@role_required('ENTITY_ADMIN')
def dashboard():
    from app.models.user import User
    from app.models.initiative import Initiative
    from app.models.funding import FundingSource

    entity = current_user.entity

    users_active   = User.objects(entity=entity, is_active=True).count()
    users_total    = User.objects(entity=entity).count()

    base = Initiative.objects(entity=entity, is_deleted=False)
    initiatives_total    = base.count()
    initiatives_draft    = base.filter(status='DRAFT').count()
    initiatives_progress = base.filter(status='IN_PROGRESS').count()
    initiatives_review   = base.filter(status='UNDER_REVIEW').count()
    initiatives_approved = base.filter(status='APPROVED').count()
    initiatives_rejected = base.filter(status='REJECTED').count()

    funding_sources = FundingSource.objects(entity=entity, is_active=True)
    budget_total     = sum(f.total_budget for f in funding_sources)
    budget_allocated = sum(f.allocated_budget for f in funding_sources)
    budget_available = max(0.0, budget_total - budget_allocated)

    recent_initiatives = base.order_by('-updated_at')[:6]

    metrics = dict(
        users_active=users_active, users_total=users_total,
        initiatives_total=initiatives_total, initiatives_draft=initiatives_draft,
        initiatives_progress=initiatives_progress, initiatives_review=initiatives_review,
        initiatives_approved=initiatives_approved, initiatives_rejected=initiatives_rejected,
        budget_total=budget_total, budget_allocated=budget_allocated,
        budget_available=budget_available,
        funding_sources=funding_sources,
        recent_initiatives=recent_initiatives,
    )
    return render_template('admin/dashboard.html', metrics=metrics)


# ─── Usuarios ─────────────────────────────────────────────────────────────────

@admin_bp.route('/users')
@login_required
@role_required('ENTITY_ADMIN')
def users():
    from app.models.user import User
    role_filter = request.args.get('role', '').strip()
    query = User.objects(entity=current_user.entity)
    if role_filter and role_filter in ALLOWED_ROLES:
        query = query.filter(role=role_filter)
    return render_template('admin/users.html',
                           users=query.order_by('last_name'),
                           roles=ALLOWED_ROLES,
                           role_labels=ROLE_LABELS,
                           selected_role=role_filter)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@role_required('ENTITY_ADMIN')
def user_create():
    from app.models.user import User

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name  = request.form.get('last_name', '').strip()
        email      = request.form.get('email', '').strip().lower()
        role       = request.form.get('role', '')
        password   = request.form.get('password', '')

        errors = []
        if not first_name: errors.append('El nombre es obligatorio.')
        if not last_name:  errors.append('El apellido es obligatorio.')
        if not email:      errors.append('El email es obligatorio.')
        if role not in ALLOWED_ROLES:
            errors.append('Rol no permitido para este nivel de administración.')
        if not password:   errors.append('La contraseña es obligatoria.')
        elif len(password) < 8:
            errors.append('La contraseña debe tener al menos 8 caracteres.')
        if email and User.objects(email=email).first():
            errors.append('Ya existe un usuario con ese email.')

        if errors:
            for e in errors: flash(e, 'danger')
            data = dict(first_name=first_name, last_name=last_name,
                        email=email, role=role)
            return render_template('admin/user_form.html', action='create', data=data,
                                   roles=ALLOWED_ROLES, role_labels=ROLE_LABELS)

        user = User(first_name=first_name, last_name=last_name,
                    email=email, role=role,
                    entity=current_user.entity, is_active=True)
        user.set_password(password)
        user.save()
        flash(f'Usuario "{user.full_name}" creado exitosamente.', 'success')
        return redirect(url_for('admin.users'))

    data = dict(first_name='', last_name='', email='', role='PLANNING_DIRECTOR')
    return render_template('admin/user_form.html', action='create', data=data,
                           roles=ALLOWED_ROLES, role_labels=ROLE_LABELS)


@admin_bp.route('/users/<user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('ENTITY_ADMIN')
def user_edit(user_id):
    from app.models.user import User

    try:
        user = User.objects(id=user_id, entity=current_user.entity).first()
    except Exception:
        user = None
    if not user:
        abort(404)

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name  = request.form.get('last_name', '').strip()
        email      = request.form.get('email', '').strip().lower()
        role       = request.form.get('role', '')
        password   = request.form.get('password', '')
        is_active  = request.form.get('is_active') == 'on'

        errors = []
        if not first_name: errors.append('El nombre es obligatorio.')
        if not last_name:  errors.append('El apellido es obligatorio.')
        if not email:      errors.append('El email es obligatorio.')
        if role not in ALLOWED_ROLES:
            errors.append('Rol no permitido para este nivel de administración.')
        if password and len(password) < 8:
            errors.append('La contraseña debe tener al menos 8 caracteres.')
        if email and User.objects(email=email, id__ne=user.id).first():
            errors.append('Ya existe otro usuario con ese email.')

        if errors:
            for e in errors: flash(e, 'danger')
            data = dict(first_name=first_name, last_name=last_name,
                        email=email, role=role, is_active=is_active)
            return render_template('admin/user_form.html', action='edit', data=data,
                                   user=user, roles=ALLOWED_ROLES, role_labels=ROLE_LABELS)

        user.first_name = first_name
        user.last_name  = last_name
        user.email      = email
        user.role       = role
        user.is_active  = is_active
        if password:
            user.set_password(password)
        user.save()
        flash(f'Usuario "{user.full_name}" actualizado correctamente.', 'success')
        return redirect(url_for('admin.users'))

    data = dict(first_name=user.first_name, last_name=user.last_name,
                email=user.email, role=user.role, is_active=user.is_active)
    return render_template('admin/user_form.html', action='edit', data=data,
                           user=user, roles=ALLOWED_ROLES, role_labels=ROLE_LABELS)


@admin_bp.route('/users/<user_id>/toggle', methods=['POST'])
@login_required
@role_required('ENTITY_ADMIN')
def user_toggle(user_id):
    from app.models.user import User

    try:
        user = User.objects(id=user_id, entity=current_user.entity).first()
    except Exception:
        user = None
    if not user:
        abort(404)

    user.is_active = not user.is_active
    user.save()
    estado = 'activado' if user.is_active else 'desactivado'
    flash(f'Usuario "{user.full_name}" {estado} correctamente.', 'success')
    return redirect(url_for('admin.users'))


# ─── Fuentes de Financiamiento ────────────────────────────────────────────────

@admin_bp.route('/funding')
@login_required
@role_required('ENTITY_ADMIN')
def funding():
    from app.models.funding import FundingSource
    sources = FundingSource.objects(entity=current_user.entity).order_by('name')
    return render_template('admin/funding.html', sources=sources)


@admin_bp.route('/funding/create', methods=['GET', 'POST'])
@login_required
@role_required('ENTITY_ADMIN')
def funding_create():
    from app.models.funding import FundingSource

    if request.method == 'POST':
        name         = request.form.get('name', '').strip()
        code         = request.form.get('code', '').strip().upper()
        total_budget = request.form.get('total_budget', '').strip()

        errors = []
        if not name:  errors.append('El nombre es obligatorio.')
        if not code:  errors.append('El código es obligatorio.')
        if not total_budget: errors.append('El presupuesto total es obligatorio.')
        else:
            try:
                total_budget = float(total_budget.replace(',', '.'))
                if total_budget <= 0:
                    errors.append('El presupuesto debe ser mayor a cero.')
            except ValueError:
                errors.append('El presupuesto debe ser un número válido.')
                total_budget = ''
        if code and FundingSource.objects(entity=current_user.entity, code=code).first():
            errors.append(f'Ya existe una fuente con el código "{code}" en esta entidad.')

        if errors:
            for e in errors: flash(e, 'danger')
            data = dict(name=name, code=code, total_budget=total_budget)
            return render_template('admin/funding_form.html', action='create', data=data)

        FundingSource(entity=current_user.entity, name=name, code=code,
                      total_budget=float(total_budget), allocated_budget=0.0,
                      is_active=True).save()
        flash(f'Fuente "{name}" creada exitosamente.', 'success')
        return redirect(url_for('admin.funding'))

    data = dict(name='', code='', total_budget='')
    return render_template('admin/funding_form.html', action='create', data=data)


@admin_bp.route('/funding/<source_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('ENTITY_ADMIN')
def funding_edit(source_id):
    from app.models.funding import FundingSource

    try:
        source = FundingSource.objects(id=source_id, entity=current_user.entity).first()
    except Exception:
        source = None
    if not source:
        abort(404)

    if request.method == 'POST':
        name         = request.form.get('name', '').strip()
        code         = request.form.get('code', '').strip().upper()
        total_budget = request.form.get('total_budget', '').strip()

        errors = []
        if not name:  errors.append('El nombre es obligatorio.')
        if not code:  errors.append('El código es obligatorio.')
        if not total_budget: errors.append('El presupuesto total es obligatorio.')
        else:
            try:
                total_budget = float(total_budget.replace(',', '.'))
                if total_budget <= 0:
                    errors.append('El presupuesto debe ser mayor a cero.')
            except ValueError:
                errors.append('El presupuesto debe ser un número válido.')
                total_budget = ''
        if code and FundingSource.objects(
                entity=current_user.entity, code=code, id__ne=source.id).first():
            errors.append(f'Ya existe otra fuente con el código "{code}".')

        if errors:
            for e in errors: flash(e, 'danger')
            data = dict(name=name, code=code, total_budget=total_budget)
            return render_template('admin/funding_form.html', action='edit',
                                   data=data, source=source)

        source.name         = name
        source.code         = code
        source.total_budget = float(total_budget)
        source.save()
        flash(f'Fuente "{name}" actualizada correctamente.', 'success')
        return redirect(url_for('admin.funding'))

    data = dict(name=source.name, code=source.code,
                total_budget=f'{source.total_budget:,.0f}')
    return render_template('admin/funding_form.html', action='edit',
                           data=data, source=source)


@admin_bp.route('/funding/<source_id>/toggle', methods=['POST'])
@login_required
@role_required('ENTITY_ADMIN')
def funding_toggle(source_id):
    from app.models.funding import FundingSource

    try:
        source = FundingSource.objects(id=source_id, entity=current_user.entity).first()
    except Exception:
        source = None
    if not source:
        abort(404)

    source.is_active = not source.is_active
    source.save()
    estado = 'activada' if source.is_active else 'desactivada'
    flash(f'Fuente "{source.name}" {estado} correctamente.', 'success')
    return redirect(url_for('admin.funding'))


# ─── Perfil de Entidad ────────────────────────────────────────────────────────

@admin_bp.route('/entity')
@login_required
@role_required('ENTITY_ADMIN')
def entity_profile():
    return render_template('admin/entity_profile.html', entity=current_user.entity)


@admin_bp.route('/entity/address', methods=['POST'])
@login_required
@role_required('ENTITY_ADMIN')
def entity_address():
    address = request.form.get('address', '').strip()
    entity  = current_user.entity
    entity.address = address
    entity.save()
    flash('Dirección actualizada correctamente.', 'success')
    return redirect(url_for('admin.entity_profile'))


# ─── Logs de Actividad ────────────────────────────────────────────────────────

@admin_bp.route('/logs')
@login_required
@role_required('ENTITY_ADMIN')
def logs():
    from datetime import datetime
    from app.models.initiative import Initiative

    action_filter = request.args.get('action', '').strip()
    date_from     = request.args.get('date_from', '').strip()
    date_to       = request.args.get('date_to', '').strip()

    dt_from = dt_to = None
    if date_from:
        try: dt_from = datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError: pass
    if date_to:
        try: dt_to = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError: pass

    entries = []
    for initiative in Initiative.objects(entity=current_user.entity):
        for entry in initiative.audit_trail:
            if action_filter and entry.action != action_filter:
                continue
            if dt_from and entry.timestamp < dt_from:
                continue
            if dt_to and entry.timestamp > dt_to:
                continue
            entries.append(dict(
                timestamp=entry.timestamp,
                user=entry.user,
                action=entry.action,
                details=entry.details or '',
                initiative_code=initiative.code,
                initiative_title=initiative.title,
            ))

    entries.sort(key=lambda x: x['timestamp'], reverse=True)
    total   = len(entries)
    entries = entries[:200]

    return render_template('admin/logs.html',
                           entries=entries, total=total,
                           audit_actions=AUDIT_ACTIONS,
                           selected_action=action_filter,
                           date_from=date_from, date_to=date_to)
