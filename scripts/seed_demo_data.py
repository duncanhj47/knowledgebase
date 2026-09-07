#!/usr/bin/env python3
"""Generate synthetic demo content so you can see how the site looks and
performs with a realistic volume of data.

Usage (from the project root, with the venv active - same as `python app.py`):

    python scripts/seed_demo_data.py                # adds 800 demo resources
    python scripts/seed_demo_data.py --count 1500    # a different amount
    python scripts/seed_demo_data.py --reset         # wipe existing demo data first, then regenerate
    python scripts/seed_demo_data.py --reset --count 0   # just wipe, don't regenerate

Every resource this script creates is tagged internally (admin_notes =
DEMO_MARKER) so --reset only ever deletes demo data, never anything a
real person submitted. It's safe to run repeatedly.

Resources are generated with realistic titles/descriptions across all
five submission types, tagged with a random mix of engine/vehicle
models, and mostly (85%) pre-approved so they show up in the library
immediately - with a smaller slice left pending/rejected so the admin
queue also has something to look at.
"""
import argparse
import os
import random
import sys
from datetime import datetime, timedelta

# Make the project root importable regardless of where this script is run from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from webapp.extensions import db
from webapp.models import Resource, Category, EngineModel, VehicleModel, User
from webapp.services.resource_service import index_resource, ensure_search_index

DEMO_MARKER = '__DEMO_SEED_DATA__'

# ---------------------------------------------------------------------
# Content pools - real Toyota-diesel-flavoured terminology, not "Test Item N"
# ---------------------------------------------------------------------

EXTRA_ENGINES = [
    ('1HZ', 'H series'), ('1HDT', 'H series'), ('1PZ', 'H series'),
    ('3L', 'L series'), ('5L', 'L series'), ('1KZ-TE', 'KZ series'),
]
EXTRA_VEHICLES = [
    ('BJ40', '40 Series'), ('BJ42', '40 Series'), ('BJ43', '40 Series'),
    ('BJ70', '70 Series'), ('BJ73', '70 Series'), ('BJ74', '70 Series'),
    ('PZJ70', '70 Series'), ('HDJ80', '80 Series'), ('HZJ75', '70 Series'),
    ('HZJ105', '100 Series'),
]

TOPICS = {
    'file': [
        'Repair Manual', 'Service Training Information', 'Wiring Diagram',
        'Parts Catalogue', 'Engine Overhaul Manual', "Owner's Handbook Supplement",
        'Chassis & Body Manual', 'Maintenance Procedures Manual', 'EDIC Circuit Diagram',
    ],
    'photo': [
        'Early vs Late Block Casting Comparison', 'Oil Cooler Cover Comparison',
        'Timing Case Comparison', 'Cutaway Engine Photos', 'Injection Pump Parts Breakdown',
        'Bell Housing Bolt Pattern', 'Cam Comparison', 'Engine Mount Photos',
        'Fuel Sedimenter Images', 'Factory Marketing Photos',
    ],
    'video': [
        'Fuel Rack Movement Demonstration', 'Blowby Comparison - Good vs Bad',
        'Lift Pump Failure Walkthrough', 'Oil Pump Replacement', 'Harmonic Balancer Nut Removal',
        'Glow Control Installation', 'Full Rebuild Playlist', 'Rocker Wear Inspection',
        'Cranking with Cracked Injector', 'ECU Firmware Flash Walkthrough',
    ],
    'text': [
        'Notes on Early vs Late Identification', 'My Experience Rebuilding the Injection Pump',
        'Field Notes - Diagnosing a Fuel-Sucking-Air Issue', 'Converting from 3F - What I Learned',
        'How to Adjust the Fuel Control Screw', 'How to Bleed the Fuel System',
        'How to Replace the Head Gasket', 'How to Fit an Engine Guard',
        'Starts then Stalls when Cold - Resolution', 'Click, No Crank - Resolution',
        'Losing Power Every 10 Seconds - Resolution', 'Overheating Under Load - Resolution',
        'Cylinder Head Torque Sequence Notes', 'Bellhousing Bolt Torque Notes',
    ],
    'url': [
        'Trusted Parts Supplier', 'Forum Thread on Common Failures',
        'Reference Page on the Injection Pump', 'Community Wiki Entry',
        'Bosch VE Pump Deep-Dive', 'Owners Group Facebook Page',
    ],
}

DESCRIPTIONS = [
    'Scanned and cleaned up for readability.',
    'Covers the whole procedure start to finish, with photos.',
    "Useful if you're chasing down an intermittent fault.",
    'Community-contributed - thanks to the original poster.',
    "Handy reference for when you don't want to pull the factory manual out.",
    'A few gotchas worth knowing before you start.',
    'Matches the early-block casting variant - check yours first.',
    'Long thread but the good info is in the first few replies.',
    None, None, None,  # sometimes there's no description at all
]

NAMES = [
    'Dave R.', 'HiluxHermit', 'Steve_M', 'the_bush_mechanic', 'Karen T.',
    'diesel_dan', 'Rob (VIC)', 'overland_al', 'M. Ferreira', 'chasingcogs',
    'Toyota_Terry', 'Wanderlust_Wade', None, None, None,
]


def get_or_create_taxonomy():
    for code, family in EXTRA_ENGINES:
        if not EngineModel.query.filter_by(code=code).first():
            db.session.add(EngineModel(code=code, family=family))
    for code, family in EXTRA_VEHICLES:
        if not VehicleModel.query.filter_by(code=code).first():
            db.session.add(VehicleModel(code=code, chassis_family=family))
    db.session.commit()

    return (
        EngineModel.query.all(),
        VehicleModel.query.all(),
        Category.query.all(),
    )


