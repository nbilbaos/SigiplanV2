from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.blueprints.auth import auth_bp
from app.models.user import User

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Redirigir al dashboard si ya está autenticado
    if current_user.is_authenticated:
        return redirect(url_for('public.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        user = User.objects(email=email).first()
        
        if user and user.is_active and user.check_password(password):
            login_user(user)
            
            # Actualizar el último acceso
            from datetime import datetime
            user.last_login = datetime.utcnow()
            user.save()
            
            flash(f'¡Bienvenido, {user.first_name}! Has iniciado sesión con éxito.', 'success')
            
            # Redirigir a la página previa o al dashboard principal
            next_page = request.args.get('next')
            return redirect(next_page or url_for('public.dashboard'))
        else:
            flash('Credenciales incorrectas o usuario inactivo. Inténtalo de nuevo.', 'danger')
            
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente. ¡Que tengas un buen día!', 'success')
    return redirect(url_for('public.landing'))
