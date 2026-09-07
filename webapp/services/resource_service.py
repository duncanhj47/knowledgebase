"""Business logic for the knowledge-base resources: submission intake,
moderation, and search. Kept out of routes so it's reusable/testable
independently of the request/response cycle.
"""
import os
import re
import uuid
from datetime import datetime

from flask import current_app
from sqlalchemy import text
from werkzeug.utils import secure_filename

from webapp.extensions import db
from webapp.models import Resource, Category, EngineModel, VehicleModel, Tag
from webapp.services import email_service


# ---------------------------------------------------------------------
# File uploads
# ---------------------------------------------------------------------

def save_upload(file_storage):
    """Save an uploaded file under a randomized name (never trust the
    original filename), return the stored filename."""
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    stored_name = f'{uuid.uuid4().hex}.{ext}'
    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, stored_name))
    return stored_name


# ---------------------------------------------------------------------
# Submission / moderation
# ---------------------------------------------------------------------

def create_submission(form):
    """Build a pending Resource from a validated SubmissionForm."""
    resource = Resource(
        title=form.title.data,
        resource_type=form.resource_type.data,
        description=form.description.data or None,
        category_id=form.category.data or None,
        status='pending',
        submitted_by_name=form.submitted_by_name.data or None,
        submitted_by_contact=form.submitted_by_contact.data or None,
        created_at=datetime.utcnow(),
    )

    if form.resource_type.data in ('video', 'url'):
        resource.url = form.url.data
    elif form.resource_type.data == 'photo':
        if form.file.data:
            resource.file_path = save_upload(form.file.data)
        else:
            resource.url = form.url.data
    elif form.resource_type.data == 'file':
        resource.file_path = save_upload(form.file.data)
    elif form.resource_type.data == 'text':
        resource.body = form.body.data

    _apply_tags(resource, form)

    db.session.add(resource)
    db.session.commit()

    try:
        email_service.notify_new_submission(resource)
    except Exception as exc:  # belt and suspenders - email_service already catches internally
        print(f'[email] unexpected error notifying of submission: {exc}')

    return resource


def update_resource(resource, form):
    """Apply admin edits to metadata and content fields, re-index if live."""
    resource.title = form.title.data
    resource.description = form.description.data or None
    resource.category_id = form.category.data or None
    _apply_tags(resource, form)
    # Content fields — only update if the field is relevant to this resource type
    if resource.resource_type in ('video', 'url', 'photo') and form.url.data:
        resource.url = form.url.data.strip()
    if resource.resource_type == 'text' and form.body.data is not None:
        resource.body = form.body.data
    db.session.commit()
    if resource.status == 'approved':
        index_resource(resource)


def _apply_tags(resource, form):
    with db.session.no_autoflush:
        resource.engine_models = (
            EngineModel.query.filter(EngineModel.id.in_(form.engine_models.data)).all()
            if form.engine_models.data else []
        )
        resource.vehicle_models = (
            VehicleModel.query.filter(VehicleModel.id.in_(form.vehicle_models.data)).all()
            if form.vehicle_models.data else []
        )
        # Freeform type-tags (Wiring Diagram, FAQ, etc.) are only ever set by
        # an admin during moderation - SubmissionForm has no 'tags' field,
        # so this is a no-op for public submissions.
        if hasattr(form, 'tags'):
            resource.tags = get_or_create_tags(form.tags.data)


def get_or_create_tags(tag_names_str):
    """Parse a comma-separated string of tag names into Tag rows,
    creating any that don't already exist yet. Matching is
    case-insensitive so 'faq' and 'FAQ' don't become two tags."""
    if not tag_names_str:
        return []
    names = [n.strip() for n in tag_names_str.split(',') if n.strip()]

    seen = {}
    for n in names:
        key = n.lower()
        if key not in seen:
            seen[key] = n

    tags = []
    for key, display_name in seen.items():
        tag = Tag.query.filter(db.func.lower(Tag.name) == key).first()
        if not tag:
            tag = Tag(name=display_name)
            db.session.add(tag)
            db.session.flush()  # assigns tag.id without a full commit
        tags.append(tag)
    return tags


def get_pending():
    return Resource.query.filter_by(status='pending').order_by(Resource.created_at.asc()).all()


