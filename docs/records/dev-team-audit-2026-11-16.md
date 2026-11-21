# Dev-team audit: 16 November 2026

Historical findings at `e3280e4`. See [implemented fixes and current verification](dev-team-fixes-2026-11-16.md) for follow-up status; the original evidence below is retained.

Reviewed revision: `e3280e4` on `main`. **Request changes before public launch.** Controlled technical review can continue on the existing deployment; public account onboarding is blocked. This audit changes documentation only. No production settings, accounts, files, or email jobs were changed.

Read all ten installed dev-team skills and `D:\Programming\Skills\dev team\dev-team-playbook.md`. Applied its requirements, architecture, implementation review, QA, security, and operations handoffs. Findings distinguish executed reproductions, static review, and unverified gates. Passing regression tests do not cover every public-launch failure mode.

## Prioritized findings

### A1. Blocker: hosted account email has never been dispatched

**Evidence:** a fresh read-only production database transaction found two accounts, zero verified accounts, two pending mail jobs, zero sent jobs, and a maximum attempt count of zero. No addresses, message bodies, or tokens were retrieved. Public GETs returned `/health/` 200, `/accounts/login/` 200, and `/ready/` 503. The readiness response is generic and alone cannot identify the failing dependency; the old pending queue is sufficient to fail its mail-age check.

**Where:** [verification/signup](../../checker/accounts.py), [queue and SMTP dispatcher](../../checker/mail.py), [disabled-by-default dispatcher workflow](../../.github/workflows/mail-delivery.yml).

**Impact and next action:** users cannot complete signup, invitations, or recovery without email. Zero attempts distinguish this from a demonstrated spam-folder or rejected-SMTP issue. Earlier setup left SMTP credentials and scheduled dispatch unconfigured. The owner must finish private provider credential setup, then configure sender/SMTP secrets and rehearse delivery to an approved recipient. Verify actual receipt, expiry/replay protection, invitations, reset, retries and queue drainage before enabling scheduled real-user delivery. Do not bypass verification or expose pending tokens as a workaround.

### A2. Major / security Medium: equivalent username spellings bypass the account throttle

