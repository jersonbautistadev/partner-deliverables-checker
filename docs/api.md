# Session-authenticated API

The API uses Django sessions, verified accounts and the selected workspace. Select a workspace through the CSRF-protected `POST /workspaces/` form; the session is revalidated against membership on each request. There is no public token API or cross-workspace superuser bypass.

- `GET /api/v1/packages/`: package ID, title, partner, stage and owner for the selected workspace; contributors see only their own packages.
- `GET /api/v1/packages/ID/report/`: the current report ID/fingerprint, engine version, checked timestamp and findings. Object scope and ownership are checked before report generation.
- `GET /packages/ID/assets/ASSET/download/`: authorized attachment download. Local/Compose files are a protected response; S3 files return a 302 to a signed attachment URL expiring after 60 seconds. Such URLs are temporary bearer credentials.

Unauthenticated application requests redirect to login. An authenticated but unverified/missing-workspace API request receives 403. Objects outside scope receive 404. Unsupported methods receive 405; the audit endpoint accepts GET only. Write forms require CSRF. Throttled requests receive 429 with Retry-After; APIs receive a generic JSON error.

`GET /health/` is process liveness. `GET /ready/` returns only ready/unavailable and uses 503 when database/storage/mail readiness fails. It does not validate every provider permission or capacity.

## Evidence and coverage additions

Reports retain the same JSON envelope. Newly generated findings may include
`responsibility`, `applicability`, `conditions`, an `evidence` kind and a
`not_applicable` status. Older cached findings can omit the new metadata. Consumers
must handle unknown/additive finding fields and must not treat a resolved report as
proof of full agreement completion or delivery.

- `GET /coverage/?partner=ID`: recorded obligations and visible last-report snapshots;
  optional partner filtering is scoped to the selected workspace. This read does not
  regenerate reports or fetch originals/external evidence.
- `POST /packages/ID/evidence/REQUIREMENT/`: CSRF-protected form with `version`
  (latest evidence ID, or zero), optional HTTPS `url`, and required `note`. Package
  ownership/coordinator access and applicable requirement IDs are checked server-side.
  Invalid input returns 400, stale evidence returns 409, quota exhaustion returns 429,
  and report/storage failures roll back the submission and return 503.
- `GET /packages/ID/evidence/REQUIREMENT/history/`: authorized, private, paginated
  submission history. No public evidence or unauthenticated URL-fetch endpoint exists.
- The existing review POST also accepts `not_applicable` for approved, unambiguous
  optional/conditional evidence obligations only. A review note and the finding's
  current `review_key` (or the current report fingerprint) remain required; a stale key
  returns 409. Contributors cannot record reviews.

`POST /ops/mail/` is a separate machine endpoint. It requires `Authorization: Bearer OPS_SECRET` with at least 32 random characters, accepts no payload and processes at most five queued messages. It does not use session authentication and is a CSRF exemption. Keep the secret in the scheduler and application secret stores; never in the URL or browser. Its response reports only the delivered count.

`POST /ops/maintenance/` uses the same bearer-secret protection and no browser session. It prunes expired security records and sessions without deleting originals, revisions or audit history. Schedule it daily; the optional GitHub workflow is disabled until explicitly enabled. Both machine endpoints reject GET.
