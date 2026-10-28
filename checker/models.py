import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

STAGES = [("pre", "Pre-event"), ("post", "Post-event")]
SLOTS = [("article", "Article"), ("caption", "Caption"), ("image", "Promotional image"), ("logo", "Logo")]
KINDS = [
    ("required_file", "Required file"),
    ("word_count", "Word count"),
    ("dimensions", "Image dimensions"),
    ("required_phrase", "Required phrase"),
    ("manual", "Manual review"),
]


class Partner(models.Model):
    name = models.CharField(max_length=120, unique=True)
    notes = models.TextField(blank=True, max_length=3000)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Requirement(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="requirements")
    stage = models.CharField(max_length=8, choices=STAGES)
    title = models.CharField(max_length=160)
    kind = models.CharField(max_length=24, choices=KINDS)
    slot = models.CharField(max_length=12, choices=SLOTS)
    config = models.JSONField(default=dict)
    source = models.CharField(max_length=500, help_text="Document/message title, section, date or URL.")
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
        constraints = [models.UniqueConstraint(fields=["requirement", "number"], name="unique_revision")]

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
        constraints = [models.UniqueConstraint(fields=["package", "slot"], name="one_asset_per_slot")]


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
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=120)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
