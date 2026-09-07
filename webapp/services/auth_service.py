"""Account creation and authentication logic.

Kept out of routes.py so the request/response layer stays thin, and so
this logic is reusable from a CLI command, a test, or an admin script
later without dragging Flask request objects along.
"""
from webapp.extensions import db
from webapp.models import User


def register_user(username, password):
    """Create and persist a new user.

    Assumes the caller (a validated WTForms form) has already confirmed
    the username is free and the two password fields matched.
    """
    is_first_user = User.query.count() == 0
    user = User(username=username, is_admin=is_first_user)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(username, password):
    """Return the matching User if credentials are valid, else None."""
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return None
    return user
