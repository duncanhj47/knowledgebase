from webapp.routes.main import bp as main_bp
from webapp.routes.auth import bp as auth_bp
from webapp.routes.resources import bp as kb_bp
from webapp.routes.articles import bp as articles_bp
from webapp.routes.suppliers import bp as suppliers_bp
from webapp.routes.problems import bp as problems_bp

__all__ = ["main_bp", "auth_bp", "kb_bp", "articles_bp", "suppliers_bp", "problems_bp"]
