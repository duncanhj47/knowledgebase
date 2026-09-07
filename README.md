# Duncan Diesel — Toyota diesel knowledge base

Flask + SQLite app: a curated, searchable archive of Toyota diesel
documentation. Anyone can browse and submit; nothing goes live until an
admin approves it from a moderation queue.

Deployed at `/var/www/app/`, entry point is `app.py` (exposes `app`).

## ⚠️ Before you deploy this version

The database schema changed significantly (new tables, plus a new
`is_admin` column on the existing `User` table). `db.create_all()` only
creates *missing* tables — it does not alter existing ones — so your old
`app.db` won't pick up the new column and things will break in
confusing ways.

**Delete the old database before starting the app**, then re-register:

```bash
rm /var/www/app/app.db
```

The **first account you register after that becomes an admin
automatically** (`is_admin=True`) — there's no manual SQL step. Anyone who
registers after that is a normal (non-admin) account.

## How submission and moderation work

- Anyone can submit at `/submit` — no login required. Five types:
  **video** (URL), **link** (URL), **write-up** (typed text), **photo**
  (uploaded image or a linked album), **file** (PDF/doc upload).
- Every submission lands as `pending` and is invisible to the public.
- Logging in as an admin shows **🗂️ Queue** and **🏷️ Tags** links in
  the nav. The queue (`/admin/queue`) lists everything pending. Opening
  one lets you edit its title/description/category/tags, then
  **Approve**, **Save** (without approving), or **Reject**.
- To edit or delete something that's already approved: find it via
  `/library` like anyone else, open its detail page, and an admin sees
  an **✏️ Edit / delete (admin)** link there that goes to the same
  admin edit screen. **Delete permanently** removes the resource, its
  uploaded file (if any), and its search index entry - it's a real
  delete, not a status change, and asks for confirmation first.
- Approved resources appear in `/library` (browse/filter/search) and get
  indexed for full-text search. Rejected ones stay in the database
  (with your notes) but are never shown publicly.
- A non-admin logged-in user gets a 403 if they try to hit `/admin/*`
  directly.

## Recently added, reporting broken links, and search-as-you-type

- **Homepage "Recently added"** shows the 6 most recently approved
  resources. This is a separate, deliberately small fixed-size query
  (`resource_service.recent_resources()`) - not a relaxation of the
  "browse shows nothing by default" rule on `/library`, which still
  applies as before.
- **"⚠️ Report broken link"** sits at the bottom of every resource's
  detail page, with an optional note field. No login needed. It sends
  you the same kind of notification email as a new submission (subject,
  content link, direct edit link) - silently does nothing if SMTP isn't
  configured, same as submission notifications.
- **Search-as-you-type** on the library search box: type 2+ characters
  and a dropdown of matching titles appears (debounced, via a small new
  `/library/suggest` JSON endpoint backed by the same FTS5 index).
  Arrow keys + Enter to navigate, Escape or clicking away to close.
  Clicking a suggestion goes straight to that resource.

## Browsing: filter by tag, grouped by category

`/library` shows nothing until you search or filter - with a large
archive, an unfiltered "show everything" view doesn't scale and isn't
useful anyway. It supports:
- Free-text search (`?q=`), full-text via SQLite FTS5.
- Filtering by one or more engine models (`?engine=<id>`) and/or one or
  more vehicle models (`?vehicle=<id>`) via a searchable dropdown picker
  (type to filter, click to select, selected tags show as removable
  pills) rather than a wall of checkboxes - this stays usable as the
  taxonomy grows into the hundreds. Selections build the URL query
  string, so results are shareable/bookmarkable links. Multiple engine
  selections are OR'd together; an engine filter and a vehicle filter
  are AND'd (e.g. "2H or B, AND fitted to a HJ60").
- Results render as a dense list (title, one-line description, tags,
  category) rather than a card grid, grouped into fixed sections in
  this order: Videos, Manuals & files, Photos, Write-ups, Links. A
  section only appears if it has matching results.

The picker widget (`static/js/filters.js`) is a small vanilla-JS
component with no dependencies - it filters the option list client-side
as you type. All options still render into the page on load (verified
working fine up to ~1,200 combined tags in testing), so if the taxonomy
eventually grows into the thousands, the next step would be swapping
client-side filtering for a server-side autocomplete endpoint - not
needed at current or expected scale.

## Importing the original site content

`scripts/import_site_content.py` migrates everything from
https://sites.google.com/view/toyotadiesel/home into the knowledge base
in one go - manuals, photo comparisons, videos, how-to guides,
troubleshooting write-ups, wiring diagrams, the lot (132 resources).

