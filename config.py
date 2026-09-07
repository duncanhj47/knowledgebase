import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-this-to-something-random'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 250 * 1024 * 1024  # 250 MB

    # Email notifications on new submissions. All of this comes from the
    # environment - nothing sensitive lives in this file. If SMTP_USERNAME,
    # SMTP_PASSWORD, or NOTIFY_EMAIL is unset, notifications are silently
    # skipped rather than breaking submissions for the public.
    SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')      # your Gmail address
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')      # Gmail App Password (not your normal password)
    NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL')        # where submission alerts go (can be the same address)

    # Scheme + host only, e.g. "https://yourdomain.com" - no trailing slash,
    # no /app path. Used to build absolute links (edit link, file downloads)
    # in notification emails, since relative links don't mean anything
    # outside a browser session on the site itself.
    SITE_BASE_URL = os.environ.get('SITE_BASE_URL', '')
