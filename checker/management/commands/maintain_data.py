from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from checker.models import ActionToken, AuditEvent, CheckRun, MailJob, RateBucket

# Reports are reproducible snapshots; reviews keep their own keys, so old runs can go.
KEEP_RUNS_PER_PACKAGE = 10
RUN_RETENTION_DAYS = 30


class Command(BaseCommand):
    help = "Prune expired security records. Audit retention is opt-in and must match the published policy."

    def add_arguments(self, parser):
        parser.add_argument("--audit-retention-days", type=int, default=0)

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff = now - timedelta(days=7)
        call_command("clearsessions", verbosity=0)
        RateBucket.objects.filter(expires_at__lt=now).delete()
        ActionToken.objects.filter(Q(expires_at__lt=cutoff) | Q(consumed_at__lt=cutoff)).delete()
        MailJob.objects.filter(Q(sent_at__lt=cutoff) | Q(created_at__lt=cutoff)).delete()
        run_cutoff = now - timedelta(days=RUN_RETENTION_DAYS)
        crowded = (
            CheckRun.objects.values("package_id")
            .annotate(total=Count("id"))
            .filter(total__gt=KEEP_RUNS_PER_PACKAGE)
            .values_list("package_id", flat=True)
        )
        for package_id in crowded:
            keep = list(
                CheckRun.objects.filter(package_id=package_id)
                .order_by("-id")
                .values_list("id", flat=True)[:KEEP_RUNS_PER_PACKAGE]
            )
            CheckRun.objects.filter(package_id=package_id, created_at__lt=run_cutoff).exclude(
                id__in=keep
            ).delete()
        days = options["audit_retention_days"]
        if days >= 30:
            AuditEvent.objects.filter(created_at__lt=now - timedelta(days=days)).delete()
        self.stdout.write(
            "Expired security records and superseded reports pruned. Original files, requirement snapshots and reviews retained."
        )