Links (Drive/Photos/YouTube/Docs) are preserved as-is rather than
downloaded and re-hosted, so there's no storage/bandwidth cost and
nothing breaks if the migration script has a typo somewhere - worst
case a link 404s and you fix that one entry.

```bash
python scripts/import_site_content.py --dry-run   # preview counts, writes nothing
python scripts/import_site_content.py             # actually import
python scripts/import_site_content.py --reset     # remove a previous import, then re-import
```

Everything is set live immediately (approved, not sitting in the
moderation queue) since it's your own already-curated content. A
handful of engine tags the original site references but the default
taxonomy didn't have (13B, 1C-T, 2C-T, 3L, 5L) are created
automatically. Like the demo data script, everything this creates is
internally marked so `--reset` only ever removes what this script
added - it won't touch real visitor submissions.

One thing worth knowing: one imported video link
("How to Flash the 2H ECU Firmware...") points at what's clearly a
joke in the original site rather than real content. Imported verbatim
since that's what the source page had - worth deciding whether to keep
the joke or swap/remove that one entry once you're looking at the live
site.

## Generating demo data

`scripts/seed_demo_data.py` creates realistic synthetic resources (proper
titles/descriptions, not "Test Item 47") spread across all five types,
tagged with a random mix of engine/vehicle models, mostly pre-approved
so you can see the library populated immediately:

```bash
python scripts/seed_demo_data.py                # 800 resources (default)
python scripts/seed_demo_data.py --count 1500    # a different amount
python scripts/seed_demo_data.py --reset         # wipe demo data, then regenerate
python scripts/seed_demo_data.py --reset --count 0   # just wipe, don't regenerate
```

Everything it creates is internally marked, so `--reset` only ever
deletes what the script generated - real submissions are never touched,
even if you run it repeatedly.

**Worth knowing before you run this on the live server**: with ~700
approved resources, the unfiltered `/library` page renders everything
on one page (~270KB of HTML, roughly 400ms to render in testing).
Filtered or searched views are fast (single-digit ms) since they return
far fewer results. If the unfiltered browse view feels heavy once you
see it live, pagination on `/library` is the natural next addition -
not built yet.

## Type tags (Wiring Diagram, FAQ, How To, etc.)

A third tagging dimension alongside engine and vehicle - freeform,
0-to-many per resource, typed directly by an admin during moderation
rather than pre-managed on a taxonomy page.

- On `/admin/resource/<id>`, the **Type tags** field takes a
  comma-separated list (`Wiring Diagram, FAQ`). As you type each tag, a
  dropdown suggests matching existing tags for whatever you're
  currently typing after the last comma - not just the first tag, every
  segment (native HTML `<datalist>` can't do this, so this is a small
  custom widget: `static/js/tag-autocomplete.js`). Arrow keys + Enter or
  a click selects a suggestion; anything you type that doesn't match an
  existing tag just gets created automatically on save - no separate
  "add this tag first" step.
- Matching is case-insensitive, so typing `faq` when `FAQ` already
  exists reuses the same tag rather than creating a duplicate.
- Public submitters never set these - `SubmissionForm` has no tags
  field, so this is entirely an admin/moderation-time decision.
- Filterable on `/library` via a third **🏷️ Type** picker (same
  searchable-dropdown widget as Engine/Vehicle), and shown as pills
  everywhere the other tags show up - resource rows, resource detail
  pages, and the homepage's Recently Added panel. Indexed into search
  too, so a resource tagged "FAQ" is findable by searching "faq" even
  if the word doesn't appear in its title or description.

## Managing engine/vehicle tags (admin)

