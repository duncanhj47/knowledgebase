from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from webapp.extensions import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f'<Category {self.name}>'


class EngineModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)   # e.g. "2H"
    family = db.Column(db.String(40))                              # e.g. "H series"

    def __repr__(self):
        return f'<EngineModel {self.code}>'


class VehicleModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)   # e.g. "HJ60"
    chassis_family = db.Column(db.String(40))                      # e.g. "60 Series"

    def __repr__(self):
        return f'<VehicleModel {self.code}>'


class Tag(db.Model):
    """Freeform resource-type tags - Wiring Diagram, Factory Manual, How To,
    FAQ, etc. Unlike EngineModel/VehicleModel, these aren't pre-managed on
    an admin taxonomy page - they're typed directly during moderation and
    created on the fly if they don't already exist."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)

    def __repr__(self):
        return f'<Tag {self.name}>'


resource_engine_models = db.Table(
    'resource_engine_models',
    db.Column('resource_id', db.Integer, db.ForeignKey('resource.id'), primary_key=True),
    db.Column('engine_model_id', db.Integer, db.ForeignKey('engine_model.id'), primary_key=True),
)

resource_vehicle_models = db.Table(
    'resource_vehicle_models',
    db.Column('resource_id', db.Integer, db.ForeignKey('resource.id'), primary_key=True),
    db.Column('vehicle_model_id', db.Integer, db.ForeignKey('vehicle_model.id'), primary_key=True),
)

resource_tags = db.Table(
    'resource_tags',
    db.Column('resource_id', db.Integer, db.ForeignKey('resource.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True),
)

RESOURCE_TYPES = ('video', 'photo', 'text', 'url', 'file')
RESOURCE_STATUSES = ('pending', 'approved', 'rejected')


class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    resource_type = db.Column(db.String(10), nullable=False)  # see RESOURCE_TYPES
    description = db.Column(db.Text)

    url = db.Column(db.String(500))         # video / url types, or a linked photo album
    file_path = db.Column(db.String(300))   # file / uploaded-photo types (stored filename)
    body = db.Column(db.Text)               # text type - authored write-up content

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    category = db.relationship('Category', backref='resources')

    engine_models = db.relationship('EngineModel', secondary=resource_engine_models, backref='resources')
    vehicle_models = db.relationship('VehicleModel', secondary=resource_vehicle_models, backref='resources')
    tags = db.relationship('Tag', secondary=resource_tags, backref='resources')

    status = db.Column(db.String(10), nullable=False, default='pending')  # see RESOURCE_STATUSES

    submitted_by_name = db.Column(db.String(120))
    submitted_by_contact = db.Column(db.String(200))
    admin_notes = db.Column(db.Text)

    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    reviewed_by = db.relationship('User')
    reviewed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Resource {self.id} {self.title!r}>'


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body_html = db.Column(db.Text, nullable=False)  # sanitized HTML from the rich text editor

    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = db.relationship('User')

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Article {self.id} {self.title!r}>'


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)  # the supplier's link - may be an affiliate URL
    image_filename = db.Column(db.String(300))  # card/logo image, separate from inline body images
    body_html = db.Column(db.Text, nullable=False)  # sanitized HTML from the rich text editor

    added_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    added_by = db.relationship('User')

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Supplier {self.id} {self.name!r}>'


class Problem(db.Model):
    """A named fault/symptom that links directly to one resource.
    Shown as a dropdown on the Browse page so visitors can jump
    straight to the relevant content without searching."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)   # e.g. "Starts then dies when cold"
    sort_order = db.Column(db.Integer, default=0, nullable=False)  # controls list order

    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=False)
    resource = db.relationship('Resource', backref='problems')

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Problem {self.id} {self.name!r}>'
