from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user, logout_user
from app.utils.account import has_active_tenant

def role_required(*roles):
    """
    Decorador para restringir el acceso a vistas basado en el rol del usuario.
    Ejemplo de uso:
    @planning_bp.route('/funding')
    @login_required
    @role_required('PLANNING_DIRECTOR', 'ENTITY_ADMIN')
    def funding():
        ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))

            if not has_active_tenant(current_user):
                logout_user()
                flash(
                    'La entidad asociada a tu cuenta no está activa. '
                    'Contacta al administrador de la plataforma.',
                    'warning',
                )
                return redirect(url_for('auth.login'))
            
            if current_user.role not in roles:
                flash('No tienes permisos suficientes para acceder a este módulo.', 'warning')
                # Intentar redirigir al panel de inicio o abortar 403
                return redirect(url_for('public.dashboard'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
