# Migration, recovery and operator procedures

The protected Supabase staging deployment uses a [two-minute mail scheduler](staging-mail-scheduler.md).
Its provider configuration and credentials are deliberately separate from production and application backup bundles.

## Releasing changes

`main` is protected: changes land through a pull request whose `test` and
`migration-gate` checks pass. Vercel deploys every commit on `main` to production
straight away, so a merged pull request is a release. Merge stacked branches in one
step; merging them one at a time deploys each intermediate commit.

### Releasing a change that includes a migration

Production code goes live on merge, but migrations are applied by an operator. Keep
each migration backward compatible with the code currently in production (expand
first: add nullable columns or columns with database defaults, add tables; drop or
tighten only in a later release). Then:

1. Take and verify an encrypted production backup (see below).
2. Apply the migration with the migration role from the pull request's branch.
3. Verify runtime grants on any new table (`pdc_web` needs SELECT/INSERT/UPDATE/DELETE).
4. Add the `migration-applied` label to the pull request; `migration-gate` then passes.
5. Merge, wait for the production deployment, and run the smoke checks.

The gate is a reminder enforced by CI, not proof: it checks the label, not the
database. If a migration cannot be made backward compatible, use an explicit
production-target deployment without the public domain, migrate, smoke-test, and
promote (as recorded in the 21 November evidence rollout).

## Legacy single-team migration

Take a database **and originals** backup and pause traffic before `migrate`. Migration 0002 creates a legacy workspace if legacy accounts/data exist, assigns existing partners and audit events, and converts Coordinator/Contributor groups into memberships. Superusers receive a coordinator membership in that legacy workspace only. Users without a team role remain without membership. Existing package IDs, paths, revisions, snapshots, fingerprints and review decisions are not rewritten.

Every existing user gets an Account record. Email is normalized; duplicate/missing emails remain unresolved rather than being marked verified. Existing email ownership is not assumed. An operator must confirm the intended destination with the person, then queue verification:

```bash
python manage.py set_account_email USERNAME user@their-address.example
python manage.py send_mail_queue --once
```

The person confirms the link and signs in with the original username/password. Password reset becomes available after verification. Recover the coordinator first. Global groups no longer authorize application requests. A superuser has no blanket workspace bypass. If a legacy team has no active coordinator, a trusted database/operator intervention must establish the intended member; do not provide a public coordinator-claim endpoint.

The data migration is intentionally irreversible through Django's reverse migration operation. Once multiple workspaces or new accounts exist, flattening them into the old model could leak or lose data. To roll back, stop traffic and restore the pre-migration paired backup and matching old application version. Test this in an isolated environment. A new migration filename or successful local run is not a production rollback rehearsal.

`python scripts/rehearse_migration.py` creates a temporary database at schema 0001, inserts legacy accounts/groups, duplicate emails, a file reference, snapshot, review, report and audit event, migrates forward and checks preservation. It never changes the development database.

## Account administration

Coordinators manage invitations and roles in Team settings. Promote a second active verified coordinator before transferring/removing the last one. Membership removal retains owned packages; remaining coordinators can access those packages. Self-deactivation requires the password, blocks the last coordinator, disables the user and removes memberships. Account/email/history remain under the documented retention policy; reactivation or identity corrections require a trusted operator.

The operator CLI for a newly provisioned account requires explicit workspace and email:

```bash
python manage.py create_team_user USERNAME --workspace WORKSPACE_ID --email user@example.test --role Contributor
```

The password is prompted and validated; verification is still required. Do not pass passwords as CLI arguments. Do not hand an operator shell or Django superuser credentials to team coordinators.

## Encrypted backup

Use a trusted external runner with network access to the database/object store and the same application version/settings. PostgreSQL needs matching `pg_dump`/`pg_restore` clients; override their executable paths with `PG_DUMP` and `PG_RESTORE` if needed. The Vercel web function is not the backup runner.

