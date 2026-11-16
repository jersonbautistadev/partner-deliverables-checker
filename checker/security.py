import math
import time
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.crypto import salted_hmac

from checker.models import Asset, RateBucket, Workspace
from checker.permissions import require_member


class LimitExceeded(ValidationError):
    pass


def consume_limit_wait(identity, limit, seconds, *, consume=True):
    """Return zero or seconds until reset; optionally inspect without consuming an attempt."""
    key = salted_hmac("rate-bucket", identity, algorithm="sha256").hexdigest()
    now = time.time()
    window = int(now) // seconds
    wait = max(1, math.ceil((window + 1) * seconds - now))
    if not consume:
        return wait if RateBucket.objects.filter(key=key, window=window, count__gte=limit).exists() else 0
    with transaction.atomic():
        bucket, _ = RateBucket.objects.get_or_create(
            key=key,
            window=window,
            defaults={"expires_at": timezone.now() + timedelta(seconds=seconds * 2)},
        )
        bucket = RateBucket.objects.select_for_update().get(pk=bucket.pk)
        if bucket.count >= limit:
            return wait
        bucket.count += 1
        bucket.save(update_fields=["count"])
    return 0


def consume_limit(identity, limit, seconds):
    return consume_limit_wait(identity, limit, seconds) == 0


def workspace_write(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != "POST":
            return view(request, *args, **kwargs)
        require_member(request.user, request.workspace)
        try:
            with transaction.atomic():
                Workspace.objects.select_for_update().get(pk=request.workspace.pk)
                require_member(request.user, request.workspace)
                return view(request, *args, **kwargs)
        except LimitExceeded as exc:
            from django.shortcuts import render

            return render(
                request,
                "checker/error.html",
                {"title": "Workspace limit reached", "detail": " ".join(exc.messages)},
                status=429,
            )

    return wrapped


def count_limit(queryset, setting_name):
    if queryset.count() >= getattr(settings, setting_name):
        raise LimitExceeded(
            "This workspace has reached its configured usage limit. Contact the operator."
        )


def storage_used(workspace):
    return (
        Asset.objects.filter(package__partner__workspace=workspace).aggregate(total=Sum("size"))[
            "total"
        ]
        or 0
    )
