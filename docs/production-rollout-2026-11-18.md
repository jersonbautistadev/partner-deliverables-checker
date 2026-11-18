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
  checks and dependency audit passed. New changes still need their hosted CI.
- Native PostgreSQL executed the operator SQL with disposable HTTP/Vault/cron
  fixtures: five jobs installed paused; role denials, capacity thresholds,
  malformed/NULL/redirected responses and scoped log retention passed.
- Updated staging SQL was installed against the actual provider. Mail and
  readiness acknowledged actual HTTPS responses; their two-minute jobs were
  reactivated. Backup dispatch/activation evidence is recorded separately below.
- Orca's local pilot page was inspected at actual 390, 768 and 1200 CSS pixel
  widths; measured page widths did not overflow. A full mobile capture and
  desktop/tablet viewport captures were viewed. Some initial full-page captures
  timed out; successful ordinary captures and actual viewport measurements were
  used instead. This is local UI evidence, not a production browser claim.

## Production baseline and upgrade recovery

Read-only production inventory found schema through migration 0003, two
unverified accounts, no workspaces/packages/originals and two pending emails.
The database was approximately 12.6 MB at that inspection. Runtime/migration
roles had no superuser, database-creation or role-creation privileges.

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

Two queued messages (IDs 1 and 2) were matched to expired verification tokens.
A cleanup is prepared and dry-run only. It requires explicit owner approval and
verified off-site backup before deleting those two queue rows. Accounts and other
records are outside its scope. **No cleanup or production migration has run at
this checkpoint.**

## Remaining rollout steps

1. Complete private Vercel identity verification and Backblaze sign-in.
2. Verify the pre-upgrade backup off-site; provision separate production backup
   storage/credentials, source guards and independent monitoring.
3. Apply the additive migration with the migration role, handle the two expired
   queue rows only if approved, configure production SMTP/origins/contact/caps,
   and verify migration/runtime/storage permissions.
4. Pass hosted CI and protected preview checks for the new code. Review the
   concrete diff before merging. Keep the staging branch while its scheduler
   still references it.
5. Rehearse the production backup runner and schedulers; enable mail only after
   reviewing its queue. Verify actual owner email receipt and production account,
   workspace, upload/download, security-header and browser flows.
6. Confirm public-access approval and remaining provider/support/capacity
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
