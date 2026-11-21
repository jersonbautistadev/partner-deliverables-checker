# Isolated staging: 16 November 2026

Subsequent invitation, contributor-access and resumed-service evidence is in the
[17 November follow-up](staging-verification-2026-11-17.md). The results below
remain the record of their execution checkpoint.

Branch: `fix/dev-team-release-gaps`; production `main` remains separate. This record distinguishes completed service/recovery checks from email and hosted acceptance still in progress.

## Provisioned and verified

- Created dedicated Supabase Free project `partner-deliverables-staging` (`dwijbooalncbcaogbjnc`) in North Virginia, separate from the existing production project. No paid plan/add-on was selected. Future provider limits/availability remain operator responsibilities.
- Disabled Data API at project creation. Created separate migration/runtime roles with independently generated credentials. Runtime role has no superuser, database/role creation, or public-schema creation privileges. An administrator query confirmed zero anonymous/authenticated Data API DML grants on all Django-owned tables.
- Connected through the actual dashboard-provided `aws-1-us-east-1.pooler.supabase.com` endpoint, using session mode for migrations and transaction mode for runtime. Certificate and hostname verification succeeded using the bundled public provider CA. Managed server version at the check was PostgreSQL 17.11.
- Applied all 19 migrations, including `0004_service_heartbeat`, to the new staging application database and the separate empty `pdc_recovery` database. Production migrations were not run.
- Created private bucket `staging-deliverables` with an independently verified 3,145,728-byte cap. Actual synthetic object write/read, private signed download and rejection of public-object access passed. The generated probe object was removed afterward.
- Saved and re-read 20 application/database/storage settings as Secret variables targeting **Preview + `fix/dev-team-release-gaps` only**. A before/after snapshot of production environment record IDs, targets, timestamps and value digests was unchanged. The backup encryption key is kept outside the web runtime. Credentials and temporary setup tooling remain ignored; recovery secrets are Windows-user encrypted.

## Managed backup and recovery

The initial full-database dump failed because the least-privilege migration role cannot lock Supabase's `auth` tables. Reproduced the permission error without broadening role permissions. Changed backups to explicitly include Django-managed public tables, automatic many-to-many tables and migration history, excluding provider schemas/unrelated tables. `--strict-names` prevents silently missing required tables. Legacy whole-database PostgreSQL bundles are rejected by current restore; recovery implications are in [operations](operations.md).

Created a real AES-256-GCM encrypted bundle from the staging managed database and referenced private original. Restored it into the separate managed `pdc_recovery` database and fresh `recovery/originals` object prefix. Actual verification passed for original SHA-256, preserved manual-review/report fingerprints, coordinator and owner-contributor private signed downloads, and denial of direct report/API/download IDs to an unrelated workspace.

This rehearsal used two explicitly synthetic workspaces and three `example.test` accounts with unusable passwords. Fixture verification state supports automated authorization testing; it does not prove real-user email verification. No real partner material, production records or customer account was restored or deleted. No mail worker ran on the recovery target. The source fixtures were retained.

The encrypted bundle is stored locally under ignored `.local-backups/staging-rehearsal`. This is a managed-provider restore rehearsal, not a scheduled off-site backup service. A durable off-site destination, separate key custody, backup schedule/retention and alert delivery remain launch requirements.

## Executed code checks

- Full SQLite suite: **125 tests, OK, three PostgreSQL-only skips, 92.312 seconds**.
- Full native PostgreSQL 17.12 suite: **125 tests, OK, no skips, 111.726 seconds**.
- New regressions cover exact HTTPS preview origins, explicit overrides, invalid/missing platform hosts, the PostgreSQL table allowlist and rejection of legacy whole-database archives before restore writes. The native PostgreSQL restore rehearsal now verifies unrelated provider-schema and public sentinel records remain unchanged.
- Ruff, Django system checks, migration consistency and diff whitespace checks passed. Local ignored logs: `.runtime/staging-final-sqlite-tests.log`, `.runtime/staging-final-postgres-tests.log`. The managed recovery result is in `.runtime/staging-recovery-status.json`.
- Hosted Linux CI passed for `493d7e5`: [quality and release checks](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/43820521414). This includes the workflow's PostgreSQL recovery and container build checks; it is not a full Compose HTTPS deployment rehearsal.

## Hosted preview and email handoff

