# Deployment runbook

Requested target: **Vercel**, with an optional Linux Compose alternative. Neither hosted target has been deployed from this workspace. See `release-readiness.md` for actual execution evidence.

## Vercel prerequisites

1. A Vercel account/project using its Django framework preset (current documented minimum CLI: 50.38.0).
2. External PostgreSQL with TLS, credentials and suitable connection limits. URL settings preserve stricter `verify-ca`/`verify-full` modes rather than replacing them with `require`; follow the provider's certificate-verification instructions. Use a pooled URL if recommended by the provider; server-side cursors and automatic prepared statements are disabled in URL-configured connections. Configure a suitable statement timeout on the database role through the provider; startup options are deliberately not forced through unknown poolers. The web role needs application data access; run migrations through a separate privileged release runner where possible.
3. A private S3-compatible bucket and credentials scoped to the application prefix. Configure block-public-access, no public ACL/policy, and test read/write/delete and authorized signed downloads. Use a separate bucket or prefix for each environment.
4. An SMTP service with a verified sender, and explicit approval before sending to real users.
5. A scheduler/worker to deliver the database mail queue. Vercel's legacy Hobby cron is daily, which is unsuitable for timely account email. The included GitHub Actions dispatcher is **disabled** until repository variable `ENABLE_MAIL_DISPATCH=true`; it needs `MAIL_DISPATCH_URL=https://YOUR_HOST/ops/mail/` , `MAINTENANCE_URL=https://YOUR_HOST/ops/maintenance/`, and secret `OPS_SECRET`. It runs every five minutes, best effort, and dispatches five messages per call. Measure queue delay and provider limits; this is not a delivery SLA. A sustained higher volume needs a faster worker/scheduler.
6. An external backup runner, encrypted off-site destination, monitoring and a published support/retention policy. These services may have free tiers, but this repository does not guarantee zero cost, commercial eligibility, capacity or availability.

Official references: [Django on Vercel](https://vercel.com/docs/frameworks/full-stack/django), [function limits](https://vercel.com/docs/functions/limitations), [Hobby plan](https://vercel.com/docs/plans/hobby), [cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing).

## Configure and build

- Import this repository; use the Django preset. `manage.py`, `WSGI_APPLICATION`, `.python-version` and `tool.vercel.entrypoint` identify the Python 3.12 app.
- Install from `requirements.txt`, which includes the hash-locked `requirements.lock`. The lock was resolved for Python 3.12/Linux; a real Vercel build is still required.
- Vercel automatically collects `STATIC_ROOT` and serves it at `STATIC_URL`. WhiteNoise remains useful locally/Compose.
- Set production variables from `.env.example` through the platform's secret store. Set `DJANGO_DEBUG=0`, exact hostname(s), matching HTTPS `PUBLIC_BASE_URL` and CSRF origin, random Django/operations secrets, database URL, private-storage settings and SMTP sender/credentials. Choose exactly one SMTP TLS mode.
- Keep `TRUST_PROXY_HEADERS=0` on Vercel. The application uses Vercel's forwarded client-IP header; the Compose proxy trust setting is not portable.
- Keep Vercel `UPLOAD_MAX_BYTES` at most 3145728 (3 MiB), below the documented 4.5 MB function request cap including multipart overhead. Browser help and server checks share this limit. Private downloads use authorized 60-second signed attachment URLs rather than routing large response bodies through the function.
- `.vercelignore` excludes databases, private files, test mail, fixtures, recovery artifacts and runtime downloads. Check the actual deployment artifact before launch. Do not deploy `.env` files or backups.
- Preview environments must have their own database, bucket/prefix, origin, secrets and safe email destinations. Never let a preview migration or test write to production.

Do not run migrations at WSGI import or on every request. With traffic closed, use a trusted runner with the intended environment injected:

```bash
python manage.py migrate --noinput
python manage.py check --deploy --fail-level WARNING
python manage.py collectstatic --noinput
```

A settings check does not verify actual TLS, storage policy, SMTP receipt, or all authorization behavior. Deploy a protected staging environment, then run the following acceptance exercise before any public launch approval:

- Register two unrelated teams using actual verification email; confirm workspaces are private.
- Exercise invitations, expiry/replay/revocation, member removal, password reset/change and coordinator transfer.
- Test direct URLs, API requests, submitted owner/partner IDs and downloads across teams and contributor ownership.
- Upload valid and invalid files, replace a file, trigger a stale review and a quota, and verify recovery messages and retained originals.
- Confirm session/CSRF cookies, HTTPS redirects, no DEBUG pages, no public original listing, signed attachment expiry and actual throttling behind Vercel.
- Exercise browser layouts, keyboard flows and expected concurrent load. Tune quotas to measured latency, provider connections and free-tier usage.
- Verify `/ready/` failure detection and that error, queue-age, storage and backup alerts reach an operator.
- Restore a real staging backup into an isolated remote database/bucket and download an original through both allowed roles. Check denial from the other team.

## Optional Linux Compose target

Configure private `.env` values for `POSTGRES_*`, `APP_DOMAIN`, Django settings, SMTP, operations secret and backup encryption. Compose sets internal proxy trust; it uses persistent database/private-file volumes. The application and Nginx ports are private; only Caddy publishes 80/443. Do not expose Gunicorn/Nginx directly or trust arbitrary forwarded headers.

```bash
docker compose build app worker
docker compose up -d db
docker compose run --rm app python manage.py migrate --noinput
docker compose run --rm app python manage.py check --deploy --fail-level WARNING
docker compose up -d
```

Create the first real account through signup and verification. Existing legacy accounts use `set_account_email` as described in `operations.md`. Do not re-enable the development seeder in production. The app image runs as UID 10001; host bind mounts must have matching permissions. Backup runners require access to the private files and a PostgreSQL client compatible with the server.

Build the operational image before enabling backups:

```bash
docker compose --profile operations build backup
```

Schedule `sh deploy/backup.sh` from the repository on the host. It stops app/mail writers, produces a consistent encrypted database+file bundle, applies retention/security-record cleanup, then restarts writers even if the backup fails. Send the encrypted result off-site and alert on any failure; a second copy on the same host is not disaster recovery. The Docker/proxy/TLS and operational-image path could not be executed here because Docker is absent.

## Monitoring and release decisions

`/health/` is process liveness. `/ready/` checks database access, storage reachability and pending mail older than fifteen minutes, returning only ready/unavailable. Storage reachability is not a proof of bucket privacy, write permission or available quota. Monitor provider database connections, object storage/volume usage, CPU/latency, email failures, queue age and backup age separately.

A missing/failed mail scheduler blocks public onboarding. Five-message batches may be insufficient during bursts; measure and provision a suitable scheduler rather than assuming free capacity. Hosted deployment, email, storage policy, backup destination and alert delivery remain external launch gates until configured and rehearsed.
