# Public release readiness

Current decision: **protected staging is running; public launch remains no-go**. The [16 November staging record](staging-verification-2026-11-16.md) supersedes the historical checkpoints below: 125-test SQLite/PostgreSQL suites and hosted CI passed; isolated managed backup restoration, real owner verification/password reset, hosted sign-in and private workspace creation passed. A two-minute staging dispatcher also completed an actual scheduled send. Remaining hosted account/file acceptance, approved production dispatch, off-site backup operations, monitoring and launch approval are still required. The [dev-team fixes](dev-team-fixes-2026-11-16.md) describe the implementation behind this release.

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

## Executed evidence

- SQLite: **106 tests, OK, three PostgreSQL-only skips**, in a fresh runtime-only installation.
- PostgreSQL 17.12: **106 tests, OK, no skips**, including row-lock races and actual encrypted PostgreSQL recovery with original downloads.
- Ruff, Django checks, migration consistency, static collection, runtime package audit and production fixture checks passed. Deployment schema rules/YAML syntax validated.
- Orca executed local signup, email verification, sign-in, workspace creation, invitations/acceptance and password reset/new-password sign-in. Phone/tablet/desktop screenshots inspected. No real-user email sent.

Full timings, commands and limitations: [verification](verification.md).

## External blockers and exact actions

| Blocker | Impact | Required input/action |
| --- | --- | --- |
| Hosted account acceptance | Vercel built/promoted the provider-configured release; HTTPS sign-in, health/readiness and CSS passed. | Complete real email, tenant/account/file workflows and operational acceptance before public launch. |
| Hosted database workflows | Supabase migrations, separate roles, transaction-pooler reads and verified TLS passed. | Exercise tenant/account workflows through the deployed application and rehearse remote recovery. |
| Hosted file workflows | Provider write/read/delete, private flag, signed attachment, expiry mechanism and public denial passed. | Verify authenticated upload/download/replacement through the deployed application after account email is available. |
| SMTP and mail scheduler | Onboarding/recovery cannot reliably deliver messages. | Configure verified sender/SMTP; approve real-recipient testing. Enable a worker/dispatcher and measure receipt/retries/queue age. Included Actions dispatcher is disabled and five-minute scheduling is best effort. |
| External backup runner/destination | Local restore is not disaster recovery. | Choose an encrypted off-site destination and trusted runner, store the separate encryption key securely, schedule backups and restore into an isolated remote database/bucket. |
| Monitoring/policy/capacity | Hosted failures and operator response unverified. | Configure alert destination; publish support/retention rules; test readiness/mail/storage/backup alerts, HTTPS and expected concurrency. |
| Optional Linux/Compose rehearsal | Container/proxy/TLS/backup image unverified. | Use a Docker-capable runner if selecting this alternative. This does not require buying a host for the Vercel target. |

Keep keys/passwords out of chat/source. Free-tier eligibility, quotas, commercial-use rules, costs and availability depend on the chosen services; zero cost is not guaranteed. No paid resources, destructive production writes, real-user emails or public launch were initiated.

## Assumptions and product boundaries

- Ready means configured checks passed; sending happens outside the app. New workspaces start empty; demo data is development-only.
- Migrated accounts must verify email. An operator resolves missing/duplicate destinations; old email ownership is not assumed.
- Migration 0002 is intentionally irreversible. Rollback requires the paired pre-migration backup and matching prior code with traffic closed.
- Membership removal/deactivation retains ownership/history. Identity corrections, reactivation and retention requests require a trusted operator. No public account-claim or workspace-deletion endpoint is provided.
- Validation is bounded parsing, not malware scanning. Replacement/removal deletes previous original bytes after commit. Signed URLs are bearer credentials until expiry.
- S3/SMTP contracts have local/mocked coverage; actual services remain a release gate. SMTP is at least once: an interruption after acceptance can produce duplicates.
- No complete assistive-technology, hosted load, remote CI, production rollback or security-certification claim is made.

Proceed to protected staging configuration after choosing the services. Approve public access only after the hosted acceptance and off-site recovery exercises in [deployment](deployment.md) pass.

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
