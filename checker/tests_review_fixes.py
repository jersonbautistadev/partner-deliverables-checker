"""Regression tests for the 21 Nov 2026 dev-team review findings."""

import tempfile
from datetime import timedelta
from html.parser import HTMLParser
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from checker.models import (
    Account,
    Asset,
    AuditEvent,
    CheckRun,
    Membership,
    Package,
    Partner,
    Requirement,
    Workspace,
)
from checker.services import store_asset

PASSWORD = "Test-Password-829!"


def user(name, verified=True):
    u = get_user_model().objects.create_user(name, email=f"{name}@example.test", password=PASSWORD)
    Account.objects.create(
        user=u, email=u.email, verified_at=timezone.now() if verified else None
    )
    return u


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    AUTH_RATE_LIMIT=1000,
    WORK_RATE_LIMIT=1000,
)
class ReviewFixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.coord, cls.writer = user("coord"), user("writer")
        cls.team = Workspace.objects.create(name="Fictional team", created_by=cls.coord)
        Membership.objects.create(workspace=cls.team, user=cls.coord, role="coordinator")
        Membership.objects.create(workspace=cls.team, user=cls.writer, role="contributor")
        cls.partner = Partner.objects.create(workspace=cls.team, name="Fictional partner")
        cls.package = Package.objects.create(
            partner=cls.partner, stage="pre", title="Press kit", owner=cls.writer
        )
        Requirement.objects.create(
            partner=cls.partner, stage="pre", title="Article", kind="required_file",
            slot="article", approved=True, source="Fictional brief",
        )

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        media = override_settings(MEDIA_ROOT=self.folder.name)
        media.enable()
        self.addCleanup(media.disable)

    def login(self, who):
        self.client.force_login(who)
        session = self.client.session
        session["workspace_id"] = self.team.pk
        session.save()

    # --- Security headers ---------------------------------------------------------
    def test_pages_send_strict_content_security_and_permissions_policies(self):
        response = self.client.get(reverse("login"))
        csp = response["Content-Security-Policy"]
        for directive in ("script-src 'none'", "object-src 'none'", "frame-ancestors 'none'",
                          "base-uri 'none'", "form-action 'self'"):
            self.assertIn(directive, csp)
        self.assertIn("camera=()", response["Permissions-Policy"])
        self.login(self.coord)
        self.assertIn("script-src 'none'", self.client.get(reverse("dashboard"))["Content-Security-Policy"])

    # --- Coverage page gate -------------------------------------------------------
    def test_coverage_redirects_unverified_and_unselected_users_like_other_pages(self):
        unverified = user("unverified", verified=False)
        self.client.force_login(unverified)
        response = self.client.get(reverse("coverage"))
        self.assertRedirects(response, reverse("verification_required"), fetch_redirect_response=False)
        roaming = user("roaming")
        for name in ("One", "Two"):
            Membership.objects.create(
                workspace=Workspace.objects.create(name=name), user=roaming, role="coordinator"
            )
        self.client.force_login(roaming)
        response = self.client.get(reverse("coverage"))
        self.assertRedirects(response, reverse("workspaces"), fetch_redirect_response=False)

    # --- Sign-in lockout ----------------------------------------------------------
    def attempt(self, ip, password="wrong-password"):
        return self.client.post(
            reverse("login"), {"username": "writer", "password": password}, REMOTE_ADDR=ip
        )

    def test_failures_from_one_network_do_not_lock_the_account_elsewhere(self):
        for _ in range(5):
            self.assertEqual(self.attempt("203.0.113.5").status_code, 200)
        self.assertEqual(self.attempt("203.0.113.5").status_code, 429)
        response = self.attempt("198.51.100.7", PASSWORD)
        self.assertEqual(response.status_code, 302)

    @override_settings(ACCOUNT_RATE_LIMIT=3)
    def test_account_wide_ceiling_still_stops_distributed_guessing(self):
        for index in range(3):
            self.assertEqual(self.attempt(f"203.0.113.{index + 10}").status_code, 200)
        self.assertEqual(self.attempt("203.0.113.99", PASSWORD).status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    # --- Uploads outside the workspace lock -----------------------------------------
    def test_file_bytes_are_written_before_any_lock_is_taken(self):
        depth = []
        original = FileSystemStorage._save

        def spy(storage, name, content):
            depth.append(len(connection.atomic_blocks))
            return original(storage, name, content)

        baseline = len(connection.atomic_blocks)
        with patch.object(FileSystemStorage, "_save", spy):
            store_asset(self.package, self.writer, "article", SimpleUploadedFile("a.txt", b"hello world"))
        self.assertEqual(depth, [baseline])
        self.assertTrue(Asset.objects.filter(package=self.package, slot="article").exists())

    def test_access_revoked_during_upload_keeps_no_record_or_file(self):
        Membership.objects.filter(user=self.writer).delete()
        with self.assertRaises(PermissionDenied):
            store_asset(self.package, self.writer, "article", SimpleUploadedFile("a.txt", b"hello"))
        self.assertFalse(Asset.objects.exists())
        leftovers = [p for p in __import__("pathlib").Path(self.folder.name).rglob("*") if p.is_file()]
        self.assertEqual(leftovers, [])

    # --- Report retention -----------------------------------------------------------
    def test_maintenance_keeps_recent_and_latest_reports_only(self):
        old = timezone.now() - timedelta(days=45)
        runs = [
            CheckRun.objects.create(package=self.package, fingerprint=f"{i:064d}",
                                    engine_version="1", findings=[])
            for i in range(15)
        ]
        CheckRun.objects.filter(pk__in=[r.pk for r in runs[:13]]).update(created_at=old)
        call_command("maintain_data", stdout=StringIO())
        kept = list(CheckRun.objects.filter(package=self.package).order_by("id").values_list("id", flat=True))
        self.assertEqual(kept, [r.pk for r in runs[5:]])

    # --- Previously untested view paths ---------------------------------------------
    def test_coordinator_adds_partner_and_contributor_cannot(self):
        self.login(self.writer)
        self.assertEqual(self.client.post(reverse("partner_new"), {"name": "Nope"}).status_code, 403)
        self.login(self.coord)
        response = self.client.post(reverse("partner_new"), {"name": "Campus Radio", "notes": ""})
        self.assertRedirects(response, reverse("partners"), fetch_redirect_response=False)
        partner = Partner.objects.get(name="Campus Radio")
        self.assertEqual(partner.workspace, self.team)
        self.assertTrue(AuditEvent.objects.filter(action="partner.created", workspace=self.team).exists())

    @override_settings(MAX_SERVICE_WORKSPACES=0)
    def test_creating_a_workspace_makes_the_creator_its_coordinator(self):
        self.login(self.writer)
        response = self.client.post(reverse("workspace_create"), {"name": "Writer's own team"})
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        created = Workspace.objects.get(name="Writer's own team")
        self.assertTrue(Membership.objects.filter(workspace=created, user=self.writer, role="coordinator").exists())
        self.assertEqual(self.client.session["workspace_id"], created.pk)


class _Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = None
        self.h1 = 0
        self.images_without_alt = 0
        self.inputs = []
        self.labels = set()
        self.skip_link = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "img" and "alt" not in a:
            self.images_without_alt += 1
        elif tag == "label" and a.get("for"):
            self.labels.add(a["for"])
        elif tag in {"input", "select", "textarea"} and a.get("type") not in {"hidden", "submit"}:
            self.inputs.append(a.get("id"))
        elif tag == "a" and a.get("class") == "skip" and a.get("href") == "#main":
            self.skip_link = True


@override_settings(AUTH_RATE_LIMIT=1000, WORK_RATE_LIMIT=1000)
class AccessibilityStructureTests(TestCase):
    """Static HTML checks; they complement, not replace, browser and screen-reader testing."""

    @classmethod
    def setUpTestData(cls):
        cls.coord = user("a11y")
        cls.team = Workspace.objects.create(name="Fictional team", created_by=cls.coord)
        Membership.objects.create(workspace=cls.team, user=cls.coord, role="coordinator")

    def test_key_pages_have_language_one_heading_labels_alt_text_and_skip_link(self):
        pages = [reverse("login"), reverse("signup"), reverse("password_reset")]
        for path in pages:
            self.check(path)
        self.client.force_login(self.coord)
        session = self.client.session
        session["workspace_id"] = self.team.pk
        session.save()
        for name in ("dashboard", "partners", "coverage", "package_new", "partner_new", "requirement_new"):
            self.check(reverse(name))

    def check(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        page = _Structure()
        page.feed(response.content.decode())
        self.assertEqual(page.lang, "en", path)
        self.assertEqual(page.h1, 1, path)
        self.assertEqual(page.images_without_alt, 0, path)
        self.assertTrue(page.skip_link, path)
        unlabeled = [i for i in page.inputs if not i or i not in page.labels]
        self.assertEqual(unlabeled, [], path)
