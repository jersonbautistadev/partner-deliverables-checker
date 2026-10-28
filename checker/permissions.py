from django.core.exceptions import PermissionDenied


def is_coordinator(user):
    return user.is_authenticated and user.is_active and (
        user.is_superuser or user.groups.filter(name="Coordinator").exists()
    )


def require_member(user):
    if not (is_coordinator(user) or (
        user.is_authenticated and user.is_active and
        user.groups.filter(name="Contributor").exists()
    )):
        raise PermissionDenied("An event-team role is required.")


def require_coordinator(user):
    if not is_coordinator(user):
        raise PermissionDenied("Only coordinators can change requirements or record reviews.")


def visible_packages(user):
    from checker.models import Package

    require_member(user)
    qs = Package.objects.select_related("partner", "owner")
    return qs if is_coordinator(user) else qs.filter(owner=user)
