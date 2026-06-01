import os
import uuid
from flask import (
    render_template, redirect, url_for, flash, request, abort,
    current_app, send_from_directory
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.blueprints.formulation import formulation_bp
from app.utils.decorators import role_required

# Roles que trabajan en la formulación técnica
WORK_ROLES = ['FORMULATION_LEADER', 'TECHNICAL_FORMULATOR']

# Estados en los que la ficha técnica es editable y admite adjuntos
EDITABLE_STATUSES = ('DRAFT', 'IN_PROGRESS', 'REJECTED')

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv',
    'png', 'jpg', 'jpeg', 'gif', 'txt', 'ppt', 'pptx', 'zip',
}

STATUS_ORDER = ['REJECTED', 'IN_PROGRESS', 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'ARCHIVED']
STATUS_LABELS = {
    'DRAFT': 'Borrador',
    'IN_PROGRESS': 'En Formulación',
    'UNDER_REVIEW': 'En Revisión',
    'APPROVED': 'Aprobada',
    'REJECTED': 'Devuelta con Observaciones',
    'ARCHIVED': 'Archivada',
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _visible_query():
    """El Coordinador ve todas las iniciativas de la entidad; el Formulador, solo las asignadas."""
    from app.models.initiative import Initiative
    base = Initiative.objects(entity=current_user.entity, is_deleted=False)
    if current_user.role == 'TECHNICAL_FORMULATOR':
        base = base.filter(assigned_formulators=current_user.id)
    return base


def _get_initiative(initiative_id):
    from app.models.initiative import Initiative
    try:
        init = Initiative.objects(
            id=initiative_id, entity=current_user.entity, is_deleted=False
        ).first()
    except Exception:
        init = None
    if not init:
        abort(404)
    if current_user.role == 'TECHNICAL_FORMULATOR' and current_user.id not in [
        f.id for f in init.assigned_formulators if f
    ]:
        abort(403)
    return init


def _allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _last_rejection(init):
    """Devuelve la última entrada de rechazo de la bitácora, si la hay."""
    rejects = [e for e in init.audit_trail if e.action == 'REJECT']
    if not rejects:
        return None
    return sorted(rejects, key=lambda e: e.timestamp, reverse=True)[0]


# ─── Dashboard / Listado de trabajo ───────────────────────────────────────────

@formulation_bp.route('/')
@login_required
@role_required(*WORK_ROLES)
def index():
    initiatives = list(_visible_query().order_by('-updated_at'))

    metrics = dict(
        total=len(initiatives),
        in_progress=sum(1 for i in initiatives if i.status == 'IN_PROGRESS'),
        under_review=sum(1 for i in initiatives if i.status == 'UNDER_REVIEW'),
        rejected=sum(1 for i in initiatives if i.status == 'REJECTED'),
    )

    # Agrupar por estado en un orden de prioridad de trabajo
    groups = []
    for status in STATUS_ORDER:
        items = [i for i in initiatives if i.status == status]
        if items:
            groups.append((status, STATUS_LABELS[status], items))

    return render_template('formulation/dashboard.html',
                           groups=groups, metrics=metrics,
                           is_leader=current_user.role == 'FORMULATION_LEADER')


# ─── Vista de trabajo de una iniciativa ───────────────────────────────────────

@formulation_bp.route('/initiative/<initiative_id>')
@login_required
@role_required(*WORK_ROLES)
def initiative_work(initiative_id):
    from app.models.user import User

    init = _get_initiative(initiative_id)
    rejection = _last_rejection(init)

    # Solo el coordinador puede asignar formuladores
    formulators = []
    if current_user.role == 'FORMULATION_LEADER':
        formulators = User.objects(
            entity=current_user.entity, role='TECHNICAL_FORMULATOR',
            is_active=True).order_by('first_name')

    assigned_ids = [str(f.id) for f in init.assigned_formulators if f]

    return render_template('formulation/initiative_work.html',
                           init=init,
                           rejection=rejection,
                           editable=init.status in EDITABLE_STATUSES,
                           can_submit=init.status == 'IN_PROGRESS',
                           is_leader=current_user.role == 'FORMULATION_LEADER',
                           formulators=formulators,
                           assigned_ids=assigned_ids,
                           status_labels=STATUS_LABELS)


# ─── Formulación Técnica (editar ficha) ───────────────────────────────────────

@formulation_bp.route('/initiative/<initiative_id>/technical', methods=['POST'])
@login_required
@role_required(*WORK_ROLES)
def edit_technical(initiative_id):
    init = _get_initiative(initiative_id)
    if init.status not in EDITABLE_STATUSES:
        flash('Esta iniciativa no admite cambios en su estado actual.', 'warning')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))

    title       = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    cost_raw    = request.form.get('estimated_cost', '').strip()

    errors = []
    if not title:       errors.append('El título es obligatorio.')
    if not description: errors.append('La descripción es obligatoria.')

    cost = init.estimated_cost
    if cost_raw:
        try:
            cost = float(cost_raw.replace('.', '').replace(',', '.')) \
                if cost_raw.count(',') else float(cost_raw)
        except ValueError:
            errors.append('El costo estimado debe ser un número válido.')

    if errors:
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))

    init.title = title
    init.description = description
    init.estimated_cost = cost
    init.save()
    init.log_action(current_user, 'UPDATE', 'Ficha técnica actualizada.')
    flash('Ficha técnica actualizada correctamente.', 'success')
    return redirect(url_for('formulation.initiative_work', initiative_id=init.id))


