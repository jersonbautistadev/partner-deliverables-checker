"""Django integration tests: database, permissions, HTTP, cache invalidation.

Run with python manage.py test. Pure engine tests live in tests/test_engine.py.
"""

import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from checker.forms import RequirementForm
from checker.models import AuditEvent, Package, Partner, Requirement
from checker.services import ensure_report, record_revision, store_asset
from tests.test_engine import image_bytes


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class WorkflowTests(TestCase):
    def setUp(self):
        self.files = tempfile.TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        self.settings = override_settings(MEDIA_ROOT=self.files.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.coord = get_user_model().objects.create_user("coordinator", password="Test-Password-829!")
        self.alex = get_user_model().objects.create_user("alex", password="Test-Password-829!")
        self.sam = get_user_model().objects.create_user("sam", password="Test-Password-829!")
        self.no_role = get_user_model().objects.create_user("unassigned", password="Test-Password-829!")
        cg = Group.objects.create(name="Coordinator")
        tg = Group.objects.create(name="Contributor")
        self.coord.groups.add(cg)
        self.alex.groups.add(tg)
        self.sam.groups.add(tg)
        self.partner = Partner.objects.create(name="Fictional partner")
        self.package = Package.objects.create(partner=self.partner, stage="pre", title="Press kit", owner=self.alex)
        self.req = Requirement.objects.create(partner=self.partner, stage="pre", title="Article word count",
                                              kind="word_count", slot="article", config={"min": 2, "max": 3},
                                              source="Fictional brief §2", approved=True)
        record_revision(self.req, self.coord, "Initial approved fixture")

    def upload(self, text="one two", user=None, package=None):
        self.client.force_login(user or self.alex)
        return self.client.post(reverse("asset_upload", args=[(package or self.package).id]), {
            "slot": "article", "file": SimpleUploadedFile("article.txt", text.encode()),
        })

    def test_anonymous_redirected(self):
        for route in ["dashboard", "partners", "api_packages"]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 302)
        self.assertEqual(self.client.get(reverse("api_report", args=[self.package.id])).status_code, 302)

    def test_session_signin_and_post_signout(self):
        response = self.client.post(reverse("login"), {"username": "alex", "password": "Test-Password-829!"})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_no_role_denied(self):
        self.client.force_login(self.no_role)
        for route in ["dashboard", "partners", "api_packages", "package_new"]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_contributor_cannot_change_requirements_or_view_audit(self):
        self.client.force_login(self.alex)
        for route in ["partner_new", "requirement_new", "audit"]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)
            self.assertEqual(self.client.post(reverse(route), {}).status_code, 403)
        self.assertEqual(self.client.post(reverse("requirement_edit", args=[self.req.id]), {}).status_code, 403)

    def test_other_contributor_cannot_read_report_or_upload(self):
        self.client.force_login(self.sam)
        for route in ["package_detail", "api_report"]:
            self.assertEqual(self.client.get(reverse(route, args=[self.package.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("asset_upload", args=[self.package.id]), {}).status_code, 404)
        self.assertEqual(self.client.get(reverse("api_packages")).json()["packages"], [])

    def test_private_download_and_remove_enforce_owner(self):
        self.upload()
        asset = self.package.assets.get()
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("asset_download", args=[self.package.id, asset.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("asset_remove", args=[self.package.id, asset.id])).status_code, 404)
        self.client.force_login(self.alex)
        response = self.client.get(reverse("asset_download", args=[self.package.id, asset.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", response["Cache-Control"])
        response.close()

    def test_no_direct_media_route(self):
        self.upload()
        asset = self.package.assets.get()
        self.client.logout()
        self.assertEqual(self.client.get("/media/" + asset.file.name).status_code, 404)
        self.assertEqual(self.client.get("/private_uploads/" + asset.file.name).status_code, 404)

    def test_coordinator_can_manage_another_users_package(self):
        response = self.upload(user=self.coord)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.package.assets.count(), 1)
        self.assertEqual(self.client.get(reverse("package_detail", args=[self.package.id])).status_code, 200)

    def test_invalid_upload_not_persisted_or_audited_as_uploaded(self):
        self.client.force_login(self.alex)
        for name, content, slot in [("file.png", b"fake png", "image"), ("file.docx", b"bad zip", "article"),
                                    ("file.txt", b"", "article")]:
            response = self.client.post(reverse("asset_upload", args=[self.package.id]), {
                "slot": slot, "file": SimpleUploadedFile(name, content),
            })
            self.assertEqual(response.status_code, 302)
        self.assertEqual(self.package.assets.count(), 0)
        self.assertFalse(AuditEvent.objects.filter(action="asset.uploaded").exists())

    def test_upload_checks_content_ignoring_mime_header(self):
        self.client.force_login(self.alex)
        self.client.post(reverse("asset_upload", args=[self.package.id]), {
            "slot": "image", "file": SimpleUploadedFile("fake.png", b"<html>bad</html>", content_type="image/png"),
        })
        self.assertEqual(self.package.assets.count(), 0)

    def test_upload_refreshes_and_replacement_retains_check_history(self):
        first = ensure_report(self.package)
        self.assertEqual(first.findings[0]["status"], "missing")
        self.upload("one two")
        second = ensure_report(self.package)
        self.assertNotEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(second.findings[0]["status"], "passed")
        self.upload("one two three four")
        third = ensure_report(self.package)
        self.assertEqual(third.findings[0]["status"], "failed")
        self.assertEqual(self.package.assets.count(), 1)
        self.assertEqual(self.package.runs.count(), 3)

    def test_unchanged_report_is_cached(self):
        first = ensure_report(self.package)
        second = ensure_report(self.package)
        self.assertEqual(first.id, second.id)

    def test_requirement_content_change_invalidates_even_if_revision_not_incremented(self):
        self.upload()
        first = ensure_report(self.package)
        Requirement.objects.filter(pk=self.req.id).update(config={"min": 3})
        second = ensure_report(self.package)
        self.assertNotEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(second.findings[0]["status"], "failed")

    def test_removed_asset_refreshes_report(self):
        self.upload()
        asset = self.package.assets.get()
        self.client.post(reverse("asset_remove", args=[self.package.id, asset.id]))
        self.assertEqual(ensure_report(self.package).findings[0]["status"], "missing")

    def test_unavailable_stored_file_cannot_reuse_passed_report(self):
        self.upload()
        asset = self.package.assets.get()
        old = ensure_report(self.package)
        asset.file.storage.delete(asset.file.name)
        new = ensure_report(self.package)
        self.assertNotEqual(old.fingerprint, new.fingerprint)
        self.assertEqual(new.findings[0]["status"], "missing")

    def test_contributor_cannot_assign_package_to_someone_else(self):
        self.client.force_login(self.alex)
        self.client.post(reverse("package_new"), {"partner": self.partner.id, "stage": "post", "title": "My kit", "owner": self.sam.id})
        self.assertEqual(Package.objects.get(title="My kit").owner, self.alex)

    def test_stage_does_not_inherit_other_stage_requirements(self):
        post = Package.objects.create(partner=self.partner, stage="post", title="Post kit", owner=self.alex)
        run = ensure_report(post)
        self.assertEqual(run.findings[0]["status"], "needs_review")
        self.assertIsNone(run.findings[0]["requirement_id"])

    def manual_requirement(self):
        return Requirement.objects.create(partner=self.partner, stage="pre", title="Logo placement", kind="manual",
                                           slot="image", config={}, source="Fictional brief", approved=True)

    def test_contributor_cannot_record_review(self):
        req = self.manual_requirement()
        self.client.force_login(self.alex)
        self.assertEqual(self.client.post(reverse("manual_review", args=[self.package.id, req.id]), {}).status_code, 403)

    def test_manual_review_lifecycle_and_stale_rejection(self):
        req = self.manual_requirement()
        store_asset(self.package, self.alex, "image", SimpleUploadedFile("poster.png", image_bytes()))
        run = ensure_report(self.package)
        self.client.force_login(self.coord)
        url = reverse("manual_review", args=[self.package.id, req.id])
        response = self.client.post(url, {"fingerprint": run.fingerprint, "decision": "passed", "note": "Logo legibility inspected."})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ensure_report(self.package).findings[-1]["status"], "passed")
        store_asset(self.package, self.alex, "image", SimpleUploadedFile("replacement.png", image_bytes(101, 50)))
        self.assertEqual(ensure_report(self.package).findings[-1]["status"], "needs_review")
        self.assertEqual(self.client.post(url, {"fingerprint": run.fingerprint, "decision": "passed", "note": "Old form"}).status_code, 409)
        self.assertEqual(self.package.reviews.count(), 1)

    def test_review_cannot_bypass_missing_unapproved_or_automatic_rule(self):
        self.client.force_login(self.coord)
        req = self.manual_requirement()
        for target in [req, self.req]:
            run = ensure_report(self.package)
            response = self.client.post(reverse("manual_review", args=[self.package.id, target.id]), {
                "fingerprint": run.fingerprint, "decision": "passed", "note": "Attempt bypass",
            })
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.package.reviews.count(), 0)

    def requirement_payload(self, **overrides):
        data = {"partner": self.partner.id, "stage": "pre", "title": "Updated word count",
                "kind": "word_count", "slot": "article", "source": "New fictional source §3",
                "minimum": 4, "maximum": 8, "approved": "on", "version": self.req.revision,
                "reason": "Reviewed new word limit."}
        data.update(overrides)
        return data

    def test_requirement_edit_creates_snapshot_audit_and_refresh(self):
        self.upload()
        self.client.force_login(self.coord)
        response = self.client.post(reverse("requirement_edit", args=[self.req.id]), self.requirement_payload())
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.revision, 2)
        self.assertEqual(self.req.history.count(), 2)
        self.assertEqual(self.req.history.get(number=1).snapshot["config"], {"min": 2, "max": 3})
        self.assertEqual(ensure_report(self.package).findings[0]["status"], "failed")
        self.assertTrue(AuditEvent.objects.filter(action="requirement.revised", detail__revision=2).exists())

    def test_stale_requirement_edit_cannot_overwrite(self):
        self.client.force_login(self.coord)
        url = reverse("requirement_edit", args=[self.req.id])
        data = self.requirement_payload()
        self.client.post(url, data)
        response = self.client.post(url, {**data, "minimum": 10, "maximum": 12})
        self.assertContains(response, "changed while you were editing")
        self.req.refresh_from_db()
        self.assertEqual(self.req.config["min"], 4)
        self.assertEqual(self.req.history.count(), 2)

    def test_invalid_rule_and_ambiguous_approval_rejected(self):
        self.assertFalse(RequirementForm(self.requirement_payload(minimum=9, maximum=2)).is_valid())
        self.assertFalse(RequirementForm(self.requirement_payload(ambiguous="on")).is_valid())

    def test_manila_deadline_is_converted_to_utc(self):
        form = RequirementForm(self.requirement_payload(deadline="2026-12-14T00:30"))
        self.assertTrue(form.is_valid(), form.errors)
        deadline = form.cleaned_data["deadline"]
        self.assertEqual(deadline.astimezone(ZoneInfo("UTC")), datetime(2026, 12, 13, 16, 30, tzinfo=ZoneInfo("UTC")))

    def test_dashboard_renders_deadline_in_manila(self):
        self.req.deadline = datetime(2026, 12, 13, 16, 30, tzinfo=ZoneInfo("UTC"))
        self.req.save()
        self.client.force_login(self.coord)
        with timezone.override("Asia/Manila"):
            response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "00:30")

    def test_html_escaping_for_source_reference(self):
        self.req.source = '<script>alert("xss")</script>'
        self.req.save()
        self.client.force_login(self.alex)
        response = self.client.get(reverse("requirement_detail", args=[self.req.id]))
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_csrf_required_and_get_cannot_mutate(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.alex)
        self.assertEqual(csrf_client.post(reverse("asset_upload", args=[self.package.id]), {}).status_code, 403)
        self.client.force_login(self.alex)
        self.assertEqual(self.client.get(reverse("asset_upload", args=[self.package.id])).status_code, 405)

    def test_pages_and_api_render(self):
        self.client.force_login(self.coord)
        for name in ["dashboard", "partners", "partner_new", "requirement_new", "package_new", "audit"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for name, pk in [("requirement_detail", self.req.id), ("requirement_edit", self.req.id),
                         ("package_detail", self.package.id), ("api_report", self.package.id)]:
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("api_report", args=[self.package.id])).json()["findings"][0]["requirement_id"], self.req.id)

    @override_settings(DEBUG=False)
    def test_production_seeding_rejected(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo")


class SeedTests(TestCase):
    @override_settings(DEBUG=True)
    def test_demo_is_fictional_and_repeat_is_safe(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            call_command("seed_demo")
            self.assertEqual(Partner.objects.count(), 3)
            self.assertEqual(Package.objects.count(), 3)
            statuses = [f["status"] for p in Package.objects.all() for f in ensure_report(p).findings]
            for status in ["passed", "failed", "missing", "needs_review"]:
                self.assertIn(status, statuses)
            with self.assertRaises(CommandError):
                call_command("seed_demo")
            self.assertEqual(Partner.objects.count(), 3)
