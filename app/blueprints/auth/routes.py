from urllib.parse import urlsplit

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.blueprints.auth import auth_bp
from app.models.user import User
from app.services.audit import log_event
from app.utils.account import can_authenticate


def _is_safe_next(target):
    """Permite redirecciones post-login solo dentro del mismo sitio."""
    if not target:
        return False
    ref = urlsplit(request.host_url)
    test = urlsplit(target)
    return not test.netloc or test.netloc == ref.netloc

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Redirigir al dashboard si ya está autenticado
    if current_user.is_authenticated:
        return redirect(url_for('public.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        user = User.objects(email=email).first()
        
        if can_authenticate(user) and user.check_password(password):
            login_user(user)
            log_event(
                actor=user,
                entity=user.entity,
                action='LOGIN',
                target=user,
                target_type='User',
                details='Inicio de sesion exitoso.',
            )
            
            # Actualizar el último acceso
            from datetime import datetime
            user.last_login = datetime.utcnow()
            user.save()
            
            flash(f'¡Bienvenido, {user.first_name}! Has iniciado sesión con éxito.', 'success')
            
            # Redirigir a la página previa o al dashboard principal
            next_page = request.args.get('next')
            if _is_safe_next(next_page):
                return redirect(next_page)
            return redirect(url_for('public.dashboard'))
        else:
            if user:
                log_event(
                    actor=user,
                    entity=user.entity,
                    action='LOGIN_FAILED',
                    target=user,
                    target_type='User',
                    details='Intento de inicio de sesion fallido.',
                )
            flash('Credenciales incorrectas o usuario inactivo. Inténtalo de nuevo.', 'danger')
            
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    log_event(
        actor=current_user,
        entity=current_user.entity,
        action='LOGOUT',
        target=current_user,
        target_type='User',
        details='Cierre de sesion.',
    )
    logout_user()
    flash('Has cerrado sesión correctamente. ¡Que tengas un buen día!', 'success')
    return redirect(url_for('public.landing'))
