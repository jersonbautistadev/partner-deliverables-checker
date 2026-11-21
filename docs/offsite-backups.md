# Private off-site backups and failure alerts

This covers operator configuration, separate from public launch approval.
Staging acceptance and the current production checkpoint are distinguished in
[the rollout record](records/production-rollout-2026-11-18.md). Never apply a staging-only
scheduler SQL file or its source credentials to production.
The web function does not receive backup credentials or the encryption key.

## Production setup and recovery

The `production-backup` Actions job uses its own `PRODUCTION_*` secrets: runner
Django key, migration-role database URL, source S3 access/secret keys, AES key,
destination S3 access/secret keys and private backup Healthchecks URL. Repository
variables supply `PRODUCTION_BACKUP_REF`, destination endpoint/region/bucket and
`ENABLE_PRODUCTION_BACKUP`. Keep the gate false until privacy/retention/source
guards pass. The production file prefix is `production/`, with a separate 3 GiB
budget; staging and production still share the account-wide free allowances.

`deploy/production-operations.sql` is installed with the dedicated production
provider administrator after backup/migration checks. It installs **five paused
jobs**. Provision these Vault names privately before invoking functions:

- `pdc_production_origin`, `pdc_production_ops_secret`,
  `pdc_production_vercel_bypass`.
- `pdc_production_readiness_ping`, `pdc_production_maintenance_ping`,
  `pdc_production_capacity_ping`.
- `pdc_production_actions_token`, `pdc_production_backup_ref`.

The shared project-scoped automation bypass and repository-scoped Actions token
must be rotated in both environments together. Source/database/S3/AES/destination
credentials are separate. Never put credentials in SQL source or command history.
Verify application-role/Vault/networking denials after installation. Invoke and
check actual acknowledgements before activating each corresponding job. Re-running
the installation pauses all five again: inspect state and restore only jobs that
have passed verification. Check runner results and bundle read-back separately;
a successful GitHub dispatch is not a successful backup.

All five production jobs are active after the owner's separate retention
approval. Actual mail/readiness cron succeeded from 12:08 UTC on 18 November;
the actual maintenance endpoint and independent monitor passed at 12:30 UTC.
Its first normal daily cron execution is still in the future. Do not infer state
from the paused-by-default SQL file. See [production acceptance](records/production-acceptance-2026-11-18.md)
for live file/backup/recovery results and current limits.
The app's Production-only `OPS_SECRET` and Vault's `pdc_production_ops_secret`
must hold the same credential. On rotation, pause affected jobs, update both,
rebuild the protected app, and prove an authenticated request succeeds before
resuming schedules. Metadata existence and a valid credential length do not
prove authentication; acceptance found and corrected this mismatch.
Maintenance deletes expired sessions/rate windows, old tokens/queued-mail records
and its own cron logs older than seven days; it does not delete account/workspace
history or original files. Review/approve this production retention action before
enabling it. Audit pruning and orphan-file deletion are separate opt-in actions.

For recovery, retrieve the exact object version from the receipt and verify its
ciphertext digest, inject the matching AES key outside the storage service, create
a **new** isolated managed database and empty private-file prefix, migrate it with
the matching source version, then use `restore_bundle --confirm-empty`. Read all
application tables with the ordinary runtime role and exercise authorized original
downloads. Keep mail, provider cron and restored sessions offline until reviewed.
Never restore over the source or an earlier recovery rehearsal. A zero-original
bundle proves database recovery only; use an actual original-file bundle for the
download acceptance gate.

## Services and limits