def approve_resource(resource, reviewer):
    resource.status = 'approved'
    resource.reviewed_by = reviewer
    resource.reviewed_at = datetime.utcnow()
    db.session.commit()
    index_resource(resource)
    return resource


def reject_resource(resource, reviewer, notes=None):
    resource.status = 'rejected'
    resource.reviewed_by = reviewer
    resource.reviewed_at = datetime.utcnow()
    if notes:
        resource.admin_notes = notes
    db.session.commit()
    remove_from_index(resource)
    return resource


def delete_resource(resource):
    """Permanently remove a resource: its uploaded file (if any), its
    search index entry, and the database row itself."""
    if resource.file_path:
        upload_dir = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_dir, resource.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    remove_from_index(resource)
    db.session.delete(resource)
    db.session.commit()


# ---------------------------------------------------------------------
# Search (SQLite FTS5)
# ---------------------------------------------------------------------

def ensure_search_index():
    db.session.execute(text(
        "CREATE VIRTUAL TABLE IF NOT EXISTS resources_fts "
        "USING fts5(resource_id UNINDEXED, title, body, tags, tokenize='porter')"
    ))
    db.session.commit()


def _tag_text(resource):
    parts = [e.code for e in resource.engine_models] + [v.code for v in resource.vehicle_models]
    parts += [t.name for t in resource.tags]
    if resource.category:
        parts.append(resource.category.name)
    return ' '.join(parts)


def index_resource(resource):
    db.session.execute(text("DELETE FROM resources_fts WHERE resource_id = :rid"), {'rid': resource.id})
    db.session.execute(
        text("INSERT INTO resources_fts (resource_id, title, body, tags) VALUES (:rid, :title, :body, :tags)"),
        {
            'rid': resource.id,
            'title': resource.title,
            'body': resource.description or resource.body or '',
            'tags': _tag_text(resource),
        },
    )
    db.session.commit()


def remove_from_index(resource):
    db.session.execute(text("DELETE FROM resources_fts WHERE resource_id = :rid"), {'rid': resource.id})
    db.session.commit()


def _sanitize_fts_query(query):
    """Turn free text into a safe FTS5 prefix query: each word becomes a
    prefix term, ANDed together. Strips characters that would otherwise
    be interpreted as FTS5 query syntax."""
    terms = re.findall(r'\w+', query)
    return ' '.join(f'{t}*' for t in terms)


def search_resources(query, engine_ids=None, vehicle_ids=None):
    """Kept as an alias for callers that only care about text search."""
    return browse_resources(query=query, engine_ids=engine_ids, vehicle_ids=vehicle_ids)


def _fts_ids(query):
    """Resource ids matching an FTS5 query, in rank order. None means
    'no text filter requested' (as opposed to an empty result list)."""
    if not query:
        return None
    safe_query = _sanitize_fts_query(query)
    if not safe_query:
        return []
    rows = db.session.execute(
        text("SELECT resource_id FROM resources_fts WHERE resources_fts MATCH :q ORDER BY rank"),
        {'q': safe_query},
    ).fetchall()
    return [row[0] for row in rows]


def browse_resources(query=None, engine_ids=None, vehicle_ids=None, tag_ids=None, show_all=False):
    """Approved resources matching an optional text query and optional
    engine/vehicle/type-tag filters. Multiple ids within one facet are
    OR'd together (any match); different facets are AND'd.

    Deliberately returns nothing when no query or filter is given and
    show_all isn't set - with a large archive, browsing shouldn't
    default to "load everything". show_all=True is an explicit opt-in
    (the "See all resources" button), not the default path.
    """
    if not query and not engine_ids and not vehicle_ids and not tag_ids and not show_all:
        return []

    q = Resource.query.filter_by(status='approved')

    fts_ids = _fts_ids(query)
    if fts_ids is not None:
        if not fts_ids:
            return []
        q = q.filter(Resource.id.in_(fts_ids))

    if engine_ids:
        q = q.filter(Resource.engine_models.any(EngineModel.id.in_(engine_ids)))
    if vehicle_ids:
        q = q.filter(Resource.vehicle_models.any(VehicleModel.id.in_(vehicle_ids)))
    if tag_ids:
        q = q.filter(Resource.tags.any(Tag.id.in_(tag_ids)))

    resources = q.order_by(Resource.created_at.desc()).all()

    if fts_ids is not None:
        order = {rid: i for i, rid in enumerate(fts_ids)}
        resources.sort(key=lambda r: order.get(r.id, len(fts_ids)))

    return resources


