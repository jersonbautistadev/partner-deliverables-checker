from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from checker.models import ActionToken, AuditEvent, MailJob, RateBucket


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
        days = options["audit_retention_days"]
        if days >= 30:
            AuditEvent.objects.filter(created_at__lt=now - timedelta(days=days)).delete()
        self.stdout.write(
            "Expired security records pruned. Original files and requirement snapshots retained."
        )
