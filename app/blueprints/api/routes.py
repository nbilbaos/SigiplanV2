from flask import jsonify, request
from flask_login import login_required, current_user
from app.blueprints.api import api_bp
from app.utils.decorators import role_required
from app.utils.executive import build_executive_context
from app.utils.tenant import (
    tenant_funding_sources,
    tenant_initiatives,
    tenant_users,
    visible_tenant_initiatives,
)

# Roles con entidad que pueden consultar datos de iniciativas
INITIATIVE_ROLES = [
    'ENTITY_ADMIN', 'PLANNING_DIRECTOR', 'FORMULATION_LEADER', 'TECHNICAL_FORMULATOR'
]

ROLE_TIERS = [
    'ENTITY_ADMIN', 'PLANNING_DIRECTOR', 'FORMULATION_LEADER', 'TECHNICAL_FORMULATOR'
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _iso(dt):
    return dt.isoformat() if dt else None


def _scoped_initiatives():
    return visible_tenant_initiatives()


# ─── Organigrama (datos para visualización tipo grafo) ────────────────────────

@api_bp.route('/org-data')
@login_required
@role_required('ENTITY_ADMIN', 'PLANNING_DIRECTOR', 'FORMULATION_LEADER')
def org_data():
    users = tenant_users()
    by_role = {tier: list(users.filter(role=tier).order_by('first_name')) for tier in ROLE_TIERS}

    nodes, edges = [], []
    for tier in ROLE_TIERS:
        for u in by_role[tier]:
            nodes.append({
                'id': str(u.id),
                'label': u.full_name,
                'role': u.role,
                'title': u.get_role_display(),
                'group': tier,
                'is_active': u.is_active,
            })

    # Conectar cada nivel jerárquico con el inmediatamente inferior
    for parent_tier, child_tier in zip(ROLE_TIERS, ROLE_TIERS[1:]):
        for parent in by_role[parent_tier]:
            for child in by_role[child_tier]:
                edges.append({'from': str(parent.id), 'to': str(child.id)})

    return jsonify({'nodes': nodes, 'edges': edges})


# ─── Iniciativas ──────────────────────────────────────────────────────────────

@api_bp.route('/initiatives')
@login_required
@role_required(*INITIATIVE_ROLES)
def initiatives():
    status_filter = request.args.get('status', '').strip()

    q = _scoped_initiatives()
    if status_filter:
        q = q.filter(status=status_filter)

    items = []
    for i in q.order_by('-updated_at'):
        items.append({
            'id': str(i.id),
            'code': i.code,
            'title': i.title,
            'status': i.status,
            'status_display': i.get_status_display(),
            'estimated_cost': i.estimated_cost or 0.0,
            'deadline': _iso(i.deadline),
            'planning_director': i.planning_director.full_name if i.planning_director else None,
            'formulation_leader': i.formulation_leader.full_name if i.formulation_leader else None,
            'formulators_count': len([f for f in i.assigned_formulators if f]),
            'funding_sources': [s.code for s in i.funding_sources if s],
            'attachments_count': len(i.attachments),
            'updated_at': _iso(i.updated_at),
        })

    return jsonify({'count': len(items), 'initiatives': items})


# ─── Fuentes de Financiamiento ────────────────────────────────────────────────

@api_bp.route('/funding-sources')
@login_required
@role_required('ENTITY_ADMIN', 'PLANNING_DIRECTOR')
def funding_sources():
    sources = tenant_funding_sources().order_by('name')

    items = []
    for s in sources:
        usage = tenant_initiatives(funding_sources=s).count()
        items.append({
            'id': str(s.id),
            'name': s.name,
            'code': s.code,
            'total_budget': s.total_budget,
            'allocated_budget': s.allocated_budget,
            'remaining_budget': s.remaining_budget,
            'is_active': s.is_active,
            'usage_count': usage,
        })

    return jsonify({'count': len(items), 'funding_sources': items})


# ─── Métricas del Dashboard (según rol) ───────────────────────────────────────

@api_bp.route('/dashboard-metrics')
@login_required
def dashboard_metrics():
    from app.models.user import User
    from app.models.initiative import Initiative

    role = current_user.role

    if role == 'SUPER_ADMIN':
        from app.models.entity import Entity
        return jsonify({
            'role': role,
            'metrics': {
                'entities': Entity.objects.count(),
                'entities_active': Entity.objects(is_active=True).count(),
                'users': User.objects.count(),
                'initiatives': Initiative.objects(is_deleted=False).count(),
            },
        })

    entity = current_user.entity

    if role == 'ENTITY_ADMIN':
        base = tenant_initiatives(entity=entity)
        sources = tenant_funding_sources(entity=entity, is_active=True)
        budget_total = sum(s.total_budget for s in sources)
        budget_allocated = sum(s.allocated_budget for s in sources)
        return jsonify({
            'role': role,
            'metrics': {
                'users': tenant_users(entity=entity).count(),
                'users_active': tenant_users(entity=entity, is_active=True).count(),
                'initiatives': base.count(),
                'by_status': {s: base.filter(status=s).count() for s in
                              ['DRAFT', 'IN_PROGRESS', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'ARCHIVED']},
                'budget_total': budget_total,
                'budget_allocated': budget_allocated,
                'budget_available': max(0.0, budget_total - budget_allocated),
            },
        })

    if role in ('PLANNING_DIRECTOR', 'FORMULATION_LEADER', 'TECHNICAL_FORMULATOR'):
        base = _scoped_initiatives()
        return jsonify({
            'role': role,
            'metrics': {
                'initiatives': base.count(),
                'by_status': {s: base.filter(status=s).count() for s in
                              ['DRAFT', 'IN_PROGRESS', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'ARCHIVED']},
            },
        })

    return jsonify({'role': role, 'metrics': {}})


@api_bp.route('/executive-metrics')
@login_required
@role_required('SUPER_ADMIN', 'ENTITY_ADMIN', 'PLANNING_DIRECTOR', 'FORMULATION_LEADER', 'TECHNICAL_FORMULATOR')
def executive_metrics():
    metrics = build_executive_context(current_user)
    return jsonify({
        'scope': metrics['scope_label'],
        'initiatives_total': metrics['initiatives_total'],
        'estimated_total': metrics['estimated_total'],
        'status_counts': metrics['status_counts'],
        'risks': [
            {key: item[key] for key in ('key', 'label', 'value', 'tone')}
            for item in metrics['risks']
        ],
        'funding': {
            'total': metrics['funding_total'],
            'allocated': metrics['funding_allocated'],
            'available': metrics['funding_available'],
        },
    })
