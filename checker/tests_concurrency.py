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

from checker.models import Account, Asset, Membership, Package, Partner, Workspace
from checker.security import LimitExceeded
from checker.services import store_asset


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
