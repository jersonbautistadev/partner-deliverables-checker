from checker.permissions import is_coordinator


def team_context(request):
    return {"coordinator": is_coordinator(request.user)}
