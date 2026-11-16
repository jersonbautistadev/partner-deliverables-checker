# Dev-team fixes: 16 November 2026

This is the implementation checkpoint before live staging setup. For current 125-test, hosted CI, managed recovery and owner email evidence, use the [subsequent staging record](staging-verification-2026-11-16.md). Statements below about unexecuted provider/container checks describe this earlier checkpoint.

Branch: `fix/dev-team-release-gaps`, based on `e3280e4`. Implements the repository fixes from the [dev-team audit](dev-team-audit-2026-11-16.md), following `D:\Programming\Skills\dev team\dev-team-playbook.md`. Production configuration, accounts, mail jobs and originals were not changed. No production migration, real email, paid resource or public release was performed.

## Changes and acceptance evidence

| Audit issue | Implementation | Verification |
| --- | --- | --- |
| A2: username throttle normalization | Username identities use bounded NFKC normalization matching Django. Email normalization remains separate. IP and account buckets stay enforced. Retry advice reports the longer active block, even when both buckets block. | Equivalent ASCII/fullwidth logins remain 429 after exhausting the account bucket, including after the IP bucket fills; session stays unauthenticated. Fixed-clock reset boundary tested. |
| A3: PostgreSQL backup CA | `pg_environment()` supplies configured `sslrootcert` to libpq as `PGSSLROOTCERT`, overriding a conflicting inherited CA, without reducing `verify-full`. With no application CA, runner libpq configuration remains available. CI's client wrapper forwards/mounts the CA path. | Explicit/inherited CA regressions pass; complete local PostgreSQL encrypted recovery still passes. Managed-provider backup/restore remains unverified. |
| A4: storage outages | A narrow storage exception produces generic HTML/JSON 503 responses for report reads and download preparation. Missing objects remain missing/404. Replacement rollback preserves the old file/report when checking the replacement fails. | Filesystem and botocore report failures, file-open failure, signing failure, cross-team signing denial, replacement rollback, and recovery tested. Failures after a download stream has begun cannot retroactively change HTTP status. |
| A5: readiness | Production requires valid SMTP settings and a recent persistent dispatcher heartbeat, including while idle. Stale/exhausted mail also fails readiness. Logs use fixed dependency categories, without provider exception text. Health GETs never send mail. | Missing configuration, missing/stale/renewed heartbeat, recent/stale/exhausted/completed queue entries and recovery tested. No health call sent email. |
| A6: dashboard cost | Batch latest report summaries; no report writes or object-store requests on the dashboard. Flag known package/requirement/engine changes and absent reports. Date summaries and explicitly describe their freshness. Paginate attention/passed lists at 20 rows. Explicit reports retain authoritative checking. | Warm dashboard: **25 SQL statements and zero storage checks** at both 10 and 30 packages, versus audit baseline 92 SQL / 10 storage calls at 10 packages. Pagination, changed requirements, new/engine-stale reports and isolation tested. This is local request-count evidence, not hosted capacity or latency evidence. |
| A7: copy | Upload error uses the configured size formatter; throttled responses give the actual remaining bucket wait. | Three-MiB configuration and fixed-clock retry tests pass. |
| A8: Compose TLS | Shared environment forwards `EMAIL_USE_SSL` and the mail health interval. | Source reviewed; Django production fixture checks pass for STARTTLS and implicit TLS. Docker unavailable, so container execution remains unverified. |
| A9: documentation | Current evidence pointers and explicit historical audit/verification records; rollout, heartbeat, snapshot freshness and CA handling documented. | Documentation/diff reviewed. |

Dashboard summaries intentionally describe the last report. Opening a report is still required to detect out-of-band changes in private storage. Summary classification reads latest report metadata for visible packages within workspace limits; large-workspace hosted performance still needs measurement. Requirements, report fingerprints, manual review behavior, tenant ownership and private-download authorization are preserved.

## Executed final checks

