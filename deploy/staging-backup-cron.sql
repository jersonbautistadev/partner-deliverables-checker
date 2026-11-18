-- Dedicated Supabase STAGING project only. Does not change the default branch.
-- Prerequisite: staging-mail-cron.sql. Provision pdc_staging_actions_token in
-- Vault: fine-grained token, this repository only, Actions read/write, expiring.
-- First push/review the workflow, configure STAGING_* secrets and variables,
-- and manually verify the job before activating this nightly dispatcher.
BEGIN;
CREATE OR REPLACE FUNCTION pdc_staging_ops.dispatch_backup()
RETURNS boolean
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
AS $backup$
DECLARE
    credential text;
    response extensions.http_response;
BEGIN
    SELECT decrypted_secret INTO STRICT credential FROM vault.decrypted_secrets
        WHERE name = 'pdc_staging_actions_token';
    IF credential !~ '^github_pat_[A-Za-z0-9_]{40,250}$' THEN
        RAISE EXCEPTION 'Configure a dedicated fine-grained staging Actions token';
    END IF;
    PERFORM extensions.http_reset_curlopt();
    PERFORM extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '20000');
    PERFORM extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT', '10');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYPEER', '1');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYHOST', '2');
    SELECT * INTO response FROM extensions.http(ROW(
        'POST',
        'https://api.github.com/repos/jersonbautistadev/partner-deliverables-checker/actions/workflows/mail-delivery.yml/dispatches',
        ARRAY[
            extensions.http_header('Authorization', 'Bearer ' || credential),
            extensions.http_header('Accept', 'application/vnd.github+json'),
            extensions.http_header('X-GitHub-Api-Version', '2026-03-10'),
            extensions.http_header('User-Agent', 'PDC-staging-backup-scheduler')
        ],
        'application/json', '{"ref":"fix/dev-team-release-gaps"}'
    )::extensions.http_request);
    PERFORM extensions.http_reset_curlopt();
    IF response.status IS DISTINCT FROM 200 OR COALESCE(response.content_type, '') NOT LIKE 'application/json%'
       OR jsonb_typeof(response.content::jsonb -> 'workflow_run_id') IS DISTINCT FROM 'number' THEN
        RAISE EXCEPTION 'Staging backup dispatch unavailable';
    END IF;
    -- Dispatch acknowledgement is not backup success. Only backup_offsite's
    -- verified upload + full read-back sends the independent success heartbeat.
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    PERFORM extensions.http_reset_curlopt();
    RAISE EXCEPTION 'Staging backup dispatch failed; inspect Actions and backup age';
END
$backup$;
REVOKE ALL ON FUNCTION pdc_staging_ops.dispatch_backup()
    FROM PUBLIC, anon, authenticated, pdc_web, pdc_migrator;
SELECT cron.schedule('pdc-staging-backup', '17 18 * * *',
                     'SELECT pdc_staging_ops.dispatch_backup();');
SELECT cron.alter_job(jobid, active := false) FROM cron.job
    WHERE jobname = 'pdc-staging-backup';
COMMIT;
