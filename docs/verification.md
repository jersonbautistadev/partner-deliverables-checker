# Verification record

Recorded 15 November 2026 (Asia/Manila). This replaces the obsolete October record. Local and hosted evidence are distinguished below. The latest hosted checkpoint is at the end; earlier results are retained as history.

| Check actually executed | Result and scope |
| --- | --- |
| Repository baseline | Reproduced 67/68. Audit POST returns 405 because it is read-only; contributor GET remains 403. Corrected the test contract without widening access. |
| Clean installation | Python 3.12.16, Django 5.2.19. A new runtime-only environment installed from the hash lock and ran the full SQLite suite. Windows installation; no Linux/Vercel build claim. |
| Full SQLite suite | **106 tests, OK, 3 skipped, 91.850 seconds.** Skips: two PostgreSQL row-lock races and PostgreSQL recovery. |
| Full PostgreSQL suite | **106 tests, OK, no skips, 113.904 seconds.** Native PostgreSQL 17.12 on loopback, matching pg_dump/pg_restore. |
| Isolation/roles | Executed unrelated workspaces, differing roles, direct URLs, submitted IDs, APIs, downloads, revoked sessions, audit and owner-restriction regressions. |
| Accounts | Executed signup, generic duplicate/unknown responses, verification expiry/replay/resend, invitations/revocation, reset, last-coordinator transfer/removal and deactivation tests. |
| Files/quotas | Executed rejection, replacement, storage-failure recovery, shared quota race, stale reviews and authorized attachment-link contracts. S3 signing/access was mocked; no remote bucket was accessed. |
| Legacy migration | Executed the isolated schema-0001 forward migration rehearsal through the suite; checked accounts, roles, paths, records, revisions, reports and review fingerprints. |
| Encrypted recovery | Executed SQLite and PostgreSQL database+original-file recovery through the suite, including actual restored downloads, both roles and cross-workspace denial. Tampering/overwrite prevention tested. No off-site recovery attempted. |
| Ruff | `python -m ruff check .` passed. |
| Django | `manage.py check` passed; `makemigrations --check --dry-run` reported no changes. |
| Static files | `collectstatic --noinput` passed with compressed manifest assets. |
| Dependencies | `pip_audit -r requirements.lock --disable-pip --no-deps` found no known vulnerabilities; a point-in-time advisory check. |
| Production settings | `check --deploy --fail-level WARNING` passed for Compose-style and Vercel-style fixture settings. SMTP/bucket placeholders were not authenticated or contacted. Startup tests reject missing Vercel secrets and production DEBUG; database TLS tests enforce encryption while preserving stricter certificate verification. |
| Deployment syntax | Relevant official Vercel JSON-schema rules passed; Compose/workflow YAML parsed. No actual Vercel build or Docker execution. |
| Browser execution | Orca performed signup, queued file-mail delivery, POST verification, sign-in, workspace creation, invitation issuance/acceptance and password reset followed by new-password sign-in, and authenticated password change. Only fictional example.test recipients. |
| Responsive/keyboard review | Inspected actual screenshots at 390px phone, 768px tablet and 1440px desktop. Checked keyboard account menu, visible focus, errors, empty workspaces and role navigation. Browser workspace switching also changed the same user between contributor and coordinator permissions. A rendered 320px long-name stress case had document width 320px; it changed no persistent data. |
| Contrast spot check | Body/paper 14.46:1, metadata/paper 5.38:1, accent/white 7.29:1; status pairs 5.49?6.40:1, input border/white 3.05:1. Not a complete WCAG or assistive-technology audit. |
| CI/hosted deployment | The initial local checkpoint preceded Git pushes and deployment. See the hosted checkpoint below for current Vercel/provider evidence. Remote CI results have not been reviewed; hosted load, real-user email and public-launch acceptance remain unverified. |
| Docker/proxy/TLS | **Not built/run:** Docker is absent. Native PostgreSQL does not substitute for the optional Compose rehearsal. |
| Pilot measurements | Not collected. |

Final logs are ignored local artifacts: `.runtime/final-sqlite-tests.log` and `.runtime/final-postgres-tests.log`. Runtime downloads, test mail, databases, fixtures and the local pre-migration SQLite snapshot are excluded from deployment artifacts. Screenshots were inspected from Orca's temporary directory; they are not durable release artifacts.

See [deployment](deployment.md), [operations](operations.md) and [release gates](release-readiness.md). Repeat hosted acceptance and record the deployed revision before public approval.

