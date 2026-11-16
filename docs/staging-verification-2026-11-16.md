# Isolated staging: 16 November 2026

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

## Remaining acceptance

Email sender/app-password entry, actual recipient delivery, branch deployment/readiness, hosted account/workspace flows, protection/monitoring and operational scheduling must be recorded after execution. No production promotion or public-launch approval is implied by this setup. Do not copy production services into the preview or weaken verification/readiness to bypass a missing service.
