def has_active_tenant(user):
    if not user:
        return False
    if user.role == 'SUPER_ADMIN':
        return True
    return bool(user.entity and user.entity.is_active and not user.entity.is_deleted)


def can_authenticate(user):
    return bool(user and user.is_active and has_active_tenant(user))
