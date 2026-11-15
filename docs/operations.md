# Migration, recovery and operator procedures

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

## Encrypted offline backup

Use a trusted external runner with network access to the database/object store and the same application version/settings. PostgreSQL needs matching `pg_dump`/`pg_restore` clients; override their executable paths with `PG_DUMP` and `PG_RESTORE` if needed. The Vercel web function is not the backup runner.

Generate and securely store a separate random 32-byte base64-url-safe `BACKUP_ENCRYPTION_KEY`. Keep it outside the repository and outside the backup destination; retain the correct old key when rotating. Without the key, recovery is impossible. Bundles contain account data, private files, sessions and possibly unexpired email tokens. Restrict destination/key access and maintain encrypted off-site copies.

Stop **all** web, worker and maintenance writers first. `--traffic-paused` is an operator assertion, not an automatic lock across remote function instances. A `pg_dump` alone is internally consistent for the database but cannot prevent a simultaneous original-file replacement/deletion. For Vercel, use a controlled maintenance/protection procedure and stop the external mail dispatcher; provider-native snapshots plus bucket versioning are another option only after a consistent restore is proven.

```bash
python manage.py backup_bundle --directory /secure/backups --traffic-paused --retention-days 30
```

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

Run `python manage.py maintain_data` daily (or configure the protected `POST /ops/maintenance/` scheduler) to remove expired rate buckets and security/mail records older than seven days. It keeps original files, revisions, reports and audit history by default. An explicit `--audit-retention-days N` of at least 30 enables audit-event retention; choose and publish that policy first.

`python manage.py reconcile_files` reports unreferenced objects older than a day. Review it before using `--delete`. Grace time protects in-flight uploads; storage-prefix access must be limited to this application. S3 versioned deletion/retention and provider costs are separate policies. File cleanup failures are logged without original contents and require follow-up.

Alert on non-200 readiness, old pending/exhausted mail jobs, SMTP rejection, backup age/failure, high storage/connection usage and HTTP 5xx. Application request logs omit URL tokens and bodies; platform/proxy logs need their own redaction, access and retention settings. Record the version, configuration changes, verified restore and observed capacity for each release.
