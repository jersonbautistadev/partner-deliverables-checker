# Architecture

## Worklist freshness and operational health

The dashboard uses tenant/owner-scoped package queries, a latest-run subquery, and one batch of the latest reports. It does not generate reports or contact original-file storage. It labels summaries as last reports, dates each one, and flags absent reports, engine changes, package edits or later applicable requirement edits as needing a report. Each attention/passed list displays 20 rows per page. Summary classification still reads the latest report metadata for visible packages within the configured workspace limits; this is not a hosted capacity guarantee. Opening a report/API report or changing a package still performs the authoritative fingerprint/storage checks. Out-of-band storage changes are detected there, not silently asserted current by the dashboard.

Storage adapter failures become a dedicated unavailable exception, rendered as generic HTML/JSON 503 responses. A genuinely missing original remains a missing finding or 404. Failed replacement transactions retain the prior asset/report; failures after an HTTP stream has begun cannot retroactively change its status. Private signed-URL downloads are served by the storage provider after authorization.

`ServiceHeartbeat` is global operator state, not workspace content or a user-facing metric. Production readiness requires configured mail, recent dispatcher activity and no stale/exhausted pending jobs, alongside database/storage probes. A completed dispatcher batch records activity even when idle; actual delivery health is also determined by queue state and separately monitored SMTP receipt. No health GET sends email.

Django 5.2 / Python 3.12 serves templates and plain CSS. PostgreSQL is the production database; SQLite is for local development. Vercel runs the WSGI application as a function and serves collected static assets. Remote originals use a private S3-compatible bucket. Compose alternatively runs Gunicorn, a mail worker, PostgreSQL, Nginx, and Caddy on one Linux host.

## Data boundaries

Evidence obligations reuse `Requirement` with kind `evidence` and no file slot.
Responsibility and applicability describe the agreement; they grant no additional
permissions. An across-stage requirement applies to pre/event/post packages, while
an unconfirmed-stage draft cannot be approved through the form. Coverage does not
resolve an across-stage instruction while any of those stages lacks a visible package.
Contributors see shared instructions and only their own package report statuses.

`Evidence` is an append-only package+requirement submission history. The latest row
is included in the package fingerprint. Each finding also carries a per-requirement
`review_key`: a SHA-256 of that requirement's snapshot plus only its slot's file or its
latest evidence (ID, URL, note, submitting actor). New manual reviews store that key,
so a decision survives unrelated changes in the package but not changes to its own
requirement or input. Reviews stored with the package fingerprint stay valid while
the package is unchanged. Submissions
lock workspace then package, check an optimistic current-evidence ID, enforce the
workspace history quota, append evidence/audit and refresh the report atomically.
Failures roll back all database writes. The server never follows supplied URLs.

Legacy default requirement metadata is omitted from fingerprint serialization,
and no evidence key is added when there is none. Thus unchanged existing file-only
fingerprints and boolean manual reviews remain applicable. New decisions use an
explicit outcome, including `not_applicable` only for optional/conditional evidence.
The pure file-check engine's existing behavior/version is unchanged; the evidence
branch and optional fingerprint payload are additive.

`Workspace` -> `Partner` -> `Requirement` / `Package`. Assets and reports belong to packages; revisions belong to requirements. Manual reviews are attached to package+requirement and a review key (per-requirement, or a legacy package fingerprint). These records inherit their workspace through their parent relation. `AuditEvent` has an explicit workspace; global account events have no workspace and are excluded from workspace audit pages.

`Account` associates a unique normalized email and verification timestamp with Django's existing User model. `Membership` stores one role per user/workspace. Global groups are historical data only. There is no superuser workspace bypass. `ActionToken` stores only a random token's SHA-256 digest, purpose, bound email/user/workspace, expiry and consumption time. `MailJob` holds delivery data privately until acknowledgement, then clears body and recipient. `RateBucket` uses secret-keyed identity digests and short-lived fixed windows.

## Request flow

Django sessions authenticate the user. Workspace middleware validates email verification and the selected membership on each application request. Missing/revoked workspace selection goes to the workspace chooser (APIs return 403). Views/forms filter all object queries and model choices. Coordinators can access packages only within the selected workspace; contributors also require ownership. Side effects use POST and CSRF, except the isolated machine mail/maintenance endpoints which use a constant-time bearer-secret check and accepts no user payload.

## Writes and concurrency

Workspace mutations lock the workspace row in a transaction before checking count/storage limits or changing related records. Uploads then lock the package, save a new original, update the asset and report, and schedule old-file removal on commit. A failed save keeps the previous database state; failed orphan cleanup is logged for maintenance. Email/invitation lifecycle operations lock account/workspace/token rows in a consistent order. Membership changes and self-deactivation serialize coordinator-count checks through workspace locks. SQLite does not provide equivalent row locks, so concurrency guarantees are verified against PostgreSQL.

The pure engine in `engine.py` remains independent of Django. Services compute current input fingerprints, validate upload contents and generate reports. Requirements are refreshed on authorized reads instead of synchronously regenerating every package on an instruction edit. File availability is included in each input read. External mutation of bytes is not rehashed on every read; the reconciliation/backup checks and storage access controls address that operational boundary.

## Accounts and operations

Django password validators, hashing, session login/logout and password-reset tokens are reused. Custom verification/invitation tokens are random, expiring and consumed on POST; GET does not change verification or membership. Delivery is queued to avoid SMTP-dependent response timing and to retry transport failures. Delivery is at least once: a worker crash after SMTP acknowledgement but before commit can duplicate an email. Tokens remain single use.

Readiness checks database access, storage reachability, and old pending mail. They do not prove bucket privacy, write permissions, end-to-end SMTP arrival, or capacity. Offline encrypted recovery bundles use streaming AES-256-GCM and include both database and original files. See `operations.md` for consistency, encryption-key handling, restore and retention requirements.
