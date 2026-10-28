# Deployment runbook

**Status:** configuration written, not built or deployed in this workspace. Treat this as a reviewable runbook. Run the full tests and a clean deployment rehearsal before inviting users.

The easiest first demonstration is a local Django server with fictional data. Use that until the website passes its workflow tests. Public hosting is a separate milestone, not required for your first practice walkthrough.

## Local verification gate

After installing `requirements-dev.txt` in your virtual environment:

```bash
ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2
python manage.py collectstatic --noinput
```

Only record a green result after those commands actually complete. In a fresh environment, resolve dependency versions, save `python -m pip freeze > requirements.lock`, inspect the lock, then confirm `python -m pip install -r requirements.lock` and the checks above. Change the release Dockerfile to install the verified lock. Pin release image digests after the build is tested. Current bounds and image tags provide a repeatable setup procedure, not byte-identical builds.

## One Linux server

Prerequisites: Docker Engine with the Compose plugin, a domain pointing at the host, inbound TCP 80/443, sufficient memory for PostgreSQL and two application workers, and a backup destination. App/database/edge ports stay private to the Compose network. There are no paid API services in the application.

1. Copy `.env.example` to `.env`. Use a new random secret (at least 50 characters), a unique database password, your hostname, `https://your-hostname` for the CSRF origin and your hostname for `APP_DOMAIN`. Keep `.env` out of Git. Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(64))"` on your own machine.
2. Build the application and migrate the new PostgreSQL database:

   ```bash
   docker compose build app
   docker compose up -d db
   docker compose run --rm app python manage.py migrate
   docker compose run --rm app python manage.py check --deploy --fail-level WARNING
   docker compose run --rm app python manage.py create_team_user coordinator --role Coordinator
   ```

3. Start the HTTPS path:

   ```bash
   docker compose up -d
   docker compose ps
   docker compose logs --tail=100 app edge https
   ```

4. Visit your HTTPS hostname. Create fictional partners manually for the public demonstration. The insecure demo seeder is blocked in production; do not disable that guard to reuse known demo passwords.
5. Provision a second invited contributor via the same CLI. Verify direct report and download URLs cannot access the other contributor's package. Upload a wrong extension, invalid PNG, and oversized file; verify previous valid files are unchanged. Check a download's attachment/nosniff/no-store headers. Check date display around Manila midnight.
6. Capture screenshots using fictional data only. Record the commit/tag, actual checks, deployment date and any known issues.

The Docker image runs as UID 10001. Named volumes persist PostgreSQL data and private files; original files are not copied into the image. The private-file volume inherits the image directory ownership on first creation. If you substitute host bind mounts, set ownership for UID 10001 and directory permissions before starting.

Caddy obtains HTTPS certificates. Its proxy explicitly overwrites `X-Forwarded-For`; Nginx uses this trusted header for login limiting and overwrites `X-Forwarded-Proto` for Django. Do not expose the app or Nginx directly to the public internet or trust forwarded headers from arbitrary clients. If deploying behind another managed proxy, review its header and body-limit behavior instead of copying this trust configuration unchanged.

The app container's health check is TCP liveness. `/health/` is process liveness, not database/file readiness. Monitor database connectivity and storage separately. The 512 MiB app container limit is an initial guard, not a measured capacity guarantee; inspect real memory use during the rehearsal before choosing a host plan.

## Backup, restore, and updates

Back up PostgreSQL **and** the `private_files` volume, plus the securely stored environment configuration. Never put a real backup in the repository or portfolio archive. A database dump alone cannot restore original documents.

For a consistent rehearsal, pause app/proxy traffic while taking both backups. Use `pg_dump` through `docker compose exec -T db`, and a read-only volume mount in a temporary backup container for the private files. Keep backups encrypted with restricted access. Select backup frequency and retention with the event team. No backup automation is configured yet.

Restore into an isolated fresh stack. Restore PostgreSQL, restore private files with UID 10001 ownership, run migrations and the deployment checks, then confirm an original file download, both roles and a report refresh. Do this once before collecting real documents. A backup that has never been restored is unverified.

Before an update: record the image/commit, take a paired backup, run CI, build a tagged image, apply migrations once, restart the app, and check logs and an end-to-end package. Migration compatibility determines whether rolling back only the application is safe; otherwise restore the paired backup. `docker compose down -v` deletes persistent data and is not part of routine updates.
