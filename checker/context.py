from django.conf import settings

from checker.permissions import is_coordinator


def team_context(request):
    workspace = getattr(request, 'workspace', None)
    return {'upload_limit': settings.UPLOAD_MAX_BYTES, 'workspace': workspace, 'coordinator': is_coordinator(request.user, workspace)}
