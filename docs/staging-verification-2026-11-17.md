# Staging acceptance and operations: 17 November 2026

Branch: `fix/dev-team-release-gaps`. This extends the
[16 November record](staging-verification-2026-11-16.md). Main and production were
not changed. App acceptance used the protected immutable preview for `493d7e5`;
application/runtime files matched `f05730c`. New operator work below is separate
from that deployed app and does not establish public-launch readiness.

## Actual hosted account and workspace acceptance

The owner received verification/reset emails and completed those flows privately.
Automatic staging dispatch processed subsequent reset requests on its two-minute
schedule. After forgetting the reset password, the owner requested another,
reported its delayed arrival, then signed in. The agent observed the coordinator
workspace and used that authorized session for HTTPS acceptance checks. No new
password was read, recorded or supplied by the agent.

The invitation received in Gmail preserved its destination through Brave sign-in
with the verified plus-alias account. **Join workspace** opened Packages as
Contributor. Database reads confirmed one membership and the consumed invitation.
Reusing the link displayed the generic expired/used/wrong-address error without
creating another membership.

| Actual authenticated HTTPS scenario | Observed result |
| --- | --- |
| Contributor GET audit; POST read-only audit | 403; 405, preserving the method contract |
| Contributor partner/requirement creation, invitation POST | 403 |
| Contributor settings | No invitation/membership-edit controls |
| Unrelated package, report API and original download | 404 |
| Contributor accessing another owner's package in the same workspace | Page/API 404 |
| Submitted partner/owner IDs outside membership | Invalid choices; contributor owner override ignored |
| Promote another coordinator, demote original coordinator | Permissions changed immediately |
| Demote last coordinator; contributor self-promotion | Blocked |
| End of role exercise | Original roles restored and checked |

Dedicated staging has three workspaces and five accounts, including the original
unusable-password recovery fixtures. Fictional Campus Current and DevLoop Journal
content/rules came from existing demo content. No demo seeding command ran
against staging/production; no deadline, logo or publishing claim was invented.

## Actual hosted file, finding and review acceptance

- Six initial missing findings linked their actual requirement/source/revision.
  A requirement detail link returned 200.
- Short article word count failed. Replacement passed; its digest matched and
  the prior storage object was absent. Unsupported executable and oversize
  uploads retained the prior asset ID/fingerprint.
- A temporarily reduced workspace quota rejected growth without losing the
  original. The original 100 MiB limit was restored in `finally` and checked.
- A 1000 by 1000 PNG failed dimensions; a 1080 by 1080 replacement passed.
  Caption upload completed. Contributor review POST returned 403.
- The coordinator recorded a truthful Fail review because the plain test image
  lacked a logo. Replacement invalidated the review. Old-fingerprint submission
  returned 409 without another review; a current Fail with explanation saved.
  Two review-history rows remain; no fictitious logo approval was recorded.
- A 233-word DevLoop package passed its two checks. Ready explicitly required
  confirming delivery separately.
- Six actual signed HTTPS downloads (three originals for each permitted role)
  matched SHA-256 and attachment headers. Anonymous requests went to sign-in;
  unsigned Supabase object access returned 403; unrelated asset-ID injection
  under a permitted package returned 404.
- Requirement editing created revision 2. A stale version-1 submission displayed
  the conflict message without creating revision 3.
- Five nonexistent-username logins followed by a Unicode-equivalent sixth
  returned 429 with `Retry-After`. No real account was locked for this drill.

Orca report screenshots were inspected at 320, 390, 768 and 1200 CSS pixels,
without horizontal page overflow. An actual `.html` upload showed its labelled
error and retained the original and Ready state. Tab advanced the active element,
but `document.hasFocus()` was false in this background page; this follow-up does
not claim visual focus-outline verification. Existing focus CSS remains.

## Actual backup and monitoring evidence

- New PostgreSQL SHARE-lock capture passed real concurrent-read/blocked-write,
  rollback-release and lost-session tests. SQLite recovery remains offline.
- A real locked snapshot was restored into fresh managed database
  `pdc_recovery_20261117` / prefix `recovery-20261117/originals`. Runtime-role
  verification passed five original hashes, six actual signed downloads for
  both roles, three review records/fingerprints and unrelated-workspace
  page/API/download 404. Previous recovery targets were preserved.
- The owner completed free B2/Healthchecks signups privately. Actual B2 ACL was
  owner-only. Console retention appeared through S3 as 7-day hiding, 1-day hidden
  deletion and paired marker cleanup; code/tests were corrected for that response.
- `backup_offsite` captured, authenticated and uploaded a real **24,898-byte**
  encrypted bundle, downloaded its exact version and checked full ciphertext
  SHA-256. The independent backup monitor acknowledged start and success.
  A separate retrieval matched its receipt; unsigned B2 access returned **401**.
- The retrieved B2 bundle was restored into another fresh managed target,
  `pdc_offsite_20261117` / `recovery-offsite-20261117/originals`. Runtime-role
  verification again passed five original hashes, six real signed downloads,
  three reviews/fingerprints and unrelated-workspace denial. Provider cron/Vault
  schemas were absent. Restored workers stayed disabled. This is an executed
  off-site restore, not a mocked S3 exercise.
