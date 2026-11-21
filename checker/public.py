from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def pilot_information(request):
    return render(request, "checker/pilot_information.html", {
        "service_workspace_limit": settings.MAX_SERVICE_WORKSPACES,
        "workspace_storage_limit": settings.WORKSPACE_STORAGE_BYTES,
    })
