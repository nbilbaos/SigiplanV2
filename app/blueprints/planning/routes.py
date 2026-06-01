from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.blueprints.planning import planning_bp
from app.utils.decorators import role_required

# Roles con acceso de lectura al módulo (la formulación tiene su propio blueprint)
READ_ROLES = ['PLANNING_DIRECTOR', 'FORMULATION_LEADER', 'TECHNICAL_FORMULATOR']

STATUS_LABELS = {
    'DRAFT': 'Borrador',
    'IN_PROGRESS': 'En Formulación',
    'UNDER_REVIEW': 'En Revisión',
    'APPROVED': 'Aprobada',
    'REJECTED': 'Devuelta con Observaciones',
    'ARCHIVED': 'Archivada',
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _base_query(include_deleted=False):
    """Iniciativas de la entidad del usuario, con aislamiento de tenant."""
    from app.models.initiative import Initiative
    q = Initiative.objects(entity=current_user.entity)
    if not include_deleted:
        q = q.filter(is_deleted=False)
    return q


def _scoped_visible(query):
    """El Formulador Técnico solo ve las iniciativas que tiene asignadas."""
    if current_user.role == 'TECHNICAL_FORMULATOR':
        return query.filter(assigned_formulators=current_user.id)
    return query


def _get_initiative(initiative_id, include_deleted=False):
    from app.models.initiative import Initiative
    try:
        init = Initiative.objects(
            id=initiative_id, entity=current_user.entity
        ).first()
    except Exception:
        init = None
    if not init:
        abort(404)
    if init.is_deleted and not include_deleted:
        abort(404)
    if current_user.role == 'TECHNICAL_FORMULATOR' and current_user.id not in [
        f.id for f in init.assigned_formulators if f
    ]:
        abort(403)
    return init


def _entity_team():
    """Devuelve los usuarios de la entidad agrupados por rol para los selectores."""
    from app.models.user import User
    users = User.objects(entity=current_user.entity, is_active=True)
    return {
        'directors':   users.filter(role='PLANNING_DIRECTOR').order_by('first_name'),
        'leaders':     users.filter(role='FORMULATION_LEADER').order_by('first_name'),
        'formulators': users.filter(role='TECHNICAL_FORMULATOR').order_by('first_name'),
    }


def _parse_initiative_form(form):
    """Extrae y normaliza los campos del formulario de iniciativa."""
    from app.models.user import User
    from app.models.funding import FundingSource

    data = dict(
        code=form.get('code', '').strip().upper(),
        title=form.get('title', '').strip(),
        description=form.get('description', '').strip(),
        planning_director=form.get('planning_director', '').strip(),
        formulation_leader=form.get('formulation_leader', '').strip(),
        assigned_formulators=form.getlist('assigned_formulators'),
        funding_sources=form.getlist('funding_sources'),
        estimated_cost=form.get('estimated_cost', '').strip(),
        deadline=form.get('deadline', '').strip(),
    )

    errors = []
    if not data['code']:        errors.append('El código es obligatorio.')
    if not data['title']:       errors.append('El título es obligatorio.')
    if not data['description']: errors.append('La descripción es obligatoria.')

    # Costo estimado
    cost = 0.0
    if data['estimated_cost']:
        try:
            cost = float(data['estimated_cost'].replace('.', '').replace(',', '.')) \
                if data['estimated_cost'].count(',') else float(data['estimated_cost'])
        except ValueError:
            errors.append('El costo estimado debe ser un número válido.')

    # Plazo
    deadline = None
    if data['deadline']:
        try:
            deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
        except ValueError:
            errors.append('La fecha de plazo no es válida.')

    # Resolver referencias (siempre dentro de la entidad)
    director = leader = None
    if data['planning_director']:
        director = User.objects(
            id=data['planning_director'], entity=current_user.entity,
            role='PLANNING_DIRECTOR').first()
    if data['formulation_leader']:
        leader = User.objects(
            id=data['formulation_leader'], entity=current_user.entity,
            role='FORMULATION_LEADER').first()

    formulators = list(User.objects(
        id__in=data['assigned_formulators'], entity=current_user.entity,
        role='TECHNICAL_FORMULATOR')) if data['assigned_formulators'] else []

    sources = list(FundingSource.objects(
        id__in=data['funding_sources'], entity=current_user.entity)) \
        if data['funding_sources'] else []

    resolved = dict(
        director=director, leader=leader, formulators=formulators,
        sources=sources, cost=cost, deadline=deadline,
    )
    return data, resolved, errors


# ─── Listado de Iniciativas ───────────────────────────────────────────────────

@planning_bp.route('/initiatives')
@login_required
@role_required(*READ_ROLES)
def initiatives():
    status_filter = request.args.get('status', '').strip()
    search        = request.args.get('q', '').strip()

    query = _scoped_visible(_base_query())
    if status_filter in STATUS_LABELS:
        query = query.filter(status=status_filter)
    if search:
        query = query.filter(__raw__={'$or': [
            {'code':  {'$regex': search, '$options': 'i'}},
            {'title': {'$regex': search, '$options': 'i'}},
        ]})

    initiatives = query.order_by('-updated_at')

    # Conteo por estado para los chips de filtro (sobre el universo visible)
    visible = _scoped_visible(_base_query())
    counts = {s: visible.filter(status=s).count() for s in STATUS_LABELS}
    counts['ALL'] = visible.count()

    return render_template('planning/initiatives.html',
                           initiatives=initiatives,
                           status_labels=STATUS_LABELS,
                           counts=counts,
                           selected_status=status_filter,
                           search=search,
                           can_manage=current_user.role == 'PLANNING_DIRECTOR')


# ─── Crear Iniciativa ─────────────────────────────────────────────────────────

@planning_bp.route('/initiative/create', methods=['GET', 'POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def create_initiative():
    from app.models.initiative import Initiative

    team = _entity_team()

    if request.method == 'POST':
        data, resolved, errors = _parse_initiative_form(request.form)

        if data['code'] and Initiative.objects(
                entity=current_user.entity, code=data['code']).first():
            errors.append(f"Ya existe una iniciativa con el código \"{data['code']}\".")

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('planning/initiative_form.html',
                                   action='create', data=data, team=team,
                                   funding_sources=_entity_funding(),
                                   initiative=None)

        init = Initiative(
            entity=current_user.entity,
            code=data['code'], title=data['title'], description=data['description'],
            planning_director=resolved['director'] or current_user._get_current_object(),
            formulation_leader=resolved['leader'],
            assigned_formulators=resolved['formulators'],
            funding_sources=resolved['sources'],
            estimated_cost=resolved['cost'],
            deadline=resolved['deadline'],
            status='DRAFT',
        )
        init.save()
        init.log_action(current_user, 'CREATE',
                        f"Iniciativa \"{init.title}\" creada en estado Borrador.")
        flash(f'Iniciativa "{init.code}" creada exitosamente.', 'success')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))

    data = dict(code='', title='', description='',
                planning_director=str(current_user.id), formulation_leader='',
                assigned_formulators=[], funding_sources=[],
                estimated_cost='', deadline='')
    return render_template('planning/initiative_form.html',
                           action='create', data=data, team=team,
                           funding_sources=_entity_funding(), initiative=None)


def _entity_funding():
    from app.models.funding import FundingSource
    return FundingSource.objects(
        entity=current_user.entity, is_active=True).order_by('name')


# ─── Detalle de Iniciativa ────────────────────────────────────────────────────

@planning_bp.route('/initiative/<initiative_id>')
@login_required
@role_required(*READ_ROLES)
def initiative_detail(initiative_id):
    init = _get_initiative(initiative_id)
    # Bitácora en orden cronológico inverso
    trail = sorted(init.audit_trail, key=lambda e: e.timestamp, reverse=True)
    return render_template('planning/initiative_detail.html',
                           init=init, trail=trail,
                           status_labels=STATUS_LABELS,
                           can_manage=current_user.role == 'PLANNING_DIRECTOR')


# ─── Editar Iniciativa ────────────────────────────────────────────────────────

@planning_bp.route('/initiative/<initiative_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_edit(initiative_id):
    from app.models.initiative import Initiative

    init = _get_initiative(initiative_id)
    if init.status not in ('DRAFT', 'IN_PROGRESS', 'REJECTED'):
        flash('Solo se pueden editar iniciativas en Borrador, En Formulación o Devueltas.', 'warning')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))

    team = _entity_team()

    if request.method == 'POST':
        data, resolved, errors = _parse_initiative_form(request.form)

        if data['code'] and Initiative.objects(
                entity=current_user.entity, code=data['code'],
                id__ne=init.id).first():
            errors.append(f"Ya existe otra iniciativa con el código \"{data['code']}\".")

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('planning/initiative_form.html',
                                   action='edit', data=data, team=team,
                                   funding_sources=_entity_funding(),
                                   initiative=init)

        init.code        = data['code']
        init.title       = data['title']
        init.description = data['description']
        init.planning_director   = resolved['director']
        init.formulation_leader  = resolved['leader']
        init.assigned_formulators = resolved['formulators']
        init.funding_sources     = resolved['sources']
        init.estimated_cost      = resolved['cost']
        init.deadline            = resolved['deadline']
        init.save()
        init.log_action(current_user, 'UPDATE',
                        'Datos de la iniciativa actualizados.')
        flash('Iniciativa actualizada correctamente.', 'success')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))

    data = dict(
        code=init.code, title=init.title, description=init.description,
        planning_director=str(init.planning_director.id) if init.planning_director else '',
        formulation_leader=str(init.formulation_leader.id) if init.formulation_leader else '',
        assigned_formulators=[str(f.id) for f in init.assigned_formulators if f],
        funding_sources=[str(s.id) for s in init.funding_sources if s],
        estimated_cost=('%0.0f' % init.estimated_cost) if init.estimated_cost else '',
        deadline=init.deadline.strftime('%Y-%m-%d') if init.deadline else '',
    )
    return render_template('planning/initiative_form.html',
                           action='edit', data=data, team=team,
                           funding_sources=_entity_funding(), initiative=init)


