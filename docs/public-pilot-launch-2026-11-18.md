# Public pilot launch: 18 November 2026

The owner explicitly approved opening the small personal/educational pilot.
Public access was verified at **13:08:58 UTC / 21:08:58 Asia/Manila**:

https://partner-deliverables-checker-puux.vercel.app

Functional release: `c1fbe726016bdc4cbd849ce984aee875b5807e0e`.
Production deployment: `dpl_EHMB7muEkQxpvbXmoJNWHzq9S2qz`.
Main remains `e3280e42e395f9622779a96ba58a552fd6defd77`; the working branch and
draft PR were not merged. No paid resources were enabled.

## Executed anonymous checks

- Health, readiness, sign-in, signup and pilot/privacy pages returned 200 with
  no cookies, Vercel bypass or application credentials.
- Package-list API, package detail and an existing original's download route
  redirected to application sign-in; they did not expose private content.
- The staging branch and production deployment's immutable URL still redirected
  anonymous visitors to Vercel Authentication.

Vercel Authentication uses Standard Protection (`all_except_custom_domains`),
following its [documented API configuration](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/vercel-authentication#how-to-manage-vercel-authentication-with-the-api).
Initial immediate probes still saw the old gate on different routes, so the
safety checks restored All Deployments protection. A subsequent bounded
propagation wait verified every public route and both private-data/preview
boundaries before recording successful launch. No permissions were relaxed in
Django, PostgreSQL or object storage.

## Operating state

The five-workspace cap remains. Two preserved acceptance teams use two slots.
Other bounds remain 100 SMTP attempts per UTC day, 100 MiB per workspace and
3 MiB per file. All five production schedules remain active; no additional
emails, accounts, deletions or scheduler changes were performed by the launch.
Preserve the working branch while scheduled backup/staging jobs reference it.

After launch, the temporary project-scoped Vercel setup token was revoked. It
disappeared from the account token list and its API access returned 403. Active
mail/monitor/backup credentials were not revoked. Future API configuration changes
require a new scoped setup token; dashboard access remains available to the owner.

[Production acceptance](production-acceptance-2026-11-18.md) records the actual
mail/account/workspace/file/review checks, build checks, full PostgreSQL tests
and five-original recovery with ten matching downloads across both roles.
The first normal daily maintenance run remains a future operating check.
Free capacity, file-security limits and the absence of a sustained-load or full
assistive-technology audit remain as documented there.

To close the pilot, set this project's Vercel Authentication scope back to All
Deployments (`all`) and verify anonymous production routes redirect to Vercel.
This does not delete accounts, workspaces or files. Use the documented recovery
procedure for data recovery; never overwrite the live database during a rollback.
