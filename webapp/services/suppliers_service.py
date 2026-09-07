"""Business logic for Preferred Suppliers - nearly identical to
articles_service.py, but each entry also has a link (the supplier's
site, possibly an affiliate URL) and a card/logo image.
"""
import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

from webapp.extensions import db
from webapp.models import Supplier
from webapp.services.articles_service import sanitize_html, IMAGE_EXTENSIONS

PER_PAGE = 20


def _supplier_image_folder():
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'suppliers')
    os.makedirs(folder, exist_ok=True)
    return folder


def save_supplier_image(file_storage):
    filename = secure_filename(file_storage.filename or '')
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in IMAGE_EXTENSIONS:
        raise ValueError('Unsupported image type. Use PNG, JPG, GIF, or WEBP.')

    stored_name = f'{uuid.uuid4().hex}.{ext}'
    file_storage.save(os.path.join(_supplier_image_folder(), stored_name))
    return stored_name


def create_supplier(name, url, body_html, image_file, added_by):
    supplier = Supplier(
        name=name,
        url=url,
        body_html=sanitize_html(body_html),
        added_by=added_by,
    )
    if image_file and image_file.filename:
        supplier.image_filename = save_supplier_image(image_file)

    db.session.add(supplier)
    db.session.commit()
    return supplier


def update_supplier(supplier, name, url, body_html, image_file):
    supplier.name = name
    supplier.url = url
    supplier.body_html = sanitize_html(body_html)
    if image_file and image_file.filename:
        # Remove the old image file so replacing a logo doesn't leak orphaned uploads
        if supplier.image_filename:
            old_path = os.path.join(_supplier_image_folder(), supplier.image_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
        supplier.image_filename = save_supplier_image(image_file)
    db.session.commit()
    return supplier


def delete_supplier(supplier):
    if supplier.image_filename:
        path = os.path.join(_supplier_image_folder(), supplier.image_filename)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(supplier)
    db.session.commit()


def list_suppliers(page=1):
    return Supplier.query.order_by(Supplier.created_at.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )
