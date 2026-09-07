from flask import Flask, flash, redirect, url_for
from config import Config
from webapp.extensions import db, login_manager


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from webapp.models import User  # noqa: F401  registers the user_loader
    from webapp.routes import main_bp, auth_bp, kb_bp, articles_bp, suppliers_bp, problems_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(kb_bp)
    app.register_blueprint(articles_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(problems_bp)

    @app.errorhandler(413)
    def file_too_large(e):
        # The only route that accepts uploads today is /submit, so send
        # people back there with a clear reason rather than showing the
        # default unstyled Werkzeug error page.
        max_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
        flash(f'That file is too large - the limit is {max_mb}MB.', 'error')
        return redirect(url_for('kb.submit'))

    with app.app_context():
        db.create_all()
        from webapp.services.resource_service import ensure_search_index, seed_defaults
        ensure_search_index()
        seed_defaults()

    return app
