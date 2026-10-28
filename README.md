# Partner Deliverables Checker

A solo portfolio project for event media-partnership coordination. It turns manually reviewed publishing instructions into traceable submission checks: word counts, image dimensions, required files and phrases, plus recorded human reviews.

**Current state:** the checking engine and standalone demo run in this workspace; 38 engine tests pass. The Django application, migrations, integration tests, and deployment configuration are written, but **have not been executed here**: this environment blocks PyPI downloads and has no browser binary. Do not describe this as a deployed or fully validated application yet. See [verification status](docs/verification.md).

## Try the verified increment

Open [the standalone engine demo](docs/engine-demo.html). It contains real output from checks executed on fictional files, with all four result types. It is a generated report, not the authenticated website.

With Python 3.12+ and Pillow installed:

```bash
python scripts/demo_checks.py
python -m unittest tests.test_engine -v
```

## Stack and why

| Choice | Purpose and tradeoff |
| --- | --- |
| Python 3.12 + Django 5.2 LTS | Built-in session authentication, CSRF protection, forms, ORM, migrations and testing. Less infrastructure to learn at once. |
| Django templates + plain CSS | A responsive website without a separate frontend build or state management layer. |
| SQLite locally | No database service needed for your first demo. Local development only; concurrent team writes use PostgreSQL. |
| PostgreSQL for deployment | Transactions and row locks for coordinated changes and uploads. |
| Pillow | Decode and validate JPG/PNG files and read natural pixel dimensions. |
| Python ZIP/XML libraries | Bounded DOCX text extraction without starting Office, extracting archives to disk, or fetching relationships. |
| Gunicorn + Docker Compose | Documented Linux deployment with persistent database and private file volumes. |

Local development uses free, open-source software. Hosting is optional until the local workflow passes. No cloud subscriptions are required to start. AI extraction, OCR, messaging, multiple organizations and public registration are outside v1.

## Local setup

Install Python 3.12 or newer. In PowerShell, in this directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py seed_demo
.\.venv\Scripts\python manage.py runserver
```

On macOS/Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Seeding requires an empty development database and refuses production mode. Re-running it leaves existing data unchanged and returns an explanatory error.

| Fictional account | Role | Password, local demo only |
| --- | --- | --- |
| `demo_coordinator` | Coordinator | `Demo-Only-2026!` |
| `demo_alex` | Contributor; owns two packages | `Demo-Only-2026!` |
| `demo_sam` | Contributor; owns the ready example | `Demo-Only-2026!` |

The seed includes three fictional partners, twelve instructions, and three packages. “Campus Current” has a wrong-size poster, a missing caption and a pending logo review. “Signal Student Network” needs its cover image. “DevLoop Journal” has a complete text package. A deliberately ambiguous post-event instruction has no package yet.

Use an empty separate database for real pilot work. Provision accounts with Django password validation:

```bash
python manage.py create_team_user jerson --role Coordinator
python manage.py create_team_user contributor_name --role Contributor
python manage.py changepassword contributor_name
```

These examples assume the virtual environment is activated; alternatively use its Python path. `.env` is read by Docker Compose, **not automatically by local Django**. Local defaults work without it. Production settings come from process environment variables.

## First end-to-end exercise, once Django runs

1. Sign in as `demo_coordinator`. Open **Launch press kit**.
2. Read each finding and follow its requirement link to the source and revision history.
3. Replace the 1000 × 1000 poster with a 1080 × 1080 PNG. Observe the dimension finding change.
4. Upload a caption TXT file. Observe the missing-file finding change.
5. Download and inspect the poster. Record a logo-placement pass or fail with an honest note. The seed poster has no actual logo, so a real review should fail it.
6. Revise a requirement or replace a file. Observe a new report and invalidated manual review.
7. Sign in as `demo_sam`. Attempt to open Alex's package URL. Expect a 404, enforced by the server.

## Permissions

| Action | Coordinator | Contributor |
| --- | --- | --- |
| Read shared requirements, sources and their history | Yes | Yes |
| Create/revise/approve requirements or add partners | Yes | No |
| Create a package | For any active team member | For self |
| Read report, upload, remove or download package files | Any package | Own packages only |
| Record subjective review decisions | Yes | No |
| Read audit trail | Yes | No |
| Provision accounts and change roles | Operator CLI | No |

An authenticated account without a team role has no workspace access. The application does not expose user administration or a Django admin route. Roles are Django groups; object access is checked separately in `permissions.py` and every relevant view.

## How checks behave

- Word bounds are **inclusive**. Either bound can be omitted. Words are Unicode letters/digits; internal apostrophes and hyphens keep a word together. This is a documented project policy, not a claim to match Microsoft Word's counter.
- Phrases use Unicode NFKC normalization, case folding and collapsed whitespace, then substring matching. Punctuation remains significant. Hashtags retain `#`.
- Dimensions are exact natural pixel width/height. EXIF display orientation, DPI, crop, visual quality and logo position do not affect this rule.
- Each package has at most one article, caption, promotional image and logo. Required-file checks validate configured slots.
- Every approved non-ambiguous rule produces `passed`, `failed`, `missing`, or `needs_review`. Unapproved/ambiguous instructions never pass. A stage with no requirements remains `needs_review`.
- Subjective checks require a coordinator's decision and explanation, scoped to the current fingerprint.
- Deadlines are entered/displayed in **Asia/Manila**, stored as aware datetimes, and shown independently from readiness. An elapsed deadline does not prove a submission was missed; delivery happens outside this app.
- Changes trigger report generation. Reads also verify the input fingerprint to avoid returning outdated cached findings. File unavailability is included. Old check runs and reviews are retained.

