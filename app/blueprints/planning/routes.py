import csv
import io
import re
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from mongoengine import Q
from app.blueprints.planning import planning_bp
from app.services.exceptions import ServiceError
from app.services.initiative import InitiativeService
from app.utils.decorators import role_required
from app.utils.executive import build_executive_context, next_action_for
from app.utils.tenant import (
    get_tenant_initiative,
    tenant_funding_sources,
    tenant_initiatives,
    tenant_users,
    visible_tenant_initiatives,
)

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
    return tenant_initiatives(include_deleted=include_deleted)


def _scoped_visible(query):
    """El Formulador Técnico solo ve las iniciativas que tiene asignadas."""
    if current_user.role == 'TECHNICAL_FORMULATOR':
        return query.filter(assigned_formulators=current_user._get_current_object())
    return query


def _portfolio_query_for_user():
    return visible_tenant_initiatives()


def _get_initiative(initiative_id, include_deleted=False):
    return get_tenant_initiative(initiative_id, include_deleted=include_deleted)


def _entity_team():
    """Devuelve los usuarios de la entidad agrupados por rol para los selectores."""
    users = tenant_users(is_active=True)
    return {
        'directors':   users.filter(role='PLANNING_DIRECTOR').order_by('first_name'),
        'leaders':     users.filter(role='FORMULATION_LEADER').order_by('first_name'),
        'formulators': users.filter(role='TECHNICAL_FORMULATOR').order_by('first_name'),
    }


def _parse_initiative_form(form):
    """Extrae y normaliza los campos del formulario de iniciativa."""
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
        director = tenant_users(
            id=data['planning_director'], role='PLANNING_DIRECTOR').first()
    if data['formulation_leader']:
        leader = tenant_users(
            id=data['formulation_leader'], role='FORMULATION_LEADER').first()

    formulators = list(tenant_users(
        id__in=data['assigned_formulators'],
        role='TECHNICAL_FORMULATOR')) if data['assigned_formulators'] else []

    sources = list(tenant_funding_sources(id__in=data['funding_sources'])) \
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
    responsible   = request.args.get('responsible', '').strip()
    funding_id    = request.args.get('funding', '').strip()
    due_filter    = request.args.get('due', '').strip()
    sort          = request.args.get('sort', '-updated_at').strip()
    post_filter = None

    query = _scoped_visible(_base_query())
    if status_filter in STATUS_LABELS:
        query = query.filter(status=status_filter)
    if search:
        safe_search = re.escape(search)
        query = query.filter(__raw__={'$or': [
            {'code':  {'$regex': safe_search, '$options': 'i'}},
            {'title': {'$regex': safe_search, '$options': 'i'}},
        ]})
    if responsible:
        user = tenant_users(id=responsible).first()
        if user:
            query = query.filter(
                Q(planning_director=user) |
                Q(formulation_leader=user) |
                Q(assigned_formulators=user)
            )
    if funding_id:
        source = tenant_funding_sources(id=funding_id).first()
        if source:
            query = query.filter(funding_sources=source)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if due_filter == 'overdue':
        query = query.filter(deadline__lt=today, status__nin=['APPROVED', 'ARCHIVED'])
    elif due_filter == 'due_soon':
        query = query.filter(deadline__gte=today, deadline__lte=today + timedelta(days=30),
                             status__nin=['APPROVED', 'ARCHIVED'])
    elif due_filter == 'no_deadline':
        query = query.filter(deadline=None)
    elif due_filter == 'no_formulators':
        post_filter = lambda item: (
            item.status not in ('APPROVED', 'ARCHIVED') and
            not [f for f in item.assigned_formulators if f]
        )
    elif due_filter == 'no_funding':
        post_filter = lambda item: (
            item.status not in ('APPROVED', 'ARCHIVED') and
            not [s for s in item.funding_sources if s]
        )

    sort_map = {
        '-updated_at': '-updated_at',
        'deadline': 'deadline',
        '-estimated_cost': '-estimated_cost',
        'status': 'status',
        'code': 'code',
    }
    initiatives = query.order_by(sort_map.get(sort, '-updated_at'))
    if post_filter:
        initiatives = [item for item in initiatives if post_filter(item)]

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
                           responsible=responsible,
                           funding_id=funding_id,
                           due_filter=due_filter,
                           sort=sort,
                           team=_entity_team(),
                           funding_sources=_entity_funding(),
                           can_manage=current_user.role == 'PLANNING_DIRECTOR')


