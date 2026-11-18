# Production rollout: 18 November 2026

Status: **in progress, no public-launch readiness claim**. Branch
`fix/dev-team-release-gaps`; main has not been changed during this checkpoint.
The owner authorized proceeding with review/rollout, selected a small
personal/educational pilot and approved publishing the staging Gmail address as
the public support/data-request contact. No personal address or credential is
hardcoded in the repository.

## Review and resulting changes

Self-review covered the diff against main: authentication/throttles, scoped
queries, error handling, cached dashboard findings, history/fingerprints,
configuration, backups, scheduler SQL, tests and frontend changes. This is not
an independent human approval or a claim that no defects remain.

Production preparation exposed additional operational gaps:

- Workspace quotas alone can collectively exhaust a small free store. Optional
  `MAX_SERVICE_WORKSPACES` now serializes the global count and creation across
  accounts, using a persistent activity row separate from the mail heartbeat.
  The planned pilot cap is five workspaces at the existing 100 MiB each.
- Public account traffic can exhaust a personal SMTP account. Optional
  `MAIL_DAILY_ATTEMPT_LIMIT` bounds attempts across concurrent dispatchers,
  including failed sends. Waiting messages retain their retry count. Readiness
  and account pages expose a service-wide delay rather than silently discarding
  mail. Planned budgets: 100 production attempts/day and 25 staging attempts/day.
  These do not guarantee availability or account-wide Gmail capacity.
- Public support/retention information was missing. `/pilot/` is accessible
  anonymously and before verification, retains the editorial style and reads
  its contact from `PUBLIC_SUPPORT_EMAIL`. Deployment checks require a valid
  contact. The footer links the page throughout account/workspace flows.
- SQL NULL response fields could bypass an acknowledgement condition. Scheduler
  SQL now treats missing content type/body/status as failure. A disposable native
  PostgreSQL boundary rehearsal executes the new production SQL and tests
  malformed, redirected and NULL responses, private-role denials and scoped log
  retention. Its HTTP/Vault/cron fixtures are doubles, not actual provider proof.

## Executed checks

- Overnight staging cron ran at **18:17 UTC on 17 November / 02:17 Manila on
  18 November**. Its [hosted job](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44146150894)
  passed. Its actual B2 bundle independently decrypted; all five original hashes
  matched. At inspection four retained versions totaled 99,687 bytes.
- Staging mail/readiness cron runs at 05:16, 05:18 and 05:20 UTC succeeded.
- Current local suites: **150 tests**, SQLite OK with nine PostgreSQL-only skips
  in 92.242 s; PostgreSQL 17.12 OK with no skips in 119.773 s. This includes new
  cross-account workspace and concurrent SMTP-budget races.
- Ruff, Django checks, migration consistency, YAML parsing, production fixture
  checks and dependency audit passed. Hosted Linux CI for source `3042cd5`
  [passed](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44249660879),
  including both full suites, dependency audit, static collection, operator SQL,
  production fixture checks, Compose configuration and three image builds.
  The PR run [also passed](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44249666728).
- Native PostgreSQL executed the operator SQL with disposable HTTP/Vault/cron
  fixtures: five jobs installed paused; role denials, capacity thresholds,
  malformed/NULL/redirected responses and scoped log retention passed.
- Updated staging SQL was installed against the actual provider. Mail and
  readiness acknowledged actual HTTPS responses; their two-minute jobs were
  reactivated. Backup dispatch also received GitHub's acknowledgement and was
  reactivated at 18:17 UTC. Its real hosted backup run passed:
  [44249060819](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44249060819).
- First hosted CI for the new pilot changes passed SQLite but found a test
  fixture gap in the new PostgreSQL workspace-capacity form response: no static
  manifest exists before collection on a clean runner. The test now explicitly
  uses ordinary static storage, consistent with other form tests. Capacity
  assertions and production static settings are unchanged; the hosted recheck
  passed as linked above.
- Orca's local pilot page was inspected at actual 390, 768 and 1200 CSS pixel
  widths; measured page widths did not overflow. A full mobile capture and
  desktop/tablet viewport captures were viewed. Some initial full-page captures
  timed out; successful ordinary captures and actual viewport measurements were
  used instead. This is local UI evidence, not a production browser claim.
