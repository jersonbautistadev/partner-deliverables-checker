-- Dedicated Supabase STAGING project only. Prerequisite: staging-mail-cron.sql.
-- Provision these Vault entries privately: pdc_staging_ready_url,
-- pdc_staging_readiness_ping. Existing Vercel bypass remains in Vault.
BEGIN;
CREATE OR REPLACE FUNCTION pdc_staging_ops.check_readiness()
RETURNS boolean
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
AS $monitor$
DECLARE
    endpoint text;
    monitor_url text;
    preview_secret text;
    response extensions.http_response;
    healthy boolean := false;
BEGIN
    SELECT decrypted_secret INTO STRICT endpoint FROM vault.decrypted_secrets
        WHERE name = 'pdc_staging_ready_url';
    SELECT decrypted_secret INTO STRICT monitor_url FROM vault.decrypted_secrets
        WHERE name = 'pdc_staging_readiness_ping';
    SELECT decrypted_secret INTO STRICT preview_secret FROM vault.decrypted_secrets
        WHERE name = 'pdc_staging_vercel_bypass';
    IF endpoint !~ '^https://[a-z0-9-]+-git-[a-z0-9-]+\.vercel\.app/ready/$'
       OR monitor_url !~ '^https://hc-ping\.com/[a-f0-9-]{36}$'
       OR length(preview_secret) <> 32 THEN
        RAISE EXCEPTION 'Invalid staging monitoring configuration';
    END IF;
    PERFORM extensions.http_reset_curlopt();
    PERFORM extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '20000');
    PERFORM extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT', '10');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYPEER', '1');
    PERFORM extensions.http_set_curlopt('CURLOPT_SSL_VERIFYHOST', '2');
    BEGIN
        SELECT * INTO response FROM extensions.http(ROW(
            'GET', endpoint,
            ARRAY[extensions.http_header('x-vercel-protection-bypass', preview_secret)],
            NULL, NULL
        )::extensions.http_request);
        healthy := COALESCE(response.status = 200
            AND response.content_type LIKE 'application/json%'
            AND response.content::jsonb = '{"status":"ready"}'::jsonb, false);
    EXCEPTION WHEN OTHERS THEN
        healthy := false;
    END;
    -- No application response body, headers, URL or logs are sent to the monitor.
    SELECT * INTO response FROM extensions.http(ROW(
        'POST', monitor_url || CASE WHEN healthy THEN '' ELSE '/fail' END,
        ARRAY[]::extensions.http_header[], 'application/octet-stream', ''
    )::extensions.http_request);
    PERFORM extensions.http_reset_curlopt();
    IF response.status IS DISTINCT FROM 200 OR btrim(COALESCE(response.content, '')) <> 'OK' THEN
        RAISE EXCEPTION 'Independent monitor acknowledgement unavailable';
    END IF;
    IF NOT healthy THEN
        RAISE EXCEPTION 'Staging readiness unavailable; independent monitor notified';
    END IF;
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    PERFORM extensions.http_reset_curlopt();
    RAISE EXCEPTION 'Staging readiness monitoring failed; inspect readiness and monitor';
END
$monitor$;
REVOKE ALL ON FUNCTION pdc_staging_ops.check_readiness()
    FROM PUBLIC, anon, authenticated, pdc_web, pdc_migrator;
SELECT cron.schedule('pdc-staging-readiness', '*/2 * * * *',
                     'SELECT pdc_staging_ops.check_readiness();');
SELECT cron.alter_job(jobid, active := false) FROM cron.job
    WHERE jobname = 'pdc-staging-readiness';
COMMIT;
