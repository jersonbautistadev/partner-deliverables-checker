"""Execute production operator SQL against native PostgreSQL boundary fixtures.

HTTP, Vault and cron are doubles in a disposable local database. This verifies
SQL/control flow/role denials, NOT Supabase networking or actual alert delivery.
No HTTP implementation or real credentials are installed in this rehearsal.
"""
import os
from pathlib import Path
import uuid

import psycopg
from psycopg import sql


def main():
    host = os.environ.get("POSTGRES_HOST", "localhost")
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Operator SQL rehearsal requires a local disposable PostgreSQL server.")
    params = dict(host=host, port=os.environ.get("POSTGRES_PORT", "5432"),
                  user=os.environ.get("POSTGRES_USER", "postgres"),
                  password=os.environ.get("POSTGRES_PASSWORD", ""), autocommit=True)
    name = "pdc_ops_" + uuid.uuid4().hex[:12]
    created_roles = []
    database_created = False
    with psycopg.connect(dbname=os.environ.get("POSTGRES_DB", "postgres"), **params) as admin:
        try:
            for role in ["postgres", "anon", "authenticated", "pdc_web", "pdc_migrator"]:
                if not admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [role]).fetchone():
                    admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
                    created_roles.append(role)
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            database_created = True
            with psycopg.connect(dbname=name, **params) as conn:
                conn.execute(FIXTURES)
                source = Path("deploy/production-operations.sql").read_text(encoding="utf-8")
                for line in ("CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;",
                             "CREATE EXTENSION IF NOT EXISTS http WITH SCHEMA extensions;"):
                    assert line in source
                    source = source.replace(line, "-- Provided by the local boundary fixture.")
                if os.environ.get("OPS_SQL_DEBUG") == "1":
                    source = source.replace("RAISE EXCEPTION 'Production application request unavailable';", "RAISE;")
                    source = source.replace("RAISE EXCEPTION 'Production mail dispatch failed; inspect readiness and queue';", "RAISE;")
                cur = conn.execute(source)
                while cur.nextset():
                    pass
                assert conn.execute("SELECT count(*) FROM cron.job WHERE NOT active").fetchone()[0] == 5
                base = "https://partner-deliverables-checker-puux.vercel.app"
                ready_ping = "https://hc-ping.com/00000000-0000-0000-0000-000000000001"
                for key, value in {
                    "pdc_production_origin": base,
                    "pdc_production_ops_secret": "fixture-operations-secret-with-at-least-32-characters",
                    "pdc_production_vercel_bypass": "0" * 32,
                    "pdc_production_readiness_ping": ready_ping,
                    "pdc_production_maintenance_ping": ready_ping[:-1] + "2",
                    "pdc_production_capacity_ping": ready_ping[:-1] + "3",
                    "pdc_production_actions_token": "github_pat_" + "0" * 80,
                    "pdc_production_backup_ref": "main",
                }.items():
                    conn.execute("INSERT INTO vault.decrypted_secrets VALUES(%s,%s)", [key, value])
                for route, body in [("/ready/", '{"status":"ready"}'),
                                    ("/ops/mail/", '{"delivered":0}'),
                                    ("/ops/maintenance/", '{"status":"completed"}')]:
                    conn.execute("INSERT INTO extensions.responses VALUES(%s,200,'application/json',%s)", [base + route, body])
                github = "https://api.github.com/repos/jersonbautistadev/partner-deliverables-checker/actions/workflows/mail-delivery.yml/dispatches"
                conn.execute("INSERT INTO extensions.responses VALUES(%s,200,'application/json',%s)", [github, '{"workflow_run_id":123}'])
                for suffix in ("1", "2", "3"):
                    for path in ("", "/fail"):
                        conn.execute("INSERT INTO extensions.responses VALUES(%s,200,'text/plain','OK')", [ready_ping[:-1] + suffix + path])
                for role in ["anon", "authenticated", "pdc_web", "pdc_migrator"]:
                    conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
                    try:
                        conn.execute("SELECT pdc_production_ops.dispatch_mail()")
                    except psycopg.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise AssertionError("Untrusted operator access: " + role)
                    finally:
                        conn.execute("RESET ROLE")
                assert conn.execute("SELECT pdc_production_ops.dispatch_mail()").fetchone()[0] == 0
                assert conn.execute("SELECT pdc_production_ops.check_readiness()").fetchone()[0]
                assert conn.execute("SELECT pdc_production_ops.dispatch_backup()").fetchone()[0]
                assert conn.execute("SELECT pdc_production_ops.check_capacity()").fetchone()[0]
                conn.execute("INSERT INTO cron.job_run_details SELECT jobid,now()-interval '8 days' FROM cron.job")
                conn.execute("INSERT INTO cron.job_run_details VALUES(9999,now()-interval '8 days')")
                assert conn.execute("SELECT pdc_production_ops.maintain()").fetchone()[0]
                assert conn.execute("SELECT jobid FROM cron.job_run_details").fetchall() == [(9999,)]

                def failure(function):
                    try:
                        conn.execute("SELECT pdc_production_ops." + function + "()")
                    except psycopg.errors.RaiseException:
                        return
                    raise AssertionError("Unexpected success: " + function)

                for status, ctype, body in [(302, "text/html", "sign in"),
                                           (200, None, '{"status":"ready"}'),
                                           (200, "application/json", "malformed")]:
                    conn.execute("UPDATE extensions.responses SET status=%s,ctype=%s,body=%s WHERE url=%s", [status, ctype, body, base + "/ready/"])
                    before = conn.execute("SELECT last_value FROM extensions.failure_pings").fetchone()[0]
                    failure("check_readiness")
                    assert conn.execute("SELECT last_value FROM extensions.failure_pings").fetchone()[0] == before + 1
                conn.execute("UPDATE extensions.responses SET status=200,ctype='application/json',body=%s WHERE url=%s", ['{"status":"ready"}', base + "/ready/"])
                conn.execute("UPDATE extensions.responses SET body=NULL WHERE url=%s", [ready_ping])
                failure("check_readiness")
                conn.execute("UPDATE extensions.responses SET body='OK' WHERE url=%s", [ready_ping])
                conn.execute("UPDATE extensions.responses SET body='{}' WHERE url=%s", [github])
                failure("dispatch_backup")
                conn.execute("UPDATE extensions.responses SET body=%s WHERE url=%s", ['{"delivered":999}', base + "/ops/mail/"])
                failure("dispatch_mail")
                conn.execute("INSERT INTO storage.objects VALUES (%s)", ['{"size":900000000}'])
                failure("check_capacity")
                print("Operator SQL boundary rehearsal passed: 5 paused jobs, role denials, ready/mail/maintenance/backup/capacity contracts, NULL acknowledgements, failures and scoped log retention.")
        finally:
            assert name.startswith("pdc_ops_")
            if database_created:
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            for role in reversed(created_roles):
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


