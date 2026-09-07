"""Business logic for the Articles blog: create/update/delete, listing
with pagination, sanitizing editor HTML, embedding YouTube links, and
handling inserted images.
"""
import os
import re
import uuid

import bleach
from flask import current_app
from werkzeug.utils import secure_filename

from webapp.extensions import db
from webapp.models import Article

PER_PAGE = 20

# Deliberately narrow allow-list matching what the editor toolbar exposes
# (bold/italic/underline/links/images) plus the basic structural tags
# Quill produces (paragraphs, line breaks, lists). Anything else in the
# HTML - scripts, styles, iframes, event handlers - gets stripped.
# Note: YouTube embeds are NOT stored as iframes - they're computed at
# render time from plain <a> links (see embed_youtube_links below), so
# the sanitizer never needs to allow iframe at all.
ALLOWED_TAGS = ['p', 'br', 'strong', 'b', 'em', 'i', 'u', 'a', 'ul', 'ol', 'li', 'blockquote', 'img']
ALLOWED_ATTRIBUTES = {'a': ['href', 'title'], 'img': ['src', 'alt']}

IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp']


def sanitize_html(raw_html):
    return bleach.clean(
        raw_html or '',
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )


def create_article(title, body_html, author):
    article = Article(
        title=title,
        body_html=sanitize_html(body_html),
        author=author,
    )
    db.session.add(article)
    db.session.commit()
    return article


def update_article(article, title, body_html):
    article.title = title
    article.body_html = sanitize_html(body_html)
    db.session.commit()
    return article


def delete_article(article):
    db.session.delete(article)
    db.session.commit()


def list_articles(page=1):
    return Article.query.order_by(Article.created_at.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )


# ---------------------------------------------------------------------
# YouTube embeds - computed at render time, not stored. A plain <a> link
# to YouTube (whatever the editor produced) gets a responsive embedded
# player injected right after it. Since this happens on every render
# rather than at save time, changing the embed markup later applies
# retroactively to old articles too.
# ---------------------------------------------------------------------

_YOUTUBE_LINK_RE = re.compile(
    r'<a\s+[^>]*href="https?://(?:www\.)?'
    r'(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)'
    r'([\w-]{11})[^"]*"[^>]*>.*?</a>',
    re.IGNORECASE,
)


def _youtube_embed_html(video_id):
    return (
        '<div class="video-embed">'
        f'<iframe src="https://www.youtube-nocookie.com/embed/{video_id}" '
        'title="YouTube video player" allow="accelerometer; autoplay; clipboard-write; '
        'encrypted-media; gyroscope; picture-in-picture; web-share" '
        'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen loading="lazy"></iframe>'
        '</div>'
    )


def render_article_body(body_html):
    """Sanitized storage HTML -> HTML for display, with a player embedded
    after any YouTube link found in the text."""
    def replace(match):
        return match.group(0) + _youtube_embed_html(match.group(1))
    return _YOUTUBE_LINK_RE.sub(replace, body_html)


# ---------------------------------------------------------------------
# Images inserted into article bodies via the editor's image button.
# Stored separately from resource uploads (which are approval-gated) -
# article images are always public once the article itself exists,
# since only an admin can create an article in the first place.
# ---------------------------------------------------------------------

def _article_image_folder():
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'articles')
    os.makedirs(folder, exist_ok=True)
    return folder


def save_article_image(file_storage):
    filename = secure_filename(file_storage.filename or '')
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in IMAGE_EXTENSIONS:
        raise ValueError('Unsupported image type. Use PNG, JPG, GIF, or WEBP.')

    stored_name = f'{uuid.uuid4().hex}.{ext}'
    file_storage.save(os.path.join(_article_image_folder(), stored_name))
    return stored_name


def recent_articles(limit=6):
    """A small, fixed-size slice for the homepage 'recently added' panel -
    same pattern as resource_service.recent_resources()."""
    return Article.query.order_by(Article.created_at.desc()).limit(limit).all()
