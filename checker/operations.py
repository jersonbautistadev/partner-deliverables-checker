import secrets

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from checker.mail import deliver_batch
from checker.models import MailJob


@require_GET
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        default_storage.exists(".readiness-probe")
        stale = MailJob.objects.filter(
            sent_at__isnull=True, created_at__lt=timezone.now() - timezone.timedelta(minutes=15)
        ).exists()
        if stale:
            raise RuntimeError("mail worker unavailable")
    except Exception:
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
