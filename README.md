# Partner Deliverables Checker

A Django application for teams coordinating event media partnerships. It checks publishing packages against reviewed instructions: word bounds, required phrases/files, exact image dimensions, and recorded human decisions. A ready package has passed configured checks; delivery to the partner happens outside this app.

## Release status

Public-account and workspace features are implemented. Protected staging and
production passed real email/account, workspace isolation, file/review and
private-download exercises. Backup and recovery evidence is recorded separately
from public-access approval. The owner-approved small personal/educational pilot
is now public; previews remain protected. See [launch evidence](docs/public-pilot-launch-2026-11-18.md),
[current acceptance evidence](docs/production-acceptance-2026-11-18.md),
[release readiness](docs/release-readiness.md) and [verification](docs/verification.md).
The [Vercel deployment](https://partner-deliverables-checker-puux.vercel.app) must
not be described as public-launch ready solely because a build or test passed.

The UI retains the editorial layout, responsive worklist, source-linked findings, and accessible native forms. New accounts create a private workspace or accept an invitation. Roles are per workspace: a person can coordinate one team and contribute to another.

## Run locally

Use Python 3.12 (see `.python-version`). From this directory in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements.lock
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

Open `http://127.0.0.1:8000/accounts/signup/`. Signup queues a verification message. In another terminal, deliver queued messages to the **local file mailbox**, then open the verification link from the newest file in `.local-mail/`:

```powershell
.\.venv\Scripts\python manage.py send_mail_queue --once
```

POST-confirm the link, sign in, and create a workspace. To process local mail continuously, omit `--once`. The production SMTP backend is selected when `DJANGO_DEBUG=0`; no console/file mailbox is a production delivery service. `.env` is read by Compose, not automatically by local Django.

For fictional fixtures only, `python manage.py seed_demo` works in an empty development database and creates verified `example.test` accounts with the documented development-only password printed by the command. Production mode rejects seeding. The seeder, fixtures, private files, local mail, and local databases are excluded from deployment artifacts.

## Permissions

| Action | Workspace coordinator | Workspace contributor |
| --- | --- | --- |
| Read workspace partners, requirements, sources, history and deadlines | Yes | Yes |
| Create/revise requirements or add partners | Yes | No |
| Create a package | For active verified members | For self |
| Open report or upload/remove/download files | Workspace packages | Own packages in that workspace |
| Record subjective reviews | Yes | No |
| Read workspace audit trail | Yes | No |
| Invite, revoke invitations, change/remove membership | Yes | No |

Coordinators do not receive access to other workspaces. Global Django groups and superuser status do not bypass workspace membership. Direct object IDs, API requests, form choices, and private-download routes enforce the same boundaries. A selected workspace is stored in the session and checked on every request. Revoked access is rejected rather than silently applying an action to a different workspace.

The last active verified coordinator cannot be demoted, removed, or deactivate their account. Promote another verified member first. Membership removal and account deactivation retain package ownership, requirement snapshots, reports, and audit history. Account deactivation disables sign-in and removes memberships; the operator handles any later identity/retention requests.

## Accounts and email

Signup and verification/recovery acknowledgements do not disclose whether an identity exists. Verification and invitation links expire and are consumed only on POST confirmation; new links revoke previous outstanding links for the same destination/purpose. Invitations require the receiving verified email and do not elevate an existing member automatically. Password reset/change use Django's built-in views and token mechanism.

Email is stored in a durable database queue. Run a worker on Compose, or configure the protected `POST /ops/mail/` endpoint with an external scheduler for Vercel. Successful delivery clears the stored body and recipient. Retries are bounded; monitor delivery failures and queue age. SMTP acknowledgement does not guarantee arrival in an inbox. See [deployment](docs/deployment.md).

## Checks and file handling

Requirements can also describe linked evidence or off-site work. Record the responsible
party (our team, partner, or not specified), required/optional/conditional applicability,
source and conditions. Pre-event, event-day, post-event and across-stage instructions
are supported. A stage-not-confirmed draft must be assigned a stage before approval.
The obligation coverage page lists entered instructions, missing package stages and
unresolved last-report findings. Compare the inventory with the source agreement;
the app cannot establish that every source obligation has been entered.

Package owners and coordinators may submit an HTTPS evidence link and explanation.
Links are never fetched or automatically assessed by the server. A coordinator must
inspect the evidence and record an explained decision. Optional/conditional evidence
obligations may be explicitly marked not applicable; they never disappear automatically.
Evidence submissions are retained in private, paginated history. Every submission
invalidates earlier package reviews, including when the text is unchanged. Uploading
or replacing a supporting screenshot also invalidates reviews through the file fingerprint.
The existing image slots can hold screenshots; PDF/video uploads and automatic follower,
publication or logo verification are not provided.

- Word bounds are inclusive. Unicode letters/digits are words; internal apostrophes and hyphens remain part of a word. This is project policy, not a promise to match Microsoft Word.
- Phrase matching uses NFKC normalization, case folding, and collapsed whitespace. Punctuation remains significant.
- Dimensions are exact natural pixels, independent of EXIF orientation, DPI, crop, or logo placement.
- Four file slots exist per package: article, caption, promotional image, and logo.
- Findings are passed, failed, missing, needs review, or an explained not-applicable decision for optional/conditional evidence. Ambiguous or unapproved instructions never pass automatically.
- Manual decisions apply to an exact input fingerprint. Replacements and changed instructions invalidate old approvals.
- Upload/removal generates the affected report. Authorized report reads verify current inputs. The dashboard shows dated snapshots and flags changed packages/requirements for a new report; it does not recheck every original file while listing packages.
- Requirement history is paginated; previous snapshots remain in the database.
- Deadlines display in Asia/Manila, separately from readiness. An elapsed deadline does not prove delivery was missed.

Files are at most 5 MiB locally/Compose; Vercel defaults to 3 MiB to leave room beneath function request limits. Extracted/plain text is bounded to 2 MiB and images to 20 megapixels. TXT/DOCX and JPG/PNG undergo content validation, not just extension/MIME checks. DOCX extraction is bounded and rejects unsafe XML/archive features, macros, external relationships, tracked changes, fields and text boxes. Normal body paragraphs/tables are supported; headers, footnotes, image text and other excluded content are not checked.

Originals are private attachments. S3 deployments issue authorized signed attachment links valid for 60 seconds; recipients can use those bearer URLs until expiry. Validation is not malware scanning. Previous original bytes are removed after a successful replacement/removal; historical digests and reviews are retained. Use a separate archive if old originals must be preserved.

## Initial usage limits

Defaults are configurable through Django environment settings: 3 created workspaces/account; 20 memberships/account; 20 members and 20 pending invitations/workspace; 100 MiB current-file storage/workspace; 50 partners, 200 packages and 500 requirements/workspace; 60 upload operations/hour/workspace. These are guardrails, not measured hosting capacity.

`MAX_EVIDENCE_REVISIONS` defaults to 2,000 retained submissions per workspace, including
earlier versions. Enforcement is serialized through the workspace row; a rejected
submission preserves the previous evidence. Request throttling also covers evidence
submissions and coverage reads. Evidence notes/links remain in the database and its
encrypted backups; do not paste credentials, expiring private-download links or unnecessary
personal information into them.

The pilot can additionally cap workspaces across all accounts with
`MAX_SERVICE_WORKSPACES` and SMTP attempts per UTC day with
`MAIL_DAILY_ATTEMPT_LIMIT`. Zero disables either optional service-wide cap.
Workspace creation is serialized across accounts; SMTP attempts share a database
budget across dispatchers, including failed transport attempts. A full mail
budget retains queued messages without consuming their retries, displays an
account-email delay notice and makes readiness fail when mail is waiting.
`PUBLIC_SUPPORT_EMAIL` is intentionally public on `/pilot/` and is required by
production deployment checks. That page explains the pilot's access, retention,
provider and support arrangements before sign-in.

Account POST requests have an IP limit of 10/minute and an identity limit of 5/15 minutes. Checking operations have IP/user limits of 60/minute. Counters are shared in the database. Shared networks and fixed-window boundaries affect those limits. Configure and load-test them for the actual team and provider quotas.

## Verify changes

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2
python manage.py collectstatic --noinput
python -m pip_audit -r requirements.lock --disable-pip --no-deps
python scripts/rehearse_migration.py
python scripts/rehearse_recovery.py
```

Use PostgreSQL for concurrency tests; SQLite skips row-lock tests. The PostgreSQL backup rehearsal additionally needs matching `pg_dump` / `pg_restore` clients and a local test role permitted to create temporary databases. See [deployment](docs/deployment.md), [architecture](docs/architecture.md), [API](docs/api.md), [security](docs/security.md), and [migration/recovery procedures](docs/operations.md).

## Deployment target

Vercel is the requested primary target. It requires external PostgreSQL, a private S3-compatible bucket, SMTP, a mail scheduler and an off-site backup runner/destination. Vercel Hobby scheduling and function limits apply, and free-tier eligibility/capacity is not guaranteed by this project. Use separate databases/buckets/prefixes and mail settings for previews. The optional Linux Compose path includes the app, mail worker, PostgreSQL, Nginx and Caddy.
