import logging

import os

from django.conf import settings
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import redirect

from checker.models import Membership
from checker.permissions import is_verified
from checker.security import consume_limit

logger = logging.getLogger(__name__)


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace = None
        request.membership = None
        if is_verified(request.user):
            memberships = Membership.objects.filter(user=request.user).select_related("workspace")
            selected = request.session.get("workspace_id")
            if selected:
                request.membership = memberships.filter(workspace_id=selected).first()
            elif memberships.count() == 1:
                request.membership = memberships.first()
            if request.membership:
                request.workspace = request.membership.workspace
        return self.get_response(request)

    def process_view(self, request, view, args, kwargs):
        if view.__module__ != "checker.views" or view.__name__ in {"health", "readiness"}:
            return None
        if not request.user.is_authenticated:
            return None  # Preserve Django's login redirect.
        if not is_verified(request.user):
            if request.path.startswith("/api/"):
                return JsonResponse({"error": "Email verification required."}, status=403)
            return redirect("verification_required")
        if not request.workspace:
            if request.path.startswith("/api/"):
                return JsonResponse({"error": "Select an active workspace."}, status=403)
            return redirect("workspaces")


class ThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view, args, kwargs):
        name = getattr(request.resolver_match, "url_name", "")
        guarded = {
            "login",
            "signup",
            "password_reset",
            "verification_required",
            "verify_email",
            "invitation_accept",
            "workspace_invite",
            "workspace_create",
            "password_change",
            "password_reset_confirm",
            "deactivate_account",
        }
        expensive = {
            "dashboard",
            "package_detail",
            "api_report",
            "asset_upload",
            "requirement_edit",
            "requirement_new",
            "manual_review",
            "asset_remove",
            "package_new",
            "partner_new",
            "membership_change",
            "invitation_revoke",
        }
        if not ((request.method == "POST" and name in guarded | expensive) or name in expensive):
            return None
        ip = request.META.get("REMOTE_ADDR", "")
        if os.environ.get("VERCEL"):
            ip = request.META.get("HTTP_X_VERCEL_FORWARDED_FOR", ip).split(",")[0].strip()
        elif settings.TRUST_PROXY_HEADERS:
            ip = request.META.get("HTTP_X_CLIENT_IP", ip)
        try:
            allowed = consume_limit(
                f"ip:{ip}:{'account' if name in guarded else 'work'}",
                settings.AUTH_RATE_LIMIT if name in guarded else settings.WORK_RATE_LIMIT,
                60,
            )
            if allowed and name in guarded and request.method == "POST":
                identities = {
                    request.POST.get(field, "").strip().casefold()
                    for field in ("username", "email")
                }
                for identity in identities - {""}:
                    if not consume_limit(f"account:{identity}", 5, 900):
                        allowed = False
            if allowed and request.user.is_authenticated and name in expensive:
                allowed = consume_limit(
                    f"user:{request.user.pk}:work", settings.WORK_RATE_LIMIT, 60
                )
            if not allowed:
                response = JsonResponse(
                    {"error": "Too many requests. Try again in one minute."}, status=429
                )
                response["Retry-After"] = "60"
                if not request.path.startswith("/api/"):
                    from django.shortcuts import render

                    response = render(
                        request,
                        "checker/error.html",
                        {
                            "title": "Please wait",
                            "detail": "Too many requests. Try again in one minute.",
                        },
                        status=429,
                    )
                    response["Retry-After"] = "60"
                return response
        except DatabaseError:
            return JsonResponse({"error": "Service temporarily unavailable."}, status=503)


class PrivateResponsesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Cache-Control"] = "private, no-store"
        if response.status_code >= 500:
            logger.error(
                "request_failed route=%s status=%s",
                getattr(request.resolver_match, "url_name", "unresolved"),
                response.status_code,
            )
        return response