# ─── Crear Iniciativa ─────────────────────────────────────────────────────────

@planning_bp.route('/initiative/create', methods=['GET', 'POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def create_initiative():
    team = _entity_team()

    if request.method == 'POST':
        data, resolved, errors = _parse_initiative_form(request.form)

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('planning/initiative_form.html',
                                   action='create', data=data, team=team,
                                   funding_sources=_entity_funding(),
                                   initiative=None)

        try:
            init = InitiativeService.create(
                entity=current_user.entity,
                actor=current_user,
                code=data['code'],
                title=data['title'],
                description=data['description'],
                planning_director=resolved['director'],
                formulation_leader=resolved['leader'],
                assigned_formulators=resolved['formulators'],
                funding_sources=resolved['sources'],
                estimated_cost=resolved['cost'],
                deadline=resolved['deadline'],
            )
        except ServiceError as exc:
            flash(str(exc), 'danger')
            return render_template('planning/initiative_form.html',
                                   action='create', data=data, team=team,
                                   funding_sources=_entity_funding(),
                                   initiative=None)

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
    return tenant_funding_sources(is_active=True).order_by('name')


# ─── Detalle de Iniciativa ────────────────────────────────────────────────────

@planning_bp.route('/initiative/<initiative_id>')
@login_required
@role_required(*READ_ROLES)
def initiative_detail(initiative_id):
    init = _get_initiative(initiative_id)
    # Bitácora en orden cronológico inverso
    trail = sorted(init.audit_trail, key=lambda e: e.timestamp, reverse=True)
    next_action = next_action_for(init, current_user.role)
    return render_template('planning/initiative_detail.html',
                           init=init, trail=trail,
                           status_labels=STATUS_LABELS,
                           next_action=next_action,
                           can_manage=current_user.role == 'PLANNING_DIRECTOR')


# ─── Editar Iniciativa ────────────────────────────────────────────────────────

@planning_bp.route('/initiative/<initiative_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_edit(initiative_id):
    init = _get_initiative(initiative_id)
    if init.status not in InitiativeService.EDITABLE_STATUSES:
        flash('Solo se pueden editar iniciativas en Borrador, En Formulacion o Devueltas.', 'warning')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))

    team = _entity_team()

    if request.method == 'POST':
        data, resolved, errors = _parse_initiative_form(request.form)

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('planning/initiative_form.html',
                                   action='edit', data=data, team=team,
                                   funding_sources=_entity_funding(),
                                   initiative=init)

        try:
            InitiativeService.update_details(
                init,
                actor=current_user,
                code=data['code'],
                title=data['title'],
                description=data['description'],
                planning_director=resolved['director'],
                formulation_leader=resolved['leader'],
                assigned_formulators=resolved['formulators'],
                funding_sources=resolved['sources'],
                estimated_cost=resolved['cost'],
                deadline=resolved['deadline'],
            )
        except ServiceError as exc:
            flash(str(exc), 'danger')
            return render_template('planning/initiative_form.html',
                                   action='edit', data=data, team=team,
                                   funding_sources=_entity_funding(),
                                   initiative=init)

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
    try:
        InitiativeService.transition_status(
            init,
            actor=current_user,
            target_status='IN_PROGRESS',
            action='UPDATE',
            details='Iniciativa activada: pasa a formulacion tecnica.',
            allowed_from=('DRAFT',),
        )
        flash('Iniciativa activada. Ahora esta en formulacion.', 'success')
    except ServiceError:
        flash('Solo se puede activar una iniciativa en Borrador.', 'warning')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))


@planning_bp.route('/initiative/<initiative_id>/approve', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_approve(initiative_id):
    init = _get_initiative(initiative_id)
    comment = request.form.get('comment', '').strip()
    try:
        InitiativeService.transition_status(
            init,
            actor=current_user,
            target_status='APPROVED',
            action='APPROVE',
            details=comment or 'Iniciativa aprobada por el Director de Planificacion.',
            allowed_from=('UNDER_REVIEW',),
        )
    except ServiceError:
        flash('Solo se pueden aprobar iniciativas que estan En Revision.', 'warning')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))
    flash(f'Iniciativa "{init.code}" aprobada.', 'success')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))


