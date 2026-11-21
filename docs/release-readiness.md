# Public release readiness

Current decision: **staging and production acceptance passed; the owner-approved
bounded educational pilot is public**. [Launch evidence](public-pilot-launch-2026-11-18.md)
records anonymous account-page, private-data and protected-preview checks.
The [18 November production acceptance](production-acceptance-2026-11-18.md)
is the latest evidence, following the [rollout history](production-rollout-2026-11-18.md)
and [17 November staging acceptance](staging-verification-2026-11-17.md).
The owner confirmed production verification, reset and invitation email receipt.
Live reset/sign-in, invitations, two-team roles/isolation, upload/replacement/quota,
review invalidation, source/history and private-download flows passed. Both
150-test suites passed hosted CI; SQLite skips nine PostgreSQL-only cases and
PostgreSQL skips none. The latest build guard validates the actual Vercel build
environment in addition to CI's production fixture checks.

All five production jobs are active: mail/readiness every two minutes, capacity
every 15 minutes, backup at 02:47 Manila and approved maintenance at 11:23 Manila.
Manual maintenance completed without changing protected record counts; its first
normal daily execution remains in the future. A production file backup restored
into an isolated managed database/private prefix; both roles downloaded matching
original bytes. The latest five-original bundle authenticated and its full-set
restore passed ten matching downloads and ten wrong-workspace denials across
both roles. All four independent production monitors
were up. Staging backup remains active at 02:17 Manila.

Previews remain protected and main is unchanged. Two preserved acceptance teams
consume two of the five pilot workspace slots. See the acceptance record for
limits, non-executed checks and file-security limitations, and [off-site operations](offsite-backups.md)
for scheduling, rotation and recovery. Public access was explicitly approved;
no paid-plan approval is implied.

## Historical 15 November checkpoint

Recorded 15 November 2026. Local implementation and verification are finished for this release candidate. **Vercel build and database/storage health are verified; email/account acceptance is pending and public launch remains blocked.** This is execution evidence, not a security certification.

## Prioritized gaps and resolution

| Priority | Confirmed gap | Resolution and file references |
| --- | --- | --- |
| Critical | Single-team data/permissions could not safely support public teams. | Scoped memberships, queries, writes, forms, APIs, deadlines, history and downloads: `checker/models.py`, `permissions.py`, `middleware.py`, `forms.py`, `views.py`, `services.py`, migrations 0002/0003. |
| Critical | Incomplete public account and membership lifecycle. | Verified signup, expiring single-use POST-confirmed tokens, Django reset/change, invitations, last-coordinator protection and deactivation: `checker/accounts.py`, `account_forms.py`, `mail.py`, `config/urls.py`, account/registration templates. |
| High | Public abuse and concurrent quota/role changes required enforcement. | Shared throttles, count/storage quotas, workspace/account row locks and race tests: `checker/security.py`, `middleware.py`, `accounts.py`, `services.py`, `tests_concurrency.py`. |
| High | Local SQLite/files are not durable Vercel storage; function limits differ. | Fail-closed settings, remote PostgreSQL/TLS, private S3, 3 MiB uploads, authorized 60-second attachment URLs: `config/settings.py`, `checker/checks.py`, `views.py`, `.python-version`, `pyproject.toml`, `vercel.json`. |
| High | Recovery/dependency/configuration claims lacked current evidence. | Hash locks, package audit, authenticated encrypted backups, migration/recovery rehearsals and operator commands: `checker/backup.py`, management commands, `scripts/rehearse_*.py`, requirements locks, CI, `docs/operations.md`. |
| Medium | Audit test expected 403 for unsupported POST. | Reproduced contract: POST 405; contributor GET 403. `checker/tests.py` retains both. This was a test-contract defect, not permission to weaken authorization. |
| Medium | Verification documents described an obsolete unexecuted state. | Replaced current evidence, architecture, API, security, deployment and project notes in `docs/`. |

The editorial frontend was retained. Account/team forms share its typography, restrained accent, explicit labels and responsive layout. The keyboard-operated account menu reduces wrapping. Validation, quota, stale-review and storage failures have specific messages.

## Historical executed evidence: 15 November

- SQLite: **106 tests, OK, three PostgreSQL-only skips**, in a fresh runtime-only installation.
- PostgreSQL 17.12: **106 tests, OK, no skips**, including row-lock races and actual encrypted PostgreSQL recovery with original downloads.
- Ruff, Django checks, migration consistency, static collection, runtime package audit and production fixture checks passed. Deployment schema rules/YAML syntax validated.
- Orca executed local signup, email verification, sign-in, workspace creation, invitations/acceptance and password reset/new-password sign-in. Phone/tablet/desktop screenshots inspected. No real-user email sent.

Full timings, commands and limitations: [verification](verification.md).

## Operating follow-ups after launch