# ─── Transiciones de Estado ───────────────────────────────────────────────────

@planning_bp.route('/initiative/<initiative_id>/activate', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_activate(initiative_id):
    init = _get_initiative(initiative_id)
    if init.status != 'DRAFT':
        flash('Solo se puede activar una iniciativa en Borrador.', 'warning')
    else:
        init.status = 'IN_PROGRESS'
        init.save()
        init.log_action(current_user, 'UPDATE',
                        'Iniciativa activada: pasa a formulación técnica.')
        flash('Iniciativa activada. Ahora está en formulación.', 'success')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))


@planning_bp.route('/initiative/<initiative_id>/approve', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_approve(initiative_id):
    init = _get_initiative(initiative_id)
    if init.status != 'UNDER_REVIEW':
        flash('Solo se pueden aprobar iniciativas que están En Revisión.', 'warning')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))
    comment = request.form.get('comment', '').strip()
    init.status = 'APPROVED'
    init.save()
    init.log_action(current_user, 'APPROVE',
                    comment or 'Iniciativa aprobada por el Director de Planificación.')
    flash(f'Iniciativa "{init.code}" aprobada.', 'success')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))


@planning_bp.route('/initiative/<initiative_id>/reject', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_reject(initiative_id):
    init = _get_initiative(initiative_id)
    if init.status != 'UNDER_REVIEW':
        flash('Solo se pueden rechazar iniciativas que están En Revisión.', 'warning')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))
    comment = request.form.get('comment', '').strip()
    if not comment:
        flash('Debes indicar las observaciones del rechazo.', 'danger')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))
    init.status = 'REJECTED'
    init.save()
    init.log_action(current_user, 'REJECT', comment)
    flash(f'Iniciativa "{init.code}" devuelta con observaciones.', 'warning')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))


