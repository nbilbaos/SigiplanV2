from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from app.blueprints.public import public_bp
from app.utils.executive import build_executive_context

@public_bp.route('/')
def landing():
    # Si el usuario ya inició sesión, redirigir directamente al dashboard interno
    if current_user.is_authenticated:
        return redirect(url_for('public.dashboard'))
    return render_template('public/landing.html')

@public_bp.route('/dashboard')
@login_required
def dashboard():
    metrics = build_executive_context(current_user)
    return render_template('public/dashboard.html', metrics=metrics)


# ─── Perfil del usuario ───────────────────────────────────────────────────────

@public_bp.route('/profile')
@login_required
def profile():
    return render_template('public/profile.html')


@public_bp.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    first_name = request.form.get('first_name', '').strip()
    last_name  = request.form.get('last_name', '').strip()

    errors = []
    if not first_name: errors.append('El nombre es obligatorio.')
    if not last_name:  errors.append('El apellido es obligatorio.')

    if errors:
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('public.profile'))

    user = current_user._get_current_object()
    user.first_name = first_name
    user.last_name  = last_name
    user.save()
    flash('Datos personales actualizados correctamente.', 'success')
    return redirect(url_for('public.profile'))


@public_bp.route('/profile/password', methods=['POST'])
@login_required
def profile_password():
    current  = request.form.get('current_password', '')
    new      = request.form.get('new_password', '')
    confirm  = request.form.get('confirm_password', '')

    user = current_user._get_current_object()

    errors = []
    if not user.check_password(current):
        errors.append('La contraseña actual no es correcta.')
    if len(new) < 8:
        errors.append('La nueva contraseña debe tener al menos 8 caracteres.')
    if new != confirm:
        errors.append('La confirmación no coincide con la nueva contraseña.')
    if current and new and current == new:
        errors.append('La nueva contraseña debe ser distinta de la actual.')

    if errors:
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('public.profile'))

    user.set_password(new)
    user.save()
    flash('Contraseña actualizada correctamente.', 'success')
    return redirect(url_for('public.profile'))
