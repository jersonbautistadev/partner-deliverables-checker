import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from checker.models import Account, Asset, Evidence, Membership, Package, Partner, Requirement, Workspace
from checker.security import LimitExceeded
from checker.services import store_asset, submit_evidence


@skipUnless(connection.vendor == "postgresql", "Row-lock behavior requires PostgreSQL.")
@override_settings(AUTH_RATE_LIMIT=1000, WORK_RATE_LIMIT=1000)
class PostgreSQLConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.storage = override_settings(MEDIA_ROOT=self.folder.name)
        self.storage.enable()
        self.addCleanup(self.storage.disable)
        self.users = []
        self.workspace = Workspace.objects.create(name="Concurrent team", storage_limit=10)
        for index in range(2):
            user = get_user_model().objects.create_user(
                f"concurrent{index}", password="Test-Password-829!"
            )
            Account.objects.create(
                user=user, email=f"concurrent{index}@example.test", verified_at=timezone.now()
            )
            Membership.objects.create(user=user, workspace=self.workspace, role="coordinator")
            self.users.append(user)
        self.partner = Partner.objects.create(workspace=self.workspace, name="Partner")

    def test_two_uploads_cannot_exceed_shared_storage_limit(self):
        packages = [
            Package.objects.create(
                partner=self.partner, owner=user, title=f"Kit {user.pk}", stage="pre"
            )
            for user in self.users
        ]
        barrier = Barrier(2)

        def upload(index):
            try:
                package = Package.objects.select_related("partner").get(pk=packages[index].pk)
                barrier.wait(timeout=10)
                try:
                    store_asset(
                        package,
                        self.users[index],
                        "article",
                        SimpleUploadedFile("file.txt", b"sixsix"),
                    )
                    return "stored"
                except LimitExceeded:
                    return "quota"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(upload, range(2)))
        self.assertCountEqual(result, ["stored", "quota"])
        self.assertEqual(Asset.objects.count(), 1)

    @override_settings(MAX_EVIDENCE_REVISIONS=1)
    def test_concurrent_evidence_submissions_cannot_exceed_workspace_quota(self):
        rule = Requirement.objects.create(partner=self.partner, stage="pre", title="Published story", kind="evidence", slot="", source="Fictional brief")
        packages = [Package.objects.create(partner=self.partner, stage="pre", title=f"Evidence {user.pk}", owner=user) for user in self.users]
        barrier = Barrier(2)

        def submit(index):
            try:
                package = Package.objects.select_related("partner").get(pk=packages[index].pk)
                barrier.wait(timeout=10)
                try:
                    submit_evidence(package, rule, self.users[index], 0, "https://example.test/story", "Synthetic observation")
                    return "stored"
                except LimitExceeded:
                    return "quota"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(submit, range(2)))
        self.assertCountEqual(result, ["stored", "quota"])
        self.assertEqual(Evidence.objects.count(), 1)

    def test_two_coordinators_cannot_simultaneously_remove_the_last_coordinator(self):
        barrier = Barrier(2)
        memberships = list(Membership.objects.order_by("pk"))

        def demote(index):
            try:
                client = Client()
                client.force_login(self.users[index])
                session = client.session
                session["workspace_id"] = self.workspace.pk
                session.save()
                barrier.wait(timeout=10)
                return client.post(
                    reverse("membership_change", args=[memberships[index].pk]),
                    {"role": "contributor"},
                ).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(demote, range(2)))
        self.assertEqual(result, [302, 302])
        self.assertEqual(Membership.objects.filter(role="coordinator").count(), 1)

    @override_settings(
        MAX_SERVICE_WORKSPACES=2,
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        },
    )
    def test_different_accounts_cannot_exceed_pilot_workspace_capacity(self):
        barrier = Barrier(2)

        def create(index):
            try:
                client = Client()
                client.force_login(self.users[index])
                barrier.wait(timeout=10)
                return client.post(reverse("workspace_create"), {"name": f"New pilot team {index}"}).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, range(2)))
        self.assertCountEqual(results, [302, 200])
        self.assertEqual(Workspace.objects.count(), 2)
        self.assertEqual(Workspace.objects.filter(name__startswith="New pilot team").count(), 1)

    @override_settings(MAIL_DAILY_ATTEMPT_LIMIT=1)
    def test_two_dispatchers_share_one_daily_mail_budget(self):
        from unittest.mock import patch
        from checker.mail import deliver_batch
        from checker.models import MailJob

        for index in range(2):
            MailJob.objects.create(recipient=f"fixture{index}@example.test", subject="Fixture", body="Fixture", available_at=timezone.now())
        barrier = Barrier(2)

        def dispatch(index):
            try:
                barrier.wait(timeout=10)
                return deliver_batch(1)
            finally:
                connections.close_all()

        with patch("checker.mail.send_mail", return_value=1) as send:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(dispatch, range(2)))
        self.assertCountEqual(results, [1, 0])
        self.assertEqual(send.call_count, 1)
        self.assertEqual(MailJob.objects.filter(sent_at__isnull=False).count(), 1)
        self.assertEqual(MailJob.objects.get(sent_at__isnull=True).attempts, 0)