- The actual protected branch deployment's final pilot/support page was then
  viewed in Orca at 390, 768 and 1200 CSS pixels with no measured horizontal
  overflow. The approved contact appeared correctly. Sign-in, signup, reset,
  pilot and readiness GETs returned 200; manifest CSS and security headers passed.
  A bounded readiness probe returned 20/20 successes with five concurrent
  clients (p95 2.532 s, maximum 2.594 s). This is not sustained load/capacity proof.

The approved public support config was saved for Production and Preview.
Production limits of five workspaces and 100 SMTP attempts/day, plus a separate
25-attempt setting restricted to the staging branch, were saved in Vercel.
New settings require a deployment; production enforcement has not been verified.
The existing write-only staging SMTP credential remains restricted to its branch;
no credential was revealed or broadened to all Preview branches.
Eight production runner secrets and destination/ref variables are now configured
in GitHub, separately from staging. Production backup is enabled and verified
as described below. Backup/capacity monitors are up; readiness/maintenance checks
remain unarmed pending the new production app and mail setup.

## Provider setup and actual protection correction

Private provider verification/sign-in completed. The temporary replacement Vercel
token is limited to this project and one day; the earlier unused setup token was
deleted. Existing production database/S3/Django credentials were also scoped to
general Preview deployments. Their scopes were narrowed to Production, keeping
the four dedicated staging overrides. All ten ready Previews in the deployment
inventory were on the staging branch and were created after those overrides;
this is configuration evidence, not a claim that every historical runtime was
forensically examined.