FIXTURES = """
CREATE SCHEMA extensions; CREATE SCHEMA vault; CREATE SCHEMA cron;
CREATE SCHEMA storage; CREATE TABLE storage.objects(metadata jsonb);
CREATE TABLE vault.decrypted_secrets(name text PRIMARY KEY,decrypted_secret text);
CREATE TYPE extensions.http_header AS (field text,value text);
CREATE FUNCTION extensions.http_header(text,text) RETURNS extensions.http_header LANGUAGE sql AS $$SELECT ROW($1,$2)::extensions.http_header$$;
CREATE TYPE extensions.http_request AS (method text,uri text,headers extensions.http_header[],content_type text,content text);
CREATE TYPE extensions.http_response AS (status integer,content_type text,headers extensions.http_header[],content text);
CREATE TABLE extensions.responses(url text PRIMARY KEY,status integer,ctype text,body text);
CREATE SEQUENCE extensions.failure_pings MINVALUE 0 START 0;
SELECT setval('extensions.failure_pings',0,true);
CREATE FUNCTION extensions.http_reset_curlopt() RETURNS boolean LANGUAGE sql AS $$SELECT true$$;
CREATE FUNCTION extensions.http_set_curlopt(text,text) RETURNS boolean LANGUAGE sql AS $$SELECT true$$;
CREATE FUNCTION extensions.http(r extensions.http_request) RETURNS extensions.http_response LANGUAGE plpgsql AS $$
DECLARE result extensions.http_response;
BEGIN
 IF r.uri LIKE 'https://hc-ping.com/%/fail' THEN PERFORM nextval('extensions.failure_pings'); END IF;
 SELECT status,ctype,ARRAY[]::extensions.http_header[],body INTO STRICT result FROM extensions.responses WHERE url=r.uri;
 RETURN result;
END$$;
CREATE TABLE cron.job(jobid bigserial PRIMARY KEY,jobname text UNIQUE,schedule text,command text,active boolean DEFAULT true);
CREATE TABLE cron.job_run_details(jobid bigint,end_time timestamptz);
CREATE FUNCTION cron.schedule(text,text,text) RETURNS bigint LANGUAGE sql AS $$
 INSERT INTO cron.job(jobname,schedule,command) VALUES($1,$2,$3)
 ON CONFLICT(jobname) DO UPDATE SET schedule=$2,command=$3 RETURNING jobid
$$;
CREATE FUNCTION cron.alter_job(bigint,schedule text DEFAULT NULL,active boolean DEFAULT NULL) RETURNS void LANGUAGE sql AS $$
 UPDATE cron.job j SET schedule=COALESCE($2,j.schedule),active=COALESCE($3,j.active) WHERE j.jobid=$1
$$;
"""


if __name__ == "__main__":
    main()
