"""Run an isolated encrypted SQLite backup/restore rehearsal; never touches the app database."""

import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def main():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        env = dict(
            os.environ,
            DJANGO_SETTINGS_MODULE="config.settings",
            DJANGO_DEBUG="1",
            DJANGO_SQLITE_PATH=str(root / "source.sqlite3"),
            PRIVATE_UPLOAD_ROOT=str(root / "source-files"),
            BACKUP_ENCRYPTION_KEY=base64.urlsafe_b64encode(os.urandom(32)).decode(),
        )
        postgres = os.environ.get("REHEARSAL_USE_POSTGRES") == "1"
        for key in list(env):
            if (
                (key.startswith("POSTGRES_") and not postgres)
                or key.startswith("PRIVATE_S3_")
                or key in {"DATABASE_URL", "VERCEL"}
            ):
                env.pop(key, None)
        if postgres:
            env["POSTGRES_DB"] = os.environ["REHEARSAL_SOURCE_DB"]

        def run(code, active_env=env):
            subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=active_env, check=True)

        run("""
import django
django.setup()
from django.core.management import call_command
call_command('migrate',verbosity=0)
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from checker.models import Account,Membership,Workspace,Partner,Package,Requirement
from checker.services import store_asset,ensure_report,submit_evidence,record_review
from django.db import connection
if connection.vendor == 'postgresql':
    with connection.cursor() as cur:
        cur.execute('CREATE SCHEMA provider_fixture')
        cur.execute('CREATE TABLE provider_fixture.settings (value text)')
        cur.execute("INSERT INTO provider_fixture.settings VALUES ('source provider data')")
        cur.execute('CREATE TABLE public.provider_sentinel (value text)')
        cur.execute("INSERT INTO public.provider_sentinel VALUES ('source public data')")
users=[]
for name in ['recovery_coord','recovery_owner','recovery_other']:
    user=get_user_model().objects.create_user(name,password='Rehearsal-Password-829!')
    Account.objects.create(user=user,email=f'{name}@example.test',verified_at=timezone.now())
    users.append(user)
w=Workspace.objects.create(name='Recovery fixture')
Membership.objects.create(workspace=w,user=users[0],role='coordinator')
Membership.objects.create(workspace=w,user=users[1],role='contributor')
other=Workspace.objects.create(name='Other fixture')
Membership.objects.create(workspace=other,user=users[2],role='coordinator')
p=Partner.objects.create(workspace=w,name='Recovery partner')
k=Package.objects.create(partner=p,stage='pre',title='Recovered package',owner=users[1])
Requirement.objects.create(partner=p,stage='pre',title='Article required',kind='required_file',slot='article',approved=True)
store_asset(k,users[1],'article',SimpleUploadedFile('original.txt',b'original recovery fixture'))
assert ensure_report(k).findings[0]['status']=='passed'
r=Requirement.objects.create(partner=p,stage='pre',title='Published acknowledgement',kind='evidence',slot='',config={'instructions':'Inspect published credit'},source='Fictional recovery brief',approved=True,responsibility='partner')
first=submit_evidence(k,r,users[1],0,'https://example.test/first','Original observation')
submit_evidence(k,r,users[1],first.pk,'https://example.test/corrected','Corrected observation')
record_review(k,r,users[0],ensure_report(k).fingerprint,True,'Inspected corrected publication evidence.')
""")
        subprocess.run(
            [
                sys.executable,
                "manage.py",
                "backup_bundle",
                "--lock-assets" if postgres else "--traffic-paused",
                "--directory",
                str(root / "bundles"),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
        backup = next((root / "bundles").glob("*.pdc"))
        assert b"original recovery fixture" not in backup.read_bytes()
        restored = dict(
            env,
            DJANGO_SQLITE_PATH=str(root / "restored.sqlite3"),
            PRIVATE_UPLOAD_ROOT=str(root / "restored-files"),
            REHEARSAL_BUNDLE=str(backup),
        )
        if postgres:
            restored["POSTGRES_DB"] = os.environ["REHEARSAL_TARGET_DB"]
        run(
            """
import django,os
django.setup()
from django.core.management import call_command
call_command('migrate',verbosity=0)
from django.db import connection
if connection.vendor == 'postgresql':
    with connection.cursor() as cur:
        cur.execute('CREATE SCHEMA provider_fixture')
        cur.execute('CREATE TABLE provider_fixture.settings (value text)')
        cur.execute("INSERT INTO provider_fixture.settings VALUES ('retained target provider data')")
        cur.execute('CREATE TABLE public.provider_sentinel (value text)')
        cur.execute("INSERT INTO public.provider_sentinel VALUES ('retained target public data')")
call_command('restore_bundle',os.environ['REHEARSAL_BUNDLE'],confirm_empty=True)
if connection.vendor == 'postgresql':
    with connection.cursor() as cur:
        cur.execute('SELECT value FROM provider_fixture.settings')
        assert cur.fetchone()[0]=='retained target provider data'
        cur.execute('SELECT value FROM public.provider_sentinel')
        assert cur.fetchone()[0]=='retained target public data'
from django.contrib.auth import get_user_model
from django.test import Client,override_settings
from checker.models import Asset,Package,Evidence,ManualReview
from checker.services import ensure_report
k=Package.objects.get(title='Recovered package')
a=Asset.objects.get(package=k)
with a.file.open('rb') as stream:
    assert stream.read()==b'original recovery fixture'
assert ensure_report(k).findings[0]['status']=='passed'
assert Evidence.objects.filter(package=k).count()==2
assert Evidence.objects.filter(package=k).first().note=='Corrected observation'
assert ManualReview.objects.get(package=k).note=='Inspected corrected publication evidence.'
assert all(f['status']=='passed' for f in ensure_report(k).findings)
with override_settings(ALLOWED_HOSTS=['testserver']):
    for username in ['recovery_coord','recovery_owner']:
        client=Client()
        client.force_login(get_user_model().objects.get(username=username))
        assert client.get(f'/packages/{k.pk}/').status_code==200
        download=client.get(f'/packages/{k.pk}/assets/{a.pk}/download/')
        assert b''.join(download.streaming_content)==b'original recovery fixture'
        assert 'no-store' in download['Cache-Control']
        assert client.get(f'/packages/{k.pk}/evidence/{Evidence.objects.first().requirement_id}/history/').status_code==200
    client=Client()
    client.force_login(get_user_model().objects.get(username='recovery_other'))
    assert client.get(f'/packages/{k.pk}/').status_code==404
    assert client.get(f'/packages/{k.pk}/assets/{a.pk}/download/').status_code==404
    assert client.get(f'/packages/{k.pk}/evidence/{Evidence.objects.first().requirement_id}/history/').status_code==404
print('RESTORE REHEARSAL PASSED: encrypted database, original bytes, evidence history, reviews, reports, both roles, and cross-workspace denial.')
""",
            restored,
        )


if __name__ == "__main__":
    main()
