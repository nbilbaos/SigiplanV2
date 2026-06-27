from app.services.exceptions import ServiceError


class UserService:
    @staticmethod
    def create_for_entity(*, entity, first_name, last_name, email, role, password, allowed_roles, actor=None):
        from app.models.user import User
        from app.services.audit import log_event

        if role not in allowed_roles:
            raise ServiceError('Rol no permitido para este nivel de administracion.')
        if User.objects(email=email).first():
            raise ServiceError('Ya existe un usuario con ese email.')

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=role,
            entity=entity,
            is_active=True,
        )
        user.set_password(password)
        user.save()
        log_event(
            actor=actor,
            entity=entity,
            action='USER_CREATE',
            target=user,
            target_type='User',
            details=f'Usuario creado: {user.email}.',
        )
        return user

    @staticmethod
    def update_for_entity(
        user,
        *,
        first_name,
        last_name,
        email,
        role,
        password='',
        is_active=True,
        allowed_roles,
        actor=None,
    ):
        from app.models.user import User
        from app.services.audit import log_event

        if role not in allowed_roles:
            raise ServiceError('Rol no permitido para este nivel de administracion.')
        if User.objects(email=email, id__ne=user.id).first():
            raise ServiceError('Ya existe otro usuario con ese email.')

        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.role = role
        user.is_active = is_active
        if password:
            user.set_password(password)
        user.save()
        log_event(
            actor=actor,
            entity=user.entity,
            action='USER_UPDATE',
            target=user,
            target_type='User',
            details=f'Usuario actualizado: {user.email}.',
        )
        return user