`/admin/taxonomy` (the **🏷️ Tags** nav link) lets an admin add or
remove engine models and vehicle models directly — no DB browser needed
anymore. Each entry shows how many resources currently use it. Deleting
a tag untags every resource that had it (the resources themselves
aren't touched or removed) and re-indexes them so search reflects the
change immediately.

## Structure

```
app.py                       entry point (gunicorn target: app:app)
config.py                    SECRET_KEY, DB URI, upload folder/size limit,
                              SMTP/email config
webapp/
├── __init__.py                app factory - registers blueprints,
│                               ensures the FTS5 index exists, seeds
│                               default categories/engine/vehicle tags
├── extensions.py              shared db / login_manager instances
├── models.py                  User, Category, EngineModel, VehicleModel,
│                               Resource (+ tag join tables), Article
├── forms.py                   RegistrationForm, LoginForm,
│                               SubmissionForm, ResourceReviewForm,
│                               ArticleForm
├── routes/
│   ├── main.py                  landing page
│   ├── auth.py                   register / login / logout
│   ├── utils.py                   shared admin_required decorator
│   ├── resources.py              /library, /library/<id>, /submit,
│   │                              /uploads/<file>, /admin/queue,
│   │                              /admin/resource/<id>, /admin/taxonomy
│   └── articles.py               /articles, /articles/<id>,
│                                  /admin/articles/new,
│                                  /admin/articles/<id>/edit,
│                                  /admin/articles/<id>/delete
├── services/
│   ├── auth_service.py           register_user(), authenticate_user()
│   ├── resource_service.py       submission intake, moderation,
│   │                              FTS5 search, upload handling, seeding
│   ├── email_service.py          submission notification emails
│   └── articles_service.py       article CRUD, HTML sanitization,
│                                  pagination
├── static/css/style.css       theme
├── static/js/filters.js       tag-picker widget (library page)
└── templates/                 one template per page above
```

Routes stay thin; the actual logic lives in `services/`. `resource_service.py`
is the one worth reading first — it's the whole submission → moderation →
search pipeline in one file.

## Preferred Suppliers

Nearly identical to Articles under the hood - same rich text editor,
same sanitization, same admin/public split - with two additions: each
entry has a **link** (the supplier's site, which can be an affiliate
URL) and a **card image/logo**.

- **Public**: `/suppliers` lists them as a card grid (logo + name),
  20 per page, newest first. Click through to `/suppliers/<id>` for
  the full description and a "Visit" button.
- **The Visit button doesn't link directly to the supplier** - it goes
  through `/suppliers/<id>/go`, which redirects to the stored URL.
  This keeps the actual (possibly affiliate) link in one place in the
  database rather than scattered across rendered HTML, so updating a
  link later is a one-field edit, and it's the natural point to add
  click tracking later if you ever want it. The link carries
  `rel="sponsored"` too, which is what Google recommends for
  affiliate/paid links.
- **Admin only** for adding/editing/deleting, same pattern as
  Articles - visible nav links and buttons only when logged in as
  admin, 403 for anyone else who hits the admin routes directly.
- Editing and replacing a supplier's logo cleans up the old image file
  rather than leaving it orphaned on disk.

## Articles (blog)

A separate feature from the knowledge base - simple posts with rich
text, meant for write-ups/announcements rather than tagged reference
material.

- **Public**: `/articles` lists everything, 20 per page, newest first.
  Click through to `/articles/<id>` to read one. No login needed to read.
- **Admin only**: creating, editing, and deleting requires an admin
  account - the **📰 Articles** nav link is visible to everyone, but
  the **✏️ New Article** button and the **✏️ Edit** link on each
  article only show up when you're logged in as admin. Non-admins
  (including logged-in non-admin accounts) get a 403 if they hit the
  admin routes directly.
- **Rich text editing** uses [Quill](https://quilljs.com/) (loaded from
  cdnjs, no build step) with a deliberately small toolbar: bold,
  italic, underline, links, and images - matching what was asked for,
  not a full word-processor. Whatever HTML Quill produces is sanitized
  server-side before it's ever stored (via `bleach`, added to
  `requirements.txt`) - only the tags the toolbar can actually produce
  are allowed through (`p`, `br`, `strong`, `em`, `u`, `a`, `img`,
  lists, blockquote); anything else - scripts, event handlers, embeds -
  is stripped. This happens both on create and on every edit.
- **YouTube links auto-embed.** Paste a normal YouTube link (any of
  `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`) and a
  responsive embedded player appears right after it when the article is
  viewed - no special markup needed, just a normal link. This is
  computed at render time from the plain link, not stored as an
  iframe, so if the embed style ever changes later it applies
  retroactively to every existing article without needing to re-save
  anything.
- **Images** can be inserted via the toolbar's image button - picks a
  file, uploads it, and drops it into the article at the cursor.
  Stored separately from resource-submission uploads (in
  `uploads/articles/`, served via `/article-images/<file>`) since
  article images have no approval gate - only an admin can create the
  article that references them in the first place. Allowed types: PNG,
  JPG, GIF, WEBP.

## Search

Full-text search runs on SQLite's built-in **FTS5** extension — no
external search service. A standalone `resources_fts` virtual table
(title/body/tags) is created automatically on startup and kept in sync
manually: a resource is indexed when approved, removed from the index if
later rejected. Query terms are turned into safe FTS5 prefix terms before
matching, so odd characters in a search box can't break the query.

## File uploads

