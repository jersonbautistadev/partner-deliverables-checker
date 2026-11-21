# Engineering decisions

Why the project is built the way it is, and the trade-offs each choice accepts.

## Why Django and server-rendered pages?

The project needs secure accounts, forms, persistent records and private files. Django supplies established building blocks. A separate React app would add a build pipeline, API authentication choices and duplicated validation without improving this first workflow. The JSON report endpoint still demonstrates a clear HTTP boundary.

## Why separate rules from the web app?

`engine.evaluate(rule, asset)` accepts plain dictionaries and returns a finding. It does not read the database or inspect a request. That makes boundary tests fast and lets me explain one rule without tracing the entire website. `inspect_upload` produces validated metadata; services connect this engine to files, reports and transactions.

Read the code in this order: `engine.word_count`, `engine.validate_rule`, `engine.evaluate`, one test in `tests/test_engine.py`, `models.Requirement`, `services.ensure_report`, then `views.asset_upload` and `permissions.visible_packages`.

## Why source references and snapshots?

A failed check should explain the approved instruction it enforces. Revisions retain the old configuration, source, deadline, approval state, author and change reason. This lets a coordinator explain why a package that passed yesterday needs work today. Sources are manually reviewed references, not claims that the app verified an external document.

## Why fingerprints instead of a “checked” boolean?

A boolean cannot say which file or requirement was checked. Each report stores a
SHA-256 fingerprint of every applicable requirement snapshot, file digest, the latest
evidence and the engine version. If any input changes, the old report cannot be reused.

Manual reviews use a narrower key: one requirement's snapshot plus only the file or
evidence that requirement inspects. Replacing a poster invalidates the logo review on
that poster, while evidence submitted for a different obligation leaves it intact.
The first version bound reviews to the whole-package fingerprint. That was safe but
unusable once a package held a dozen evidence obligations, because every submission
reset every other decision. Changing a requirement's source label or deadline still
invalidates that requirement's review; re-review is preferred to silently reusing a
potentially stale decision.

## Why do authorization checks filter the database query?

`visible_packages` first restricts to a verified membership and selected workspace, then returns that workspace's packages to coordinators and only owned packages to contributors. The same filter protects detail pages, JSON, upload, remove and download routes. Hiding a button would not prevent a direct HTTP request. A 404 for inaccessible package IDs also avoids revealing whether another contributor's package exists.

## Why private attachments instead of public media URLs?

A public URL would bypass role checks and expose original documents. Files use random names outside static assets and are opened only after authorization. Attachment downloads and disabled content sniffing reduce risks from active/polyglot content. This does not prove that a document is safe to open in a desktop program.

## What is atomic, and what is not?

Database changes and audit events commit together. Package row locks coordinate writes in PostgreSQL. Filesystem storage is not part of a database transaction; new files are cleaned up on caught failures and old files are deleted after commit. A sudden process crash can still leave orphaned storage objects. Backups and reconciliation remain operational responsibilities.

## Why a durable email queue?

Verification, invitations and recovery need retries and should not wait for SMTP in the browser request. Mail jobs are stored in PostgreSQL and delivered by a worker or a protected external scheduler. Delivery can duplicate after a worker crash, while tokens remain single use. Synchronous file inspection is still bounded; requirement changes invalidate reports on the next authorized read rather than regenerating every package inside an edit.

## What has actually been exercised?

Beyond the automated suites (SQLite and PostgreSQL, including row-lock races and
encrypted restores), the app runs in production on Vercel with Supabase PostgreSQL,
private S3-compatible storage, SMTP email and scheduled jobs. Production releases are
built with production settings, smoke-tested, then promoted; nightly encrypted backups
go off-site and have been restored into fresh databases with file checksums verified.
Dated evidence is in [records](records/README.md).

What is not claimed: measured time savings, load capacity beyond a small pilot, or
automatic verification of external evidence.
