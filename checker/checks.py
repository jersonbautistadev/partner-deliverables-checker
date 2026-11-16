import os
from email.utils import parseaddr
from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def mail_configured():
    sender = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
    try:
        validate_email(sender)
    except ValidationError:
        return False
    return bool(
        settings.EMAIL_HOST
        and "localhost" not in sender.casefold()
        and settings.DELIVERY_EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        and settings.EMAIL_USE_TLS != settings.EMAIL_USE_SSL
    )


@register(deploy=True)
def release_checks(app_configs, **kwargs):
    issues = []
    if settings.DEBUG:
        return issues

    def need(condition, message, number):
        if not condition:
            issues.append(Error(message, id=f"checker.E{number:03}"))

    need(
        settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql",
        "Production requires PostgreSQL.",
        1,
    )
    base = urlsplit(settings.PUBLIC_BASE_URL)
    need(
        base.scheme == "https" and base.hostname in settings.ALLOWED_HOSTS,
        "PUBLIC_BASE_URL must be an allowed HTTPS hostname.",
        2,
    )
    need(
        mail_configured(),
        "Configure production SMTP and an authenticated sender.",
        3,
    )
    need(
        settings.DELIVERY_EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend",
        "Production mail must use the configured SMTP transport.",
        4,
    )
    need(settings.EMAIL_USE_TLS != settings.EMAIL_USE_SSL, "Enable exactly one SMTP TLS mode.", 8)
    need(len(settings.OPS_SECRET) >= 32, "Set an OPS_SECRET of at least 32 random characters.", 5)
    if os.environ.get("VERCEL"):
        need(
            settings.DATABASES["default"].get("OPTIONS", {}).get("sslmode")
            in {"require", "verify-ca", "verify-full"},
            "Remote Vercel PostgreSQL connections require TLS.",
            9,
        )
        need(
            settings.STORAGES["default"]["BACKEND"] == "storages.backends.s3.S3Storage",
            "Vercel requires a private, durable S3-compatible object store.",
            6,
        )
    need(
        not settings.SECRET_KEY.startswith("replace-"), "Replace placeholder production secrets.", 7
    )
    return issues
