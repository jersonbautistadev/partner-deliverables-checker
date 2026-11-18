# Production acceptance: 18 November 2026

Decision: **go for the bounded educational pilot**. Protected staging and
production acceptance passed. The owner subsequently approved public access;
the [verified launch](public-pilot-launch-2026-11-18.md) opened the production
domain while retaining preview protection. Main is unchanged.
This record supplements the [rollout history](production-rollout-2026-11-18.md)
and distinguishes production evidence from earlier staging and fixture tests.

## Accounts, workspaces and mail

The owner confirmed receipt and verification of both production acceptance
accounts, then confirmed receipt of the password-reset email and both workspace
invitations. The actual scheduler handed each message to Gmail on its first SMTP
attempt. Sent message bodies and recipients were cleared from the queue.

Both accounts signed in through the HTTPS forms. A reset changed the acceptance
account password: the old password/session were rejected, the new password
authenticated, and reuse of the reset link failed. Both invitations were
accepted; wrong-recipient and reused invitations were rejected. The operator
captured the generated invitation/reset links privately from the queued test
messages to exercise the flows; inbox receipt was separately confirmed by the
owner. No email link or password is included in repository evidence.

Two independent acceptance workspaces now have four memberships: each account
coordinates one team and contributes to the other. Tests proved unrelated
workspace selection, submitted partner IDs, package/report URLs, API lists and
downloads are denied; contributors cannot access another owner's package or
coordinator actions. Submitted package-owner overrides are ignored for
contributors. Coordinator transfer took effect immediately, and original roles
were restored. Last-coordinator removal, demotion and account deactivation were
blocked. Unsafe external sign-in redirects were rejected.

Repeated test sign-ins reached the configured five-attempt/15-minute identity
limit. Tests waited for that window; no throttle was disabled or cleared.
Duplicate signup returned a generic acknowledgement without creating another
account, token or email. Missing CSRF returned the friendly 403 page; malformed
fields showed validation errors. Session/CSRF cookies retained their secure flags.

## Requirements, files and reviews

Production fixtures reuse fictional Campus Current/DevLoop Journal instructions
and demo originals. They are explicitly named as acceptance data. Existing
accounts were preserved; no real partner data or publishing approval was invented.

- Missing findings retained their source and requirement revision.
- A short release failed word count; replacement passed and removed the prior
  stored original. Required event phrases were checked.
- Unsupported and over-3-MiB uploads preserved the original and fingerprint.
- A temporary quota on acceptance team A rejected replacement without losing the
  original. Its original 100-MiB limit was restored in a `finally` block.
- Wrong image dimensions failed; correct dimensions and caption checks passed.
- A contributor's manual review returned 403. The coordinator recorded an
  explanatory failure because the plain demo image has no partner logo.
- Replacing the image invalidated the review; submitting its old fingerprint
  returned 409 without creating another review. A current review was recorded.
- A ready package passed configured checks and retained the instruction to
  confirm delivery separately.
- Six live original downloads across coordinator and owning-contributor roles
  matched SHA-256 hashes. Anonymous/cross-workspace/mismatched-asset requests were
  denied. An unsigned private-object request returned 403.
- Requirement revision history persisted; a stale edit was rejected while
  preserving the new revision and its deadline.

## Operations and recovery

The owner separately approved daily retention. Its real production operation
completed with 23 expired rate windows eligible; protected account, workspace,
membership, partner, requirement, package, asset, review and audit counts were
unchanged. The daily 03:23 UTC / 11:23 Manila job is active. This is a manual
operation proof; the next daily cron execution has not yet occurred.

Mail/readiness run every two minutes; capacity every 15 minutes; encrypted backup
runs at 18:47 UTC / 02:47 Manila. All four production Healthchecks were up at the
checkpoint. Failure and recovery email delivery for the shared alert channel was
already confirmed during staging. A separate production alert drill was not run.

