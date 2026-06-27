from datetime import datetime, timedelta


STATUS_LABELS = {
    'DRAFT': 'Borrador',
    'IN_PROGRESS': 'En Formulación',
    'UNDER_REVIEW': 'En Revisión',
    'APPROVED': 'Aprobada',
    'REJECTED': 'Devuelta',
    'ARCHIVED': 'Archivada',
}

STATUS_ORDER = ['DRAFT', 'IN_PROGRESS', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'ARCHIVED']


def _initiative_scope(user, include_deleted=False):
    from app.models.initiative import Initiative

    query = Initiative.objects()
    if user.role != 'SUPER_ADMIN':
        query = query.filter(entity=user.entity)
    if not include_deleted:
        query = query.filter(is_deleted=False)
    if user.role == 'TECHNICAL_FORMULATOR':
        query = query.filter(assigned_formulators=user)
    return query


def _funding_scope(user):
    from app.models.funding import FundingSource

    query = FundingSource.objects(is_active=True)
    if user.role != 'SUPER_ADMIN':
        query = query.filter(entity=user.entity)
    return query


def _recent_audit(initiatives, limit=8):
    entries = []
    for initiative in initiatives:
        for entry in initiative.audit_trail[-6:]:
            entries.append({
                'timestamp': entry.timestamp,
                'user': entry.user,
                'action': entry.action,
                'details': entry.details or '',
                'initiative': initiative,
            })
    entries.sort(key=lambda item: item['timestamp'] or datetime.min, reverse=True)
    return entries[:limit]


def _status_counts(query):
    return {status: query.filter(status=status).count() for status in STATUS_ORDER}


def _risk_items(query):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    soon = today + timedelta(days=30)
    initiatives = list(query)
    active = [item for item in initiatives if item.status not in ('APPROVED', 'ARCHIVED')]

    overdue = sum(1 for item in active if item.deadline and item.deadline < today)
    due_soon = sum(1 for item in active if item.deadline and today <= item.deadline <= soon)
    no_formulators = sum(1 for item in active if not [f for f in item.assigned_formulators if f])
    no_funding = sum(1 for item in active if not [s for s in item.funding_sources if s])
    rejected = sum(1 for item in initiatives if item.status == 'REJECTED')

    return [
        {
            'key': 'overdue',
            'label': 'Plazo vencido',
            'value': overdue,
            'tone': 'danger',
            'icon': 'fa-calendar-xmark',
            'href': 'overdue',
        },
        {
            'key': 'due_soon',
            'label': 'Próximas a vencer',
            'value': due_soon,
            'tone': 'warning',
            'icon': 'fa-hourglass-half',
            'href': 'due_soon',
        },
        {
            'key': 'no_formulators',
            'label': 'Sin formulador',
            'value': no_formulators,
            'tone': 'warning',
            'icon': 'fa-user-slash',
            'href': 'no_formulators',
        },
        {
            'key': 'no_funding',
            'label': 'Sin financiamiento',
            'value': no_funding,
            'tone': 'info',
            'icon': 'fa-sack-xmark',
            'href': 'no_funding',
        },
        {
            'key': 'rejected',
            'label': 'Devueltas',
            'value': rejected,
            'tone': 'danger',
            'icon': 'fa-triangle-exclamation',
            'href': 'rejected',
        },
    ]


def _critical_portfolio(query, limit=8):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    critical = []
    for initiative in query.order_by('deadline', '-updated_at'):
        flags = []
        if initiative.status == 'REJECTED':
            flags.append('Devuelta')
        if initiative.deadline and initiative.deadline < today and initiative.status not in ('APPROVED', 'ARCHIVED'):
            flags.append('Vencida')
        if not [f for f in initiative.assigned_formulators if f] and initiative.status not in ('APPROVED', 'ARCHIVED'):
            flags.append('Sin formulador')
        if not [s for s in initiative.funding_sources if s] and initiative.status not in ('APPROVED', 'ARCHIVED'):
            flags.append('Sin fuente')
        if flags:
            critical.append({'initiative': initiative, 'flags': flags})
        if len(critical) >= limit:
            break
    return critical


def next_action_for(initiative, role):
    if initiative.status == 'DRAFT':
        return 'Activar formulación' if role == 'PLANNING_DIRECTOR' else 'Esperando activación'
    if initiative.status == 'IN_PROGRESS':
        return 'Completar ficha y enviar a revisión'
    if initiative.status == 'UNDER_REVIEW':
        return 'Aprobar o devolver con observaciones' if role == 'PLANNING_DIRECTOR' else 'Esperando revisión'
    if initiative.status == 'REJECTED':
        return 'Corregir observaciones y reenviar'
    if initiative.status == 'APPROVED':
        return 'Archivar cuando cierre el ciclo'
    return 'Sin acción pendiente'


def build_executive_context(user):
    from app.models.entity import Entity
    from app.models.user import User

    query = _initiative_scope(user)
    initiatives = list(query.order_by('-updated_at'))
    sources = list(_funding_scope(user))

    estimated_total = sum(item.estimated_cost or 0 for item in initiatives)
    funding_total = sum(source.total_budget or 0 for source in sources)
    funding_allocated = sum(source.allocated_budget or 0 for source in sources)

    if user.role == 'SUPER_ADMIN':
        users_count = User.objects.count()
        entities_count = Entity.objects.count()
        entities_active = Entity.objects(is_active=True).count()
    else:
        users_count = User.objects(entity=user.entity).count()
        entities_count = 1
        entities_active = 1 if user.entity and user.entity.is_active else 0

    return {
        'status_labels': STATUS_LABELS,
        'status_order': STATUS_ORDER,
        'scope_label': 'Plataforma global' if user.role == 'SUPER_ADMIN' else user.entity.name,
        'initiatives_total': len(initiatives),
        'estimated_total': estimated_total,
        'status_counts': _status_counts(query),
        'risks': _risk_items(query),
        'critical': _critical_portfolio(query),
        'recent_initiatives': initiatives[:8],
        'top_initiatives': sorted(initiatives, key=lambda item: item.estimated_cost or 0, reverse=True)[:5],
        'recent_audit': _recent_audit(initiatives),
        'funding_total': funding_total,
        'funding_allocated': funding_allocated,
        'funding_available': max(0, funding_total - funding_allocated),
        'sources': sources,
        'users_count': users_count,
        'entities_count': entities_count,
        'entities_active': entities_active,
        'next_action_for': next_action_for,
    }
