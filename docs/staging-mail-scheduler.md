# Staging mail scheduler

The dedicated Supabase staging project runs `pdc-staging-mail` every two minutes.
It POSTs to the protected Vercel **branch alias**, using the existing `/ops/mail/`
endpoint. Each invocation handles at most five eligible messages and records the
application's mail heartbeat. No local laptop process is required. This is best
effort: provider outages, free-tier pauses, expired credentials or a growing queue
can delay delivery. Production's Actions dispatcher remains disabled.

## Provisioning

Use this configuration only in the separate Django staging project, with Data API
disabled and the existing `pdc_web`/`pdc_migrator` roles. It does not configure a
production dispatcher. Supabase's `pg_cron`, `http` and Vault extensions are
provider infrastructure, not application dependencies or Django migrations.

1. In the staging project's Vault, privately create these uniquely named entries:

   | Name | Value |
   | --- | --- |
   | `pdc_staging_mail_url` | Exact staging Git branch alias plus `/ops/mail/` |
   | `pdc_staging_ops_secret` | Staging app's `OPS_SECRET` |
   | `pdc_staging_vercel_bypass` | Active Vercel automation credential for the staging preview |

   Enter credentials privately in Vault or use a trusted parameterized database
   client. Do not place them in SQL history, cron commands, URLs, Git or logs.
   The Vercel automation credential is project scoped: protect it accordingly.

2. Apply [the SQL configuration](../deploy/staging-mail-cron.sql) as the staging
   `postgres` operator. It creates/updates **one paused job**. The function rejects
   canonical production URLs, verifies HTTPS certificates/hostnames, bounds its
   connection/request times and does not follow redirects. Credentials are read
   from Vault into headers; they are not persisted in an HTTP request queue.

   Supabase owns the HTTP functions and grants PUBLIC execution. The SQL removes
   `extensions` schema access from the two application roles and the unused
   `anon`/`authenticated` Data API roles. Existing `service_role` and dashboard
   grants are preserved. It refuses inherited networking/Vault access; do not
   weaken that check. Do not apply this script to a project whose other apps need
   those roles to access extension functions.

3. Verify all four roles lack `extensions` schema usage and SELECT on
   `vault.decrypted_secrets`; application roles must also be denied execution of
   `pdc_staging_ops.dispatch_mail()`. Then invoke the function once against the
   staging queue containing only approved test recipients:

   ```sql
   SELECT pdc_staging_ops.dispatch_mail();
   SELECT cron.alter_job(jobid, active := true)
   FROM cron.job WHERE jobname = 'pdc-staging-mail';
   ```

4. Queue a test message for an approved mailbox. Verify a subsequent **scheduled**
   run succeeds, that message's `sent_at`/attempt count changes, and the recipient
   receives it. A manual function call alone does not verify scheduling; SMTP
   acknowledgement alone does not establish inbox receipt.

## Monitoring and recovery

Inspect actual scheduled execution as the operator:

```sql
SELECT jobid, jobname, schedule, active
FROM cron.job WHERE jobname = 'pdc-staging-mail';

SELECT status, start_time, end_time, return_message
FROM cron.job_run_details
WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'pdc-staging-mail')
ORDER BY start_time DESC LIMIT 10;
```

The function accepts only HTTP 200 with a JSON delivery count from zero to five.
Other responses or network failures fail the job with a fixed message; provider
error details and mail content are not copied into cron history. Check protected
`/ready/` and the application queue/heartbeat when investigating. Configure an
independent alert destination; no alert delivery is implied by cron history.
Retain cron history according to operator policy to prevent unbounded growth.

The preview automation credential is now a scheduler credential, retained while
this job is active. Rotating/revoking it or the app's operations secret requires
updating Vault and repeating a scheduled delivery test. Moving the branch alias
to another service configuration also requires re-verification.

Application backup bundles intentionally exclude this provider schema, Vault and
cron configuration. An offline restore must remain without a dispatcher; review
restored queues/tokens before deliberately configuring a new scheduler. Provider
project clones/snapshots can copy cron/Vault state: disable copied jobs and rotate
the destination credential before operating a clone.

## Pause or remove

```sql
SELECT cron.alter_job(jobid, active := false)
FROM cron.job WHERE jobname = 'pdc-staging-mail';
-- To remove this one job permanently:
SELECT cron.unschedule('pdc-staging-mail');
```

After removing the job, remove its three named Vault entries and revoke its Vercel
automation credential. Remove the operator function if no longer needed. Do not
drop shared extensions or restore anonymous networking access blindly. No
production queue, global GitHub dispatcher variable or main-branch change is
needed for this staging setup.

Primary references: [Supabase Cron installation](https://supabase.com/docs/guides/cron/install),
[HTTP extension](https://supabase.com/docs/guides/database/extensions/http),
[Vault](https://supabase.com/docs/guides/database/vault),
[pgsql-http options](https://github.com/pramsey/pgsql-http), and
[Vercel automation protection](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation).