## Vercel dependency-discovery correction

The user supplied a real Vercel CLI 65.14.0 build log for commit `876decc`. It failed before Django settings discovery: Vercel selected the tool-only `pyproject.toml` and installed no Django dependency. Removed that ambiguous manifest, moved lint configuration to `ruff.toml`, and retained automatic `manage.py`/WSGI entrypoint discovery. A fresh Python 3.12 environment installed all 23 runtime packages from `requirements.txt` using hashes; Django system checks, static collection and Ruff passed. These local results address the reported import failure; a successful hosted rebuild remains unverified. Earlier table entries describe the local-verification cutoff before the user's deployment attempt.

## Self-contained Vercel requirements

The subsequent user-provided Vercel CLI 65.14.0 build log for `c0e88a4` failed while resolving `-r requirements.lock`. Replaced that include with a byte-identical, self-contained copy of the runtime lock in `requirements.txt`; package versions and hashes are unchanged. Added a CI equality check to prevent drift after lock updates. Executed the published `@vercel/python-analysis` 0.15.3 parser locally: an include without a file resolver reproduced the included-file error, while the self-contained file parsed all 23 requirements, including Django, with hashes. Hash-enforced uv installation, Django checks, static collection and Ruff passed locally. This parser exercise is not a complete Vercel CLI build; hosted rebuild success remains unverified.

## Supabase provisioning and private-service verification

Created a Supabase Free organization/project and a private bucket with no real user documents. Supabase Data API was disabled at creation. Separate migration/runtime roles were created, and Django migrations completed through the session pooler. The runtime transaction-pooler connection passed authentication, TLS and certificate/hostname verification; it read Django tables and had no superuser, role/database-creation or public-schema-creation privileges. The account count at this check was zero.

Django S3 storage successfully wrote, located and read back a synthetic object. A signed attachment URL returned the original bytes with attachment disposition; unsigned S3 and public-object endpoint requests were denied. Only the generated rehearsal object was removed afterward. The S3 addressing mode is configurable for Supabase's path-style endpoint. The bundled public CA came from the certificate URL in Supabase Studio's official source.

All 107 SQLite tests passed in 85.500 seconds, with three PostgreSQL-only skips. This includes a new provider CA/path-style regression. The previous 106-test native PostgreSQL run remains the full concurrency/recovery evidence; it was not rerun for this provider configuration change. Actual provider connections/storage were exercised separately as described above.

Vercel production variables were saved through its dashboard, including the least-privilege runtime database URL, private-storage credentials and provider settings. A successful hosted rebuild and account email delivery are still pending at this checkpoint. Generated credentials are encrypted in ignored local recovery files; they are not in this record or Git.

## Hosted checkpoint: Vercel and Supabase

Vercel successfully built commit `171a45b` in 20 seconds. An older redeployment briefly took the canonical URL; the new deployment (`3Fs2zSzdUJA36QFhkQH3ortA726o`) was then explicitly promoted and the dashboard reported `Deployment promoted`. The canonical HTTPS origin is https://partner-deliverables-checker-puux.vercel.app. Actual public requests returned 200 for `/health/`, `/ready/` and `/accounts/login/`; health/readiness JSON reported `ok` and `ready`. HSTS was present. Collected CSS returned 200 with the application design tokens.

The live sign-in page was inspected in Orca at phone (390px), tablet (768px) and desktop (1200px) widths. At 1440px, DOM measurements showed one header/brand/footer and no horizontal document overflow; the browser screenshot capture repeated a right-edge strip, so the clean desktop visual check used 1200px rather than treating that capture artifact as an application defect.

Provider policy checks confirmed the bucket is private with a 3,145,728-byte file cap, and anonymous/authenticated Supabase Data API roles have no DML grants on Django tables. Normal signed URLs request 60-second expiry. A separate three-second signed URL downloaded successfully before expiration, then was denied with HTTP 400 while its object still existed. Supabase's expiry rejection uses 400 here, rather than the initially expected 403. Generated rehearsal objects were removed.

Gmail was selected for initial email testing, but the account's App passwords page was unavailable because 2-Step Verification was off. The owner was handed the Google setup page to enable it privately. No Google password, app password or verification code has been collected, and no real-recipient email test has run. The mail-dispatch workflow remains disabled. Passing service readiness does not verify email delivery, account acceptance, load/capacity, monitoring or off-site recovery; those remain release gates.
