from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, PasswordField, SubmitField, RadioField, SelectField,
    SelectMultipleField, TextAreaField, HiddenField,
)
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from webapp.models import User, Category, EngineModel, VehicleModel

UPLOAD_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx']


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    password2 = PasswordField(
        'Repeat Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match.')]
    )
    submit = SubmitField('Register')

    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError('That username is already taken.')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')


def _tag_choices(form):
    """Populate the dynamic dropdown choices that need a DB query -
    can't be set at class-definition time since there's no app context."""
    form.category.choices = [(0, '\u2014 none \u2014')] + [
        (c.id, c.name) for c in Category.query.order_by(Category.name)
    ]
    form.engine_models.choices = [(e.id, e.code) for e in EngineModel.query.order_by(EngineModel.code)]
    form.vehicle_models.choices = [(v.id, v.code) for v in VehicleModel.query.order_by(VehicleModel.code)]


class SubmissionForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    resource_type = RadioField(
        'Type',
        choices=[
            ('video', 'Video'),
            ('photo', 'Photo'),
            ('text', 'Write-up'),
            ('url', 'Link'),
            ('file', 'File (PDF etc.)'),
        ],
        validators=[DataRequired()],
    )
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    url = StringField('URL', validators=[Optional(), Length(max=500)])
    file = FileField('File', validators=[FileAllowed(UPLOAD_EXTENSIONS, 'Unsupported file type.')])
    body = TextAreaField('Write-up content', validators=[Optional()])
    category = SelectField('Category', coerce=int, validators=[Optional()])
    engine_models = SelectMultipleField('Engine model(s)', coerce=int, validators=[Optional()])
    vehicle_models = SelectMultipleField('Vehicle model(s)', coerce=int, validators=[Optional()])
    submitted_by_name = StringField('Your name (optional)', validators=[Optional(), Length(max=120)])
    submitted_by_contact = StringField('Contact (optional)', validators=[Optional(), Length(max=200)])
    submit = SubmitField('Submit for review')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _tag_choices(self)

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        rt = self.resource_type.data
        ok = True
        if rt in ('video', 'url') and not self.url.data:
            self.url.errors.append('A URL is required for this type.')
            ok = False
        elif rt == 'file' and not self.file.data:
            self.file.errors.append('A file is required for this type.')
            ok = False
        elif rt == 'text' and not self.body.data:
            self.body.errors.append('Write-up content is required for this type.')
            ok = False
        elif rt == 'photo' and not self.file.data and not self.url.data:
            self.url.errors.append('Provide a photo file, or a link (e.g. Google Photos album).')
            ok = False
        return ok


class ResourceReviewForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    category = SelectField('Category', coerce=int, validators=[Optional()])
    engine_models = SelectMultipleField('Engine model(s)', coerce=int, validators=[Optional()])
    vehicle_models = SelectMultipleField('Vehicle model(s)', coerce=int, validators=[Optional()])
    tags = StringField('Type tags (comma-separated - e.g. Wiring Diagram, FAQ)', validators=[Optional(), Length(max=300)])
    # Content fields — shown conditionally based on resource_type
    url = StringField('URL', validators=[Optional(), Length(max=500)])
    body = TextAreaField('Write-up / text body', validators=[Optional()])
    admin_notes = TextAreaField('Admin notes (private)', validators=[Optional(), Length(max=1000)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _tag_choices(self)


class EngineModelForm(FlaskForm):
    code = StringField('Code', validators=[DataRequired(), Length(max=20)])
    family = StringField('Family', validators=[Optional(), Length(max=40)])
    submit = SubmitField('Add')


class VehicleModelForm(FlaskForm):
    code = StringField('Code', validators=[DataRequired(), Length(max=20)])
    family = StringField('Chassis family', validators=[Optional(), Length(max=40)])
    submit = SubmitField('Add')


class ArticleForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    # Populated by JS from the Quill editor's HTML content just before submit -
    # see the editor-sync script in admin_article_form.html.
    body_html = HiddenField('Body', validators=[DataRequired(message='Article body cannot be empty.')])
    submit = SubmitField('Save')


class SupplierForm(FlaskForm):
    name = StringField('Supplier name', validators=[DataRequired(), Length(max=200)])
    url = StringField('Link (their site, or your affiliate link)', validators=[DataRequired(), Length(max=500)])
    image = FileField('Logo / photo (optional)', validators=[FileAllowed(UPLOAD_EXTENSIONS, 'Unsupported file type.')])
    # Same pattern as ArticleForm.body_html - populated by the Quill editor on submit.
    body_html = HiddenField('Description', validators=[DataRequired(message='Description cannot be empty.')])
    submit = SubmitField('Save')


class ProblemForm(FlaskForm):
    name = StringField('Problem / symptom description', validators=[DataRequired(), Length(max=200)])
    resource_id = SelectField('Links to this resource', coerce=int, validators=[DataRequired()])
    sort_order = StringField('Sort order (lower numbers appear first)', validators=[Optional()])
    submit = SubmitField('Save')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from webapp.models import Resource
        self.resource_id.choices = [
            (r.id, r.title)
            for r in Resource.query.filter_by(status='approved')
                .order_by(Resource.title).all()
        ]