- Fresh Python 3.12 runtime environment installed all 23 pinned packages from `requirements.txt` with `--require-hashes`; `pip check` reported no broken requirements. Deployment manifest remains byte-identical to `requirements.lock`.
- **Fresh-runtime SQLite: 120 tests, OK, 3 PostgreSQL-only skips, 83.131 seconds.**
- **Native PostgreSQL 17.12: 120 tests, OK, no skips, 102.436 seconds.** Includes concurrent quotas/last-coordinator protection, legacy migration and actual encrypted database/original-file recovery with restored downloads.
- Ruff, Django system check, migration consistency, static collection, and `git diff --check` passed. The runtime advisory scan found no known vulnerabilities at execution time; that is not a security certification.
- `check --deploy --fail-level WARNING` passed using non-secret production fixture settings with both supported SMTP TLS modes. Fixtures did not authenticate an email provider or prove live settings.
- Orca inspected the local fictional demo dashboard at **390px phone, 768px tablet and 1200px desktop**. Corrected crowded timestamps and inspected the resulting screenshots. DOM width checks found no horizontal document overflow at these widths. Tab navigation showed a 2px solid focus outline; Enter opened a report. The report was also inspected at phone width. This was not a complete WCAG or screen-reader audit.
- Initial dedicated diagnostics in the audit reproduced A2-A5 before fixes. Their scenarios are now maintained regressions. Some initial verification attempts needed corrections: the baseline local PostgreSQL port was 5432, an upload-copy assertion needed Django's nonbreaking space, and the legacy readiness test needed explicit development settings for its file-mail fixture. Production readiness assertions remain strict.

Final ignored logs: `.runtime/fix-clean-install.log`, `.runtime/fix-clean-sqlite-tests.log`, `.runtime/fix-final-postgres-tests.log`. Screenshots were inspected from Orca's temporary screenshot directory and are not production artifacts. Earlier `.runtime/fix-*-tests.log` files are intermediate checks. No credentials or test databases are included in Git.

## Changed files

- Authentication/error handling: `checker/security.py`, `checker/middleware.py`, `checker/storage.py`, `checker/services.py`, `checker/views.py`.
- Mail/operations: `checker/checks.py`, `checker/mail.py`, `checker/models.py`, `checker/operations.py`, `checker/migrations/0004_service_heartbeat.py`, `config/settings.py`.
- Worklist: `checker/worklist.py`, `templates/checker/dashboard.html`, `templates/checker/package_row.html`, `templates/checker/worklist_pagination.html`, `static/app.css`.
- Regressions: `checker/tests_public.py`, `checker/tests_recovery.py`.
- Deployment: `.env.example`, `compose.yaml`, `.github/workflows/ci.yml`.
- Documentation: this record, `docs/dev-team-audit-2026-11-16.md`, `docs/architecture.md`, `docs/deployment.md`, `docs/operations.md`, `docs/verification.md`, `docs/release-readiness.md`.

## Rollout and rollback

Review the branch and CI before merge. Use a protected staging deployment with separate database, bucket/prefix, origin, secrets and safe email destinations. Apply migration `0004_service_heartbeat` with the migration role before starting the updated app/worker. It creates only operational state and is reversible; existing records and files are unchanged. Verify runtime grants on the new table. A new production-mode deployment remains unready until the configured dispatcher records fresh activity. Do not weaken readiness to make an unconfigured deployment green.

Roll back app and worker together; leaving the additive unused table in place is preferable to reversing it during an incident. If reversing later, it drops only heartbeat state. Managed recovery targets must remain isolated/offline until queue/tokens have been reviewed; never send restored real-user messages as an accidental rehearsal side effect.

## Remaining external gates

1. **Email:** owner completes private provider credentials/sender setup, then approve a real-recipient test of signup, verification, invitations and password reset. Enable dispatch only after that test; measure receipt, retries and queue drainage. Current pending production emails were left untouched.
2. **Managed disaster recovery:** select a trusted backup runner and off-site encrypted destination, secure the separate key, define data-loss/recovery objectives, and authorize a restore into a separate managed database/private bucket. Local recovery and CA tests do not prove provider-role/schema compatibility.
3. **Hosted operations:** configure and actually test uptime, queue/dispatcher, storage and backup-age alerts; measure expected hosted load/capacity. Verify the exact deployed revision and repeat the real account/workspace flows at phone/tablet/desktop sizes.
4. **Optional Compose target:** build/run containers and rehearse proxy/TLS/permissions if that target is selected. Docker was unavailable here. No claim of Linux container verification is made.

**Decision:** repository fixes are verified locally and suitable for staging review. Public launch remains **no-go** until real email, managed recovery, operational monitoring and hosted acceptance gates pass. A branch push is not public-launch approval.
