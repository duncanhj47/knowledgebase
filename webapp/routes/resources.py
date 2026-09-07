from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    abort, send_from_directory, current_app, jsonify,
)
from flask_login import login_required, current_user

from webapp.extensions import db
from webapp.forms import SubmissionForm, ResourceReviewForm, EngineModelForm, VehicleModelForm
from webapp.models import Resource, EngineModel, VehicleModel, Problem
from webapp.routes.utils import admin_required
from webapp.services import resource_service, email_service

bp = Blueprint('kb', __name__)


# ---------------------------------------------------------------------
# Public: browse, search, view, submit
# ---------------------------------------------------------------------

@bp.route('/library')
def library():
    query = request.args.get('q', '').strip()
    engine_ids = [int(v) for v in request.args.getlist('engine') if v.isdigit()]
    vehicle_ids = [int(v) for v in request.args.getlist('vehicle') if v.isdigit()]
    tag_ids = [int(v) for v in request.args.getlist('type') if v.isdigit()]
    show_all = request.args.get('all') == '1'

    resources = resource_service.browse_resources(
        query=query, engine_ids=engine_ids, vehicle_ids=vehicle_ids, tag_ids=tag_ids, show_all=show_all
    )
    groups = resource_service.group_by_type(resources)

    return render_template(
        'library.html',
        groups=groups,
        total=len(resources),
        query=query,
        show_all=show_all,
        engine_models=EngineModel.query.order_by(EngineModel.code).all(),
        vehicle_models=VehicleModel.query.order_by(VehicleModel.code).all(),
        all_tags=resource_service.all_tags(),
        problems=Problem.query.order_by(Problem.sort_order, Problem.name).all(),
        selected_engines=engine_ids,
        selected_vehicles=vehicle_ids,
        selected_tags=tag_ids,
    )


@bp.route('/library/suggest')
def library_suggest():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    results = resource_service.suggest_titles(query, limit=8)
    return jsonify([
        {'id': r.id, 'title': r.title, 'type': r.resource_type}
        for r in results
    ])


@bp.route('/library/<int:resource_id>')
def resource_detail(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    is_admin_viewer = current_user.is_authenticated and current_user.is_admin
    if resource.status != 'approved' and not is_admin_viewer:
        abort(404)
    return render_template('resource_detail.html', resource=resource)


@bp.route('/library/<int:resource_id>/report', methods=['POST'])
def report_broken_link(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    if resource.status != 'approved':
        abort(404)

    note = request.form.get('note', '').strip()[:500] or None
    try:
        email_service.notify_broken_link(resource, note=note)
    except Exception as exc:
        print(f'[email] unexpected error notifying of broken link: {exc}')

    flash('Thanks - flagged for a look.', 'success')
    return redirect(url_for('kb.resource_detail', resource_id=resource_id))


@bp.route('/submit', methods=['GET', 'POST'])
def submit():
    form = SubmissionForm()
    if form.validate_on_submit():
        resource_service.create_submission(form)
        flash('Thanks - your submission is queued for review.', 'success')
        return redirect(url_for('kb.submit'))
    return render_template('submit.html', form=form)


@bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    resource = Resource.query.filter_by(file_path=filename).first_or_404()
    is_admin_viewer = current_user.is_authenticated and current_user.is_admin
    if resource.status != 'approved' and not is_admin_viewer:
        abort(404)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


# ---------------------------------------------------------------------
# Admin: moderation queue
# ---------------------------------------------------------------------

@bp.route('/admin/queue')
@admin_required
def admin_queue():
    pending = resource_service.get_pending()
    return render_template('admin_queue.html', pending=pending)


@bp.route('/admin/resource/<int:resource_id>', methods=['GET', 'POST'])
@admin_required
def admin_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    form = ResourceReviewForm(obj=resource)

    if request.method == 'GET':
        form.category.data = resource.category_id or 0
        form.engine_models.data = [e.id for e in resource.engine_models]
        form.vehicle_models.data = [v.id for v in resource.vehicle_models]
        form.tags.data = ', '.join(t.name for t in resource.tags)
        form.url.data = resource.url or ''
        form.body.data = resource.body or ''

    if form.validate_on_submit():
        action = request.form.get('action')
        resource_service.update_resource(resource, form)

        if action == 'approve':
            resource_service.approve_resource(resource, current_user)
            flash(f'Approved: {resource.title}', 'success')
        elif action == 'reject':
            resource_service.reject_resource(resource, current_user, notes=form.admin_notes.data)
            flash(f'Rejected: {resource.title}', 'success')
        else:
            flash('Changes saved.', 'success')
        return redirect(url_for('kb.admin_queue'))

    return render_template('admin_resource.html', form=form, resource=resource, all_tags=resource_service.all_tags())


@bp.route('/admin/resource/<int:resource_id>/delete', methods=['POST'])
@admin_required
def admin_delete_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    title = resource.title
    resource_service.delete_resource(resource)
    flash(f'Deleted: {title}', 'success')
    return redirect(url_for('kb.admin_queue'))


@bp.route('/admin/taxonomy')
@admin_required
def admin_taxonomy():
    return render_template(
        'admin_taxonomy.html',
        engine_form=EngineModelForm(),
        vehicle_form=VehicleModelForm(),
        engines=EngineModel.query.order_by(EngineModel.code).all(),
        vehicles=VehicleModel.query.order_by(VehicleModel.code).all(),
    )


@bp.route('/admin/taxonomy/engines', methods=['POST'])
@admin_required
def admin_add_engine():
    form = EngineModelForm()
    if form.validate_on_submit():
        if EngineModel.query.filter_by(code=form.code.data.strip()).first():
            flash(f'"{form.code.data}" already exists.', 'error')
        else:
            resource_service.add_engine_model(form.code.data, form.family.data)
            flash(f'Added engine model "{form.code.data}".', 'success')
    else:
        flash('Could not add engine model - a code is required.', 'error')
    return redirect(url_for('kb.admin_taxonomy'))


@bp.route('/admin/taxonomy/engines/<int:engine_id>/delete', methods=['POST'])
@admin_required
def admin_delete_engine(engine_id):
    engine = EngineModel.query.get_or_404(engine_id)
    code = engine.code
    resource_service.delete_engine_model(engine)
    flash(f'Removed engine model "{code}".', 'success')
    return redirect(url_for('kb.admin_taxonomy'))


@bp.route('/admin/taxonomy/vehicles', methods=['POST'])
@admin_required
def admin_add_vehicle():
    form = VehicleModelForm()
    if form.validate_on_submit():
        if VehicleModel.query.filter_by(code=form.code.data.strip()).first():
            flash(f'"{form.code.data}" already exists.', 'error')
        else:
            resource_service.add_vehicle_model(form.code.data, form.family.data)
            flash(f'Added vehicle model "{form.code.data}".', 'success')
    else:
        flash('Could not add vehicle model - a code is required.', 'error')
    return redirect(url_for('kb.admin_taxonomy'))


@bp.route('/admin/taxonomy/vehicles/<int:vehicle_id>/delete', methods=['POST'])
@admin_required
def admin_delete_vehicle(vehicle_id):
    vehicle = VehicleModel.query.get_or_404(vehicle_id)
    code = vehicle.code
    resource_service.delete_vehicle_model(vehicle)
    flash(f'Removed vehicle model "{code}".', 'success')
    return redirect(url_for('kb.admin_taxonomy'))