- Actual protected `/ready/` JSON and Healthchecks acknowledgement passed.
  Separate two-minute readiness monitoring was activated. Mail delivery was not
  stopped. API/runtime/migration roles were denied private function/Vault/network
  access. Scheduled mail and readiness runs at 13:58, 14:00 and 14:02 UTC
  succeeded; the mail queue was empty at the final check.
- A separate missed-ping drill reached Down; the owner **confirmed receipt of
  its Gmail failure alert**. Recovery was acknowledged and the drill was paused;
  recipient recovery receipt is pending.
- Observed B2 caps: $0 storage (10 GB), $0 daily download (1 GB), 2,500 daily
  Class B/C operations, owner email alerts enabled. A 3 GiB prefix budget guards
  publication. The console-generated key is bucket/prefix scoped but includes
  deletion. No append-only/Object Lock claim is made.
- A dedicated fine-grained Actions read/write token was created for this one
  repository only, with required metadata read and expiry 15 February 2027.
  It was installed in staging Vault. All four untrusted roles were denied
  private function/Vault/network access.
- [Manual hosted backup](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44098488721)
  succeeded using the new Linux runner, hash-locked clean installation and
  PostgreSQL container client. Production mail and maintenance jobs were skipped.
- Actual cron dispatch at **14:03:00 UTC** succeeded and its
  [hosted backup job](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44098896465)
  completed successfully. Both runner-produced B2 versions independently
  authenticated/decrypted with the recovery key, with all five original hashes
  checked. At that check B2 held three versions totaling 74,754 bytes.
- Nightly backup was then activated at **18:17 UTC / 02:17 Asia/Manila**;
  read-back confirmed that schedule and both two-minute jobs active. Healthchecks
  reported backup/readiness Up and the drill Paused. Its first nightly occurrence
  is future work for the scheduler, not an executed result in this record.
- Anonymous branch `/ready/` redirected to Vercel's HTTPS `/sso-api`; the same
  endpoint with the private protection header returned actual ready JSON, 200.
  Original account roles, five assets and three reviews remained intact.

## Automated verification and remaining gates

Current local results: **142 tests**, SQLite **OK, seven PostgreSQL-only skips,
92.070 s**; native PostgreSQL 17.12 **OK, no skips, 114.439 s**. Ruff, whitespace
checks and both workflow YAML parses passed. Django checks, migration consistency,
static collection, dependency audit (no known vulnerabilities) and production
fixture checks also passed locally.

Hosted CI for application/operator commit **4212084** passed on
[push](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44098442431)
and [pull request](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44098454334),
including Linux PostgreSQL recovery, dependency checks, production fixture checks
and all three container builds. CI builds do not constitute a full Compose HTTPS
rehearsal, which was not run. Subsequent evidence-only documentation edits do not
change the tested application/operator code.

The active Vercel project `partner-deliverables-checker-puux` also reported a
[successful preview build for 4212084](https://vercel.com/jello3/partner-deliverables-checker-puux/67jaPSxfXwvDD6EgvL49GTcdWQ6o).
Three pre-existing duplicate Vercel projects attached to the repository still
reported failed deployment statuses. Their integrations/settings were not changed
or deleted. Those statuses are distinct from the passing active project and
quality workflows; repository-wide aggregate status is therefore not all green.
The owner should confirm which duplicate integrations may be disconnected.

Pending: owner confirmation of the recovery notification; normal overnight
observation; PR review; production-specific operations/rehearsal, policy/capacity
review and explicit launch approval. Recovery-key copies exist in encrypted
Actions secrets and local DPAPI, outside B2; independent decryption of the runner
bundle confirmed matching keys. Maintain owner account recovery and preferably
another offline/password-manager key copy. Main's remote hash remained
`e3280e42e395f9622779a96ba58a552fd6defd77`. No paid resource, main merge,
production configuration change or public launch was performed.

Decision: **staging acceptance and its backup/monitoring rehearsal passed**.
Public launch remains **no-go** pending the production gates above.

## Files changed in this operations follow-up

- `.github/workflows/mail-delivery.yml`
- `checker/backup.py`
- `checker/management/commands/backup_bundle.py`
- `checker/management/commands/backup_offsite.py`
- `checker/monitoring.py`
- `checker/offsite.py`
- `checker/tests_offsite.py`
- `checker/tests_recovery.py`
- `scripts/rehearse_recovery.py`
- `deploy/backup.env.example`
- `deploy/staging-backup-cron.sql`
- `deploy/staging-readiness-cron.sql`
- `docs/deployment.md`
- `docs/operations.md`
- `docs/offsite-backups.md`
- `docs/staging-mail-scheduler.md`
- `docs/staging-verification-2026-11-16.md`
- `docs/staging-verification-2026-11-17.md`
- `docs/release-readiness.md`
- `docs/verification.md`