The [first file backup run](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44305732451)
passed. Its bundle `pdc-20261118T123759278106.pdc` independently downloaded and
authenticated with the production AES key. An Orca restart interrupted its first
restore after database restoration but before file copy. The offline partial
target was preserved, and an actual original-download check failed as expected.
A fresh database/prefix restore then passed. Both restored passwords authenticated
with the runtime role, both role-authorized HTTPS object downloads matched, and
wrong-workspace downloads returned 404. Provider cron/Vault schemas were absent.

The [latest full backup run](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44308143222)
also passed. `pdc-20261118T125305043631.pdc` independently authenticated and all
five original hashes matched. Its full-set restore into a separate managed
database/private prefix passed: both restored passwords authenticated, all ten
authorized HTTPS object downloads matched (five per role), and all ten
wrong-workspace download requests returned 404. These requests used Django's
request client against the real restored database, followed by actual HTTPS
private-object downloads; this was not a second public application deployment.
The ordinary runtime role was used and provider cron/Vault schemas were absent.
All recovery targets use staging infrastructure, private
prefixes and disabled workers; source data and prior rehearsals were preserved.

## Browser and build evidence

Orca rendered the actual production sign-in/workspace/report screens at 390,
768 and 1200 CSS pixels. Viewed captures and measured widths showed no horizontal
overflow. The contributor report shows source/revision links, file privacy,
upload limits and explanatory review status. This was not an assistive-technology
audit or a physical-device compatibility certification.

Hosted CI for `943fbc3` passed both 150-test suites, dependency audit, migrations,
static collection, SQL boundary contracts, production fixture checks and three
container builds. SQLite skips nine PostgreSQL-only cases; PostgreSQL skips none.
The application code is unchanged by the following build guard.

`vercel.json` now runs `python manage.py check --deploy --fail-level WARNING`
against each Vercel deployment's own environment. The protected branch build for
`c1fbe72` reached READY; its actual logs show the command and “System check
identified no issues (0 silenced).” Vercel then ran static collection normally.
The production build `dpl_EHMB7muEkQxpvbXmoJNWHzq9S2qz` reached READY with the
same successful check log. Its actual health/account/CSS/security-header,
anonymous-protection and operations-denial checks passed again; readiness was
200. Both full release CI runs for `c1fbe72` passed:
[push](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44308606649)
and [PR](https://github.com/jersonbautistadev/partner-deliverables-checker/actions/runs/44308615685).
The guard follows [Vercel's documented build-command order](https://vercel.com/docs/frameworks/full-stack/django#build-command).

## Pilot constraints and launch gate

The approved target is a small personal/educational pilot. Production is capped
at five workspaces, 100 SMTP attempts per UTC day, 100 MiB per workspace and
3 MiB per file. Two preserved acceptance teams consume two workspace slots.
Free provider quotas remain finite; this is not a sustained-load or availability
guarantee. Keys/tokens have the rotation dates documented in the operations guide.

The Vercel target was rehearsed live. Compose configuration and images built in
CI; a complete Compose HTTPS service rehearsal was not executed. Three legacy
duplicate Vercel integrations still report failures; the active `puux` project
must be evaluated separately. Main and the draft PR remain unmerged.

Original files remain private, but no antivirus/content-disarm service is
configured. Replacement cleanup can leave private orphan objects when storage
deletion fails; cleanup requires operator review. Positive deactivation and
membership-removal regression tests are covered by automated tests; this live
production run exercised coordinator transfer and blocked unsafe deactivation,
without deleting the acceptance accounts.

The owner approved public access after this acceptance; see the launch record.
Keep the staging
branch while its scheduler/backup workflow references it. Do not remove fixtures,
earlier recovery targets or backups as part of launch without a separate scoped
cleanup decision.

Changed in this acceptance checkpoint: `vercel.json` (real-environment build
checks), `README.md`, `docs/verification.md`, `docs/release-readiness.md`,
`docs/offsite-backups.md`, `docs/production-rollout-2026-11-18.md` and this record.
Cloud changes include the aligned production operator credential and approved
mail/readiness/maintenance schedules; credentials and scratch test helpers are
excluded from Git. The earlier rollout record retains the broader implementation
manifest.