Backup and restore clients receive the configured database `sslmode` and `sslrootcert` as `PGSSLMODE` and `PGSSLROOTCERT`. The explicit application CA takes precedence over an inherited libpq CA; when none is configured, libpq's runner configuration remains available. The CA path must exist inside the runner/container. Keep `verify-full` for the managed provider; do not weaken it to repair a missing certificate. Local recovery tests do not prove managed-role permissions or managed-provider schema restoration.

PostgreSQL bundles now include only tables belonging to installed, managed Django models, their automatic many-to-many tables, and `django_migrations` in the public schema. The strict table list excludes Supabase's internal schemas and unrelated public tables; it also fails if a required application table is absent. Provider Auth/Storage metadata is not application data: referenced original bytes are bundled separately. Additional tables introduced outside Django's managed models need explicit backup support before use.

Current PostgreSQL bundles declare `database_scope=django-public-tables`. Restore rejects older whole-database PostgreSQL bundles before database/file writes, because those archives may contain provider-owned objects. To recover an old bundle, use its matching old application version in an isolated standalone PostgreSQL instance, inspect it, apply current migrations, and create a current application-scoped bundle. Never restore a legacy whole-database archive into Supabase. Existing SQLite bundles are unaffected. See the [managed staging rehearsal](records/staging-verification-2026-11-16.md) for executed evidence.

Migration `0004_service_heartbeat` is additive and reversible. Roll back application/worker code together before considering reversal; dropping this new table removes only operational heartbeat state. Prefer leaving an unused table during an application rollback. The current worker writes `ServiceHeartbeat(name="mail")` after each completed batch, including an empty batch. A restored database's heartbeat is historical: keep restored mail workers disabled until the queue/tokens are reviewed, then require fresh worker activity before reopening traffic. Do not dispatch old real-user emails during a restore rehearsal.

Migration `0005_obligation_evidence` adds evidence history, requirement metadata and
explicit review outcomes; it does not rewrite existing accounts, original paths,
requirement revisions, reports or review fingerprints. Existing requirements default
to unspecified responsibility and required applicability. Apply it to a protected
staging database before deploying the new code there. Existing runtime SQL grants
may name tables explicitly: grant the runtime role SELECT/INSERT on the new
`checker_evidence` table and USAGE/SELECT on its sequence as appropriate; rehearse
using the runtime role rather than assuming the migration owner's rights apply.

Before production rollout, take and verify an encrypted database/private-file backup,
apply the migration with the migration role, verify runtime grants, then deploy the
matching web/worker code and run acceptance checks. Do not run old code after creating
new evidence requirements or non-applicability decisions: it does not understand
their semantics and may misstate coverage. Code-only rollback is safe before those
new records are written. After adoption, prefer a forward fix or restore the paired
pre-change database/files under a controlled outage; obtain explicit approval for
destructive production recovery. Reversing the migration drops evidence/outcome
fields and loses that history, so it is not an ordinary rollback procedure.

Include the backup runner in that version change: update both
`PRODUCTION_BACKUP_REF` and Vault's `pdc_production_backup_ref` to the reviewed
code containing `Evidence`, then verify a real production backup before allowing
new evidence writes. The older runner discovers tables from its installed models
and would omit the new evidence table. Staging has a separate repository variable
and installed dispatcher ref; changing one environment must not change the other.

The tested feature Preview is bound to staging services. Build a separate
**Production-target deployment with Production environment variables**, initially
without assigning the public domain. Verify its bindings and smoke checks before
moving the public alias. Do not promote the staging-bound Preview artifact directly
to the public domain. Require the owner's explicit public-rollout approval before
the production migration, runner-ref change and alias switch.

Generate and securely store a separate random 32-byte base64-url-safe `BACKUP_ENCRYPTION_KEY`. Keep it outside the repository and outside the backup destination; retain the correct old key when rotating. Without the key, recovery is impossible. Bundles contain account data, private files, sessions and possibly unexpired email tokens. Restrict destination/key access and maintain encrypted off-site copies.

