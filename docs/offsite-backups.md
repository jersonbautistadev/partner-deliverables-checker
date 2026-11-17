# Private off-site backups and failure alerts

This is staging operator configuration, separate from public launch approval.
The web function does not receive backup credentials or the encryption key.

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

Keep a recovery copy of `BACKUP_ENCRYPTION_KEY` outside both B2 and this laptop,
for example in the owner's password manager. Keep an old key while its backups
remain retained. A DPAPI-only copy on one Windows machine is insufficient for
disaster recovery. External recovery-key custody must be confirmed before launch.

## GitHub runner and nightly dispatch

The existing `mail-delivery.yml` workflow has a separate staging-backup job.
It runs only on manual dispatch at `STAGING_BACKUP_REF` with
`ENABLE_STAGING_BACKUP=true`. Its source guard refuses a database other than the
dedicated staging source. `STAGING_*` variables and secrets supply the source,
backup credentials and private backup-check URL. Production mail dispatch remains
separately gated. No default-branch edit is required for a manual branch run.

The staged [nightly dispatcher](../deploy/staging-backup-cron.sql) uses the
already-registered workflow at `fix/dev-team-release-gaps`. Provision a dedicated
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
[17 November evidence](staging-verification-2026-11-17.md). Configuration files
alone do not prove scheduling, receipt or restoration.
