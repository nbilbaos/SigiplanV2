import os
import posixpath
import uuid
from flask import (
    render_template, redirect, url_for, flash, request, abort,
    current_app, send_from_directory
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.blueprints.formulation import formulation_bp
from app.services.exceptions import ServiceError
from app.services.initiative import InitiativeService
from app.utils.decorators import role_required
from app.utils.tenant import (
    get_tenant_initiative,
    tenant_users,
    visible_tenant_initiatives,
)

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
    return visible_tenant_initiatives()


def _get_initiative(initiative_id):
    return get_tenant_initiative(initiative_id)


def _allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _attachment_directory(init):
    return os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        str(init.entity.id),
        str(init.id),
    )


def _attachment_path(init, filename):
    return posixpath.join(str(init.entity.id), str(init.id), filename)


def _legacy_attachment_path(filename):
    return filename and '/' not in filename and '\\' not in filename


def _stored_attachment_path(init, att):
    stored = (att.file_path or '').replace('\\', '/')
    parts = stored.split('/')
    if any(part in ('', '.', '..') for part in parts):
        abort(404)
    normalized = posixpath.normpath(stored)
    if not normalized or normalized.startswith('../') or normalized.startswith('/'):
        abort(404)
    if _legacy_attachment_path(normalized):
        return normalized

    parts = normalized.split('/')
    if len(parts) < 3 or parts[0] != str(init.entity.id) or parts[1] != str(init.id):
        abort(404)
    return normalized


def _stored_attachment_full_path(init, att):
    stored = _stored_attachment_path(init, att)
    full_path = os.path.abspath(os.path.join(current_app.config['UPLOAD_FOLDER'], stored))
    upload_root = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
    if os.path.commonpath([upload_root, full_path]) != upload_root:
        abort(404)
    return full_path


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
    init = _get_initiative(initiative_id)
    rejection = _last_rejection(init)

    # Solo el coordinador puede asignar formuladores
    formulators = []
    if current_user.role == 'FORMULATION_LEADER':
        formulators = tenant_users(
            role='TECHNICAL_FORMULATOR',
            is_active=True,
        ).order_by('first_name')

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

    try:
        InitiativeService.update_technical(
            init,
            actor=current_user,
            title=title,
            description=description,
            estimated_cost=cost,
        )
    except ServiceError as exc:
        flash(str(exc), 'warning')
        return redirect(url_for('formulation.initiative_work', initiative_id=init.id))
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

    upload_dir = _attachment_directory(init)
    os.makedirs(upload_dir, exist_ok=True)
    full_path = os.path.join(upload_dir, stored)
    file.save(full_path)

    attachment = FileAttachment(
        file_id=file_id,
        name=original,
        file_path=_attachment_path(init, stored),
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
        current_app.config['UPLOAD_FOLDER'],
        _stored_attachment_path(init, att),
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
        full_path = _stored_attachment_full_path(init, att)
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
    init = _get_initiative(initiative_id)
    selected = request.form.getlist('formulators')
    users = list(tenant_users(
        id__in=selected,
        role='TECHNICAL_FORMULATOR',
    )) if selected else []

    InitiativeService.assign_formulators(init, actor=current_user, users=users)
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
    InitiativeService.transition_status(
        init,
        actor=current_user,
        target_status='IN_PROGRESS',
        action='UPDATE',
        details='Formulacion retomada tras las observaciones del revisor.',
        allowed_from=('REJECTED',),
    )
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

    InitiativeService.transition_status(
        init,
        actor=current_user,
        target_status='UNDER_REVIEW',
        action='SUBMIT_FOR_REVIEW',
        details=comment,
        allowed_from=('IN_PROGRESS',),
    )
    flash(f'Iniciativa "{init.code}" enviada a revisión.', 'success')
    return redirect(url_for('formulation.initiative_work', initiative_id=init.id))
