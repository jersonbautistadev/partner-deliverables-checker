from django.core.exceptions import PermissionDenied

from checker.models import Account, Membership


def is_verified(user):
    return (
        user.is_authenticated
        and user.is_active
        and Account.objects.filter(
            user=user, user__is_active=True, verified_at__isnull=False
        ).exists()
    )


def is_coordinator(user, workspace=None):
    return bool(
        workspace
        and is_verified(user)
        and Membership.objects.filter(user=user, workspace=workspace, role="coordinator").exists()
    )


def require_member(user, workspace):
    if not (
        is_verified(user)
        and workspace
        and Membership.objects.filter(user=user, workspace=workspace).exists()
    ):
        raise PermissionDenied("An active, verified workspace membership is required.")


def require_coordinator(user, workspace):
    require_member(user, workspace)
    if not is_coordinator(user, workspace):
        raise PermissionDenied("Only workspace coordinators can perform this action.")


def visible_packages(user, workspace):
    from checker.models import Package

    require_member(user, workspace)
    qs = Package.objects.filter(partner__workspace=workspace).select_related("partner", "owner")
    return qs if is_coordinator(user, workspace) else qs.filter(owner=user)
