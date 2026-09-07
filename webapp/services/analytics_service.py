"""Server-side visit analytics.

Records one row per page hit into the Visit table. Runs entirely
server-side so ad-blockers can't hide visits. Country/city lookup uses
a local GeoLite2 database (no external API calls). IPs are stored only
as a SHA-256 hash — enough to count rough uniques, not enough to
re-identify anyone.

The GeoLite2 database file is NOT included in the repo (it's 60MB and
requires a free MaxMind account to download). See README for setup.
If the file is missing the middleware still works — country/city are
just left blank.
"""
import hashlib
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

from flask import request
from sqlalchemy import text

from webapp.extensions import db
from webapp.models import Visit

# -----------------------------------------------------------------
# Paths we deliberately don't record — static assets, health checks,
# and the analytics dashboard itself (so your own admin browsing
# doesn't inflate the numbers).
# -----------------------------------------------------------------
_SKIP_PREFIXES = ('/static/', '/favicon', '/uploads/', '/article-images/',
                  '/supplier-images/', '/admin/analytics')
_SKIP_EXTENSIONS = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif',
                    '.webp', '.ico', '.svg', '.woff', '.woff2', '.ttf')

# Search engines whose referrer URLs contain a query string with the
# search term. Format: (domain_substring, query_param_name)
_SEARCH_ENGINES = [
    ('google.', 'q'),
    ('bing.com', 'q'),
    ('duckduckgo.com', 'q'),
    ('yahoo.com', 'p'),
    ('search.yahoo.com', 'p'),
]


def _should_skip(path):
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return True
    if any(path.endswith(e) for e in _SKIP_EXTENSIONS):
        return True
    return False


def _hash_ip(ip):
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


def _parse_referrer(referrer_url):
    """Return (domain, search_term_or_None)."""
    if not referrer_url:
        return None, None
    try:
        parsed = urlparse(referrer_url)
        domain = parsed.netloc.lower().lstrip('www.')
        search_term = None
        for engine, param in _SEARCH_ENGINES:
            if engine in domain:
                qs = parse_qs(parsed.query)
                terms = qs.get(param, [])
                if terms:
                    search_term = terms[0][:300]
                break
        return domain[:200] or None, search_term
    except Exception:
        return None, None


def _geoip_lookup(ip):
    """Return (country, city) using the local GeoLite2 database.
    Returns (None, None) if the database isn't installed yet."""
    from flask import current_app
    db_path = current_app.config.get('GEOIP_DB_PATH', '')
    if not db_path or not os.path.exists(db_path):
        return None, None
    try:
        import geoip2.database
        with geoip2.database.Reader(db_path) as reader:
            resp = reader.city(ip)
            country = resp.country.name
            city = resp.city.name
            return country, city
    except Exception:
        return None, None


def _parse_user_agent(ua_string):
    """Return (device_type, browser, os)."""
    if not ua_string:
        return 'unknown', 'unknown', 'unknown'
    try:
        from user_agents import parse as ua_parse
        ua = ua_parse(ua_string)
        if ua.is_bot:
            device_type = 'bot'
        elif ua.is_mobile:
            device_type = 'mobile'
        elif ua.is_tablet:
            device_type = 'tablet'
        else:
            device_type = 'desktop'
        browser = (ua.browser.family or 'unknown')[:60]
        os_name = (ua.os.family or 'unknown')[:60]
        return device_type, browser, os_name
    except Exception:
        return 'unknown', 'unknown', 'unknown'


def record_visit():
    """Flask after_request / before_request hook — call from app factory."""
    try:
        path = request.path
        if _should_skip(path):
            return

        # Only record successful page loads (2xx, some 3xx)
        # This is called before we have a response in before_request,
        # so we record speculatively; non-200s are rare for page hits.

        ip = (request.headers.get('X-Forwarded-For', '') or '').split(',')[0].strip() \
             or request.remote_addr

        referrer = request.referrer or ''
        referrer_domain, search_term = _parse_referrer(referrer)
        device_type, browser, os_name = _parse_user_agent(request.headers.get('User-Agent', ''))
        country, city = _geoip_lookup(ip)

        visit = Visit(
            ts=datetime.utcnow(),
            path=path[:500],
            referrer=referrer[:500] or None,
            referrer_domain=referrer_domain,
            search_term=search_term,
            ip_hash=_hash_ip(ip),
            country=country,
            city=city,
            device_type=device_type,
            browser=browser,
            os=os_name,
        )
        db.session.add(visit)
        db.session.commit()
    except Exception as exc:
        # Never let analytics break the actual page load
        db.session.rollback()
        print(f'[analytics] failed to record visit: {exc}', file=sys.stderr)


