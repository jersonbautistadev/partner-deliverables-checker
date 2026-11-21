import secrets
import logging

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from checker.mail import deliver_batch, mail_capacity_wait
from checker.models import MailJob, ServiceHeartbeat

logger = logging.getLogger(__name__)


@require_GET
def readiness(request):
    dependency = "database"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        dependency = "storage"
        default_storage.exists(".readiness-probe")
        now = timezone.now()
        if not settings.DEBUG:
            from checker.checks import mail_configured

            dependency = "mail_configuration"
            if not mail_configured():
                raise RuntimeError("mail unconfigured")
            dependency = "mail_dispatcher"
            if not ServiceHeartbeat.objects.filter(
                name="mail",
                last_seen__gte=now - timezone.timedelta(seconds=settings.MAIL_HEALTH_MAX_AGE_SECONDS),
            ).exists():
                raise RuntimeError("mail dispatcher unavailable")
        dependency = "mail_queue"
        if MailJob.objects.filter(sent_at__isnull=True).exists() and mail_capacity_wait():
            dependency = "mail_capacity"
            raise RuntimeError("mail capacity unavailable")
        stale = MailJob.objects.filter(
            sent_at__isnull=True, created_at__lt=now - timezone.timedelta(seconds=settings.MAIL_HEALTH_MAX_AGE_SECONDS)
        ).exists()
        exhausted = MailJob.objects.filter(
            sent_at__isnull=True, attempts__gte=settings.MAIL_MAX_ATTEMPTS
        ).exists()
        if stale or exhausted:
            raise RuntimeError("mail worker unavailable")
    except Exception:
        logger.warning("readiness_unavailable dependency=%s", dependency)
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})


@csrf_exempt
@require_POST
def dispatch_mail(request):
    expected = f"Bearer {settings.OPS_SECRET}"
    if len(settings.OPS_SECRET) < 32 or not secrets.compare_digest(
        request.headers.get("Authorization", "").encode(), expected.encode()
    ):
        return JsonResponse({"error": "Unauthorized."}, status=401)
    # Token-authenticated machine endpoint; it accepts no user input.
    sent = deliver_batch(limit=5)
    return JsonResponse({"delivered": sent})


@csrf_exempt
@require_POST
def maintenance(request):
    expected = f"Bearer {settings.OPS_SECRET}"
    if len(settings.OPS_SECRET) < 32 or not secrets.compare_digest(
        request.headers.get("Authorization", "").encode(), expected.encode()
    ):
        return JsonResponse({"error": "Unauthorized."}, status=401)
    from django.core.management import call_command
    from io import StringIO

    call_command("maintain_data", stdout=StringIO())
    return JsonResponse({"status": "completed"})
