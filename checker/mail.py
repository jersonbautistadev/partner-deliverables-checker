import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.mail.backends.base import BaseEmailBackend
from django.db import connection, transaction
from django.utils import timezone

from checker.models import MailJob, ServiceHeartbeat

logger = logging.getLogger(__name__)


class QueueBackend(BaseEmailBackend):
    def send_messages(self, messages):
        count = 0
        for message in messages:
            for recipient in message.to:
                MailJob.objects.create(
                    recipient=recipient,
                    subject=message.subject,
                    body=message.body,
                    available_at=timezone.now(),
                )
                count += 1
        return count


def deliver_batch(limit=10):
    sent = 0
    for _ in range(limit):
        with transaction.atomic():
            qs = MailJob.objects.filter(
                sent_at__isnull=True,
                available_at__lte=timezone.now(),
                attempts__lt=settings.MAIL_MAX_ATTEMPTS,
            ).order_by("pk")
            qs = (
                qs.select_for_update(skip_locked=True)
                if connection.features.has_select_for_update_skip_locked
                else qs.select_for_update()
            )
            job = qs.first()
            if not job:
                break
            job.attempts += 1
            try:
                backend = get_connection(settings.DELIVERY_EMAIL_BACKEND, fail_silently=False)
                if (
                    send_mail(
                        job.subject,
                        job.body,
                        settings.DEFAULT_FROM_EMAIL,
                        [job.recipient],
                        connection=backend,
                    )
                    != 1
                ):
                    raise RuntimeError("Email delivery was not acknowledged.")
            except Exception:
                # Do not log recipient, body, token, or provider exception text.
                logger.error("mail_delivery_failed job_id=%s attempt=%s", job.pk, job.attempts)
                job.available_at = timezone.now() + timedelta(
                    seconds=min(3600, 30 * 2**job.attempts)
                )
            else:
                job.sent_at = timezone.now()
                job.body = ""
                job.recipient = ""
                sent += 1
            job.save()
    # Even an idle dispatcher must demonstrate that its scheduler is still running.
    # This records activity; queue age/exhausted jobs separately signal delivery failures.
    ServiceHeartbeat.objects.update_or_create(name="mail", defaults={"last_seen": timezone.now()})
    return sent
