-- Dedicated production Supabase project only. Install as postgres after an
-- encrypted pre-upgrade backup and migration 0004. The operator provisions Vault
-- values privately; no credentials belong in this file. All jobs install PAUSED.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;
CREATE EXTENSION IF NOT EXISTS http WITH SCHEMA extensions;
CREATE SCHEMA IF NOT EXISTS pdc_production_ops AUTHORIZATION postgres;
REVOKE ALL ON SCHEMA pdc_production_ops FROM PUBLIC, anon, authenticated, pdc_web, pdc_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA pdc_production_ops
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
REVOKE USAGE ON SCHEMA extensions FROM anon, authenticated, pdc_web, pdc_migrator;
DO $permissions$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon','authenticated','pdc_web','pdc_migrator'] LOOP
        IF has_schema_privilege(role_name,'extensions','USAGE')
           OR has_table_privilege(role_name,'vault.decrypted_secrets','SELECT') THEN
            RAISE EXCEPTION 'Untrusted role retains networking or Vault access';
        END IF;
    END LOOP;
END
$permissions$;

CREATE OR REPLACE FUNCTION pdc_production_ops.request_app(route text)
RETURNS extensions.http_response
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
AS $request$
DECLARE
    origin text;
    credential text;
    bypass text;
    response extensions.http_response;
BEGIN
    SELECT decrypted_secret INTO STRICT origin FROM vault.decrypted_secrets
        WHERE name='pdc_production_origin';
    SELECT decrypted_secret INTO STRICT credential FROM vault.decrypted_secrets
        WHERE name='pdc_production_ops_secret';
    SELECT decrypted_secret INTO STRICT bypass FROM vault.decrypted_secrets
        WHERE name='pdc_production_vercel_bypass';
    IF origin <> 'https://partner-deliverables-checker-puux.vercel.app'
       OR route NOT IN ('/ops/mail/','/ops/maintenance/','/ready/')
       OR length(credential)<32 OR length(bypass)<>32 THEN
        RAISE EXCEPTION 'Invalid production operator configuration';
    END IF;
    PERFORM extensions.http_reset_curlopt();
    PERFORM extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','90000');
    PERFORM extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT','10');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYPEER','1');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYHOST','2');
    -- http 1.6 does not enable redirect following. Secrets stay in headers.
    SELECT * INTO response FROM extensions.http(ROW(
        CASE WHEN route='/ready/' THEN 'GET' ELSE 'POST' END, origin||route,
        ARRAY[extensions.http_header('Authorization','Bearer '||credential),
              extensions.http_header('x-vercel-protection-bypass',bypass)],
        CASE WHEN route='/ready/' THEN NULL ELSE 'application/json' END,
        CASE WHEN route='/ready/' THEN NULL ELSE '{}' END
    )::extensions.http_request);
    PERFORM extensions.http_reset_curlopt();
    RETURN response;
EXCEPTION WHEN OTHERS THEN
    PERFORM extensions.http_reset_curlopt();
    RAISE EXCEPTION 'Production application request unavailable';
END
$request$;

CREATE OR REPLACE FUNCTION pdc_production_ops.notify(check_name text, healthy boolean)
RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
AS $notify$
DECLARE monitor_url text; response extensions.http_response;
BEGIN
    IF check_name NOT IN ('readiness','maintenance','capacity') THEN
        RAISE EXCEPTION 'Unknown production check';
    END IF;
    SELECT decrypted_secret INTO STRICT monitor_url FROM vault.decrypted_secrets
        WHERE name='pdc_production_'||check_name||'_ping';
    IF monitor_url !~ '^https://hc-ping\.com/[a-f0-9-]{36}$' THEN
        RAISE EXCEPTION 'Invalid production monitor configuration';
    END IF;
    PERFORM extensions.http_reset_curlopt();
    PERFORM extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','10000');
    PERFORM extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT','10');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYPEER','1');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYHOST','2');
    SELECT * INTO response FROM extensions.http(ROW(
        'POST',monitor_url||CASE WHEN healthy THEN '' ELSE '/fail' END,
        ARRAY[]::extensions.http_header[],'application/octet-stream',''
    )::extensions.http_request);
    PERFORM extensions.http_reset_curlopt();
    IF response.status IS DISTINCT FROM 200 OR btrim(COALESCE(response.content,''))<>'OK' THEN
        RAISE EXCEPTION 'Independent monitor acknowledgement unavailable';
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM extensions.http_reset_curlopt();
    RAISE EXCEPTION 'Production monitor notification unavailable';
END
$notify$;

CREATE OR REPLACE FUNCTION pdc_production_ops.dispatch_mail()
RETURNS integer
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
AS $mail$
DECLARE response extensions.http_response; delivered integer;
BEGIN
    response:=pdc_production_ops.request_app('/ops/mail/');
    IF response.status IS DISTINCT FROM 200 OR COALESCE(response.content_type,'') NOT LIKE 'application/json%'
       OR jsonb_typeof(response.content::jsonb->'delivered') IS DISTINCT FROM 'number' THEN
        RAISE EXCEPTION 'Production mail dispatch unavailable';
    END IF;
    delivered:=(response.content::jsonb->>'delivered')::integer;
    IF delivered<0 OR delivered>5 THEN RAISE EXCEPTION 'Unexpected mail batch result'; END IF;
    RETURN delivered;
EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'Production mail dispatch failed; inspect readiness and queue';
END
$mail$;

