"""Synthetic evidence workflows, permissions, recovery and compatibility contracts."""

import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from checker.engine import fingerprint
from checker.forms import RequirementForm
from checker.models import (
    Account,
    AuditEvent,
    Evidence,
    ManualReview,
    Membership,
    Package,
    Partner,
    Requirement,
    Workspace,
)
from checker.services import current_inputs, ensure_report, requirement_snapshot, store_asset
from checker.storage import StorageUnavailable


@override_settings(
    WORK_RATE_LIMIT=1000,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class EvidenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.coord, cls.owner, cls.other = [
            get_user_model().objects.create(username=name)
            for name in ("editor", "writer", "outsider")
        ]
        cls.team = Workspace.objects.create(name="Synthetic coordination team")
        cls.unrelated = Workspace.objects.create(name="Unrelated team")
        for user in (cls.coord, cls.owner, cls.other):
            Account.objects.create(
                user=user, email=f"{user.username}@example.test", verified_at=timezone.now()
            )
        Membership.objects.create(workspace=cls.team, user=cls.coord, role="coordinator")
        Membership.objects.create(workspace=cls.team, user=cls.owner, role="contributor")
        Membership.objects.create(workspace=cls.unrelated, user=cls.coord, role="contributor")
        Membership.objects.create(workspace=cls.unrelated, user=cls.other, role="coordinator")
        cls.partner = Partner.objects.create(workspace=cls.team, name="Fictional media partner")
        cls.foreign = Partner.objects.create(
            workspace=cls.unrelated, name="Unrelated fictional partner"
        )
        cls.package = Package.objects.create(
            partner=cls.partner, stage="pre", title="Publicity evidence", owner=cls.owner
        )
        cls.rule = Requirement.objects.create(
            partner=cls.partner,
            stage="pre",
            title="Publish the announcement",
            kind="evidence",
            slot="",
            config={"instructions": "Inspect the published page and credit."},
            source="Fictional agreement section 4",
            approved=True,
            responsibility="team",
        )
        cls.foreign_rule = Requirement.objects.create(
            partner=cls.foreign,
            stage="pre",
            title="Private foreign obligation",
            kind="evidence",
            slot="",
            config={"instructions": "Inspect"},
            source="Private source",
            approved=True,
        )
        cls.foreign_package = Package.objects.create(
            partner=cls.foreign, stage="pre", title="Other owner's package", owner=cls.other
        )

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.storage = override_settings(MEDIA_ROOT=self.folder.name)
        self.storage.enable()
        self.addCleanup(self.storage.disable)
        self.login(self.owner)

    def login(self, user, team=None):
        self.client.force_login(user)
        session = self.client.session
        session["workspace_id"] = (team or self.team).pk
        session.save()

    def url(self, name="evidence_submit", package=None, rule=None):
        return reverse(name, args=[(package or self.package).pk, (rule or self.rule).pk])

    def submit(self, **changes):
        fields = {
            "version": 0,
            "url": "https://example.test/published-story",
            "note": "Published page with the agreed credit; coordinator to inspect.",
        }
        fields.update(changes)
        return self.client.post(self.url(), fields)

    def review(self, decision="passed", signature=None):
        self.login(self.coord)
        return self.client.post(
            self.url("manual_review"),
            {
                "fingerprint": signature or ensure_report(self.package).fingerprint,
                "decision": decision,
                "note": "Inspected the stated evidence and source conditions.",
            },
        )

    def status(self):
        return ensure_report(self.package).findings[0]["status"]

    def test_evidence_requires_coordinator_review_and_changes_invalidate_it(self):
        self.assertEqual(self.status(), "missing")
        self.assertEqual(self.submit().status_code, 302)
        self.assertEqual(self.status(), "needs_review")
        entry = Evidence.objects.get()
        signature = ensure_report(self.package).fingerprint
        self.assertEqual(
            self.client.post(
                self.url("manual_review"),
                {"fingerprint": signature, "decision": "passed", "note": "Contributor attempt"},
            ).status_code,
            403,
        )
        self.assertEqual(self.review().status_code, 302)
        self.assertEqual(self.status(), "passed")
        self.login(self.owner)
        self.assertEqual(
            self.submit(
                version=entry.pk, note="Publication was corrected; inspect this revision."
            ).status_code,
            302,
        )
        self.assertEqual(self.status(), "needs_review")
        self.assertEqual(self.review(signature=signature).status_code, 409)
        self.assertEqual(Evidence.objects.count(), 2)
        self.assertEqual(ManualReview.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="evidence.submitted").count(), 2)

    def test_missing_evidence_cannot_pass_or_be_excluded_when_required(self):
        self.assertEqual(self.review().status_code, 409)
        self.assertEqual(self.review("not_applicable").status_code, 409)
        self.assertEqual(self.status(), "missing")

    def test_optional_is_not_automatically_excluded_and_can_be_explicitly_excluded(self):
        self.rule.applicability = "optional"
        self.rule.save()
        self.assertEqual(self.status(), "missing")
        self.assertEqual(self.review("not_applicable").status_code, 302)
        self.assertEqual(self.status(), "not_applicable")
        response = self.client.get(reverse("package_detail", args=[self.package.pk]))
        self.assertContains(response, "Not applicable")
        self.assertContains(response, "Configured checks resolved")
        self.assertNotContains(response, "Ready for submission")
        self.rule.conditions = "Optional only if the organizer requests it."
        self.rule.save()
        self.assertEqual(self.status(), "missing")

    def test_unapproved_or_ambiguous_evidence_cannot_be_reviewed(self):
        self.submit()
        for fields in ({"approved": False}, {"approved": True, "ambiguous": True}):
            Requirement.objects.filter(pk=self.rule.pk).update(**fields)
            self.assertEqual(self.review().status_code, 409)
            self.assertEqual(self.status(), "needs_review")

    def test_rejected_review_remains_unresolved_and_can_be_corrected(self):
        self.submit()
        self.assertEqual(self.review("failed").status_code, 302)
        self.assertEqual(self.status(), "failed")
        self.assertEqual(self.review().status_code, 302)
        self.assertEqual(self.status(), "passed")
        self.assertEqual(ManualReview.objects.count(), 2)

    def test_stale_submission_preserves_current_evidence(self):
        self.submit()
        response = self.submit(note="Stale browser edit")
        self.assertContains(
            response,
            "Evidence changed while you were editing",
            status_code=409,
        )
        self.assertContains(response, "Open current report (new tab)", status_code=409)
        self.assertContains(response, 'type="submit" disabled', status_code=409)
        self.assertEqual(Evidence.objects.count(), 1)

    def test_unsafe_urls_and_blank_explanations_are_rejected(self):
        for fields in (
            {"url": "javascript:alert(1)"},
            {"url": "http://example.test/story"},
            {"url": "https://user:secret@example.test/story"},
            {"note": " "},
            {"version": -1},
            {"version": ""},
        ):
            self.assertEqual(self.submit(**fields).status_code, 400)
        self.assertFalse(Evidence.objects.exists())

    def test_evidence_text_is_escaped_and_external_links_are_private(self):
        self.submit(note='<script>alert("x")</script> Actual observation.')
        response = self.client.get(reverse("package_detail", args=[self.package.pk]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertIn("no-store", response["Cache-Control"])

    def test_offline_explanation_can_be_submitted_without_a_url(self):
        self.assertEqual(
            self.submit(
                url="",
                note="Observed the live acknowledgement in person; recording location and time.",
            ).status_code,
            302,
        )
        self.assertEqual(self.status(), "needs_review")

    def test_submitted_requirement_ids_and_history_are_scoped(self):
        self.assertEqual(
            self.client.post(
                self.url(rule=self.foreign_rule), {"version": 0, "note": "Attempt"}
            ).status_code,
            404,
        )
        wrong_stage = Requirement.objects.create(
            partner=self.partner,
            stage="post",
            kind="evidence",
            slot="",
            title="Later",
            config={},
            source="Fictional",
        )
        self.assertEqual(
            self.client.post(
                self.url(rule=wrong_stage), {"version": 0, "note": "Attempt"}
            ).status_code,
            404,
        )
        for name in ("evidence_submit", "evidence_history"):
            url = self.url(name, self.foreign_package, self.foreign_rule)
            self.assertEqual(
                (
                    self.client.get(url)
                    if name == "evidence_history"
                    else self.client.post(url, {"version": 0, "note": "Attempt"})
                ).status_code,
                404,
            )
        self.assertFalse(Evidence.objects.exists())

    def test_same_user_has_different_role_and_ownership_in_other_workspace(self):
        self.login(self.coord, self.unrelated)
        self.assertEqual(
            self.client.post(
                self.url(package=self.foreign_package, rule=self.foreign_rule),
                {"version": 0, "note": "Not my package"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                self.url("manual_review", self.foreign_package, self.foreign_rule), {}
            ).status_code,
            403,
        )
        self.assertNotContains(self.client.get(reverse("coverage")), self.package.title)

    def test_outsider_cannot_read_or_change_any_evidence(self):
        self.submit()
        self.login(self.other, self.unrelated)
        for name in ("package_detail", "api_report"):
            self.assertEqual(
                self.client.get(reverse(name, args=[self.package.pk])).status_code, 404
            )
        self.assertEqual(self.client.get(self.url("evidence_history")).status_code, 404)
        self.assertEqual(self.submit().status_code, 404)
        self.assertEqual(
            self.client.get(reverse("coverage") + f"?partner={self.partner.pk}").status_code, 404
        )
        self.assertEqual(Evidence.objects.count(), 1)

    def test_evidence_post_requires_csrf_and_rejects_get(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        session = strict.session
        session["workspace_id"] = self.team.pk
        session.save()
        self.assertEqual(
            strict.post(self.url(), {"version": 0, "note": "Attempt"}).status_code, 403
        )
        self.assertEqual(self.client.get(self.url()).status_code, 405)
        self.assertFalse(Evidence.objects.exists())

    def test_history_retains_previous_submissions_with_pagination(self):
        self.submit(note="First observation")
        first = Evidence.objects.get()
        self.submit(version=first.pk, note="Second observation")
        response = self.client.get(self.url("evidence_history"))
        self.assertContains(response, "First observation")
        self.assertContains(response, "Second observation")
        self.assertContains(response, "Current submission")
        first.note = "Overwrite attempt"
        with self.assertRaises(ValidationError):
            first.save()

    @override_settings(MAX_EVIDENCE_REVISIONS=1)
    def test_revision_quota_retains_previous_evidence(self):
        self.submit()
        self.assertEqual(self.submit(version=Evidence.objects.get().pk).status_code, 429)
        self.assertEqual(Evidence.objects.count(), 1)

    def test_report_failure_rolls_back_evidence_and_audit(self):
        with patch("checker.services.ensure_report", side_effect=StorageUnavailable()):
            self.assertEqual(self.submit().status_code, 503)
        self.assertFalse(Evidence.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action="evidence.submitted").exists())

    def test_across_stage_requirement_applies_to_pre_event_and_post_packages(self):
        self.rule.stage = "all"
        self.rule.save()
        for stage in ("pre", "event", "post"):
            package = Package.objects.create(
                partner=self.partner, stage=stage, title=stage, owner=self.owner
            )
            self.assertEqual(ensure_report(package).findings[0]["requirement_id"], self.rule.pk)

    def test_across_stage_coverage_does_not_treat_one_stage_as_the_whole_obligation(self):
        self.rule.stage = "all"
        self.rule.save()
        self.submit()
        self.review()
        response = self.client.get(reverse("coverage"))
        self.assertEqual(response.context["resolved"], 0)
        self.assertContains(response, "No event-day package")
        self.assertContains(response, "No post-event package")

    def test_evidence_cannot_be_reclassified_as_a_file_rule_to_skip_validation(self):
        self.login(self.coord)
        data = {
            "partner": self.partner.pk,
            "stage": "pre",
            "title": "Invalid file rule",
            "kind": "required_file",
            "slot": "",
            "source": "Fictional",
            "approved": "on",
            "reason": "Reviewed",
        }
        form = RequirementForm(data, workspace=self.team)
        self.assertFalse(form.is_valid())

    def test_coverage_keeps_missing_and_unapproved_obligations_visible(self):
        ensure_report(self.package)
        response = self.client.get(reverse("coverage"))
        self.assertContains(response, "Only entered requirements are counted")
        self.assertContains(response, "Missing")
        self.assertEqual(response.context["unresolved"], 1)
        self.assertNotContains(response, self.foreign_rule.title)
        Requirement.objects.create(
            partner=self.partner,
            stage="post",
            title="Unrecorded package stage",
            kind="evidence",
            source="Fictional",
            slot="",
            approved=False,
        )
        response = self.client.get(reverse("coverage"))
        self.assertEqual(response.context["unresolved"], 2)
        self.assertContains(response, "No applicable")
        self.assertEqual(self.client.get(reverse("coverage") + "?partner=broken").status_code, 404)

    def test_coverage_uses_snapshots_without_checking_files(self):
        ensure_report(self.package)
        with patch(
            "checker.services.file_exists",
            side_effect=AssertionError("Coverage must not contact originals"),
        ):
            self.assertEqual(self.client.get(reverse("coverage")).status_code, 200)
        self.submit()
        self.review()
        response = self.client.get(reverse("coverage"))
        self.assertEqual(response.context["resolved"], 1)
        self.rule.title = "Instruction changed"
        self.rule.save()
        self.assertContains(self.client.get(reverse("coverage")), "Report needed")

    def test_legacy_fingerprint_and_boolean_review_remain_valid(self):
        self.rule.delete()
        rule = Requirement.objects.create(
            partner=self.partner,
            stage="pre",
            kind="manual",
            slot="article",
            title="Legacy check",
            source="Fictional",
            approved=True,
        )
        store_asset(
            self.package,
            self.owner,
            "article",
            SimpleUploadedFile("original.txt", b"Original text"),
        )
        reqs, assets, signature = current_inputs(self.package)
        self.assertNotIn("responsibility", requirement_snapshot(rule))
        self.assertEqual(signature, fingerprint(reqs, assets))
        ManualReview.objects.create(
            package=self.package,
            requirement=rule,
            actor=self.coord,
            fingerprint=signature,
            passed=True,
            note="Legacy decision",
        )
        self.assertEqual(ensure_report(self.package, force=True).findings[0]["status"], "passed")

    def test_conditional_instructions_need_conditions_and_blank_slot(self):
        data = {
            "partner": self.partner.pk,
            "stage": "event",
            "title": "Optional live work",
            "kind": "evidence",
            "instructions": "Inspect the event record",
            "source": "Fictional section 8",
            "approved": "on",
            "reason": "Reviewed",
            "applicability": "conditional",
            "responsibility": "partner",
        }
        form = RequirementForm(data, workspace=self.team)
        self.assertFalse(form.is_valid())
        form = RequirementForm(
            {**data, "conditions": "Only if an on-site activation is requested."},
            workspace=self.team,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.login(self.coord)
        response = self.client.post(
            reverse("requirement_new"), {**data, "conditions": "Only if requested."}
        )
        self.assertEqual(response.status_code, 302)
        rule = Requirement.objects.get(title=data["title"])
        self.assertEqual(rule.history.get().snapshot["responsibility"], "partner")

    def test_unconfirmed_draft_can_be_assigned_a_stage_before_approval(self):
        rule = Requirement.objects.create(
            partner=self.partner,
            stage="unset",
            title="Draft obligation",
            kind="evidence",
            slot="",
            config={"instructions": "Inspect evidence"},
            source="Fictional section 9",
        )
        self.login(self.coord)
        data = {
            "partner": self.partner.pk,
            "stage": "unset",
            "title": rule.title,
            "kind": "evidence",
            "instructions": "Inspect evidence",
            "source": rule.source,
            "approved": "on",
            "version": 1,
            "reason": "Reviewed source.",
        }
        response = self.client.post(reverse("requirement_edit", args=[rule.pk]), data)
        self.assertContains(response, "Confirm the applicable stage before approving")
        rule.refresh_from_db()
        self.assertFalse(rule.approved)
        response = self.client.post(
            reverse("requirement_edit", args=[rule.pk]), {**data, "stage": "event"}
        )
        self.assertEqual(response.status_code, 302)
        rule.refresh_from_db()
        self.assertTrue(rule.approved)
        self.assertEqual(rule.stage, "event")

    def test_optional_file_rule_requires_explicit_evidence_modeling(self):
        data = {
            "partner": self.partner.pk,
            "stage": "pre",
            "title": "Optional collateral",
            "kind": "required_file",
            "slot": "image",
            "source": "Fictional",
            "applicability": "optional",
            "reason": "Reviewed source.",
        }
        form = RequirementForm(data, workspace=self.team)
        self.assertFalse(form.is_valid())
        self.assertIn("applicability", form.errors)

    def test_unconfirmed_applicability_cannot_be_approved(self):
        data = {
            "partner": self.partner.pk,
            "stage": "pre",
            "title": "Unconfirmed scope",
            "kind": "evidence",
            "slot": "",
            "instructions": "Inspect evidence",
            "source": "Fictional",
            "applicability": "unspecified",
            "approved": "on",
            "reason": "Reviewed source.",
        }
        form = RequirementForm(data, workspace=self.team)
        self.assertFalse(form.is_valid())
        self.assertIn("applicability", form.errors)
