#!/usr/bin/env python3
"""Weekly Duncan Diesel database backup.

Reads SMTP credentials from /etc/duncan-diesel.env (same file the app
uses) and emails app.db as an attachment to NOTIFY_EMAIL.

Run manually to test:
    sudo /var/www/app/venv/bin/python /var/www/app/scripts/backup_email.py

Add to cron (runs every Sunday at 2am):
    sudo crontab -e
    0 2 * * 0 /var/www/app/venv/bin/python /var/www/app/scripts/backup_email.py >> /var/log/dd-backup.log 2>&1
"""
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

# ----------------------------------------------------------------
# Config
# ----------------------------------------------------------------
ENV_FILE = '/etc/duncan-diesel.env'
DB_PATH  = '/var/www/app/app.db'

# ----------------------------------------------------------------
# Load env file — same variables the app uses, no duplication
# ----------------------------------------------------------------
def load_env(path):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                env[key.strip()] = value.strip()
    except FileNotFoundError:
        print(f'ERROR: env file not found: {path}', file=sys.stderr)
        sys.exit(1)
    return env

env = load_env(ENV_FILE)

SMTP_HOST     = env.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT     = int(env.get('SMTP_PORT', 587))
SMTP_USERNAME = env.get('SMTP_USERNAME')
SMTP_PASSWORD = env.get('SMTP_PASSWORD')
NOTIFY_EMAIL  = env.get('NOTIFY_EMAIL')

if not all([SMTP_USERNAME, SMTP_PASSWORD, NOTIFY_EMAIL]):
    print('ERROR: SMTP_USERNAME, SMTP_PASSWORD, and NOTIFY_EMAIL must all be set in the env file.', file=sys.stderr)
    sys.exit(1)

# ----------------------------------------------------------------
# Read the database file
# ----------------------------------------------------------------
db_path = Path(DB_PATH)
if not db_path.exists():
    print(f'ERROR: database not found at {DB_PATH}', file=sys.stderr)
    sys.exit(1)

db_bytes = db_path.read_bytes()
db_size_kb = len(db_bytes) / 1024
timestamp = datetime.now().strftime('%Y-%m-%d')
filename = f'duncandiesel-{timestamp}.db'

print(f'Database: {db_path} ({db_size_kb:.1f} KB)')

# ----------------------------------------------------------------
# Build and send the email
# ----------------------------------------------------------------
msg = EmailMessage()
msg['Subject'] = f'Duncan Diesel — weekly backup ({timestamp})'
msg['From']    = SMTP_USERNAME
msg['To']      = NOTIFY_EMAIL
msg.set_content(
    f'Weekly backup of app.db attached.\n\n'
    f'Date: {timestamp}\n'
    f'Size: {db_size_kb:.1f} KB\n'
    f'File: {DB_PATH}\n'
)
msg.add_attachment(
    db_bytes,
    maintype='application',
    subtype='octet-stream',
    filename=filename,
)

print(f'Sending to {NOTIFY_EMAIL} via {SMTP_HOST}:{SMTP_PORT}...')

try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
    print(f'Backup sent OK — {filename}')
except Exception as exc:
    print(f'ERROR: failed to send backup: {exc}', file=sys.stderr)
    sys.exit(1)
