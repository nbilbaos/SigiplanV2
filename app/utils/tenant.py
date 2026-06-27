from flask import abort
from flask_login import current_user


def current_tenant():
    """Return the entity for the authenticated non-global user."""
    return current_user.entity


def tenant_users(entity=None, **filters):
    from app.models.user import User

    entity = entity or current_tenant()
    return User.objects(entity=entity, **filters)


def tenant_funding_sources(entity=None, **filters):
    from app.models.funding import FundingSource

    entity = entity or current_tenant()
    return FundingSource.objects(entity=entity, **filters)


def tenant_initiatives(entity=None, include_deleted=False, **filters):
    from app.models.initiative import Initiative

    entity = entity or current_tenant()
    query = Initiative.objects(entity=entity, **filters)
    if not include_deleted:
        query = query.filter(is_deleted=False)
    return query


def visible_tenant_initiatives(entity=None, include_deleted=False, user=None, **filters):
    """Return tenant initiatives visible to the user in their current role."""
    user = user or current_user
    user_obj = user._get_current_object() if hasattr(user, '_get_current_object') else user
    query = tenant_initiatives(entity=entity, include_deleted=include_deleted, **filters)
    if user.role == 'TECHNICAL_FORMULATOR':
        query = query.filter(assigned_formulators=user_obj)
    return query


def get_tenant_initiative(initiative_id, include_deleted=False, visible_to_user=True):
    try:
        initiative = tenant_initiatives(
            include_deleted=True,
            id=initiative_id,
        ).first()
    except Exception:
        initiative = None

    if not initiative:
        abort(404)
    if initiative.is_deleted and not include_deleted:
        abort(404)
    if (
        visible_to_user
        and current_user.role == 'TECHNICAL_FORMULATOR'
        and current_user.id not in [f.id for f in initiative.assigned_formulators if f]
    ):
        abort(403)
    return initiative