- Deployment `dpl_Awo8KrJ7eoenSb3AcsjK6mSjeyPk` built commit `493d7e5` successfully as **Preview**, with separate staging services. Its URL is `https://partner-deliverables-checker-puux-a8asn1pc0-jello3.vercel.app`; Vercel authentication remains enabled. The stable branch alias is `https://partner-deliverables-checker-puux-git-fix-dev-tea-dfbb05-jello3.vercel.app`.
- The owner entered Gmail sender/app-password credentials through hidden local prompts. Actual STARTTLS SMTP authentication passed. Three additional Secret variables were saved only for this Preview branch. Neither the app password nor sender address is included in this record.
- A temporary project automation credential allowed authenticated HTTP tests without disabling deployment protection. Actual application responses, rather than a redirected Vercel sign-in page, were checked. `/health/`, signup and sign-in returned 200; the fingerprinted stylesheet returned 200. Readiness initially returned 503 without a dispatcher heartbeat, then 200 after the protected dispatcher executed.
- The hosted signup form acknowledged an account for the owner's mailbox, and its unverified sign-in attempt was rejected. Calling the staging dispatcher returned `{"delivered": 1}`. The owner subsequently confirmed inbox receipt and completed the email confirmation; an application database read independently confirmed the account's verified state. The generated test account credentials are stored locally with Windows-user encryption.
- Verified sign-in created a Secure, HttpOnly session. The new account initially had no memberships, then created `Staging acceptance workspace` through the actual HTTPS form and became its coordinator. Removing its last coordinator was rejected. Submitted selection of synthetic workspace 1, its package URL, report API and original-file download each returned 404 to this unrelated account.
- Orca's embedded browser rendered the actual hosted team settings and signup pages at 390px, 768px and 1200px. Screenshots were inspected at all three widths and document width measurements showed no horizontal overflow. The password-reset request page was also inspected at phone width. These checks are not a full WCAG or assistive-technology audit.
- A separate account using an owner-controlled Gmail plus alias was registered for the invitation exercise. Its verification, contributor invitation and the owner's password-reset message were handed to SMTP (`delivered: 3`). The owner confirmed alias verification; a staging database read independently confirmed both test accounts are active and verified. Invitation acceptance remains pending.
- Missing CSRF on signup returned 403; missing machine authentication on the mail endpoint returned 401. Responses included HSTS, frame denial and `nosniff`; the CSRF cookie was Secure. The CSRF cookie is intentionally readable by the client and is not an authentication session cookie.
- An authenticated comparison confirmed production deployment ID, production environment records and Vercel sign-in protection remained unchanged. No production mail dispatcher, migration or application write was performed.

## Reset delivery incident and automatic staging dispatch

At 13:57 UTC the owner reported an expired reset link and no replacement email.
The original reset was created at 07:11 UTC, exceeding the configured one-hour
timeout. The replacement request was present in staging at 13:55:23 UTC, unsent
with zero attempts; the last dispatcher heartbeat was still 07:11 UTC. This
confirmed an absent automatic dispatcher, rather than SMTP rejecting the message.
A protected manual dispatch handed the replacement to Gmail. The owner confirmed
receipt and completed the reset; an HTTPS request using the pre-reset session
then redirected to sign-in. New-password sign-in has not been independently run.

Configured the dedicated staging Supabase project with `pg_cron` 1.6.4, `http`
1.6 and the existing Vault extension. The `pdc-staging-mail` job calls the stable
protected branch alias every two minutes. Credentials reside in Vault and HTTP
headers, with certificate/hostname verification and bounded network timeouts.
No plaintext HTTP request queue is used. The previously temporary Vercel
automation credential is now retained as the staging scheduler credential;
revoking it requires stopping/reconfiguring the job. Setup, monitoring and pause
instructions are in [the scheduler runbook](staging-mail-scheduler.md).

Initial permission assertions identified Supabase-owned HTTP functions with
PUBLIC execution grants that `postgres` could not revoke. The job was paused
while resolving this. The final configuration removes `extensions` schema usage
from the unused anonymous/authenticated API roles and both application roles,
preserving provider service/dashboard grants. Metadata checks confirmed all four
roles lack networking schema/Vault access. Actual connections as `pdc_web` and
`pdc_migrator` returned insufficient-privilege errors for networking, decrypted
Vault reads and operator dispatch. No role was elevated to a provider superuser.

Executed scheduled evidence:

- Idle scheduled run: **14:04:00 UTC, succeeded**.
- An approved-owner test message was queued at **14:04:16 UTC**, initially unsent
  with zero attempts. With no further manual dispatch, the **14:06:00 UTC** job
  succeeded and recorded SMTP acceptance at **14:06:01 UTC**, one attempt, about
  105 seconds after enqueue. Its heartbeat updated at the same time.
- Actual protected `/ready/` returned 200. Inbox receipt of this specific automatic
  test message has not been independently confirmed; earlier owner verification
  and fresh reset receipt were confirmed directly by the owner.
- Ruff and diff checks passed for this follow-up. The complete 125-test suites
  above preceded these provider SQL/documentation changes; they were not rerun
  locally for this follow-up.

This configures staging only. The production GitHub dispatcher remains disabled;
its pending messages were not sent. The app's one-hour reset expiry was retained.

## Remaining acceptance

Remaining new-password sign-in/invitation/file flows, independent alert delivery,
off-site backup operations and approved production scheduling still require
execution. Staging readiness depends on dispatcher activity within 900 seconds;
two-minute scheduling is now exercised, without a delivery SLA. Server-side
rejection of non-TLS database connections has not been verified, although the
exercised clients enforce certificate and hostname verification. No production
promotion or public-launch approval is implied by this setup. Do not copy
production services into the preview or weaken verification/readiness to bypass
a missing service.
