from flask import Blueprint, render_template, request

from webapp.routes.utils import admin_required
from webapp.services import analytics_service

bp = Blueprint('analytics', __name__)


@bp.route('/admin/analytics')
@admin_required
def dashboard():
    days = request.args.get('days', 30, type=int)
    if days not in (7, 30, 90):
        days = 30

    return render_template('admin_analytics.html',
        days=days,
        summary=analytics_service.summary(days),
        top_pages=analytics_service.top_pages(days),
        top_referrers=analytics_service.top_referrers(days),
        top_countries=analytics_service.top_countries(days),
        top_search_terms=analytics_service.top_search_terms(days),
        device_breakdown=analytics_service.device_breakdown(days),
        hits_by_day=analytics_service.hits_by_day(days),
        top_browsers=analytics_service.top_browsers(days),
    )
