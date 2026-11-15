# Verification record

Recorded 15 November 2026 (Asia/Manila). This replaces the obsolete October record. Results describe this checkout, not a deployed public service.

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
| CI/hosted deployment | **Not executed:** no push, remote CI, Vercel deployment, real-user mail, live bucket permission test, hosted load test or public launch. |
| Docker/proxy/TLS | **Not built/run:** Docker is absent. Native PostgreSQL does not substitute for the optional Compose rehearsal. |
| Pilot measurements | Not collected. |

Final logs are ignored local artifacts: `.runtime/final-sqlite-tests.log` and `.runtime/final-postgres-tests.log`. Runtime downloads, test mail, databases, fixtures and the local pre-migration SQLite snapshot are excluded from deployment artifacts. Screenshots were inspected from Orca's temporary directory; they are not durable release artifacts.

See [deployment](deployment.md), [operations](operations.md) and [release gates](release-readiness.md). Repeat hosted acceptance and record the deployed revision before public approval.
