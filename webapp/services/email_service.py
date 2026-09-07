"""New-submission email notifications.

Uses smtplib directly against Gmail's SMTP server (smtp.gmail.com:587,
STARTTLS). All credentials and addresses come from environment variables
via config.py - nothing sensitive lives in this file, so it's safe to
commit/share as-is.

If SMTP isn't configured (SMTP_USERNAME, SMTP_PASSWORD, or NOTIFY_EMAIL
missing), notifications are silently skipped. If sending fails for any
other reason (bad credentials, network issue, Gmail rate limit), the
failure is caught and logged to stderr rather than raised - a broken
mail setup should never prevent a member of the public from submitting
something.
"""
import os
import smtplib
import sys
from email.message import EmailMessage

from flask import current_app, url_for


def _format_size(num_bytes):
    if num_bytes is None:
        return None
    size = float(num_bytes)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024:
            return f'{size:.0f}{unit}' if unit == 'B' else f'{size:.1f}{unit}'
        size /= 1024
    return f'{size:.1f}TB'


def _resource_file_size(resource):
    if not resource.file_path:
        return None
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], resource.file_path)
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _absolute_url(path):
    """Join a relative (already-prefix-correct) path onto the configured
    site base URL. Deliberately not using url_for(..., _external=True)
    here - that depends on proxy headers (X-Forwarded-Proto/Host) being
    perfectly configured to get the scheme/host right, which is fragile.
    An explicit SITE_BASE_URL sidesteps that entirely."""
    base = (current_app.config.get('SITE_BASE_URL') or '').rstrip('/')
    return f'{base}{path}' if base else path


def _content_link(resource):
    if resource.resource_type in ('video', 'url'):
        return resource.url
    if resource.resource_type == 'photo':
        if resource.url:
            return resource.url
        return _absolute_url(url_for('kb.uploaded_file', filename=resource.file_path))
    if resource.resource_type == 'file':
        return _absolute_url(url_for('kb.uploaded_file', filename=resource.file_path))
    return None  # 'text' submissions have no separate content link


def _build_message(resource):
    edit_link = _absolute_url(url_for('kb.admin_resource', resource_id=resource.id))
    content_link = _content_link(resource)
    file_size = _format_size(_resource_file_size(resource))

    lines = [f'Type: {resource.resource_type}']
    if resource.category:
        lines.append(f'Category: {resource.category.name}')
    if resource.engine_models:
        lines.append('Engine: ' + ', '.join(e.code for e in resource.engine_models))
    if resource.vehicle_models:
        lines.append('Vehicle: ' + ', '.join(v.code for v in resource.vehicle_models))
    if resource.description:
        lines.append(f'Description: {resource.description}')
    if resource.resource_type == 'text' and resource.body:
        preview = resource.body if len(resource.body) <= 300 else resource.body[:300] + '...'
        lines.append(f'Write-up preview: {preview}')
    if resource.submitted_by_name:
        lines.append(f'From: {resource.submitted_by_name}')
    if resource.submitted_by_contact:
        lines.append(f'Contact: {resource.submitted_by_contact}')
    if file_size:
        lines.append(f'File size: {file_size}')
    if content_link:
        lines.append('')
        lines.append(f'Content link: {content_link}')
    lines.append('')
    lines.append(f'Review/edit: {edit_link}')

    body = f'New submission: {resource.title}\n\n' + '\n'.join(lines)

    msg = EmailMessage()
    msg['Subject'] = f'New submission: {resource.title}'
    msg['From'] = current_app.config['SMTP_USERNAME']
    msg['To'] = current_app.config['NOTIFY_EMAIL']
    msg.set_content(body)
    return msg


def notify_new_submission(resource):
    cfg = current_app.config
    if not (cfg.get('SMTP_USERNAME') and cfg.get('SMTP_PASSWORD') and cfg.get('NOTIFY_EMAIL')):
        return  # not configured - skip silently, this is expected until env vars are set

    try:
        msg = _build_message(resource)
        with smtplib.SMTP(cfg['SMTP_HOST'], cfg['SMTP_PORT'], timeout=10) as server:
            server.starttls()
            server.login(cfg['SMTP_USERNAME'], cfg['SMTP_PASSWORD'])
            server.send_message(msg)
    except Exception as exc:  # never let a mail failure break a submission
        print(f'[email] failed to send submission notification: {exc}', file=sys.stderr)


def notify_broken_link(resource, note=None):
    cfg = current_app.config
    if not (cfg.get('SMTP_USERNAME') and cfg.get('SMTP_PASSWORD') and cfg.get('NOTIFY_EMAIL')):
        return

    edit_link = _absolute_url(url_for('kb.admin_resource', resource_id=resource.id))
    content_link = _content_link(resource)

    lines = [f'Broken link reported for: {resource.title}', '']
    if note:
        lines.append(f'Note from reporter: {note}')
        lines.append('')
    if content_link:
        lines.append(f'Content link (check this): {content_link}')
    lines.append(f'Edit/fix: {edit_link}')
    body = '\n'.join(lines)

    msg = EmailMessage()
    msg['Subject'] = f'Broken link reported: {resource.title}'
    msg['From'] = cfg['SMTP_USERNAME']
    msg['To'] = cfg['NOTIFY_EMAIL']
    msg.set_content(body)

    try:
        with smtplib.SMTP(cfg['SMTP_HOST'], cfg['SMTP_PORT'], timeout=10) as server:
            server.starttls()
            server.login(cfg['SMTP_USERNAME'], cfg['SMTP_PASSWORD'])
            server.send_message(msg)
    except Exception as exc:
        print(f'[email] failed to send broken-link notification: {exc}', file=sys.stderr)