RESOURCE_TYPE_GROUPS = [
    ('video', '🎬 Videos'),
    ('file', '📄 Manuals & files'),
    ('photo', '📷 Photos'),
    ('text', '📝 Write-ups'),
    ('url', '🔗 Links'),
]


def group_by_type(resources):
    """Split a resource list into (label, items) sections in a fixed,
    sensible display order, skipping empty sections."""
    groups = []
    for type_key, label in RESOURCE_TYPE_GROUPS:
        items = [r for r in resources if r.resource_type == type_key]
        if items:
            groups.append((label, items))
    return groups


def suggest_titles(query, limit=8):
    """Lightweight title matches for search-as-you-type - not the full
    browse_resources pipeline, just id/title/type for a fast dropdown."""
    safe_query = _sanitize_fts_query(query)
    if not safe_query:
        return []

    rows = db.session.execute(
        text("SELECT resource_id FROM resources_fts WHERE resources_fts MATCH :q ORDER BY rank LIMIT :lim"),
        {'q': safe_query, 'lim': limit},
    ).fetchall()
    ids = [row[0] for row in rows]
    if not ids:
        return []

    resources = Resource.query.filter(Resource.id.in_(ids), Resource.status == 'approved').all()
    order = {rid: i for i, rid in enumerate(ids)}
    resources.sort(key=lambda r: order.get(r.id, len(ids)))
    return resources


def recent_resources(limit=6):
    """A small, fixed-size slice for the homepage 'recently added' panel.
    Deliberately separate from browse_resources - this is a bounded,
    cheap query regardless of archive size, not a full unfiltered load."""
    return (
        Resource.query.filter_by(status='approved')
        .order_by(Resource.created_at.desc())
        .limit(limit)
        .all()
    )


def all_tags():
    return Tag.query.order_by(Tag.name).all()


# ---------------------------------------------------------------------
# Seed data - runs once, only if the relevant table is empty
# ---------------------------------------------------------------------

def _slugify(value):
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')


# ---------------------------------------------------------------------
# Taxonomy management (admin) - engine models, vehicle models
# ---------------------------------------------------------------------

def add_engine_model(code, family=None):
    engine = EngineModel(code=code.strip(), family=(family or '').strip() or None)
    db.session.add(engine)
    db.session.commit()
    return engine


def add_vehicle_model(code, family=None):
    vehicle = VehicleModel(code=code.strip(), chassis_family=(family or '').strip() or None)
    db.session.add(vehicle)
    db.session.commit()
    return vehicle


def delete_engine_model(engine):
    # Tag text is baked into the search index, so re-index anything that
    # was tagged with this engine before the association rows disappear.
    affected = [r for r in engine.resources if r.status == 'approved']
    engine.resources = []
    db.session.delete(engine)
    db.session.commit()
    for resource in affected:
        index_resource(resource)


def delete_vehicle_model(vehicle):
    affected = [r for r in vehicle.resources if r.status == 'approved']
    vehicle.resources = []
    db.session.delete(vehicle)
    db.session.commit()
    for resource in affected:
        index_resource(resource)


def seed_defaults():
    if Category.query.count() == 0:
        for name in [
            'Factory Manual', 'How-To Guide', 'Troubleshooting',
            'Torque Spec', 'Reference Photos', 'Video', 'Parts Reference',
        ]:
            db.session.add(Category(name=name, slug=_slugify(name)))

    if EngineModel.query.count() == 0:
        for code, family in [
            ('2H', 'H series'), ('12HT', 'H series'), ('H', 'H series'),
            ('B', 'B series'), ('2B', 'B series'), ('3B', 'B series'),
            ('L', 'L series'), ('2L', 'L series'), ('2LT', 'L series'),
            ('1C', 'C series'), ('2C', 'C series'),
        ]:
            db.session.add(EngineModel(code=code, family=family))

    if VehicleModel.query.count() == 0:
        for code, family in [
            ('HJ45', '40 Series'), ('HJ47', '40 Series'),
            ('HJ60', '60 Series'), ('HJ61', '60 Series'),
            ('HJ75', '70 Series'),
        ]:
            db.session.add(VehicleModel(code=code, chassis_family=family))

    db.session.commit()
