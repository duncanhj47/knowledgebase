import os

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort,
    jsonify, send_from_directory, current_app,
)
from flask_login import current_user
from wtforms import ValidationError
from flask_wtf.csrf import validate_csrf

from webapp.forms import ArticleForm
from webapp.models import Article
from webapp.routes.utils import admin_required
from webapp.services import articles_service

bp = Blueprint('articles', __name__)


@bp.route('/articles')
def list_articles():
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    pagination = articles_service.list_articles(page=page)
    return render_template('articles_list.html', pagination=pagination)


@bp.route('/articles/<int:article_id>')
def article_detail(article_id):
    article = Article.query.get_or_404(article_id)
    rendered_body = articles_service.render_article_body(article.body_html)
    return render_template('article_detail.html', article=article, rendered_body=rendered_body)


@bp.route('/admin/articles/new', methods=['GET', 'POST'])
@admin_required
def admin_new_article():
    form = ArticleForm()
    if form.validate_on_submit():
        article = articles_service.create_article(form.title.data, form.body_html.data, current_user)
        flash(f'Published: {article.title}', 'success')
        return redirect(url_for('articles.article_detail', article_id=article.id))
    return render_template('admin_article_form.html', form=form, article=None)


@bp.route('/admin/articles/<int:article_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_article(article_id):
    article = Article.query.get_or_404(article_id)
    form = ArticleForm(obj=article)
    if request.method == 'GET':
        form.body_html.data = article.body_html

    if form.validate_on_submit():
        articles_service.update_article(article, form.title.data, form.body_html.data)
        flash(f'Saved: {article.title}', 'success')
        return redirect(url_for('articles.article_detail', article_id=article.id))
    return render_template('admin_article_form.html', form=form, article=article)


@bp.route('/admin/articles/<int:article_id>/delete', methods=['POST'])
@admin_required
def admin_delete_article(article_id):
    article = Article.query.get_or_404(article_id)
    title = article.title
    articles_service.delete_article(article)
    flash(f'Deleted: {title}', 'success')
    return redirect(url_for('articles.list_articles'))


@bp.route('/admin/articles/upload-image', methods=['POST'])
@admin_required
def admin_upload_article_image():
    # This endpoint is called via fetch() from the editor, not a normal
    # form submit, so Flask-WTF's per-form CSRF check never runs against
    # it automatically - validate the token (reused from the article
    # form already on the page) by hand instead.
    try:
        validate_csrf(request.form.get('csrf_token', ''))
    except ValidationError:
        return jsonify({'error': 'Invalid or missing CSRF token.'}), 400

    file = request.files.get('image')
    if not file or file.filename == '':
        return jsonify({'error': 'No image provided.'}), 400

    try:
        filename = articles_service.save_article_image(file)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    return jsonify({'url': url_for('articles.article_image', filename=filename)})


@bp.route('/article-images/<path:filename>')
def article_image(filename):
    # Unlike resource uploads, article images have no approval gate -
    # only an admin can create the article that references them in the
    # first place, so once it exists the image is meant to be public.
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'articles')
    return send_from_directory(folder, filename)
