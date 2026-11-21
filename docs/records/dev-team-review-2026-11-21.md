# Dev-team review: 21 November 2026

A whole-project review from code-review, security, QA and DevOps perspectives after
the evidence release, redesign and PartnerReady branding. Security-critical paths were
read in full (permissions, middleware, uploads and downloads, account and invitation
flows, settings); one suspected defect was confirmed with a live request; CI coverage,
tracked files and git history were checked. No penetration test, load test or
assistive-technology audit was performed.

## Findings and fixes

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | `main` was unprotected and Vercel deploys every push to production regardless of CI; migrations are not part of the deploy. | High | Branch protection requires a pull request with passing `test` and `migration-gate` checks. `migration-gate` fails a PR that adds a migration unless it carries `migration-applied`, added after the backward-compatible migration runs in production. Procedure in [operations](../operations.md#releasing-a-change-that-includes-a-migration). |
| 2 | No Content-Security-Policy or Permissions-Policy header. | Medium | Strict CSP (`script-src 'none'`, no plugins, framing or `<base>`, same-origin forms) and a restrictive Permissions-Policy on every response. |
| 3 | The coverage page skipped the verification/workspace gate (a bare 403 instead of a redirect; no data exposed). | Medium | The gate covers `checker.coverage`; regression test added. |
| 4 | Dependency advisories were only checked on push; no automated updates. | Medium | Weekly scheduled CI (including `pip-audit`), GitHub Dependabot alerts, and Dependabot updates for GitHub Actions. |
| 5 | Five failed sign-ins from any IP locked a username for 15 minutes (targeted lockout). | Medium | Limit per username and source IP (5/15 min) plus an account-wide ceiling (`ACCOUNT_RATE_LIMIT`, 50/15 min). |
| 6 | Uploads held the workspace row lock during the storage upload. | Low | Bytes are written first; a short locked transaction re-checks access, rate and quota, and deletes the object on failure. |
| 7 | Check runs were never pruned. | Low | Daily maintenance keeps the latest 10 per package and deletes older runs past 30 days. |
| 8 | Untested paths: adding a partner, successful workspace creation; no automated page-structure checks; PostgreSQL run not measured. | Low | Tests added, plus static accessibility structure checks (language, one `h1`, labels, alt text, skip link); PostgreSQL CI run reports coverage. |
| 9 | Staging backups and scheduler referenced old feature branches. | Low | Staging moved to a dedicated `staging` branch; the old branches were retired. |
| 10 | Report reads write a cached snapshot (GET with a side effect). | Info | Documented in the [API notes](../api.md). |

Each code fix has a regression test that failed against the previous code (except
the coverage-gap tests, which exercise existing behaviour).

## Strengths observed

Query-level tenant isolation on every package, report, download and API route; hashed,
single-use, POST-confirmed tokens; no account enumeration; last-coordinator guards
under consistent lock ordering; content-validated uploads served as attachments or
60-second signed URLs with commit-ordered file deletion; hardened cookies, HSTS and
framing denial; no secrets or private partner data in tracked files or history;
encrypted off-site backups with tested restores.
