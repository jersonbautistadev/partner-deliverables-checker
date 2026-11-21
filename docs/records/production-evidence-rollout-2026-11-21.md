# Production rollout: linked evidence and obligation coverage (21 November 2026)

The owner approved rolling out draft PR #2 (`feat/linked-evidence-coverage`) to the
public pilot. Times are UTC on 20 November (Manila 21 November). Main is unchanged.

## Sequence executed

| Step | Result |
|---|---|
| Pre-change backup | GitHub production-backup job on the previous runner ref (`fix/dev-team-release-gaps`, schema 0004): encrypted bundle `pdc-20261120T165944247519.pdc` uploaded, downloaded and checksum-verified. This is the paired pre-migration restore point. |
| Production-target build | Explicit Vercel deployment of `e2ec463` with **Production** variables and `autoAssignCustomDomains=false` (`dpl_6CfYTSA5dWdkCzbnD3uzhDKsPKaM`). Build log: `check --deploy` reported no issues. Its own hostname returned Django 400 (production `ALLOWED_HOSTS`), confirming production bindings; anonymous requests were redirected to Vercel SSO. |
| Branch alias | Vercel moved the feature-branch alias onto that production-target build. It was re-pointed to the staging-bound preview of the same commit, and later to the preview of `c8081d6`. |
| Migration | `0005_obligation_evidence` applied with the migration role. Existing rows were intact (17 requirements, 8 reviews before import). `pdc_web` received `SELECT/INSERT/UPDATE/DELETE` on `checker_evidence` plus sequence usage through existing default privileges; `anon`/`authenticated` have none. |
| Public switch | Promoted `dpl_6CfY…` to the public domain. Post-promotion smoke: health, readiness, sign-in, signup and pilot pages 200 with HSTS/nosniff/frame headers; anonymous dashboard, coverage and API redirected to sign-in; tokenless operations POSTs denied; acceptance owner dashboard, coverage, report and evidence-history pages 200; private download SHA-256 matched; a contributor in another workspace was denied. |
| Backup runner | `PRODUCTION_BACKUP_REF` and Vault `pdc_production_backup_ref` set to `feat/linked-evidence-coverage`; `pdc_production_ops.dispatch_backup()` now accepts that ref (see `deploy/production-operations.sql`). A manual run and a run dispatched by the scheduler function itself both succeeded and checksum-verified (`pdc-20261120T171347520706.pdc`, `pdc-20261120T172400763602.pdc`). The nightly job remains active. |
| Owner obligations | 30 owner-confirmed obligations imported into the owner's private workspace through the requirement form (revision history recorded, all approved, zero evidence and zero reviews). Partner content is not reproduced here. |

## Defect found during rollout and fixed

Reviews were keyed to the whole-package fingerprint, so adding requirements or
submitting evidence for one obligation reset every other review in the package.
Importing the obligations invalidated the six earlier partial-scope image reviews.
`c8081d6` scopes each review to its own requirement snapshot plus only the file or
evidence it inspects; reviews saved under the package fingerprint remain valid while
the package is unchanged. 180 tests passed on SQLite (ten PostgreSQL-only skips) and
on local PostgreSQL; CI passed. It was released the same way: unaliased Production
build `dpl_Bf83upHJ2nCoMs7rxosYdwRQgXfH`, `check --deploy` clean, promotion, and the
same smoke checks passed again. The six image reviews were restored as the original
reviewer only after confirming that each requirement revision and file were unchanged
since the original review; each note cites the original review ID.

## Access and rollback

Vercel required owner identity verification for deployment creation. Two short-lived
tokens limited to the `puux` project were created only to trigger that verification
and were revoked within minutes; no token value was stored. Supabase SQL changes were
made by the owner-authenticated dashboard session.

Code-only rollback: promote `dpl_6CfY…` (pre-fix) or, before any evidence or
non-applicability decision exists, the previous release `dpl_EHMB7muEkQxpvbXmoJNWHzq9S2qz`.
Once evidence records exist, prefer a forward fix; see [operations](../operations.md).
The three other Vercel projects connected to this repository were not changed.

## Follow-up release: evidence text wrapping (21 November 2026, 08:2x UTC)

The owner approved releasing `07558f0` (CSS `overflow-wrap: anywhere` on evidence
explanations; no migration). CI and the protected Preview had passed. Released the
same way: unaliased Production-target build `dpl_BdgFTja9qhwkQonnsPNLhqQk9YZj`,
`check --deploy` clean, promotion, branch alias re-pointed to the staging preview of
the same commit. Post-promotion smoke checks passed again, and the public stylesheet
contains the new rule. The owner workspace's evidence submissions and review counts
were unchanged by the release. The one-hour team-scoped Vercel token created only to
trigger identity verification was revoked before deployment; no token value was stored.
Code-only rollback: promote `dpl_Bf83upHJ2nCoMs7rxosYdwRQgXfH`.

## Merge to main and backup ref change (21 November 2026, 08:30 UTC)

PR #1 and PR #2 were merged into `main` with merge commits; `main` (`a0ab537`) has the
same tree as the released feature branch. Vercel's production branch is `main`, so each
merge triggered an automatic production deployment. The PR #1 merge (`129ceaf`, which
predates the evidence feature) served the public domain from 08:30:57 to 08:31:18 UTC,
about 21 seconds, before the PR #2 build replaced it. A read-only check found no
reports, reviews, evidence, requirement edits, uploads or audit events written in that
window, and totals matched. Lesson: when the production branch auto-deploys, land
stacked branches in one step (for example merge the top branch directly). Smoke checks
passed on the `main` build `dpl_3HyjZvmLzimBtzMy8mXFtEQc5pQh`.

`PRODUCTION_BACKUP_REF` and Vault `pdc_production_backup_ref` now point to `main`; a
backup dispatched by the production scheduler function itself succeeded and was
checksum-verified (`pdc-20261121T083349253026.pdc`). Staging backups still use
`feat/linked-evidence-coverage`, so that branch is kept.

The three other Vercel projects connected to the repository had never built
successfully and had no environment variables or custom domains. Their Git connections
were removed (not deleted) so they no longer report failing checks on every commit.
