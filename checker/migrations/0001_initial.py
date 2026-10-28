from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import checker.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Partner", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=120, unique=True)),
            ("notes", models.TextField(blank=True, max_length=3000)),
        ], options={"ordering": ["name"]}),
        migrations.CreateModel(name="Requirement", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("stage", models.CharField(choices=[("pre", "Pre-event"), ("post", "Post-event")], max_length=8)),
            ("title", models.CharField(max_length=160)),
            ("kind", models.CharField(choices=[("required_file", "Required file"), ("word_count", "Word count"), ("dimensions", "Image dimensions"), ("required_phrase", "Required phrase"), ("manual", "Manual review")], max_length=24)),
            ("slot", models.CharField(choices=[("article", "Article"), ("caption", "Caption"), ("image", "Promotional image"), ("logo", "Logo")], max_length=12)),
            ("config", models.JSONField(default=dict)),
            ("source", models.CharField(help_text="Document/message title, section, date or URL.", max_length=500)),
            ("deadline", models.DateTimeField(blank=True, null=True)),
            ("approved", models.BooleanField(default=False)),
            ("ambiguous", models.BooleanField(default=False)),
            ("revision", models.PositiveIntegerField(default=1)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("partner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="requirements", to="checker.partner")),
        ], options={"ordering": ["partner__name", "stage", "id"]}),
        migrations.CreateModel(name="Package", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("stage", models.CharField(choices=[("pre", "Pre-event"), ("post", "Post-event")], max_length=8)),
            ("title", models.CharField(max_length=160)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("partner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="packages", to="checker.partner")),
        ], options={"ordering": ["-updated_at"]}),
        migrations.CreateModel(name="RequirementRevision", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("number", models.PositiveIntegerField()),
            ("snapshot", models.JSONField()),
            ("reason", models.CharField(max_length=500)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="history", to="checker.requirement")),
        ], options={"ordering": ["-number"], "constraints": [models.UniqueConstraint(fields=("requirement", "number"), name="unique_revision")]}),
        migrations.CreateModel(name="Asset", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("slot", models.CharField(choices=[("article", "Article"), ("caption", "Caption"), ("image", "Promotional image"), ("logo", "Logo")], max_length=12)),
            ("file", models.FileField(upload_to=checker.models.private_path)),
            ("original_name", models.CharField(max_length=255)),
            ("sha256", models.CharField(max_length=64)),
            ("size", models.PositiveIntegerField()),
            ("metadata", models.JSONField(default=dict)),
            ("uploaded_at", models.DateTimeField(auto_now_add=True)),
            ("package", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assets", to="checker.package")),
            ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={"constraints": [models.UniqueConstraint(fields=("package", "slot"), name="one_asset_per_slot")]}),
        migrations.CreateModel(name="CheckRun", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("fingerprint", models.CharField(max_length=64)),
            ("engine_version", models.CharField(max_length=20)),
            ("findings", models.JSONField()),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("package", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="runs", to="checker.package")),
        ], options={"ordering": ["-id"]}),
        migrations.CreateModel(name="ManualReview", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("fingerprint", models.CharField(max_length=64)),
            ("passed", models.BooleanField()),
            ("note", models.CharField(max_length=1000)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("package", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="checker.package")),
            ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="checker.requirement")),
        ], options={"ordering": ["-id"]}),
        migrations.CreateModel(name="AuditEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("action", models.CharField(max_length=60)),
            ("target", models.CharField(max_length=120)),
            ("detail", models.JSONField(default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["-id"]}),
    ]
