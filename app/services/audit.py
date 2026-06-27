from flask import has_request_context, request


def _current_request_meta():
    if not has_request_context():
        return None, None
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    ip_address = forwarded_for.split(',')[0].strip() if forwarded_for else request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    return ip_address, user_agent


def _actor(actor):
    if not actor:
        return None
    return actor._get_current_object() if hasattr(actor, '_get_current_object') else actor


def _entity_for(actor, entity, target):
    if entity:
        return entity
    if target is not None and hasattr(target, 'entity'):
        return target.entity
    actor_obj = _actor(actor)
    return actor_obj.entity if actor_obj and getattr(actor_obj, 'entity', None) else None


def log_event(
    *,
    actor=None,
    entity=None,
    action,
    target=None,
    target_type=None,
    target_id=None,
    details='',
    ip_address=None,
    user_agent=None,
):
    from app.models.log import ActivityLog

    actor_obj = _actor(actor)
    if target is not None:
        target_type = target_type or target.__class__.__name__
        target_id = target_id or str(target.id)

    req_ip, req_user_agent = _current_request_meta()
    event = ActivityLog(
        actor=actor_obj,
        user=actor_obj,
        entity=_entity_for(actor_obj, entity, target),
        target_type=target_type,
        target_id=target_id,
        action=action,
        details=details,
        ip_address=ip_address or req_ip,
        user_agent=user_agent or req_user_agent,
    )
    event.save()
    return event