# ─── Carga y Gestión de Adjuntos ──────────────────────────────────────────────

@formulation_bp.route('/initiative/<initiative_id>/upload', methods=['POST'])
@login_required
@role_required(*WORK_ROLES)
def upload(initiative_id):
    from app.models.initiative import FileAttachment

    init = _get_initiative(initiative_id)
    if init.status not in EDITABLE_STATUSES:
        flash('No se pueden adjuntar documentos en el estado actual.', 'warning')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))

    file = request.files.get('document')
    if not file or file.filename == '':
        flash('Selecciona un archivo para subir.', 'danger')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))

    if not _allowed_file(file.filename):
        flash('Tipo de archivo no permitido.', 'danger')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))

    original = secure_filename(file.filename)
    file_id  = uuid.uuid4().hex
    stored   = f'{file_id}_{original}'

    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    full_path = os.path.join(upload_dir, stored)
    file.save(full_path)

    attachment = FileAttachment(
        file_id=file_id,
        name=original,
        file_path=stored,
        size_bytes=os.path.getsize(full_path),
        uploaded_by=current_user._get_current_object(),
    )
    init.attachments.append(attachment)
    init.save()
    init.log_action(current_user, 'UPDATE', f'Documento adjuntado: {original}.')
    flash(f'Documento "{original}" cargado correctamente.', 'success')
    return redirect(url_for('formulation.initiative_work', initiative_id=init.id))


@formulation_bp.route('/initiative/<initiative_id>/attachment/<file_id>/download')
@login_required
@role_required(*WORK_ROLES)
def download(initiative_id, file_id):
    init = _get_initiative(initiative_id)
    att = next((a for a in init.attachments if a.file_id == file_id), None)
    if not att:
        abort(404)
    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'], att.file_path,
        as_attachment=True, download_name=att.name)


@formulation_bp.route('/initiative/<initiative_id>/attachment/<file_id>/delete', methods=['POST'])
@login_required
@role_required(*WORK_ROLES)
def attachment_delete(initiative_id, file_id):
    init = _get_initiative(initiative_id)
    if init.status not in EDITABLE_STATUSES:
        flash('No se pueden eliminar documentos en el estado actual.', 'warning')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))

    att = next((a for a in init.attachments if a.file_id == file_id), None)
    if not att:
        abort(404)

    # Borrar el archivo físico (si existe)
    try:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
    except OSError:
        pass

    init.attachments = [a for a in init.attachments if a.file_id != file_id]
    init.save()
    init.log_action(current_user, 'UPDATE', f'Documento eliminado: {att.name}.')
    flash(f'Documento "{att.name}" eliminado.', 'success')
    return redirect(url_for('formulation.initiative_work', initiative_id=init.id))


# ─── Asignar Formuladores (solo Coordinador) ──────────────────────────────────

@formulation_bp.route('/initiative/<initiative_id>/assign', methods=['POST'])
@login_required
@role_required('FORMULATION_LEADER')
def assign_formulators(initiative_id):
    from app.models.user import User

    init = _get_initiative(initiative_id)
    selected = request.form.getlist('formulators')
    users = list(User.objects(
        id__in=selected, entity=current_user.entity,
        role='TECHNICAL_FORMULATOR')) if selected else []

    init.assigned_formulators = users
    init.save()
    names = ', '.join(u.full_name for u in users) if users else 'ninguno'
    init.log_action(current_user, 'UPDATE', f'Formuladores asignados: {names}.')
    flash('Asignación de formuladores actualizada.', 'success')
    return redirect(url_for('formulation.initiative_work', initiative_id=init.id))


# ─── Retomar tras Rechazo (REJECTED → IN_PROGRESS) ────────────────────────────

@formulation_bp.route('/initiative/<initiative_id>/resume', methods=['POST'])
@login_required
@role_required(*WORK_ROLES)
def resume(initiative_id):
    init = _get_initiative(initiative_id)
    if init.status != 'REJECTED':
        flash('Solo se puede retomar una iniciativa devuelta con observaciones.', 'warning')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))
    init.status = 'IN_PROGRESS'
    init.save()
    init.log_action(current_user, 'UPDATE',
                    'Formulación retomada tras las observaciones del revisor.')
    flash('Iniciativa retomada. Aplica las correcciones y vuelve a enviarla a revisión.', 'success')
    return redirect(url_for('formulation.initiative_work', initiative_id=init.id))


# ─── Enviar a Revisión ────────────────────────────────────────────────────────

@formulation_bp.route('/initiative/<initiative_id>/submit', methods=['POST'])
@login_required
@role_required(*WORK_ROLES)
def submit_for_review(initiative_id):
    init = _get_initiative(initiative_id)
    if init.status != 'IN_PROGRESS':
        flash('Solo se pueden enviar a revisión iniciativas En Formulación.', 'warning')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))

    comment = request.form.get('comment', '').strip()
    if not comment:
        flash('Agrega un comentario para el revisor antes de enviar.', 'danger')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))

    init.status = 'UNDER_REVIEW'
    init.save()
    init.log_action(current_user, 'SUBMIT_FOR_REVIEW', comment)
    flash(f'Iniciativa "{init.code}" enviada a revisión.', 'success')
    return redirect(url_for('formulation.initiative_work', initiative_id=init.id))