@planning_bp.route('/initiative/<initiative_id>/reject', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_reject(initiative_id):
    init = _get_initiative(initiative_id)
    comment = request.form.get('comment', '').strip()
    if not comment:
        flash('Debes indicar las observaciones del rechazo.', 'danger')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))
    try:
        InitiativeService.transition_status(
            init,
            actor=current_user,
            target_status='REJECTED',
            action='REJECT',
            details=comment,
            allowed_from=('UNDER_REVIEW',),
        )
    except ServiceError:
        flash('Solo se pueden rechazar iniciativas que estan En Revision.', 'warning')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))
    flash(f'Iniciativa "{init.code}" devuelta con observaciones.', 'warning')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))


@planning_bp.route('/initiative/<initiative_id>/archive', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_archive(initiative_id):
    init = _get_initiative(initiative_id)
    try:
        InitiativeService.transition_status(
            init,
            actor=current_user,
            target_status='ARCHIVED',
            action='UPDATE',
            details='Iniciativa archivada.',
            allowed_from=('APPROVED',),
        )
    except ServiceError:
        flash('Solo se pueden archivar iniciativas Aprobadas.', 'warning')
        return redirect(url_for('planning.initiative_detail', initiative_id=init.id))
    flash(f'Iniciativa "{init.code}" archivada.', 'success')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))

# ─── Borrado Lógico / Restauración ────────────────────────────────────────────

@planning_bp.route('/initiative/<initiative_id>/delete', methods=['POST'])
@login_required
@role_required('PLANNING_DIRECTOR')
def initiative_delete(initiative_id):
    init = _get_initiative(initiative_id)
    InitiativeService.soft_delete(init, actor=current_user)
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
    InitiativeService.restore(init, actor=current_user)
    flash(f'Iniciativa "{init.code}" restaurada.', 'success')
    return redirect(url_for('planning.initiative_detail', initiative_id=init.id))

# ─── Fuentes de Financiamiento (vista del Director) ───────────────────────────

@planning_bp.route('/funding')
@login_required
@role_required('PLANNING_DIRECTOR')
def funding():
    sources = tenant_funding_sources().order_by('name')

    # Para cada fuente, cuántas iniciativas activas la usan
    usage = {}
    for s in sources:
        usage[str(s.id)] = tenant_initiatives(funding_sources=s).count()

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
    users = tenant_users()
    by_role = {
        'ENTITY_ADMIN':        list(users.filter(role='ENTITY_ADMIN').order_by('first_name')),
        'PLANNING_DIRECTOR':   list(users.filter(role='PLANNING_DIRECTOR').order_by('first_name')),
        'FORMULATION_LEADER':  list(users.filter(role='FORMULATION_LEADER').order_by('first_name')),
        'TECHNICAL_FORMULATOR': list(users.filter(role='TECHNICAL_FORMULATOR').order_by('first_name')),
    }
    return render_template('planning/org_chart.html', by_role=by_role)


@planning_bp.route('/portfolio/export.csv')
@login_required
@role_required('ENTITY_ADMIN', 'PLANNING_DIRECTOR')
def portfolio_export_csv():
    initiatives = _portfolio_query_for_user().order_by('-updated_at')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Código', 'Título', 'Estado', 'Costo estimado CLP', 'Plazo',
        'Director', 'Coordinador', 'Formuladores', 'Fuentes', 'Última actualización'
    ])
    for init in initiatives:
        writer.writerow([
            init.code,
            init.title,
            init.get_status_display(),
            f'{init.estimated_cost or 0:.0f}',
            init.deadline.strftime('%d/%m/%Y') if init.deadline else '',
            init.planning_director.full_name if init.planning_director else '',
            init.formulation_leader.full_name if init.formulation_leader else '',
            ', '.join(f.full_name for f in init.assigned_formulators if f),
            ', '.join(s.code for s in init.funding_sources if s),
            init.updated_at.strftime('%d/%m/%Y %H:%M') if init.updated_at else '',
        ])
    csv_data = '\ufeff' + output.getvalue()
    filename = f"cartera_sigiplan_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        csv_data,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@planning_bp.route('/report/executive')
@login_required
@role_required('ENTITY_ADMIN', 'PLANNING_DIRECTOR')
def executive_report():
    metrics = build_executive_context(current_user)
    return render_template(
        'planning/executive_report.html',
        metrics=metrics,
        generated_at=datetime.utcnow(),
    )