# -----------------------------------------------------------------
# Dashboard queries
# -----------------------------------------------------------------

def _date_range(days):
    return datetime.utcnow() - timedelta(days=days)


def summary(days=30):
    since = _date_range(days)
    total = Visit.query.filter(Visit.ts >= since, Visit.device_type != 'bot').count()
    uniques = db.session.execute(
        text("SELECT COUNT(DISTINCT ip_hash) FROM visit WHERE ts >= :since AND device_type != 'bot'"),
        {'since': since}
    ).scalar() or 0
    bots = Visit.query.filter(Visit.ts >= since, Visit.device_type == 'bot').count()
    return {'total': total, 'uniques': uniques, 'bots': bots}


def top_pages(days=30, limit=20):
    since = _date_range(days)
    rows = db.session.execute(text("""
        SELECT path, COUNT(*) as hits
        FROM visit
        WHERE ts >= :since AND device_type != 'bot'
        GROUP BY path
        ORDER BY hits DESC
        LIMIT :limit
    """), {'since': since, 'limit': limit}).fetchall()
    return rows


def top_referrers(days=30, limit=20):
    since = _date_range(days)
    rows = db.session.execute(text("""
        SELECT referrer_domain, COUNT(*) as hits
        FROM visit
        WHERE ts >= :since AND device_type != 'bot'
          AND referrer_domain IS NOT NULL AND referrer_domain != ''
        GROUP BY referrer_domain
        ORDER BY hits DESC
        LIMIT :limit
    """), {'since': since, 'limit': limit}).fetchall()
    return rows


def top_countries(days=30, limit=20):
    since = _date_range(days)
    rows = db.session.execute(text("""
        SELECT country, COUNT(*) as hits
        FROM visit
        WHERE ts >= :since AND device_type != 'bot'
          AND country IS NOT NULL AND country != ''
        GROUP BY country
        ORDER BY hits DESC
        LIMIT :limit
    """), {'since': since, 'limit': limit}).fetchall()
    return rows


def top_search_terms(days=30, limit=20):
    since = _date_range(days)
    rows = db.session.execute(text("""
        SELECT search_term, COUNT(*) as hits
        FROM visit
        WHERE ts >= :since AND device_type != 'bot'
          AND search_term IS NOT NULL AND search_term != ''
        GROUP BY search_term
        ORDER BY hits DESC
        LIMIT :limit
    """), {'since': since, 'limit': limit}).fetchall()
    return rows


def device_breakdown(days=30):
    since = _date_range(days)
    rows = db.session.execute(text("""
        SELECT device_type, COUNT(*) as hits
        FROM visit
        WHERE ts >= :since AND device_type != 'bot'
        GROUP BY device_type
        ORDER BY hits DESC
    """), {'since': since}).fetchall()
    return rows


def hits_by_day(days=30):
    since = _date_range(days)
    rows = db.session.execute(text("""
        SELECT DATE(ts) as day, COUNT(*) as hits
        FROM visit
        WHERE ts >= :since AND device_type != 'bot'
        GROUP BY DATE(ts)
        ORDER BY day ASC
    """), {'since': since}).fetchall()
    return rows


def top_browsers(days=30, limit=10):
    since = _date_range(days)
    rows = db.session.execute(text("""
        SELECT browser, COUNT(*) as hits
        FROM visit
        WHERE ts >= :since AND device_type != 'bot'
          AND browser IS NOT NULL AND browser != ''
        GROUP BY browser
        ORDER BY hits DESC
        LIMIT :limit
    """), {'since': since, 'limit': limit}).fetchall()
    return rows