An actual anonymous request found an incorrect earlier assumption: the legacy
`all_except_custom_domains` setting left the production domain accessible (200).
It was changed to `ssoProtection.deploymentType=all`; anonymous production health
and sign-in now redirect to Vercel (302), while the project-scoped operator bypass
works. No plan upgrade was made. Vercel's
[9 September change](https://vercel.com/changelog/protect-production-deployments-for-free-on-every-plan)
made this scope free on all plans. Earlier descriptions of protected production
were inaccurate; protected **staging** acceptance remains valid.

Vercel rejected adding Production to the existing branch-restricted SMTP Secret.
Its value was not read. A separate Production-only password field is prepared
for the owner's private entry; the other nine SMTP/proxy settings are saved.
Provider settings alone do not verify production mail or application workflows.

The private production B2 bucket has provider encryption, Object Lock disabled
and `production/` lifecycle retention of seven days before hiding plus one day
before deleting hidden versions. A separate bucket/prefix-restricted read/write
key lasts 90 days (rotate before 16 February 2027). It is not an append-only/WORM
key. Production uses a distinct AES key. The project-scoped Vercel bypass and
repository-scoped Actions dispatch credential are intentionally shared with
staging; rotate those consumers together. The Actions credential expires
15 February 2027. Neither backup credentials nor AES keys are in the web runtime.

## Production baseline and upgrade recovery

Read-only production inventory found schema through migration 0003, two
unverified accounts, no workspaces/packages/originals and two pending emails.
The database was approximately 12.6 MB at that inspection. Runtime/migration
roles had no superuser, database-creation or role-creation privileges.
The operator-only capacity queries ran read-only against production: zero bytes
in storage object metadata and 16 observed database connections of 60 configured.
These are point-in-time observations, not a concurrency capacity estimate.

Before any migration, a **14,229-byte encrypted schema-0003 bundle** captured all
23 expected Django tables with a strict table allowlist and original-file lock.
There were zero referenced originals. The routine backup allowlist was not
weakened: this operator-only pre-upgrade capture used the recorded migration
state, because the unapplied heartbeat table correctly fails a current-schema
strict backup. Provider schemas were excluded.

That bundle restored into a fresh database on staging infrastructure, migrated
from schema 0003 to 0004, and was read with the ordinary runtime role. Original
records in all 22 application/shared tables matched. Django appropriately added
one heartbeat content type and its four permissions. Provider cron/Vault schemas
were absent; restored workers remained off. Prior recovery targets were preserved.

The pre-upgrade bundle was uploaded to the separate private production B2 bucket.
Its exact version was fully downloaded for ciphertext checksum verification and
authenticated with the production AES key. Only after that check and the owner's
explicit approval did the guarded cleanup remove **exactly queued verification
rows 1 and 2**, whose links were expired. Both accounts and other records remain.
Migration 0004 then applied successfully using the migration role. Production has
two unverified accounts, zero workspaces/assets and no pending mail at that check.

The real hosted production backup runner
[passed](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44259719379).
Its 14,152-byte bundle independently downloaded, authenticated and restored into
a fresh managed database/private prefix on staging infrastructure. All 24
application/migration tables matched when read by the ordinary runtime role;
provider cron/Vault schemas were absent. This bundle has **zero originals**, so
it does not establish production original-file download recovery. Staging's
five-original/six-download recovery remains the file evidence.

All five production operator functions compiled against the actual provider;
four untrusted roles were denied networking, Vault and operator execution.
Capacity queries and independent monitor acknowledgement succeeded. A real
timed production cron dispatch ran at **07:37 UTC** and its
[hosted backup run passed](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44260277401).
Nightly backup is active at 18:47 UTC / 02:47 Manila; capacity runs every 15
minutes. Mail/readiness/maintenance remain paused until their actual contracts
are verified against the new production app.

## Remaining rollout steps

1. Finish the private Production-only SMTP password entry.
2. Review/pass the updated branch and deploy its source with production still
   protected. Keep the staging branch while its scheduler references it.
3. Verify production runtime/storage permissions and actual mail, readiness and
   maintenance contracts before activating those jobs. Verify approved owner
   email receipt, account/workspace/file/review flows and browser layouts.
4. Rehearse the production off-site backup/restore with actual original files
   created through the acceptance flow, including authorized downloads.
5. Confirm public-access approval and remaining provider/support/capacity
   decisions before exposing the pilot. Do not upgrade any paid plan.

Production scheduler SQL installs five paused jobs: mail/readiness every two
minutes, backup at **18:47 UTC / 02:47 Manila**, maintenance at **03:23 UTC /
11:23 Manila**, capacity every 15 minutes. Capacity alerts cover database size
at 400 MB, object metadata totals at 800 MB and database connections at 85% of
the provider's configured maximum. They do not measure all provider billing or
egress quotas. Installation and configuration files do not establish execution.
The generic GitHub mail dispatcher stays separately disabled to avoid duplicate
workers; the production backup job has its own explicit gate and source guard.

Rollback: keep traffic closed, stop new dispatchers and restore the prior
deployment/settings snapshot. Migration 0004 is additive; leaving its unused
table is safer than dropping it during code rollback. A data rollback requires
the paired pre-upgrade bundle and a fresh schema-0003 target before migrating
forward. Never flatten or overwrite live workspaces. Preserve keys independently
of B2; review restored queues/sessions before resuming mail or public access.

Provider references checked during preparation:
[Supabase free quotas](https://supabase.com/pricing),
[Vercel Hobby limits](https://vercel.com/docs/plans/hobby),
[Gmail sending limits](https://support.google.com/mail/answer/22839?hl=en).
These are finite service allowances, not measured application capacity or a
service-level guarantee.

## Changed-file manifest for this checkpoint

- Pilot controls and checks: `config/settings.py`, `checker/accounts.py`,
  `checker/security.py`, `checker/mail.py`, `checker/operations.py`,
  `checker/checks.py`, `checker/tests_public.py`, `checker/tests_concurrency.py`.
- Interface and public policy route: `checker/public.py`, `checker/context.py`,
  `config/urls.py`, `templates/base.html`,
  `templates/checker/pilot_information.html`, `static/app.css`.
- Deployment and verification: `.env.example`, `compose.yaml`,
  `.github/workflows/ci.yml`, `.github/workflows/mail-delivery.yml`,
  `deploy/production-operations.sql`, `deploy/staging-mail-cron.sql`,
  `deploy/staging-readiness-cron.sql`, `deploy/staging-backup-cron.sql`,
  `scripts/rehearse_operations.py`.
- Documentation: `README.md`, `docs/security.md`, `docs/release-readiness.md`,
  `docs/verification.md`, this record. Runtime credentials, cookies and operator
  scratch/recovery files remain ignored and outside the repository.