## Upload safety

Each file is at most 5 MiB; plain/extracted text is at most 2 MiB; images are at most 20 megapixels. Extensions and parsed content must agree. Text uses UTF-8. Animated images, invalid images and unsupported file types are rejected. DOCX processing reads only supported text; it rejects DTDs/entities, excessive expansion/parts, unsafe archive paths, macros/embedded objects, external relationships, tracked changes, fields and text boxes. Normal body paragraphs and tables are supported; headers, footers, comments, footnotes and image text are excluded.

Original files use random server-side names outside static assets. Downloads require package authorization, use attachment disposition and `application/octet-stream`, and disable content sniffing and caching. Originals are never displayed inline. Default templates escape text. There is no archive extraction, Office execution or outgoing fetch of references.

This is **not malware scanning**. Read [security notes and limitations](docs/security.md) before a real pilot.

## Checks to run locally and in CI

```bash
ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2
python manage.py collectstatic --noinput
```

The GitHub Actions workflow runs lint, migration checks, tests with SQLite and PostgreSQL, static collection and Django deployment checks. A workflow file is not evidence of a green CI run; no GitHub run has occurred yet.

Dependency ranges are bounded but are **not a validated lockfile**. After a clean local install and a green CI run, freeze the resolved versions into `requirements.lock`, test a fresh install from that lock and use it for the release image. Updating dependencies and pinning image digests are documented release gates.

## Project map

```text
checker/engine.py       Pure checks, counting policy and upload inspection
checker/models.py       Partners, requirements, snapshots, packages, assets and reports
checker/services.py     Transactions, audit events, fingerprints and review lifecycle
checker/permissions.py  Team roles and package access filtering
checker/forms.py        Validated browser inputs and Manila deadline conversion
checker/views.py        HTTP handling and authorization
templates/ + static/    Server-rendered responsive UI
tests/test_engine.py    Framework-independent executable tests
checker/tests.py        Database and HTTP integration tests
docs/                   Architecture, walkthrough, milestones, pilot and verification
```

See [architecture](docs/architecture.md), [API contract](docs/api.md), [deployment](docs/deployment.md), [milestones](docs/milestones.md), [interview notes](docs/engineering-notes.md), [walkthrough](docs/walkthrough.md) and [pilot plan](docs/pilot.md).
