from django.conf import settings
from django.db import DatabaseError

from checker.mail import mail_capacity_wait
from checker.permissions import is_coordinator


def team_context(request):
    workspace = getattr(request, 'workspace', None)
    delayed = False
    if getattr(request.resolver_match, 'url_name', '') in {
        'signup', 'login', 'verification_required', 'password_reset',
        'password_reset_done', 'workspace_settings',
    }:
        try:
            delayed = bool(mail_capacity_wait())
        except DatabaseError:
            delayed = True
    return {
        'upload_limit': settings.UPLOAD_MAX_BYTES, 'workspace': workspace,
        'coordinator': is_coordinator(request.user, workspace),
        'public_support_email': settings.PUBLIC_SUPPORT_EMAIL,
        'mail_delayed': delayed,
    }
