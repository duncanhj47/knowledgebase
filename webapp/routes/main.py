from flask import Blueprint, render_template, url_for

from webapp.services import resource_service, articles_service

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    resources = resource_service.recent_resources(limit=8)
    articles = articles_service.recent_articles(limit=8)

    items = []
    for r in resources:
        items.append({
            'title': r.title,
            'url': url_for('kb.resource_detail', resource_id=r.id),
            'created_at': r.created_at,
            'is_article': False,
            'engine_models': r.engine_models,
            'vehicle_models': r.vehicle_models,
            'tags': r.tags,
        })
    for a in articles:
        items.append({
            'title': a.title,
            'url': url_for('articles.article_detail', article_id=a.id),
            'created_at': a.created_at,
            'is_article': True,
            'engine_models': [],
            'vehicle_models': [],
            'tags': [],
        })
    items.sort(key=lambda x: x['created_at'], reverse=True)
    recent = items[:8]

    return render_template('index.html', recent=recent)