Uploaded files (PDF/image/doc) are stored outside `static/`, in
`UPLOAD_FOLDER` (defaults to `<project root>/uploads/`), under a
randomized filename — the original filename is never trusted or reused.
They're served through `/uploads/<filename>`, which checks the owning
resource's status: non-approved files 404 for anyone who isn't a logged-in
admin. Max upload size is 250MB (`MAX_CONTENT_LENGTH` in `config.py`).
Since `/submit` doesn't require login, this is also effectively the
most disk an anonymous visitor could consume with a single junk upload
before you get a chance to review/reject it - worth keeping an eye on
`du -sh uploads/` if submissions pick up. Gunicorn's `--timeout 300` is
needed alongside this so a large, slow upload doesn't get killed
mid-transfer - already reflected in the commands below.

## Local setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Visit http://localhost:5000

## Before deploying

Set a real secret key as an environment variable rather than using the default in config.py:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Email notifications on new submissions

Every time someone submits something at `/submit`, an email goes out
(via smtplib, straight to Gmail's SMTP server) with the title, type,
category/tags, description, submitter name/contact if given, file size
if a file was uploaded, a link to the content itself, and a direct link
to the admin edit/approve screen for it.

All of this is config, not code - set these as environment variables
(nothing is hardcoded, no secrets in the repo):

```bash
SMTP_HOST=smtp.gmail.com        # default, only needed if you're not using Gmail
SMTP_PORT=587                   # default
SMTP_USERNAME=you@gmail.com     # your Gmail address
SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # a Gmail App Password, not your normal password
NOTIFY_EMAIL=you@gmail.com      # where alerts go - can be the same address
SITE_BASE_URL=https://yourdomain.com   # scheme + host only, no /app path, no trailing slash
```

Gmail App Passwords require 2-Step Verification to be turned on for
the account; generate one at https://myaccount.google.com/apppasswords
- it's a 16-character code, not your real password.

If `SMTP_USERNAME`, `SMTP_PASSWORD`, or `NOTIFY_EMAIL` isn't set,
notifications are silently skipped - the site works fine without email
configured, this is opt-in. If sending fails for any reason (wrong
password, Gmail being Gmail), the failure is logged to stderr but never
shown to whoever submitted - a broken mail setup should never block a
real submission.

## Run under Gunicorn

```bash
gunicorn --workers 3 --timeout 300 --bind 127.0.0.1:8000 app:app
```

## systemd

WorkingDirectory should be /var/www/app, ExecStart should point at `app:app`:

```ini
[Unit]
Description=My Flask App
After=network.target

[Service]
User=youruser
WorkingDirectory=/var/www/app
EnvironmentFile=/etc/duncan-diesel.env
ExecStart=/var/www/app/venv/bin/gunicorn --workers 3 --timeout 300 --bind 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

`EnvironmentFile` is preferable to a handful of inline `Environment=`
lines now that there's a password (the Gmail App Password) in the mix -
keeps secrets out of the unit file itself. Create `/etc/duncan-diesel.env`
with each variable on its own line, no quotes, no `export`:

```
SECRET_KEY=your-generated-secret-key
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
NOTIFY_EMAIL=you@gmail.com
SITE_BASE_URL=https://yourdomain.com
```

Then lock it down so only root can read it:

```bash
sudo chmod 600 /etc/duncan-diesel.env
sudo chown root:root /etc/duncan-diesel.env
```

## Apache reverse proxy

App is served under a subpath (e.g. /app/). ProxyFix in app.py reads
X-Forwarded-Prefix to build correct URLs, so the header must be set:

```apache
<Location /app/>
    ProxyPass http://127.0.0.1:8000/
    ProxyPassReverse http://127.0.0.1:8000/
    RequestHeader set X-Forwarded-Prefix "/app"
</Location>
```

mod_headers must be enabled: `sudo a2enmod headers`

## Notes / next steps worth considering

- SQLite db (app.db) and the uploads/ folder are created automatically on
  first run. Back both up together — the DB references filenames in
  uploads/.
- Once HTTPS is set up (e.g. via certbot), add `SESSION_COOKIE_SECURE = True`
  to config.py.
- Default seeded categories: Factory Manual, How-To Guide, Troubleshooting,
  Torque Spec, Reference Photos, Video, Parts Reference. Default engine
  tags cover H/B/L/C series codes seen on the existing site; vehicle tags
  cover a handful of common HJ chassis codes. Manage these (add/remove)
  at `/admin/taxonomy`. There's still no admin UI for editing the
  Category list itself — only engine/vehicle tags.
- Theme: dark "blueprint" look — dotted grid, dashed panels with teal
  corner marks, warm amber CTAs. Colors/fonts are CSS variables at the
  top of static/css/style.css.
