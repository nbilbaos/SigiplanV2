from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from app.blueprints.public import public_bp
from app.models.initiative import Initiative
from app.models.user import User

@public_bp.route('/')
def landing():
    # Si el usuario ya inició sesión, redirigir directamente al dashboard interno
    if current_user.is_authenticated:
        return redirect(url_for('public.dashboard'))
    return render_template('public/landing.html')

@public_bp.route('/dashboard')
@login_required
def dashboard():
    # Obtener métricas y datos rápidos según el rol para el panel
    metrics = {}
    
    if current_user.role == 'SUPER_ADMIN':
        from app.models.entity import Entity
        metrics['entities_count'] = Entity.objects.count()
        metrics['users_count'] = User.objects.count()
        
    elif current_user.role == 'ENTITY_ADMIN':
        metrics['users_count'] = User.objects(entity=current_user.entity).count()
        metrics['initiatives_count'] = Initiative.objects(entity=current_user.entity, is_deleted=False).count()
        metrics['deleted_initiatives_count'] = Initiative.objects(entity=current_user.entity, is_deleted=True).count()
        
    elif current_user.role in ['PLANNING_DIRECTOR', 'FORMULATION_LEADER', 'TECHNICAL_FORMULATOR']:
        # Consultar iniciativas de la entidad que no estén borradas
        base_query = Initiative.objects(entity=current_user.entity, is_deleted=False)
        
        if current_user.role == 'TECHNICAL_FORMULATOR':
            # Formulador solo ve las que tiene asignadas
            base_query = base_query.filter(assigned_formulators=current_user.id)
            
        metrics['initiatives_draft'] = base_query.filter(status='DRAFT').count()
        metrics['initiatives_progress'] = base_query.filter(status='IN_PROGRESS').count()
        metrics['initiatives_review'] = base_query.filter(status='UNDER_REVIEW').count()
        metrics['initiatives_approved'] = base_query.filter(status='APPROVED').count()
        metrics['initiatives_total'] = base_query.count()
        
        # Obtener las últimas iniciativas modificadas para mostrar en tabla rápida
        metrics['recent_initiatives'] = base_query.order_by('-updated_at')[:5]
        
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
