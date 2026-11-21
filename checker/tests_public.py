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
    ServiceHeartbeat,
    Workspace,
)
from checker.security import LimitExceeded
from checker.services import ensure_report, store_asset
from checker.storage import StorageUnavailable


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

    @override_settings(DEBUG=True)
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

    @override_settings(AUTH_RATE_LIMIT=10)
    def test_equivalent_unicode_usernames_cannot_bypass_account_throttle(self):
        self.client.logout()
        with patch("checker.security.time.time", return_value=9001):
            for _ in range(5):
                response = self.client.post(reverse("login"), {"username": "alice", "password": "wrong"})
                self.assertEqual(response.status_code, 200)
            # Continue past the IP limit: report the longer account wait when both block.
            for name in ("alice", "\uff41\uff4c\uff49\uff43\uff45") * 3:
                response = self.client.post(reverse("login"), {"username": name, "password": "Test-Password-829!"})
                self.assertEqual(response.status_code, 429)
                self.assertEqual(response["Retry-After"], "899")
                self.assertContains(response, "899 seconds", status_code=429)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_rate_bucket_retry_wait_ends_at_actual_boundary(self):
        from checker.security import consume_limit_wait

        with patch("checker.security.time.time", return_value=9001.2):
            self.assertEqual(consume_limit_wait("audit-limit", 1, 900), 0)
            self.assertEqual(consume_limit_wait("audit-limit", 1, 900), 899)
        with patch("checker.security.time.time", return_value=9900):
            self.assertEqual(consume_limit_wait("audit-limit", 1, 900), 0)

    def test_storage_read_outage_is_503_and_does_not_change_report(self):
        from botocore.exceptions import EndpointConnectionError
        from checker.models import CheckRun

        asset = store_asset(self.k1, self.a, "article", SimpleUploadedFile("article.txt", b"original"))
        before = list(CheckRun.objects.filter(package=self.k1).values_list("fingerprint", flat=True))
        for failure in (OSError("private provider detail"), EndpointConnectionError(endpoint_url="https://objects.example.test")):
            with patch("django.core.files.storage.FileSystemStorage.exists", side_effect=failure):
                for route in ("api_report", "package_detail"):
                    response = self.client.get(reverse(route, args=[self.k1.pk]))
                    self.assertEqual(response.status_code, 503)
                    self.assertNotIn(b"private provider detail", response.content)
                    self.assertNotIn(b"objects.example.test", response.content)
            self.assertEqual(before, list(CheckRun.objects.filter(package=self.k1).values_list("fingerprint", flat=True)))
        with patch("django.core.files.storage.FileSystemStorage.open", side_effect=OSError("private provider detail")):
            self.assertEqual(self.client.get(reverse("asset_download", args=[self.k1.pk, asset.pk])).status_code, 503)
        self.assertEqual(self.client.get(reverse("api_report", args=[self.k1.pk])).status_code, 200)
        with asset.file.open("rb") as stream:
            self.assertEqual(stream.read(), b"original")

    def test_storage_outage_during_replacement_keeps_old_file_and_report(self):
        from checker.models import CheckRun

        old = store_asset(self.k1, self.a, "article", SimpleUploadedFile("old.txt", b"old bytes"))
        run = CheckRun.objects.filter(package=self.k1).first()
        with patch("checker.services.file_exists", side_effect=StorageUnavailable):
            response = self.client.post(reverse("asset_upload", args=[self.k1.pk]), {
                "slot": "article", "file": SimpleUploadedFile("new.txt", b"new bytes")
            })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.k1.assets.get().pk, old.pk)
        self.assertEqual(CheckRun.objects.filter(package=self.k1).first().pk, run.pk)
        with old.file.open("rb") as stream:
            self.assertEqual(stream.read(), b"old bytes")

    @override_settings(UPLOAD_MAX_BYTES=3145728)
    def test_invalid_upload_message_uses_configured_limit(self):
        response = self.client.post(reverse("asset_upload", args=[self.k1.pk]), {}, follow=True)
        self.assertContains(response, "upload limit is 3.0\xa0MB")
        self.assertNotContains(response, "5 MiB")

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False, EMAIL_HOST="")
    def test_production_readiness_rejects_missing_mail_configuration(self):
        deliver_batch(0)
        response = self.client.get(reverse("readiness"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    @override_settings(
        DEBUG=False, SECURE_SSL_REDIRECT=False,
        DELIVERY_EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.test", DEFAULT_FROM_EMAIL="noreply@example.test",
        EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
    )
    def test_readiness_requires_idle_worker_heartbeat_and_healthy_queue(self):
        url = reverse("readiness")
        with patch("checker.mail.send_mail") as send:
            self.assertEqual(self.client.get(url).status_code, 503)
            self.assertEqual(deliver_batch(0), 0)
            self.assertEqual(self.client.get(url).status_code, 200)
            ServiceHeartbeat.objects.filter(name="mail").update(last_seen=timezone.now() - timedelta(minutes=20))
            self.assertEqual(self.client.get(url).status_code, 503)
            deliver_batch(0)
            job = MailJob.objects.create(recipient="fixture@example.test", subject="fixture", body="fixture", available_at=timezone.now())
            self.assertEqual(self.client.get(url).status_code, 200)
            MailJob.objects.filter(pk=job.pk).update(attempts=6)
            self.assertEqual(self.client.get(url).status_code, 503)
            MailJob.objects.filter(pk=job.pk).update(attempts=1, created_at=timezone.now() - timedelta(minutes=20))
            self.assertEqual(self.client.get(url).status_code, 503)
            MailJob.objects.filter(pk=job.pk).update(sent_at=timezone.now())
            self.assertEqual(self.client.get(url).status_code, 200)
            send.assert_not_called()

    def test_dashboard_uses_dated_snapshots_and_flags_changed_rules(self):
        store_asset(self.k1, self.a, "article", SimpleUploadedFile("article.txt", b"original"))
        with patch("django.core.files.storage.FileSystemStorage.exists", side_effect=OSError("outage")) as exists:
            response = self.client.get(reverse("dashboard"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Resolved last report")
            self.assertEqual(response.context["ready_count"], 1)
            exists.assert_not_called()
        self.r1.source = "Updated source"
        self.r1.save()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["ready_count"], 0)
        self.assertContains(response, "Report needed")
        self.assertEqual(self.client.get(reverse("api_report", args=[self.k1.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard")).context["ready_count"], 1)

    def test_dashboard_batches_queries_and_paginates_cached_packages(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def add_packages(start, end):
            for index in range(start, end):
                package = self.k1 if index == 0 else Package.objects.create(
                    partner=self.p1, owner=self.a, title=f"Kit {index}", stage="pre"
                )
                store_asset(package, self.a, "article", SimpleUploadedFile("article.txt", b"original"))

        add_packages(0, 10)
        self.client.get(reverse("dashboard"))  # Warm Django's process-level caches first.
        with CaptureQueriesContext(connection) as first:
            self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        first_count = len(first)
        add_packages(10, 30)
        with patch("django.core.files.storage.FileSystemStorage.exists") as exists:
            with CaptureQueriesContext(connection) as larger:
                response = self.client.get(reverse("dashboard"))
            exists.assert_not_called()
        larger_count = len(larger)
        self.assertGreater(first_count, 0)
        self.assertLessEqual(larger_count, first_count + 2)
        self.assertEqual(len(response.context["ready_cards"]), 20)
        self.assertEqual(response.context["ready_count"], 30)
        next_page = self.client.get(reverse("dashboard") + "?ready_page=2")
        self.assertEqual(len(next_page.context["ready_cards"]), 10)
        self.assertNotContains(response, "Secret Beta")
        print(f"DASHBOARD QUERY BUDGET: 10 packages={first_count}, 30 packages={larger_count}, storage checks=0")

    def test_new_and_engine_stale_packages_are_prioritized_without_running_checks(self):
        from checker.models import CheckRun

        ensure_report(self.k1)
        CheckRun.objects.filter(package=self.k1).update(engine_version="obsolete")
        for index in range(21):
            Package.objects.create(partner=self.p1, owner=self.a, title=f"Unchecked {index}", stage="pre")
        with patch("checker.views.ensure_report") as check:
            response = self.client.get(reverse("dashboard"))
            check.assert_not_called()
        self.assertEqual(response.context["needs_report_count"], 22)
        self.assertEqual(len(response.context["action_cards"]), 20)
        self.assertContains(response, "Report needed")

    def test_s3_signing_outage_is_503_after_authorization(self):
        from botocore.exceptions import EndpointConnectionError

        asset = store_asset(self.k1, self.a, "article", SimpleUploadedFile("article.txt", b"original"))
        storages = {
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": {"bucket_name": "private-fixture", "access_key": "fixture", "secret_key": "fixture"},
            },
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        with (
            override_settings(STORAGES=storages),
            patch("storages.backends.s3.S3Storage.exists", return_value=True),
            patch("storages.backends.s3.S3Storage.url", side_effect=EndpointConnectionError(endpoint_url="https://objects.example.test")) as sign,
        ):
            response = self.client.get(reverse("asset_download", args=[self.k1.pk, asset.pk]))
            self.assertEqual(response.status_code, 503)
            self.assertNotContains(response, "objects.example.test", status_code=503)
            sign.reset_mock()
            self.select(self.b, self.w2)
            self.assertEqual(self.client.get(reverse("asset_download", args=[self.k1.pk, asset.pk])).status_code, 404)
            sign.assert_not_called()

    @override_settings(MAIL_DAILY_ATTEMPT_LIMIT=1)
    def test_daily_mail_capacity_preserves_pending_jobs_and_resets(self):
        for index in range(2):
            MailJob.objects.create(recipient=f"pilot{index}@example.test", subject="Fixture", body="Fixture", available_at=timezone.now())
        with patch("checker.mail.send_mail", return_value=1) as send:
            with patch("checker.security.time.time", return_value=86401):
                self.assertEqual(deliver_batch(5), 1)
                waiting = MailJob.objects.get(sent_at__isnull=True)
                self.assertEqual(waiting.attempts, 0)
                self.assertEqual(waiting.body, "Fixture")
                self.assertEqual(deliver_batch(5), 0)
                self.assertContains(Client().get(reverse("password_reset")), "Account email delivery is temporarily delayed")
            with patch("checker.security.time.time", return_value=172801):
                self.assertEqual(deliver_batch(5), 1)
            self.assertEqual(send.call_count, 2)
        self.assertFalse(MailJob.objects.filter(sent_at__isnull=True).exists())

    @override_settings(MAIL_DAILY_ATTEMPT_LIMIT=1)
    def test_failed_smtp_attempt_consumes_daily_capacity(self):
        for index in range(2):
            MailJob.objects.create(recipient=f"pilot{index}@example.test", subject="Fixture", body="Fixture", available_at=timezone.now())
        with patch("checker.mail.send_mail", side_effect=RuntimeError("private transport details")) as send:
            self.assertEqual(deliver_batch(5), 0)
            self.assertEqual(send.call_count, 1)
        self.assertEqual(list(MailJob.objects.order_by("pk").values_list("attempts", flat=True)), [1, 0])
        self.assertEqual(MailJob.objects.filter(sent_at__isnull=True).count(), 2)

    @override_settings(DEBUG=True, MAIL_DAILY_ATTEMPT_LIMIT=1)
    def test_readiness_reports_blocked_mail_capacity_without_losing_messages(self):
        from checker.security import consume_limit

        MailJob.objects.create(recipient="fixture@example.test", subject="Fixture", body="Fixture", available_at=timezone.now())
        self.assertTrue(consume_limit("mail-send-day", 1, 86400))
        response = self.client.get(reverse("readiness"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertEqual(MailJob.objects.filter(sent_at__isnull=True).count(), 1)

    @override_settings(PUBLIC_SUPPORT_EMAIL="support@example.test", MAX_SERVICE_WORKSPACES=5)
    def test_pilot_information_is_public_and_available_before_verification(self):
        for client in (Client(), self.client):
            response = client.get(reverse("pilot_information"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'href="mailto:support@example.test"')
            self.assertContains(response, "up to 5 workspaces")
            self.assertNotContains(response, "Secret Beta")
        Account.objects.filter(user=self.a).update(verified_at=None)
        self.assertEqual(self.client.get(reverse("pilot_information")).status_code, 200)

    @override_settings(MAX_SERVICE_WORKSPACES=2)
    def test_pilot_workspace_limit_applies_across_accounts(self):
        response = self.client.post(reverse("workspace_create"), {"name": "One more workspace"})
        self.assertContains(response, "Pilot workspace capacity has been reached")
        self.assertEqual(Workspace.objects.count(), 2)
        self.assertFalse(Workspace.objects.filter(name="One more workspace").exists())

    @override_settings(DEBUG=False, PUBLIC_SUPPORT_EMAIL="")
    def test_production_deployment_check_requires_public_support_contact(self):
        from checker.checks import release_checks

        self.assertIn("checker.E010", [item.id for item in release_checks(None)])
        with override_settings(PUBLIC_SUPPORT_EMAIL="support@example.test"):
            self.assertNotIn("checker.E010", [item.id for item in release_checks(None)])