| Blocker | Impact | Required input/action |
| --- | --- | --- |
| Public access | Owner-approved public production routes and protected previews were verified. | Monitor the bounded pilot; retain Django authentication for private data. |
| Final release checks | Actual production build checks, both full CI runs and five-original recovery passed. | Retain the evidence and repeat affected checks for upgrades. |
| Pilot capacity | Two acceptance teams consume two of five workspace slots; sustained load is unmeasured. | Keep the finite pilot caps; any fixture removal needs a separately scoped cleanup decision. |
| Operations | All five production jobs are enabled; manual maintenance passed. | Inspect the first normal daily maintenance run and rotate expiring credentials on the documented dates. |
| Legacy integrations | Three duplicate Vercel integrations report failure separately from the active project. | Decide whether to disconnect them; no legacy project was deleted during this work. |
| Optional Linux/Compose target | Compose configuration and three images built in CI; full HTTPS service rehearsal was not run. | Rehearse this alternative if choosing it instead of the verified Vercel target. |

Keep keys/passwords out of chat/source. Free-tier eligibility, quotas, costs and
availability depend on the chosen services. No paid resources were enabled.
Public access was opened, and real test emails and the precisely scoped
production cleanups were executed, only after explicit owner approvals.

## Assumptions and product boundaries

- Ready means configured checks passed; sending happens outside the app. New workspaces start empty; the demo seeder is development-only. The preserved production acceptance teams contain explicitly fictional test fixtures.
- Migrated accounts must verify email. An operator resolves missing/duplicate destinations; old email ownership is not assumed.
- Migration 0002 is intentionally irreversible. Rollback requires the paired pre-migration backup and matching prior code with traffic closed.
- Membership removal/deactivation retains ownership/history. Identity corrections, reactivation and retention requests require a trusted operator. No public account-claim or workspace-deletion endpoint is provided.
- Validation is bounded parsing, not malware scanning. Replacement/removal deletes previous original bytes after commit. Signed URLs are bearer credentials until expiry.
- S3/SMTP have automated coverage and actual hosted acceptance evidence. SMTP is at least once: an interruption after provider acceptance can produce duplicates.
- No complete assistive-technology audit, sustained hosted-load test, destructive in-place production rollback or security certification is claimed. Actual hosted CI and isolated recovery results are linked above.

The public pilot opened after the final [production acceptance](production-acceptance-2026-11-18.md) decision and explicit owner approval. Reassess capacity and deployment requirements before expanding beyond this educational pilot.

## Changed-file manifest

Working-tree changes relative to Git HEAD, including preserved editorial frontend work present when deployment preparation began:

- `.dockerignore`
- `.env.example`
- `.github/workflows/ci.yml`
- `.github/workflows/mail-delivery.yml`
- `.gitignore`
- `.python-version`
- `.vercelignore`
- `Dockerfile`
- `README.md`
- `checker/account_forms.py`
- `checker/accounts.py`
- `checker/apps.py`
- `checker/backup.py`
- `checker/checks.py`
- `checker/context.py`
- `checker/forms.py`
- `checker/logging.py`
- `checker/mail.py`
- `checker/management/commands/backup_bundle.py`
- `checker/management/commands/create_team_user.py`
- `checker/management/commands/maintain_data.py`
- `checker/management/commands/reconcile_files.py`
- `checker/management/commands/restore_bundle.py`
- `checker/management/commands/seed_demo.py`
- `checker/management/commands/send_mail_queue.py`
- `checker/management/commands/set_account_email.py`
- `checker/middleware.py`
- `checker/migrations/0002_public_workspaces.py`
- `checker/migrations/0003_workspace_creator.py`
- `checker/models.py`
- `checker/operations.py`
- `checker/permissions.py`
- `checker/security.py`
- `checker/services.py`
- `checker/tests.py`
- `checker/tests_concurrency.py`
- `checker/tests_public.py`
- `checker/tests_recovery.py`
- `checker/uploads.py`
- `checker/urls.py`
- `checker/views.py`
- `compose.yaml`
- `config/settings.py`
- `config/urls.py`
- `deploy/backup.Dockerfile`
- `deploy/backup.sh`
- `deploy/nginx.conf`
- `docs/api.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/engineering-notes.md`
- `docs/milestones.md`
- `docs/operations.md`
- `docs/release-readiness.md`
- `docs/security.md`
- `docs/verification.md`
- `docs/walkthrough.md`
- `pyproject.toml`
- `requirements-dev.in`
- `requirements-dev.lock`
- `requirements-dev.txt`
- `requirements.in`
- `requirements.lock`
- `requirements.txt`
- `scripts/rehearse_migration.py`
- `scripts/rehearse_pg_recovery.py`
- `scripts/rehearse_recovery.py`
- `static/app.css`
- `templates/accounts/page.html`
- `templates/accounts/workspace.html`
- `templates/accounts/workspaces.html`
- `templates/base.html`
- `templates/checker/audit.html`
- `templates/checker/dashboard.html`
- `templates/checker/error.html`
- `templates/checker/finding.html`
- `templates/checker/form.html`
- `templates/checker/package.html`
- `templates/checker/package_row.html`
- `templates/checker/partners.html`
- `templates/checker/requirement.html`
- `templates/registration/login.html`
- `templates/registration/password_change_done.html`
- `templates/registration/password_change_form.html`
- `templates/registration/password_reset_complete.html`
- `templates/registration/password_reset_confirm.html`
- `templates/registration/password_reset_done.html`
- `templates/registration/password_reset_email.html`
- `templates/registration/password_reset_form.html`
- `templates/registration/password_reset_subject.txt`
- `vercel.json`