Choose one consistency mode. SQLite and older releases require **all** web,
worker and maintenance writers to stop first. `--traffic-paused` is an operator
assertion, not an automatic lock across remote function instances. A `pg_dump`
alone cannot prevent simultaneous original-file replacement or deletion.

```bash
python manage.py backup_bundle --directory /secure/backups --traffic-paused --retention-days 30
```

Current PostgreSQL releases also support coordinated capture without stopping
mail delivery:

```bash
python manage.py backup_bundle --directory /secure/backups --lock-assets --retention-days 30
```

This requires a session connection and an autocommit command outside any enclosing
transaction. A PostgreSQL SHARE lock on the Asset table blocks original-file
writes and deletions while the database dump and referenced bytes are captured;
ordinary reads continue. Uploads/replacements/removals can wait during this
interval, so schedule quiet periods and monitor duration. Acquisition times out
after ten seconds. A lost lock/session aborts before encryption or publication.
Do not run migrations, external file cleanup, direct object-store edits or other
out-of-band writers during capture. Application roles must not bypass the normal
transactional file services. SQLite refuses this mode. The separate
[off-site command and runner](offsite-backups.md) use this PostgreSQL mode.

The command bundles the database and every referenced original after checking its digest, then encrypts using streaming AES-256-GCM. A successful new bundle is required before matching local bundles older than the retention period are removed. Failure does not delete an existing backup. Local output and key must be copied/stored according to the off-site policy; this command does not create cloud accounts or an off-site destination.

## Restore rehearsal

Use an isolated, fresh database and empty private directory/bucket prefix, with no users or workspaces. Inject the matching key and target settings. Keep traffic closed. Database vendor must match the bundle; PostgreSQL bundles need a compatible client/server.

```bash
python manage.py migrate --noinput
python manage.py restore_bundle /secure/backups/pdc-TIMESTAMP.pdc --confirm-empty
python manage.py migrate --noinput
python manage.py check --deploy --fail-level WARNING
```

The encrypted payload is authenticated before database/storage writes. Paths and file digests are checked without extracting arbitrary archive paths. Restoring is not transactional across SQL and object storage: on any failure keep the partial target offline, discard that rehearsal target, and retry into a fresh target. Never restore over live users. Verify actual original bytes/downloads, a refreshed report, both roles, another team's denial, invitation state and email queue state before admitting traffic. Restored outstanding tokens/queued mail may need revocation; do not accidentally send old real-user messages during a rehearsal.

Executable local exercises:

```bash
python scripts/rehearse_recovery.py
# With POSTGRES_HOST/PORT/USER/PASSWORD and matching PG_DUMP/PG_RESTORE clients:
python scripts/rehearse_pg_recovery.py
```

The PostgreSQL exercise requires permission to create temporary databases and removes only its own randomly named rehearsal databases. Both exercises restore original downloads and check permitted roles and cross-workspace denial. They are not evidence of a remote provider/off-site recovery until repeated there.

## Maintenance and monitoring

Daily maintenance also prunes superseded reports: each package keeps its latest 10
check runs, and older runs past 30 days are deleted. Reports are reproducible
snapshots; reviews store their own keys and are never pruned.


Run `python manage.py maintain_data` daily (or configure the protected `POST /ops/maintenance/` scheduler) to remove expired rate buckets and security/mail records older than seven days. It keeps original files, revisions, reports and audit history by default. An explicit `--audit-retention-days N` of at least 30 enables audit-event retention; choose and publish that policy first.

`python manage.py reconcile_files` reports unreferenced objects older than a day. Review it before using `--delete`. Grace time protects in-flight uploads; storage-prefix access must be limited to this application. S3 versioned deletion/retention and provider costs are separate policies. File cleanup failures are logged without original contents and require follow-up.

Alert on non-200 readiness, old pending/exhausted mail jobs, SMTP rejection, backup age/failure, high storage/connection usage and HTTP 5xx. Application request logs omit URL tokens and bodies; platform/proxy logs need their own redaction, access and retention settings. Record the version, configuration changes, verified restore and observed capacity for each release.