**Where:** [identity construction](../../checker/middleware.py#L100), [authentication form subclass](../../checker/account_forms.py#L35).

**Executed reproduction:** with the default ten-per-minute IP limit, five wrong passwords for fictional username `alice` exhausted its account bucket. A subsequent correct ASCII login returned 429. The same password with fullwidth Unicode letters returned 302 and authenticated. Django normalizes that spelling to the same username; middleware hashes its raw case-folded spelling into a different bucket.

**Impact:** the five-attempt account limit is inconsistent across equivalent spellings. The separate IP limit still applies; this does not bypass passwords, verification, or workspace authorization.

**Fix/acceptance:** use the same NFKC username normalization as Django before constructing the throttle identity, retain appropriate email normalization separately, and bound normalization work for oversized input. Test equivalent spellings after exhausting the account bucket: all must remain 429 without authenticating. Retain IP and concurrency checks.

### A3. Major: backup tools omit the configured PostgreSQL provider CA

**Where:** [pg_environment](../../checker/backup.py#L73), [database CA configuration](../../config/settings.py#L193).

**Executed reproduction:** supplied `sslmode=verify-full` and `sslrootcert=/fixture/provider.crt` with a clean environment. The helper forwarded `PGSSLMODE` but no `PGSSLROOTCERT`. Both backup and restore use this helper. The deployed connection uses an explicit provider CA, which earlier provider verification required.

**Impact/fix:** a runner without an independently configured libpq CA cannot use the application's trust chain. Forward the configured CA without weakening `verify-full`; test precedence against inherited environment variables. Local recovery passing does not prove managed-provider recovery. After fixing, back up with the intended backup role and restore into a separate managed database/private bucket. Verify schema scope, ownership compatibility, original bytes and authorized downloads. No production backup or managed restore was attempted in this audit.

### A4. Major: a storage read outage breaks cached reports with HTTP 500

**Where:** [current_inputs](../../checker/services.py#L67), [dashboard](../../checker/views.py#L68), [downloads](../../checker/views.py#L327).

**Executed reproduction:** created a synthetic local asset and cached report, then made storage `exists()` raise `OSError`. An authorized report API GET returned 500 rather than a controlled unavailable response. Dashboard/report reads share this path. S3 download existence/signing calls also lack a storage-service exception handler; that branch was reviewed, not separately fault-injected.

**Fix/acceptance:** handle filesystem and botocore failures through a narrow storage-unavailable error and understandable HTML/JSON 503 responses. Distinguish a missing object from a provider outage; never interpret unavailable storage as a passing check. Preserve prior files and reviews. Test dashboard, report API, downloads, and recovery after storage returns. Upload writes already handle several storage failures more clearly.

### A5. Major: readiness can succeed with mail unconfigured

**Where:** [readiness](../../checker/operations.py#L16), [production checks](../../checker/checks.py).

**Executed reproduction:** with no SMTP host, a localhost sender, and no old queued jobs, `/ready/` returned 200. Production deployment checks can detect missing SMTP configuration; readiness does not perform that validation. This finding is separate from today's hosted 503.

**Fix/acceptance:** distinguish configured dependencies, worker activity and queue-age health. Reject missing required production settings and detect stalled dispatch after a documented grace period, exposing only generic public status. Do not send email on a health GET. Test empty/recent/stale queues, failed or exhausted jobs, and recovery. Configuration checks cannot prove inbox delivery.

### A6. Major / performance: dashboard work grows with every package and asset

**Where:** [package_card/dashboard](../../checker/views.py#L35), [cached report validation](../../checker/services.py#L88).

**Measured:** ten packages with one asset each and cached reports required **92 SQL statements and 10 storage existence checks** for one dashboard GET. There is no pagination before report generation; cached reports still check every asset's storage availability. This measures request counts, not hosted latency or load capacity.

**Fix/acceptance:** bound dashboard work through pagination/batching and a documented freshness strategy while retaining authoritative revalidation for writes and explicit reports. Never present stale checks as current. Measure database/storage-call growth and hosted response time at realistic workspace limits; no performance budget is assumed here.

### A7. Minor: error copy and retry advice disagree with enforcement

- [Upload error](../../checker/views.py#L309) says 5 MiB, while Vercel defaults to 3 MiB in [settings](../../config/settings.py#L154). Build copy from the configured limit and preserve useful form errors.
- [Throttle responses](../../checker/middleware.py#L115) always promise one minute and `Retry-After: 60`, including the five-per-900-second account bucket. Calculate the remaining blocking window and test with a fixed clock.

Confirmed by source inspection; no timed 15-minute browser test was performed.

### A8. Minor: Compose does not forward implicit SMTP TLS mode

[Compose's shared environment](../../compose.yaml#L33) forwards `EMAIL_USE_TLS` but omits `EMAIL_USE_SSL`, which [settings](../../config/settings.py#L132) supports. Implicit TLS configuration cannot reach the container through this file. Forward the variable and verify both mutually exclusive modes. Static finding only; Docker is unavailable locally. Vercel configuration is separate.

### A9. Minor: historical summaries need a current pointer

[Release readiness](release-readiness.md) retains 106-test totals and removed `pyproject.toml` references. Those describe an earlier checkpoint, while later verification entries record 107 tests and real provider checks. Added current-audit links to both documents; historical results remain historical.

## Checks actually executed

| Check | Result | Scope/limitation |
| --- | --- | --- |
| Full SQLite suite under coverage | 107 tests, OK; 3 skipped; 88.188 seconds | PostgreSQL-only races/recovery skipped. |
| Full native PostgreSQL 17.12 suite | 107 tests, OK; no skips; 100.632 seconds | Includes row-lock races, legacy migration and encrypted database/original-file restoration with restored downloads. Local storage, not managed disaster recovery. |
| Ruff | Passed | `python -m ruff check .` |
| Django system check | Passed | `python manage.py check` |
| Migration consistency | No changes detected | `python manage.py makemigrations --check --dry-run` |
| Static collection | Passed | `python manage.py collectstatic --noinput` |
| Runtime dependency scan | No known vulnerabilities found | `python -m pip_audit -r requirements.lock --disable-pip --no-deps`; point-in-time advisory result. |
| Production Django checks | Passed | `check --deploy --fail-level WARNING` with non-secret Compose-style fixtures; does not authenticate SMTP or prove live settings. |
| Isolated diagnostics | Four expected assertions failed; one measurement passed | Confirmed A2-A5 and measured A6, separately from the maintained 107-test suite. |
| Public hosted GETs | Health 200, sign-in 200, readiness 503 | HSTS and `Cache-Control: private, no-store` present. No signup or real mail triggered. |
| Hosted database observation | 2 accounts / 0 verified; 2 pending emails / 0 sent / max attempts 0 | Read-only counts with TLS certificate/hostname verification. |

The first PostgreSQL attempt targeted port 55432 while the local server listened on 5432, timing out before tests ran. After checking the actual port, the complete rerun passed. The temporary local PostgreSQL server was stopped afterward.

Ignored local evidence: `.runtime/dev-team-sqlite-tests.log`, `.runtime/dev-team-postgres-tests.log`, `.runtime/dev-team-diagnostics.log`, `.runtime/dev_team_probes.py`, `.runtime/dev-team-coverage`. Diagnostics use fictional fixtures. Aggregate coverage of 83% includes tests/migrations and misses child-process execution; it is not a clean application coverage percentage. Recovery subprocesses were actually exercised.

## Ten-role coverage and handoff

| Role | Applied work | Outcome |
| --- | --- | --- |
| Requirements analyst | Public signup, verified access, tenancy, roles, traceable checks and recovery acceptance | Actual email, managed recovery and hosted load acceptance remain open. |
| Software architect | Django monolith, parent-scoped tenancy, transaction locks, queue, database/object-store boundary | Retain the stack; address dashboard I/O, failure semantics and backup trust configuration. |
| Tech lead | Dependencies, release gates and work sequencing | Code fixes can proceed independently of private SMTP setup. |
| Software developer | Traced models, forms, routes, authorization, writes and exception paths | Concrete A2-A8 fix criteria; no production code changed in this audit. |
| Code reviewer | Correctness, maintainability, performance and failure paths | Request changes with source references and reproductions. |
| Test automation engineer | Full SQLite/PostgreSQL suites and focused diagnostics | Promote A2-A5 into maintained regressions alongside fixes. |
| QA specialist | Compared observed behavior with launch journeys and recovery criteria | Controlled review only; public launch no-go. |
| Security reviewer | Auth/session/tenant boundaries, submitted IDs, downloads, quotas, throttling and dependency scan | A2 reproduced. No tenant disclosure demonstrated in reviewed paths/existing tests; no blanket security certification. |
| DevOps engineer | CI, dependency locks, Vercel/Compose, health, mail and backup operations | A1/A3/A5/A8 and external operational gates below. |
| Debugging specialist | Missing verification mail, PostgreSQL connection issue and isolated failures | Mail never attempted; local port mismatch resolved; four gaps reproduced. |

Trust boundaries reviewed: untrusted browser input -> Django session/CSRF/authentication -> verified workspace membership/role/ownership -> PostgreSQL and private object storage. Temporary account links leave through queue/SMTP. Backup bundles contain records and originals and require a separate protected encryption key. Existing isolation, single-use-token, last-coordinator, quota, review-fingerprint and private-download regressions passed. Operator/provider access remains a separate responsibility.

## Fix sequence and acceptance gates

1. **Developer/security/automation:** fix A2 and retry advice with equivalent-spelling regressions. No external credentials needed.
2. **Developer/QA:** fix A4/A5 and upload copy; cover storage/mail failures and recovery without hiding failures as ready. No real email needed for automated tests.
3. **Developer/DevOps:** fix A3/A8 and test CA forwarding/TLS modes. Rehearse managed recovery separately, using approved isolated destinations.
4. **Architect/developer/QA:** bound dashboard work and measure actual provider-backed performance, preserving checking rules and freshness.
5. **Owner/DevOps/QA:** finish private SMTP setup, approve a real-recipient rehearsal, and verify receipt, invitations, reset, retries and queue drainage before scheduled dispatch. Monitor queue age, exhausted jobs, dispatch errors, readiness, storage/database capacity and backup age.
6. **Release review:** rerun maintained suites and deploy checks, inspect remote CI, smoke-test the exact hosted revision, repeat account/workspace flows at phone/tablet/desktop sizes, and confirm rollback/managed restore before public approval.

No delivery dates are estimated: private provider setup, managed recovery constraints and hosted performance are not yet measured. Each step has evidence-based acceptance criteria above.

## External blockers and verification limits

- **Email:** owner finishes private provider credentials; configure sender/SMTP and approve test-recipient delivery. Do not send passwords or verification codes in chat. This blocks public onboarding/recovery acceptance.
- **Disaster recovery:** select a trusted runner and encrypted off-site destination, protect the separate key, define acceptable data loss/recovery times, and authorize isolated managed restore. Local rehearsal is insufficient production evidence.
- **Monitoring/capacity:** configure actual uptime/queue/storage/backup-age alerts and an operator; measure hosted limits/load. Documentation alone does not prove alerts run.
- **Docker/Compose:** not built/run because Docker is absent. Native PostgreSQL does not verify Linux containers, HTTPS proxy, volume permissions or restart behavior. Rehearse Compose separately if that target is chosen.
- **Browser/accessibility:** no new interactive browser/responsive audit in this review. Prior phone/tablet/desktop evidence is in [verification](verification.md), but does not prove hosted verified-account journeys while email is blocked. No complete assistive-technology audit or penetration test performed.
- **Build/CI:** prior clean installs and successful hosted build are historical evidence in [verification](verification.md). No fresh clean installation, hosted rebuild, remote CI inspection or managed restore was executed during this audit.

**Readiness:** controlled technical review may continue. Public launch is **no-go** until confirmed security/reliability gaps and real email, managed recovery, monitoring and hosted acceptance gates are resolved. No paid resources or public launch were performed.
