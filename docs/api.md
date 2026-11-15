# Session-authenticated API

The API uses Django sessions, verified accounts and the selected workspace. Select a workspace through the CSRF-protected `POST /workspaces/` form; the session is revalidated against membership on each request. There is no public token API or cross-workspace superuser bypass.

- `GET /api/v1/packages/`: package ID, title, partner, stage and owner for the selected workspace; contributors see only their own packages.
- `GET /api/v1/packages/ID/report/`: the current report ID/fingerprint, engine version, checked timestamp and findings. Object scope and ownership are checked before report generation.
- `GET /packages/ID/assets/ASSET/download/`: authorized attachment download. Local/Compose files are a protected response; S3 files return a 302 to a signed attachment URL expiring after 60 seconds. Such URLs are temporary bearer credentials.

Unauthenticated application requests redirect to login. An authenticated but unverified/missing-workspace API request receives 403. Objects outside scope receive 404. Unsupported methods receive 405; the audit endpoint accepts GET only. Write forms require CSRF. Throttled requests receive 429 with Retry-After; APIs receive a generic JSON error.

`GET /health/` is process liveness. `GET /ready/` returns only ready/unavailable and uses 503 when database/storage/mail readiness fails. It does not validate every provider permission or capacity.

`POST /ops/mail/` is a separate machine endpoint. It requires `Authorization: Bearer OPS_SECRET` with at least 32 random characters, accepts no payload and processes at most five queued messages. It does not use session authentication and is a CSRF exemption. Keep the secret in the scheduler and application secret stores; never in the URL or browser. Its response reports only the delivered count.

`POST /ops/maintenance/` uses the same bearer-secret protection and no browser session. It prunes expired security records and sessions without deleting originals, revisions or audit history. Schedule it daily; the optional GitHub workflow is disabled until explicitly enabled. Both machine endpoints reject GET.