def random_datetime_within(days_back):
    delta = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return datetime.utcnow() - delta


def make_title(rtype, engines, vehicles):
    topic = random.choice(TOPICS[rtype])
    tags = []
    if engines and random.random() < 0.8:
        tags.append(random.choice(engines).code)
    if vehicles and random.random() < 0.35:
        tags.append(random.choice(vehicles).code)
    prefix = '/'.join(tags) if tags else None
    title = f'{prefix} {topic}' if prefix else topic
    if rtype == 'file' and random.random() < 0.3:
        title += f' ({random.randint(1980, 1999)})'
    return title


PLACEHOLDER_PDF = b'%PDF-1.4\n% demo placeholder file - not a real document\n%%EOF'
PLACEHOLDER_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


def write_placeholder_file(upload_folder, ext):
    import uuid
    os.makedirs(upload_folder, exist_ok=True)
    stored_name = f'{uuid.uuid4().hex}.{ext}'
    content = PLACEHOLDER_PNG if ext in ('png', 'jpg', 'jpeg', 'gif') else PLACEHOLDER_PDF
    with open(os.path.join(upload_folder, stored_name), 'wb') as f:
        f.write(content)
    return stored_name


def reset_demo_data():
    demo_resources = Resource.query.filter_by(admin_notes=DEMO_MARKER).all()
    print(f'Removing {len(demo_resources)} existing demo resources...')
    upload_folder = app.config['UPLOAD_FOLDER']
    for r in demo_resources:
        if r.file_path:
            path = os.path.join(upload_folder, r.file_path)
            if os.path.exists(path):
                os.remove(path)
        db.session.execute(
            db.text('DELETE FROM resources_fts WHERE resource_id = :rid'), {'rid': r.id}
        )
        db.session.delete(r)
    db.session.commit()
    print('Done.')


def generate(count):
    engines, vehicles, categories = get_or_create_taxonomy()
    admin = User.query.filter_by(is_admin=True).first()
    upload_folder = app.config['UPLOAD_FOLDER']

    type_weights = [('file', 0.30), ('photo', 0.20), ('video', 0.20), ('text', 0.15), ('url', 0.15)]
    types_pool = [t for t, w in type_weights for _ in range(int(w * 100))]

    created = {'file': 0, 'photo': 0, 'video': 0, 'text': 0, 'url': 0}
    status_created = {'approved': 0, 'pending': 0, 'rejected': 0}

    batch = []
    for i in range(count):
        rtype = random.choice(types_pool)
        created[rtype] += 1

        roll = random.random()
        status = 'approved' if roll < 0.85 else ('pending' if roll < 0.95 else 'rejected')
        status_created[status] += 1

        resource = Resource(
            title=make_title(rtype, engines, vehicles),
            resource_type=rtype,
            description=random.choice(DESCRIPTIONS),
            category_id=random.choice(categories).id if categories and random.random() < 0.85 else None,
            status=status,
            submitted_by_name=random.choice(NAMES),
            admin_notes=DEMO_MARKER,
            created_at=random_datetime_within(900),
        )

        if rtype in ('video', 'url'):
            resource.url = f'https://example.com/{rtype}/{i}'
        elif rtype == 'photo':
            if random.random() < 0.6:
                resource.file_path = write_placeholder_file(upload_folder, 'png')
            else:
                resource.url = f'https://photos.example.com/album/{i}'
        elif rtype == 'file':
            resource.file_path = write_placeholder_file(upload_folder, 'pdf')
        elif rtype == 'text':
            resource.body = (
                'Step 1: ' + random.choice(['loosen the fitting', 'remove the cover', 'disconnect the line'])
                + '.\nStep 2: ' + random.choice(['inspect for wear', 'clean thoroughly', 'check torque spec'])
                + '.\nStep 3: reassemble and test.'
            )

        if status in ('approved', 'rejected'):
            resource.reviewed_by = admin
            resource.reviewed_at = resource.created_at + timedelta(hours=random.randint(1, 72))

        n_engines = random.choices([0, 1, 2], weights=[20, 55, 25])[0]
        if engines and n_engines:
            resource.engine_models = random.sample(engines, min(n_engines, len(engines)))

        n_vehicles = random.choices([0, 1, 2], weights=[60, 32, 8])[0]
        if vehicles and n_vehicles:
            resource.vehicle_models = random.sample(vehicles, min(n_vehicles, len(vehicles)))

        db.session.add(resource)
        batch.append(resource)

        if len(batch) >= 200:
            db.session.commit()
            for r in batch:
                if r.status == 'approved':
                    index_resource(r)
            print(f'  ...{i + 1}/{count}')
            batch = []

    if batch:
        db.session.commit()
        for r in batch:
            if r.status == 'approved':
                index_resource(r)

    print('\nDone. Created:')
    for t, n in created.items():
        print(f'  {t}: {n}')
    print('Status breakdown:')
    for s, n in status_created.items():
        print(f'  {s}: {n}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--count', type=int, default=800, help='Number of demo resources to create (default 800)')
    parser.add_argument('--reset', action='store_true', help='Delete existing demo data before generating')
    parser.add_argument('--seed', type=int, default=None, help='Random seed, for reproducible output')
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    with app.app_context():
        ensure_search_index()
        if args.reset:
            reset_demo_data()
        if args.count > 0:
            print(f'Generating {args.count} demo resources...')
            generate(args.count)


if __name__ == '__main__':
    main()
