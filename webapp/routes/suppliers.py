import os

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort,
    jsonify, send_from_directory, current_app,
)
from flask_login import current_user
from wtforms import ValidationError
from flask_wtf.csrf import validate_csrf

from webapp.forms import SupplierForm
from webapp.models import Supplier
from webapp.routes.utils import admin_required
from webapp.services import suppliers_service, articles_service

bp = Blueprint('suppliers', __name__)


@bp.route('/suppliers')
def list_suppliers():
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    pagination = suppliers_service.list_suppliers(page=page)
    return render_template('suppliers_list.html', pagination=pagination)


@bp.route('/suppliers/<int:supplier_id>')
def supplier_detail(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    rendered_body = articles_service.render_article_body(supplier.body_html)
    return render_template('supplier_detail.html', supplier=supplier, rendered_body=rendered_body)


@bp.route('/suppliers/<int:supplier_id>/go')
def supplier_go(supplier_id):
    # Click-through redirect rather than a raw external link - keeps the
    # actual (possibly affiliate) URL in the database, not scattered
    # across rendered HTML, so it's a one-place edit if it ever changes.
    supplier = Supplier.query.get_or_404(supplier_id)
    return redirect(supplier.url)


@bp.route('/admin/suppliers/new', methods=['GET', 'POST'])
@admin_required
def admin_new_supplier():
    form = SupplierForm()
    if form.validate_on_submit():
        supplier = suppliers_service.create_supplier(
            form.name.data, form.url.data, form.body_html.data, form.image.data, current_user
        )
        flash(f'Added: {supplier.name}', 'success')
        return redirect(url_for('suppliers.supplier_detail', supplier_id=supplier.id))
    return render_template('admin_supplier_form.html', form=form, supplier=None)


@bp.route('/admin/suppliers/<int:supplier_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    form = SupplierForm(obj=supplier)
    if request.method == 'GET':
        form.body_html.data = supplier.body_html

    if form.validate_on_submit():
        suppliers_service.update_supplier(
            supplier, form.name.data, form.url.data, form.body_html.data, form.image.data
        )
        flash(f'Saved: {supplier.name}', 'success')
        return redirect(url_for('suppliers.supplier_detail', supplier_id=supplier.id))
    return render_template('admin_supplier_form.html', form=form, supplier=supplier)


@bp.route('/admin/suppliers/<int:supplier_id>/delete', methods=['POST'])
@admin_required
def admin_delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    name = supplier.name
    suppliers_service.delete_supplier(supplier)
    flash(f'Deleted: {name}', 'success')
    return redirect(url_for('suppliers.list_suppliers'))


@bp.route('/admin/suppliers/upload-image', methods=['POST'])
@admin_required
def admin_upload_supplier_image():
    try:
        validate_csrf(request.form.get('csrf_token', ''))
    except ValidationError:
        return jsonify({'error': 'Invalid or missing CSRF token.'}), 400

    file = request.files.get('image')
    if not file or file.filename == '':
        return jsonify({'error': 'No image provided.'}), 400

    try:
        filename = suppliers_service.save_supplier_image(file)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    return jsonify({'url': url_for('suppliers.supplier_image', filename=filename)})


@bp.route('/supplier-images/<path:filename>')
def supplier_image(filename):
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'suppliers')
    return send_from_directory(folder, filename)
