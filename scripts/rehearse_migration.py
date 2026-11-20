"""Exercise the single-team data migration in a temporary database."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    with tempfile.TemporaryDirectory() as folder:
        env = dict(
            os.environ,
            DJANGO_SETTINGS_MODULE="config.settings",
            DJANGO_DEBUG="1",
            DJANGO_SQLITE_PATH=str(Path(folder) / "legacy.sqlite3"),
        )
        for key in list(env):
            if key.startswith("POSTGRES_") or key in {"DATABASE_URL", "VERCEL"}:
                env.pop(key, None)
        subprocess.run(
            [
                sys.executable,
                "-c",
                """
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.contrib.auth.hashers import make_password
executor=MigrationExecutor(connection)
executor.migrate([('checker','0001_initial')])
apps=executor.loader.project_state([('checker','0001_initial')]).apps
User=apps.get_model('auth','User')
Group=apps.get_model('auth','Group')
coordinator=User.objects.create(username='legacy_coord',password=make_password('Legacy-Password-829!'),email='legacy@example.test')
coordinator.groups.add(Group.objects.create(name='Coordinator'))
contributor=User.objects.create(username='legacy_owner',password=make_password('Legacy-Password-829!'),email='legacy@example.test')
contributor.groups.add(Group.objects.create(name='Contributor'))
p=apps.get_model('checker','Partner').objects.create(name='Legacy partner')
r=apps.get_model('checker','Requirement').objects.create(partner=p,stage='pre',title='Legacy instruction',kind='manual',slot='image',config={'instructions':'Inspect'},approved=True)
k=apps.get_model('checker','Package').objects.create(partner=p,owner=contributor,stage='pre',title='Legacy kit')
a=apps.get_model('checker','Asset').objects.create(package=k,slot='image',file='packages/unchanged.png',original_name='original.png',sha256='a'*64,size=42,uploaded_by=contributor)
apps.get_model('checker','RequirementRevision').objects.create(requirement=r,number=1,snapshot={'config':r.config},reason='Retain this history',actor=coordinator)
apps.get_model('checker','ManualReview').objects.create(package=k,requirement=r,actor=coordinator,fingerprint='b'*64,passed=True,note='Retain this review')
apps.get_model('checker','CheckRun').objects.create(package=k,fingerprint='b'*64,engine_version='1',findings=[{'status':'passed'}])
apps.get_model('checker','AuditEvent').objects.create(actor=coordinator,action='legacy.event',target='legacy')
executor=MigrationExecutor(connection)
executor.migrate(executor.loader.graph.leaf_nodes())
from checker.models import Account,Membership,Workspace,Partner,Asset,Requirement,RequirementRevision,ManualReview,CheckRun,AuditEvent,Evidence
assert Workspace.objects.count()==1
assert Partner.objects.get(pk=p.pk).workspace_id==Workspace.objects.get().pk
assert Membership.objects.get(user_id=coordinator.pk).role=='coordinator'
assert Membership.objects.get(user_id=contributor.pk).role=='contributor'
assert Account.objects.filter(verified_at__isnull=False).count()==0
assert Account.objects.filter(email__isnull=True).count()==1
assert Asset.objects.get(pk=a.pk).file.name=='packages/unchanged.png'
assert RequirementRevision.objects.get().reason=='Retain this history'
assert ManualReview.objects.get().note=='Retain this review'
assert ManualReview.objects.get().fingerprint=='b'*64 and ManualReview.objects.get().decision==''
assert Requirement.objects.get().responsibility=='unspecified'
assert Requirement.objects.get().applicability=='required'
assert not Evidence.objects.exists()
assert CheckRun.objects.get().fingerprint=='b'*64
assert AuditEvent.objects.get().workspace_id==Workspace.objects.get().pk
print('LEGACY MIGRATION REHEARSAL PASSED: accounts, roles, duplicates, original paths, revisions, reviews, reports, audit.')
""",
            ],
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            check=True,
        )


if __name__ == "__main__":
    main()