CREATE OR REPLACE FUNCTION pdc_production_ops.check_readiness()
RETURNS boolean
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
AS $ready$
DECLARE response extensions.http_response; healthy boolean:=false;
BEGIN
    BEGIN
        response:=pdc_production_ops.request_app('/ready/');
        healthy:=COALESCE(response.status=200 AND response.content_type LIKE 'application/json%'
            AND response.content::jsonb='{"status":"ready"}'::jsonb,false);
    EXCEPTION WHEN OTHERS THEN healthy:=false;
    END;
    PERFORM pdc_production_ops.notify('readiness',healthy);
    IF NOT healthy THEN RAISE EXCEPTION 'Production readiness unavailable'; END IF;
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'Production readiness monitoring failed; inspect independent monitor';
END
$ready$;

CREATE OR REPLACE FUNCTION pdc_production_ops.maintain()
RETURNS boolean
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
AS $maintenance$
DECLARE response extensions.http_response;
BEGIN
    response:=pdc_production_ops.request_app('/ops/maintenance/');
    IF response.status IS DISTINCT FROM 200 OR COALESCE(response.content_type,'') NOT LIKE 'application/json%'
       OR response.content::jsonb<>'{"status":"completed"}'::jsonb THEN
        RAISE EXCEPTION 'Production maintenance unavailable';
    END IF;
    DELETE FROM cron.job_run_details WHERE end_time<now()-interval '7 days'
        AND jobid IN (SELECT jobid FROM cron.job WHERE jobname IN (
            'pdc-production-mail','pdc-production-readiness',
            'pdc-production-backup','pdc-production-maintenance','pdc-production-capacity'));
    PERFORM pdc_production_ops.notify('maintenance',true);
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    BEGIN PERFORM pdc_production_ops.notify('maintenance',false);
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
    RAISE EXCEPTION 'Production maintenance failed; inspect independent monitor';
END
$maintenance$;

CREATE OR REPLACE FUNCTION pdc_production_ops.dispatch_backup()
RETURNS boolean
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
AS $backup$
DECLARE credential text; ref text; response extensions.http_response;
BEGIN
    SELECT decrypted_secret INTO STRICT credential FROM vault.decrypted_secrets
        WHERE name='pdc_production_actions_token';
    SELECT decrypted_secret INTO STRICT ref FROM vault.decrypted_secrets
        WHERE name='pdc_production_backup_ref';
    IF credential !~ '^github_pat_[A-Za-z0-9_]{40,250}$'
       OR ref NOT IN ('main','fix/dev-team-release-gaps','feat/linked-evidence-coverage') THEN
        RAISE EXCEPTION 'Invalid production backup dispatch configuration';
    END IF;
    PERFORM extensions.http_reset_curlopt();
    PERFORM extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','20000');
    PERFORM extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT','10');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYPEER','1');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYHOST','2');
    SELECT * INTO response FROM extensions.http(ROW(
        'POST','https://api.github.com/repos/jersonbautistadev/partner-deliverables-checker/actions/workflows/mail-delivery.yml/dispatches',
        ARRAY[extensions.http_header('Authorization','Bearer '||credential),
              extensions.http_header('Accept','application/vnd.github+json'),
              extensions.http_header('X-GitHub-Api-Version','2026-03-10'),
              extensions.http_header('User-Agent','PDC-production-backup-scheduler')],
        'application/json',jsonb_build_object('ref',ref)::text
    )::extensions.http_request);
    PERFORM extensions.http_reset_curlopt();
    IF response.status IS DISTINCT FROM 200 OR COALESCE(response.content_type,'') NOT LIKE 'application/json%'
       OR jsonb_typeof(response.content::jsonb->'workflow_run_id') IS DISTINCT FROM 'number' THEN
        RAISE EXCEPTION 'Production backup dispatch unavailable';
    END IF;
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    PERFORM extensions.http_reset_curlopt();
    RAISE EXCEPTION 'Production backup dispatch failed; inspect Actions and backup age';
END
$backup$;

-- Operator-only thresholds include storage objects outside Django's asset ledger.
-- Missing pings also alert if a provider query fails before notification.
CREATE OR REPLACE FUNCTION pdc_production_ops.check_capacity()
RETURNS boolean
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
AS $capacity$
DECLARE stored_bytes bigint; connections bigint; healthy boolean;
BEGIN
    SELECT COALESCE(sum((metadata->>'size')::bigint),0) INTO stored_bytes FROM storage.objects;
    SELECT count(*) INTO connections FROM pg_stat_activity;
    healthy:=pg_database_size(current_database())<400000000
        AND stored_bytes<800000000
        AND connections<floor(current_setting('max_connections')::numeric*0.85);
    PERFORM pdc_production_ops.notify('capacity',healthy);
    IF NOT healthy THEN RAISE EXCEPTION 'Production capacity threshold reached'; END IF;
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'Production capacity check failed; inspect provider usage';
END
$capacity$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA pdc_production_ops
    FROM PUBLIC, anon, authenticated, pdc_web, pdc_migrator;
SELECT cron.schedule('pdc-production-mail','*/2 * * * *','SELECT pdc_production_ops.dispatch_mail();');
SELECT cron.schedule('pdc-production-readiness','*/2 * * * *','SELECT pdc_production_ops.check_readiness();');
SELECT cron.schedule('pdc-production-backup','47 18 * * *','SELECT pdc_production_ops.dispatch_backup();');
SELECT cron.schedule('pdc-production-maintenance','23 3 * * *','SELECT pdc_production_ops.maintain();');
SELECT cron.schedule('pdc-production-capacity','*/15 * * * *','SELECT pdc_production_ops.check_capacity();');
SELECT cron.alter_job(jobid,active:=false) FROM cron.job WHERE jobname IN (
    'pdc-production-mail','pdc-production-readiness','pdc-production-backup','pdc-production-maintenance','pdc-production-capacity');
COMMIT;