@planning_bp.route('/initiative/<initiative_id>/archive', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_archive(initiative_id):
    init = _get_initiative(initiative_id)
    if init.status != 'APPROVED':
        flash('Solo se pueden archivar iniciativas Aprobadas.', 'warning')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))
    init.status = 'ARCHIVED'
    init.save()
    init.log_action(current_user, 'UPDATE', 'Iniciativa archivada.')
    flash(f'Iniciativa "{init.code}" archivada.', 'success')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))


# ─── Borrado Lógico / Restauración ────────────────────────────────────────────

@planning_bp.route('/initiative/<initiative_id>/delete', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_delete(initiative_id):
    init = _get_initiative(initiative_id)
    init.is_deleted = True
    init.save()
    init.log_action(current_user, 'SOFT_DELETE', 'Iniciativa enviada a la papelera.')
    flash(f'Iniciativa "{init.code}" movida a la papelera.', 'success')
    return redirect(url_for('planning.initiatives'))


@planning_bp.route('/trash')
@login_required
@role_required('PLANNING_DIRECTOR')
def trash():
    deleted = _base_query(include_deleted=True).filter(
        is_deleted=True).order_by('-updated_at')
    return render_template('planning/trash.html',
                           initiatives=deleted, status_labels=STATUS_LABELS)


@planning_bp.route('/initiative/<initiative_id>/restore', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_restore(initiative_id):
    init = _get_initiative(initiative_id, include_deleted=True)
    init.is_deleted = False
    init.save()
    init.log_action(current_user, 'RESTORE', 'Iniciativa restaurada desde la papelera.')
    flash(f'Iniciativa "{init.code}" restaurada.', 'success')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))


# ─── Fuentes de Financiamiento (vista del Director) ───────────────────────────

@planning_bp.route('/funding')
@login_required
@role_required('PLANNING_DIRECTOR')
def funding():
    from app.models.funding import FundingSource
    from app.models.initiative import Initiative

    sources = FundingSource.objects(entity=current_user.entity).order_by('name')

    # Para cada fuente, cuántas iniciativas activas la usan
    usage = {}
    for s in sources:
        usage[str(s.id)] = Initiative.objects(
            entity=current_user.entity, is_deleted=False,
            funding_sources=s.id).count()

    total_budget    = sum(s.total_budget for s in sources if s.is_active)
    total_allocated = sum(s.allocated_budget for s in sources if s.is_active)

    return render_template('planning/funding.html',
                           sources=sources, usage=usage,
                           total_budget=total_budget,
                           total_allocated=total_allocated)


# ─── Organigrama ──────────────────────────────────────────────────────────────

@planning_bp.route('/org-chart')
@login_required
@role_required('PLANNING_DIRECTOR')
def org_chart():
    from app.models.user import User

    users = User.objects(entity=current_user.entity)
    by_role = {
        'ENTITY_ADMIN':        list(users.filter(role='ENTITY_ADMIN').order_by('first_name')),
        'PLANNING_DIRECTOR':   list(users.filter(role='PLANNING_DIRECTOR').order_by('first_name')),
        'FORMULATION_LEADER':  list(users.filter(role='FORMULATION_LEADER').order_by('first_name')),
        'TECHNICAL_FORMULATOR': list(users.filter(role='TECHNICAL_FORMULATOR').order_by('first_name')),
    }
    return render_template('planning/org_chart.html', by_role=by_role)
