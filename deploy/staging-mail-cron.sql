-- Optional Supabase STAGING scheduler. Run as postgres in a dedicated staging
-- project after provisioning the three named Vault entries in the runbook.
-- This is operator configuration, not a Django migration or production default.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;
CREATE EXTENSION IF NOT EXISTS http WITH SCHEMA extensions;
CREATE SCHEMA IF NOT EXISTS pdc_staging_ops AUTHORIZATION postgres;
REVOKE ALL ON SCHEMA pdc_staging_ops FROM PUBLIC, anon, authenticated, pdc_web, pdc_migrator;

-- Supabase owns the HTTP functions and grants PUBLIC execution. Prevent access
-- through the enclosing schema, preserving service_role/dashboard permissions.
-- This dedicated Django project has Data API disabled; anon/authenticated do not
-- need extensions access. Refuse installation if inherited grants still allow it.
REVOKE USAGE ON SCHEMA extensions FROM anon, authenticated, pdc_web, pdc_migrator;
DO $permissions$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'pdc_web', 'pdc_migrator']
    LOOP
        IF has_schema_privilege(role_name, 'extensions', 'USAGE')
           OR has_table_privilege(role_name, 'vault.decrypted_secrets', 'SELECT') THEN
            RAISE EXCEPTION 'Untrusted role still has networking or Vault access';
        END IF;
    END LOOP;
END
$permissions$;

CREATE OR REPLACE FUNCTION pdc_staging_ops.dispatch_mail()
RETURNS integer
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog
AS $dispatch$
DECLARE
    endpoint text;
    ops_secret text;
    preview_secret text;
    response extensions.http_response;
    delivered integer;
BEGIN
    SELECT decrypted_secret INTO STRICT endpoint FROM vault.decrypted_secrets
        WHERE name = 'pdc_staging_mail_url';
    SELECT decrypted_secret INTO STRICT ops_secret FROM vault.decrypted_secrets
        WHERE name = 'pdc_staging_ops_secret';
    SELECT decrypted_secret INTO STRICT preview_secret FROM vault.decrypted_secrets
        WHERE name = 'pdc_staging_vercel_bypass';
    -- A Vercel Git branch alias is required; canonical production URLs are refused.
    IF endpoint !~ '^https://[a-z0-9-]+-git-[a-z0-9-]+\.vercel\.app/ops/mail/$'
       OR length(ops_secret) < 32 OR length(preview_secret) <> 32 THEN
        RAISE EXCEPTION 'Invalid staging dispatcher configuration';
    END IF;
    PERFORM extensions.http_reset_curlopt();
    PERFORM extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '90000');
    PERFORM extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT', '10');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYPEER', '1');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYHOST', '2');
    -- http 1.6 does not enable redirect following. Keep secrets in headers only.
    SELECT * INTO response FROM extensions.http(ROW(
        'POST', endpoint,
        ARRAY[
            extensions.http_header('Authorization', 'Bearer ' || ops_secret),
            extensions.http_header('x-vercel-protection-bypass', preview_secret)
        ],
        'application/json', '{}'
    )::extensions.http_request);
    PERFORM extensions.http_reset_curlopt();
    IF response.status IS DISTINCT FROM 200 OR COALESCE(response.content_type, '') NOT LIKE 'application/json%'
       OR jsonb_typeof(response.content::jsonb -> 'delivered') IS DISTINCT FROM 'number' THEN
        RAISE EXCEPTION 'Staging dispatcher response unavailable';
    END IF;
    delivered := (response.content::jsonb ->> 'delivered')::integer;
    IF delivered < 0 OR delivered > 5 THEN
        RAISE EXCEPTION 'Invalid dispatcher batch result';
    END IF;
    RETURN delivered;
EXCEPTION WHEN OTHERS THEN
    PERFORM extensions.http_reset_curlopt();
    -- Neither provider exception text nor response bodies belong in cron history.
    RAISE EXCEPTION 'Staging mail dispatch failed; inspect readiness and queue';
END
$dispatch$;
REVOKE ALL ON FUNCTION pdc_staging_ops.dispatch_mail()
    FROM PUBLIC, anon, authenticated, pdc_web, pdc_migrator;

-- Same name updates this one job. It runs as the current operator, postgres.
SELECT cron.schedule('pdc-staging-mail', '*/2 * * * *',
                     'SELECT pdc_staging_ops.dispatch_mail();');
-- Verify one operator invocation and role denials before explicitly activating.
SELECT cron.alter_job(jobid, active := false) FROM cron.job WHERE jobname = 'pdc-staging-mail';
COMMIT;
