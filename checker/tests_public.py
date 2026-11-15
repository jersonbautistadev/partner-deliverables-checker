import re
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from checker.accounts import action_token
from checker.mail import deliver_batch
from checker.models import (
    Account,
    ActionToken,
    AuditEvent,
    MailJob,
    Membership,
    Package,
    Partner,
    RateBucket,
    Requirement,
    Workspace,
)
from checker.security import LimitExceeded
from checker.services import ensure_report, store_asset


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    AUTH_RATE_LIMIT=1000,
    WORK_RATE_LIMIT=1000,
    EMAIL_BACKEND="checker.mail.QueueBackend",
)
class PublicWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = get_user_model().objects.create_user(
            "alice", email="alice@example.test", password="Test-Password-829!"
        )
        cls.b = get_user_model().objects.create_user(
            "bob", email="bob@example.test", password="Test-Password-829!"
        )
        cls.c = get_user_model().objects.create_user(
            "carol", email="carol@example.test", password="Test-Password-829!"
        )
        for user in [cls.a, cls.b, cls.c]:
            Account.objects.create(user=user, email=user.email, verified_at=timezone.now())
        cls.w1 = Workspace.objects.create(name="Private Alpha", created_by=cls.a)
        cls.w2 = Workspace.objects.create(name="Private Beta", created_by=cls.b)
        Membership.objects.create(user=cls.a, workspace=cls.w1, role="coordinator")
        Membership.objects.create(user=cls.a, workspace=cls.w2, role="contributor")
        Membership.objects.create(user=cls.b, workspace=cls.w2, role="coordinator")
        cls.p1 = Partner.objects.create(workspace=cls.w1, name="Alpha partner")
        cls.p2 = Partner.objects.create(workspace=cls.w2, name="Secret Beta partner")
        cls.k1 = Package.objects.create(partner=cls.p1, owner=cls.a, title="Alpha kit", stage="pre")
        cls.k2 = Package.objects.create(partner=cls.p2, owner=cls.b, title="Beta kit", stage="pre")
        cls.r1 = Requirement.objects.create(
            partner=cls.p1,
            stage="pre",
            title="Alpha rule",
            kind="required_file",
            slot="article",
            approved=True,
        )
        cls.r2 = Requirement.objects.create(
            partner=cls.p2,
            stage="pre",
            title="Secret Beta rule",
            kind="required_file",
            slot="article",
            approved=True,
            deadline=timezone.now() + timedelta(days=1),
        )

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.storage = override_settings(MEDIA_ROOT=self.folder.name)
        self.storage.enable()
        self.addCleanup(self.storage.disable)
        self.select(self.a, self.w1)

    def select(self, user, workspace):
        self.client.force_login(user)
        session = self.client.session
        session["workspace_id"] = workspace.pk
        session.save()

    def test_workspace_pages_and_api_do_not_disclose_other_tenant(self):
        for route in [
            "dashboard",
            "partners",
            "audit",
            "api_packages",
            "requirement_new",
            "package_new",
        ]:
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "Secret Beta")
            self.assertNotContains(response, "Beta kit")
        for route, pk in [
            ("package_detail", self.k2.pk),
            ("api_report", self.k2.pk),
            ("requirement_detail", self.r2.pk),
            ("requirement_edit", self.r2.pk),
        ]:
            self.assertEqual(self.client.get(reverse(route, args=[pk])).status_code, 404)
        self.assertEqual(
            self.client.post(reverse("requirement_edit", args=[self.r2.pk]), {}).status_code, 404
        )
        self.assertEqual(
            self.client.post(reverse("asset_upload", args=[self.k2.pk]), {}).status_code, 404
        )

    def test_download_remove_and_review_direct_ids_are_scoped(self):
        asset = store_asset(
            self.k2, self.b, "article", SimpleUploadedFile("secret.txt", b"private text")
        )
        for route in ["asset_download", "asset_remove"]:
            url = reverse(route, args=[self.k2.pk, asset.pk])
            response = self.client.get(url) if route == "asset_download" else self.client.post(url)
            self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.client.post(
                reverse("manual_review", args=[self.k2.pk, self.r2.pk]), {}
            ).status_code,
            404,
        )

    def test_roles_change_with_workspace_and_owner_is_restricted(self):
        self.select(self.a, self.w2)
        self.assertEqual(self.client.get(reverse("partner_new")).status_code, 403)
        self.assertEqual(self.client.get(reverse("audit")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("package_detail", args=[self.k2.pk])).status_code, 404
        )
        self.client.post(
            reverse("package_new"),
            {"partner": self.p2.pk, "stage": "pre", "title": "Own kit", "owner": self.b.pk},
        )
        self.assertEqual(Package.objects.get(title="Own kit").owner, self.a)

    def test_cross_workspace_form_ids_cannot_be_written(self):
        response = self.client.post(
            reverse("package_new"),
            {"partner": self.p2.pk, "stage": "pre", "title": "Leak", "owner": self.b.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Package.objects.filter(title="Leak").exists())
        form = self.client.get(reverse("requirement_new")).context["form"]
        self.assertNotIn(self.p2, form.fields["partner"].queryset)

    def test_revoked_membership_blocks_existing_session(self):
        Membership.objects.filter(user=self.a, workspace=self.w1).delete()
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("workspaces"))
        self.assertEqual(self.client.get(reverse("api_packages")).status_code, 403)

    def test_audit_is_scoped(self):
        AuditEvent.objects.create(
            actor=self.b, workspace=self.w2, action="secret.beta", target="secret"
        )
        self.assertNotContains(self.client.get(reverse("audit")), "secret.beta")

    def test_switching_requires_membership_and_invalid_input_is_safe(self):
        self.select(self.c, self.w1)
        self.assertEqual(
            self.client.post(reverse("workspaces"), {"workspace": self.w1.pk}).status_code, 404
        )
        for invalid in ["bad", "\u00b2", "9" * 5000]:
            self.assertEqual(
                self.client.post(reverse("workspaces"), {"workspace": invalid}).status_code, 404
            )

    def test_unverified_user_cannot_open_workspace_or_sign_in(self):
        Account.objects.filter(user=self.a).update(verified_at=None)
        self.assertRedirects(
            self.client.get(reverse("dashboard")), reverse("verification_required")
        )
        self.client.logout()
        response = self.client.post(
            reverse("login"), {"username": "alice", "password": "Test-Password-829!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def signup(self, username="newperson", email="new@example.test"):
        self.client.logout()
        return self.client.post(
            reverse("signup"),
            {
                "username": username,
                "email": email,
                "password1": "Strong-New-Password-829!",
                "password2": "Strong-New-Password-829!",
            },
        )

    def verify_token_from_mail(self):
        return re.search(r"/accounts/verify/([^/]+)/", MailJob.objects.latest("pk").body).group(1)

    def test_signup_queues_mail_and_verification_is_post_only_single_use(self):
        self.assertEqual(self.signup().status_code, 200)
        raw = self.verify_token_from_mail()
        account = Account.objects.get(email="new@example.test")
        self.assertIsNone(account.verified_at)
        self.assertNotIn(raw, ActionToken.objects.get(user=account.user).digest)
        url = reverse("verify_email", args=[raw])
        self.client.get(url)
        account.refresh_from_db()
        self.assertIsNone(account.verified_at)
        self.assertRedirects(self.client.post(url), reverse("login"))
        self.assertContains(self.client.post(url), "invalid, expired, or already used")
        self.assertEqual(
            self.client.login(username="newperson", password="Strong-New-Password-829!"), True
        )

    def test_verification_expiry_and_resend_invalidate_old_link(self):
        self.signup()
        old = self.verify_token_from_mail()
        self.client.post(reverse("verification_required"), {"email": "NEW@example.test"})
        new = self.verify_token_from_mail()
        self.assertNotEqual(old, new)
        self.assertContains(
            self.client.post(reverse("verify_email", args=[old])), "invalid, expired"
        )
        ActionToken.objects.filter(consumed_at__isnull=True).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertContains(
            self.client.post(reverse("verify_email", args=[new])), "invalid, expired"
        )

    def test_duplicate_email_signup_and_unknown_resend_are_generic(self):
        before = Account.objects.count()
        known = self.signup("another", "ALICE@example.test")
        self.assertEqual(Account.objects.count(), before)
        unknown = self.client.post(
            reverse("verification_required"), {"email": "unknown@example.test"}
        )
        verified = self.client.post(
            reverse("verification_required"), {"email": "alice@example.test"}
        )
        self.assertEqual(unknown.content, verified.content)
        self.assertContains(known, "If these details can be registered")

    def test_password_reset_is_generic_and_token_cannot_be_reused(self):
        self.client.logout()
        response = self.client.post(reverse("password_reset"), {"email": self.a.email})
        self.assertRedirects(response, reverse("password_reset_done"))
        url = re.search(
            r"http[^\s]+/accounts/password/reset/[^\s]+", MailJob.objects.latest("pk").body
        ).group(0)
        response = self.client.get(url)
        confirm = response.url
        response = self.client.post(
            confirm,
            {
                "new_password1": "Replacement-Password-829!",
                "new_password2": "Replacement-Password-829!",
            },
        )
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.a.refresh_from_db()
        self.assertTrue(self.a.check_password("Replacement-Password-829!"))
        self.assertFalse(self.client.get(url).context["validlink"])
        before = MailJob.objects.count()
        self.assertRedirects(
            self.client.post(reverse("password_reset"), {"email": "unknown@example.test"}),
            reverse("password_reset_done"),
        )
        self.assertEqual(MailJob.objects.count(), before)

    def test_invitation_binds_verified_email_and_does_not_escalate_existing_role(self):
        raw = action_token("invite", self.c.email, workspace=self.w1, role="contributor")
        self.select(self.b, self.w2)
        self.client.post(reverse("invitation_accept", args=[raw]))
        self.assertFalse(Membership.objects.filter(user=self.b, workspace=self.w1).exists())
        self.select(self.c, self.w1)
        self.client.get(reverse("invitation_accept", args=[raw]))
        self.assertFalse(Membership.objects.filter(user=self.c, workspace=self.w1).exists())
        self.assertRedirects(
            self.client.post(reverse("invitation_accept", args=[raw])), reverse("dashboard")
        )
        self.assertEqual(Membership.objects.get(user=self.c, workspace=self.w1).role, "contributor")
        self.client.post(reverse("invitation_accept", args=[raw]))
        self.assertEqual(Membership.objects.filter(user=self.c, workspace=self.w1).count(), 1)
        again = action_token("invite", self.c.email, workspace=self.w1, role="coordinator")
        self.client.post(reverse("invitation_accept", args=[again]))
        self.assertEqual(Membership.objects.get(user=self.c, workspace=self.w1).role, "contributor")

    def test_invitation_revocation_expiry_and_other_workspace_ids(self):
        raw = action_token("invite", self.c.email, workspace=self.w1)
        token = ActionToken.objects.latest("pk")
        self.client.post(reverse("invitation_revoke", args=[token.pk]))
        self.select(self.c, self.w1)
        self.client.post(reverse("invitation_accept", args=[raw]))
        self.assertFalse(Membership.objects.filter(user=self.c, workspace=self.w1).exists())
        raw = action_token("invite", self.c.email, workspace=self.w1)
        ActionToken.objects.filter(consumed_at__isnull=True).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.client.post(reverse("invitation_accept", args=[raw]))
        self.assertFalse(Membership.objects.filter(user=self.c, workspace=self.w1).exists())
        self.select(self.a, self.w1)
        foreign = Membership.objects.get(user=self.b, workspace=self.w2)
        self.assertEqual(
            self.client.post(
                reverse("membership_change", args=[foreign.pk]), {"role": "remove"}
            ).status_code,
            404,
        )

    def test_last_coordinator_guard_and_transfer(self):
        current = Membership.objects.get(user=self.a, workspace=self.w1)
        self.client.post(reverse("membership_change", args=[current.pk]), {"role": "remove"})
        self.assertTrue(Membership.objects.filter(pk=current.pk).exists())
        other = Membership.objects.create(user=self.c, workspace=self.w1, role="contributor")
        self.client.post(reverse("membership_change", args=[other.pk]), {"role": "coordinator"})
        self.client.post(reverse("membership_change", args=[current.pk]), {"role": "contributor"})
        current.refresh_from_db()
        self.assertEqual(current.role, "contributor")
        self.assertEqual(
            self.client.post(
                reverse("membership_change", args=[other.pk]), {"role": "remove"}
            ).status_code,
            403,
        )

    def test_deactivation_requires_password_and_coordination_transfer(self):
        url = reverse("deactivate_account")
        self.assertContains(self.client.post(url, {"password": "wrong"}), "Check your password")
        self.assertContains(
            self.client.post(url, {"password": "Test-Password-829!"}), "Transfer coordination"
        )
        Membership.objects.create(user=self.c, workspace=self.w1, role="coordinator")
        self.assertRedirects(
            self.client.post(url, {"password": "Test-Password-829!"}), reverse("login")
        )
        self.a.refresh_from_db()
        self.assertFalse(self.a.is_active)
        self.assertTrue(Package.objects.filter(pk=self.k1.pk).exists())
        self.assertFalse(Membership.objects.filter(user=self.a).exists())

    @override_settings(MAX_CREATED_WORKSPACES=1)
    def test_workspace_creation_limit_is_enforced(self):
        response = self.client.post(reverse("workspace_create"), {"name": "Spam"})
        self.assertContains(response, "configured usage limit")
        self.assertFalse(Workspace.objects.filter(name="Spam").exists())

    @override_settings(MAX_PACKAGES=1)
    def test_package_count_limit(self):
        response = self.client.post(
            reverse("package_new"),
            {"partner": self.p1.pk, "stage": "post", "title": "Overflow", "owner": self.a.pk},
        )
        self.assertEqual(response.status_code, 429)
        self.assertFalse(Package.objects.filter(title="Overflow").exists())

    def test_storage_replacement_quota_failure_keeps_original(self):
        first = store_asset(self.k1, self.a, "article", SimpleUploadedFile("old.txt", b"one two"))
        self.w1.storage_limit = 8
        self.w1.save()
        with self.assertRaises(LimitExceeded):
            store_asset(
                self.k1, self.a, "article", SimpleUploadedFile("large.txt", b"much longer text")
            )
        self.assertEqual(self.k1.assets.get().pk, first.pk)
        with first.file.open("rb") as stream:
            self.assertEqual(stream.read(), b"one two")
        store_asset(self.k1, self.a, "article", SimpleUploadedFile("new.txt", b"replace"))
        self.assertEqual(self.k1.assets.count(), 1)

    @override_settings(UPLOAD_MAX_BYTES=10)
    def test_configured_upload_limit_precedes_storage(self):
        with self.assertRaises(LimitExceeded):
            store_asset(self.k1, self.a, "article", SimpleUploadedFile("large.txt", b"x" * 11))
        self.assertFalse(self.k1.assets.exists())

    @override_settings(DELIVERY_EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_queued_delivery_and_retry_do_not_log_secrets(self):
        self.signup()
        job = MailJob.objects.latest("pk")
        with patch("checker.mail.send_mail", side_effect=RuntimeError("provider secret")):
            with self.assertLogs("checker.mail", level="ERROR") as captured:
                self.assertEqual(deliver_batch(1), 0)
        self.assertNotIn("provider secret", " ".join(captured.output))
        job.refresh_from_db()
        self.assertEqual(job.attempts, 1)
        MailJob.objects.filter(pk=job.pk).update(available_at=timezone.now())
        self.assertEqual(deliver_batch(1), 1)
        self.assertEqual(len(mail.outbox), 1)
        job.refresh_from_db()
        self.assertEqual(job.body, "")
        self.assertEqual(deliver_batch(1), 0)

    @override_settings(AUTH_RATE_LIMIT=2)
    def test_auth_throttle_and_csrf(self):
        self.client.logout()
        RateBucket.objects.all().delete()
        for _ in range(2):
            self.assertEqual(
                self.client.post(
                    reverse("login"), {"username": "missing", "password": "bad"}
                ).status_code,
                200,
            )
        self.assertEqual(
            self.client.post(
                reverse("login"), {"username": "missing", "password": "bad"}
            ).status_code,
            429,
        )
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("signup"), {}).status_code, 403)

    def test_external_next_url_is_not_followed(self):
        self.client.logout()
        response = self.client.post(
            reverse("login") + "?next=https://evil.example",
            {"username": "alice", "password": "Test-Password-829!"},
        )
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_readiness_and_ops_do_not_reveal_details(self):
        self.assertEqual(self.client.get(reverse("readiness")).json(), {"status": "ready"})
        with patch("checker.operations.default_storage.exists", side_effect=RuntimeError("secret")):
            response = self.client.get(reverse("readiness"))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"secret", response.content)
        self.assertEqual(self.client.post(reverse("dispatch_mail")).status_code, 401)
        self.assertEqual(self.client.post(reverse("maintenance")).status_code, 401)

    def test_ui_controls_and_fingerprint_are_preserved(self):
        response = self.client.get(reverse("package_detail", args=[self.k1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Requirement #")
        self.assertEqual(
            self.client.get(reverse("api_report", args=[self.k1.pk])).json()["fingerprint"],
            ensure_report(self.k1).fingerprint,
        )

    def test_s3_download_requires_authorization_and_uses_attachment_url(self):
        from urllib.parse import parse_qs, urlsplit

        asset = store_asset(
            self.k1, self.a, "article", SimpleUploadedFile("private.txt", b"private content")
        )
        storage = {
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": {
                    "bucket_name": "private-fixture",
                    "access_key": "fixture-key",
                    "secret_key": "fixture-secret",
                    "endpoint_url": "https://objects.example.test",
                    "signature_version": "s3v4",
                    "default_acl": None,
                    "querystring_auth": True,
                    "querystring_expire": 60,
                },
            },
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        with (
            override_settings(STORAGES=storage),
            patch("storages.backends.s3.S3Storage.exists", return_value=True),
        ):
            response = self.client.get(reverse("asset_download", args=[self.k1.pk, asset.pk]))
            self.assertEqual(response.status_code, 302)
            query = parse_qs(urlsplit(response.url).query)
            self.assertEqual(query["X-Amz-Expires"], ["60"])
            self.assertIn("attachment", query["response-content-disposition"][0])
            self.assertEqual(query["response-content-type"], ["application/octet-stream"])
            self.select(self.b, self.w2)
            self.assertEqual(
                self.client.get(reverse("asset_download", args=[self.k1.pk, asset.pk])).status_code,
                404,
            )

    def test_duplicate_partner_name_is_a_form_error_within_one_workspace(self):
        response = self.client.post(reverse("partner_new"), {"name": self.p1.name, "notes": ""})
        self.assertContains(response, "already exists in this workspace")
        Partner.objects.create(workspace=self.w2, name=self.p1.name)

    def test_storage_failure_does_not_replace_original(self):
        original = store_asset(
            self.k1, self.a, "article", SimpleUploadedFile("old.txt", b"old bytes")
        )
        with patch(
            "django.core.files.storage.FileSystemStorage.save", side_effect=OSError("unavailable")
        ):
            response = self.client.post(
                reverse("asset_upload", args=[self.k1.pk]),
                {"slot": "article", "file": SimpleUploadedFile("new.txt", b"new bytes")},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.k1.assets.get().pk, original.pk)
        with original.file.open("rb") as stream:
            self.assertEqual(stream.read(), b"old bytes")

    def test_duplicate_username_signup_returns_generic_acknowledgement(self):
        before = get_user_model().objects.count()
        response = self.signup(username="alice", email="different@example.test")
        self.assertContains(response, "If these details can be registered")
        self.assertEqual(get_user_model().objects.count(), before)

    def test_s3_orphan_reconciliation_does_not_require_local_paths(self):
        from io import StringIO
        from unittest.mock import Mock
        from django.core.management import call_command
        from storages.backends.s3 import S3Storage

        storage = Mock(spec=S3Storage)
        storage.listdir.return_value = ([], ["orphan.txt"])
        storage.get_modified_time.return_value = timezone.now() - timedelta(days=2)
        storage.path.side_effect = NotImplementedError("Remote storage has no filesystem path.")
        with patch("checker.management.commands.reconcile_files.default_storage", storage):
            call_command("reconcile_files", stdout=StringIO())
            storage.delete.assert_not_called()
            call_command("reconcile_files", delete=True, stdout=StringIO())
            storage.delete.assert_called_once_with("orphan.txt")