Backblaze B2 provides the encrypted off-site destination; Healthchecks.io provides
independent missed-job alerts to the same Gmail mailbox used for staging. The
owner completed both free signups privately. Provider terms and quotas can
change: review [B2 pricing](https://www.backblaze.com/cloud-storage/pricing) and
[Healthchecks pricing](https://healthchecks.io/pricing/) before increasing usage.
No payment card or paid plan was added by this setup.

The staging bucket is private, in `us-east-005`, with provider encryption enabled
and Object Lock disabled. The observed Caps & Alerts page showed $0 daily storage
(10 GB), $0 download bandwidth (1 GB), 2,500 daily Class B and Class C operations,
and owner email alerts enabled. These provider caps can stop backups and restores;
they are not a guarantee of unlimited free operation. Recheck them before launch.

`BACKUP_STORAGE_LIMIT_BYTES=3221225472` reserves at most 3 GiB for the staging
prefix. Inventory includes hidden versions. Serialize publishers for a prefix;
the Actions concurrency group does so for that runner. Other buckets, manual
publishers, provider lifecycle delays and downloads consume account-wide quotas.
The backup job refuses growth beyond its budget rather than deleting prior
backups to make room. Alert on failure and inspect retention or reduce usage.

Retention hides each backup after seven days and deletes its hidden version one
day later. The provider runs lifecycle processing asynchronously. S3 exposes an
additional paired orphan-marker rule; preflight requires the matching prefix.
The account owner configured the rule through the B2 console. Do not mix console
and S3 lifecycle editors: see [B2 lifecycle API mapping](https://www.backblaze.com/apidocs/s3-put-lifecycle-configuration).

## Capture and verification

Use the runtime dependency lock and matching PostgreSQL 17 client. Inject the
runner-only variables in [backup.env.example](../deploy/backup.env.example) through
a secret store, never a checked-in `.env` or CLI arguments. The source DSN uses
the migration role and session pooler with `sslmode=verify-full` and the checked-in
public CA. Keep this trusted runner separate from the ordinary web runtime.

```bash
python manage.py backup_offsite --directory /secure/temporary-backups
```

The command checks bucket privacy, retention and retained bytes, captures a
coordinated PostgreSQL snapshot, verifies each original's digest and encrypts the
archive with AES-256-GCM. It authenticates the resulting encrypted bundle before
upload, checks the returned object version and metadata, then downloads that
version fully and compares its ciphertext SHA-256. Only after these checks does
it send an empty success ping. The receipt contains the object key, version,
length and ciphertext digest; it contains no key or original contents.

Source/table locks end before cloud upload and encryption. Any capture/session
failure prevents publication. Remote verification failure leaves the previous
backups intact and signals failure. A monitoring acknowledgement failure makes
the command fail even if its backup is valid. Runner crashes or unavailable
networks are covered by missed-job monitoring. Temporary plaintext must stay on a
trusted, access-controlled runner; GitHub-hosted runners are ephemeral. Do not
upload plaintext or encrypted bundles to public Actions artifacts.

The staging application key is restricted to this bucket and `staging/`, expires
after 90 days, and must be rotated before **15 February 2027**. Console-generated
Read and Write keys include deletion and some bucket capabilities; this key is
not append-only. The publisher makes no delete calls, but stolen credentials can
still threaten retained copies. Object Lock/WORM protection was not enabled or
verified. Prefer a custom minimal-capability key when provisioning a production
account; verify its actual ACL/lifecycle/list-version/read/write API access.

Keep `BACKUP_ENCRYPTION_KEY` outside B2 and the web runtime. Staging retains it in
GitHub's encrypted Actions secret store as well as a local Windows DPAPI copy.
The hosted runner used that stored key to create a B2 bundle that independently
decrypted with the recovery copy, verifying matching key custody across machines.
Maintain GitHub account recovery and preferably an additional owner-controlled
password-manager/offline copy. A DPAPI-only copy is insufficient. Keep an old key
while its backups remain retained. Losing every usable key makes recovery impossible.

## GitHub runner and nightly dispatch

The existing `mail-delivery.yml` workflow has a separate staging-backup job.
It runs only on manual dispatch at `STAGING_BACKUP_REF` with
`ENABLE_STAGING_BACKUP=true`. Its source guard refuses a database other than the
dedicated staging source. `STAGING_*` variables and secrets supply the source,
backup credentials and private backup-check URL. Production mail dispatch remains
separately gated. No default-branch edit is required for a manual branch run.

The staged [nightly dispatcher](../deploy/staging-backup-cron.sql) uses the
already-registered workflow at `feat/linked-evidence-coverage`. This staging ref
must contain the evidence models so application-scoped dumps include their tables.
Keep `STAGING_BACKUP_REF` and the installed staging dispatcher aligned when changing
the reviewed ref; preserve the branch until both move. Production is configured
independently: since 21 November 2026 its `PRODUCTION_BACKUP_REF` and Vault
`pdc_production_backup_ref` are both `main`. Provision a dedicated
expiring **fine-grained GitHub token**, repository selection limited to this
repository, **Actions: read/write** only (plus GitHub's required metadata read).
Keep it in Supabase Vault. Never copy a general Git credential or account-wide
token into the scheduler. GitHub's [dispatch endpoint](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
requires Actions write; API version `2026-03-10` returns the dispatched run ID.

SQL installs `pdc-staging-backup` paused, at **18:17 UTC / 02:17 Asia/Manila**.
First verify the pushed workflow, restricted token, role denials and a manual
function invocation. Inspect the actual Actions run, B2 receipt and independent
success heartbeat before activating the job. A dispatch acknowledgement alone is
not a completed backup. If the reviewed branch is removed, retarget and rehearse
the workflow and dispatcher together. Disabling the cron job or repository
variable stops new runs without deleting backups. Token expiry/invalid settings
must produce a missed-backup alert.

On 17 November the operator completed both a manual dispatch and an actual timed
cron dispatch. Both hosted backup jobs succeeded and their B2 bundles were
independently authenticated/decrypted and all five originals checked. The daily
schedule above is now **active** for staging. This is evidence of the timed
rehearsal, not a claim that future nightly runs already occurred. Both the B2 key
and fine-grained GitHub token expire **15 February 2027**; rotate them beforehand.

## Independent monitoring and recovery

`PDC staging readiness` expects a successful check every two minutes, with four
minutes of grace. Its private [SQL function](../deploy/staging-readiness-cron.sql)
checks the actual protected branch's `/ready/` JSON. Readiness includes SQL,
private-store reachability, SMTP configuration, worker heartbeat and pending-mail
age. It sends no app response, email, credentials or logs to Healthchecks. The
monitor receives only empty POST pings. A failed check signals failure; a stopped
Supabase scheduler is detected through missing pings.

`PDC staging encrypted backup` expects one completed backup per day, with two
hours of grace. Its independent check URL is a secret. A separate 60-second
`PDC staging alert delivery drill` is used for a missed-ping exercise; pause that
check after confirming failure and recovery notifications. Never pause real mail
delivery just to test alert receipt. Inspect provider integrations to confirm the
verified owner address, rather than assuming an API ping proves email receipt.

For recovery, retrieve the exact object version and receipt over verified HTTPS,
check its ciphertext digest, then follow [the offline restore procedure](operations.md#restore-rehearsal)
using the separate decryption key, a fresh migrated database and empty private
prefix. Keep restored workers, cron and public traffic off. Refresh reports,
compare original hashes and actual authorized downloads for both roles, and
test unrelated-workspace denial before opening traffic. Provider cron/Vault
configuration is deliberately absent from application backup bundles and must be
reprovisioned separately. Review outstanding sessions, links and mail queue state.

Executed results and remaining operational gates are recorded in the
[17 November evidence](records/staging-verification-2026-11-17.md). Configuration files
alone do not prove scheduling, receipt or restoration.
