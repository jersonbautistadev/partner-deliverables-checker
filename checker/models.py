import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

STAGES = [("pre", "Pre-event"), ("post", "Post-event")]
SLOTS = [
    ("article", "Article"),
    ("caption", "Caption"),
    ("image", "Promotional image"),
    ("logo", "Logo"),
]
KINDS = [
    ("required_file", "Required file"),
    ("word_count", "Word count"),
    ("dimensions", "Image dimensions"),
    ("required_phrase", "Required phrase"),
    ("manual", "Manual review"),
]

ROLES = [("coordinator", "Coordinator"), ("contributor", "Contributor")]


class Account(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="account"
    )
    email = models.EmailField(unique=True, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)


class Workspace(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="created_workspaces",
    )
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    storage_limit = models.PositiveBigIntegerField(default=104857600)

    def __str__(self):
        return self.name


class Membership(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=ROLES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "user"], name="workspace_member_unique"),
            models.CheckConstraint(
                condition=models.Q(role__in=["coordinator", "contributor"]),
                name="valid_member_role",
            ),
        ]


class ActionToken(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    purpose = models.CharField(
        max_length=12, choices=[("verify", "Verify email"), ("invite", "Invitation")]
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.PROTECT, null=True, related_name="tokens"
    )
    email = models.EmailField()
    role = models.CharField(max_length=12, choices=ROLES, default="contributor")
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MailJob(models.Model):
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RateBucket(models.Model):
    key = models.CharField(max_length=64)
    window = models.BigIntegerField()
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["key", "window"], name="rate_window_unique")]


class Partner(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name="partners")
    name = models.CharField(max_length=120)
    notes = models.TextField(blank=True, max_length=3000)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "name"], name="partner_name_per_workspace")
        ]

    def __str__(self):
        return self.name


class Requirement(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="requirements")
    stage = models.CharField(max_length=8, choices=STAGES)
    title = models.CharField(max_length=160)
    kind = models.CharField(max_length=24, choices=KINDS)
    slot = models.CharField(max_length=12, choices=SLOTS)
    config = models.JSONField(default=dict)
    source = models.CharField(
        max_length=500, help_text="Document/message title, section, date or URL."
    )
    deadline = models.DateTimeField(null=True, blank=True)
    approved = models.BooleanField(default=False)
    ambiguous = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["partner__name", "stage", "id"]


class RequirementRevision(models.Model):
    requirement = models.ForeignKey(Requirement, on_delete=models.PROTECT, related_name="history")
    number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["requirement", "number"], name="unique_revision")
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Requirement revisions are append-only.")
        super().save(*args, **kwargs)


class Package(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="packages")
    stage = models.CharField(max_length=8, choices=STAGES)
    title = models.CharField(max_length=160)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


def private_path(instance, filename):
    return f"packages/{instance.package_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class Asset(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="assets")
    slot = models.CharField(max_length=12, choices=SLOTS)
    file = models.FileField(upload_to=private_path)
    original_name = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    metadata = models.JSONField(default=dict)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["package", "slot"], name="one_asset_per_slot")
        ]


class CheckRun(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="runs")
    fingerprint = models.CharField(max_length=64)
    engine_version = models.CharField(max_length=20)
    findings = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class ManualReview(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="reviews")
    requirement = models.ForeignKey(Requirement, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    passed = models.BooleanField()
    note = models.CharField(max_length=1000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class AuditEvent(models.Model):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.PROTECT, null=True, related_name="events"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=120)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
