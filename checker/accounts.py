import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from checker.account_forms import (
    ConfirmPasswordForm,
    EmailForm,
    InviteForm,
    MembershipForm,
    SignupForm,
    WorkspaceForm,
    WorkspaceSelectionForm,
)
from checker.models import Account, ActionToken, Membership, Workspace
from checker.permissions import is_verified, require_coordinator
from checker.security import LimitExceeded, count_limit, storage_used
from checker.services import audit


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def action_token(purpose, email, user=None, workspace=None, role="contributor"):
    raw = secrets.token_urlsafe(32)
    ActionToken.objects.filter(
        purpose=purpose, email=email, user=user, workspace=workspace, consumed_at__isnull=True
    ).update(consumed_at=timezone.now())
    ActionToken.objects.create(
        digest=digest(raw),
        purpose=purpose,
        email=email,
        user=user,
        workspace=workspace,
        role=role,
        expires_at=timezone.now()
        + timedelta(
            hours=settings.VERIFICATION_HOURS if purpose == "verify" else settings.INVITATION_HOURS
        ),
    )
    return raw


def queue_verification(account):
    raw = action_token("verify", account.email, user=account.user)
    link = settings.PUBLIC_BASE_URL.rstrip("/") + reverse("verify_email", args=[raw])
    send_mail(
        "Verify your Partner Deliverables account",
        f"Confirm this email address to activate workspace access. Open the link and confirm:\n{link}\n"
        f"This link expires in {settings.VERIFICATION_HOURS} hours. Ignore this email if you did not request it.",
        settings.DEFAULT_FROM_EMAIL,
        [account.email],
    )


def page(request, title, form=None, **context):
    return render(request, "accounts/page.html", {"title": title, "form": form, **context})


def require_verified(request):
    if not is_verified(request.user):
        raise PermissionDenied("Verify your email before managing workspaces.")


@sensitive_post_parameters("password1", "password2")
@require_http_methods(["GET", "POST"])
def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if not Account.objects.filter(email=form.cleaned_data["email"]).exists():
                    user = form.save()
                    account = Account.objects.create(user=user, email=form.cleaned_data["email"])
                    queue_verification(account)
                    audit(user, "account.registered", f"user:{user.pk}")
                else:
                    make_password(form.cleaned_data["password1"])
        except IntegrityError:
            pass  # A concurrent signup must not reveal an email address already in use.
        return page(
            request,
            "Check your email",
            detail="If these details can be registered, a verification email will arrive shortly. You can also request a new verification link or reset your password.",
        )
    return page(request, "Create an account", form, button="Create account")


@require_http_methods(["GET", "POST"])
def verification_required(request):
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            account = (
                Account.objects.select_for_update()
                .filter(
                    email=form.cleaned_data["email"].strip().casefold(),
                    verified_at__isnull=True,
                    user__is_active=True,
                )
                .select_related("user")
                .first()
            )
            if account:
                queue_verification(account)
        return page(
            request,
            "Check your email",
            detail="If an eligible account exists, a new verification link will arrive shortly.",
        )
    return page(
        request,
        "Verify your email",
        form,
        button="Send verification link",
        detail="Email verification is required before opening a workspace.",
    )


@require_http_methods(["GET", "POST"])
def verify_email(request, token):
    # Email scanners can open GET links without consuming the token.
    if request.method == "POST":
        with transaction.atomic():
            item = ActionToken.objects.filter(
                digest=digest(token),
                purpose="verify",
                consumed_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).first()
            if item:
                account = (
                    Account.objects.select_for_update()
                    .filter(user_id=item.user_id, email=item.email, user__is_active=True)
                    .first()
                )
                item = ActionToken.objects.select_for_update().get(pk=item.pk)
                if account and not item.consumed_at and item.expires_at > timezone.now():
                    account.verified_at = timezone.now()
                    account.save(update_fields=["verified_at"])
                    item.consumed_at = timezone.now()
                    item.save(update_fields=["consumed_at"])
                    messages.success(request, "Email verified. You can now sign in.")
                    return redirect("login")
        return page(
            request,
            "Link unavailable",
            detail="The verification link is invalid, expired, or already used. Request a new link.",
        )
    return page(
        request,
        "Confirm your email",
        confirm=True,
        button="Verify email",
        detail="Confirm that you requested this account verification.",
    )


@login_required
@require_http_methods(["GET", "POST"])
def workspaces(request):
    require_verified(request)
    if request.method == "POST":
        selection = WorkspaceSelectionForm(request.POST)
        selected_id = selection.cleaned_data["workspace"] if selection.is_valid() else 0
        membership = get_object_or_404(Membership, user=request.user, workspace_id=selected_id)
        request.session["workspace_id"] = membership.workspace_id
        return redirect("dashboard")
    return render(
        request,
        "accounts/workspaces.html",
        {"memberships": Membership.objects.filter(user=request.user).select_related("workspace")},
    )


@login_required
@require_http_methods(["GET", "POST"])
def workspace_create(request):
    require_verified(request)
    form = WorkspaceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            Account.objects.select_for_update().get(user=request.user)
            require_verified(request)
            try:
                count_limit(
                    Workspace.objects.filter(created_by=request.user), "MAX_CREATED_WORKSPACES"
                )
                count_limit(Membership.objects.filter(user=request.user), "MAX_USER_MEMBERSHIPS")
            except LimitExceeded as exc:
                form.add_error(None, exc)
            else:
                workspace = Workspace.objects.create(
                    name=form.cleaned_data["name"],
                    created_by=request.user,
                    storage_limit=settings.WORKSPACE_STORAGE_BYTES,
                )
                Membership.objects.create(
                    workspace=workspace, user=request.user, role="coordinator"
                )
                audit(
                    request.user,
                    "workspace.created",
                    f"workspace:{workspace.pk}",
                    workspace=workspace,
                )
                request.session["workspace_id"] = workspace.pk
                return redirect("dashboard")
    return page(request, "Create workspace", form, button="Create workspace")


@login_required
@require_http_methods(["GET"])
def workspace_settings(request):
    require_verified(request)
    if not request.workspace:
        return redirect("workspaces")
    return render(
        request,
        "accounts/workspace.html",
        {
            "members": Membership.objects.filter(workspace=request.workspace).select_related(
                "user"
            ),
            "invite_form": InviteForm(),
            "used_bytes": storage_used(request.workspace),
            "pending": ActionToken.objects.filter(
                workspace=request.workspace,
                purpose="invite",
                consumed_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            if request.membership.role == "coordinator"
            else [],
        },
    )


@login_required
@require_POST
def workspace_invite(request):
    require_coordinator(request.user, request.workspace)
    form = InviteForm(request.POST)
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=request.workspace.pk)
        require_coordinator(request.user, request.workspace)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().casefold()
            try:
                count_limit(
                    ActionToken.objects.filter(
                        workspace=request.workspace,
                        purpose="invite",
                        consumed_at__isnull=True,
                        expires_at__gt=timezone.now(),
                    ),
                    "MAX_PENDING_INVITATIONS",
                )
            except LimitExceeded as exc:
                messages.error(request, " ".join(exc.messages))
            else:
                raw = action_token(
                    "invite", email, workspace=request.workspace, role=form.cleaned_data["role"]
                )
                link = settings.PUBLIC_BASE_URL.rstrip("/") + reverse(
                    "invitation_accept", args=[raw]
                )
                send_mail(
                    "Workspace invitation",
                    f"You have been invited to a private Partner Deliverables workspace. Sign in with this email, then open:\n{link}\n"
                    f"This invitation expires in {settings.INVITATION_HOURS} hours. Accept only if you recognize the invitation.",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                )
                audit(
                    request.user,
                    "membership.invited",
                    f"workspace:{request.workspace.pk}",
                    workspace=request.workspace,
                )
                messages.success(request, "Invitation queued for delivery.")
        else:
            messages.error(request, "Enter a valid email and role.")
    return redirect("workspace_settings")


@login_required
@require_http_methods(["GET", "POST"])
def invitation_accept(request, token):
    require_verified(request)
    if request.method == "POST":
        try:
            with transaction.atomic():
                account = Account.objects.select_for_update().get(user=request.user)
                require_verified(request)
                item = ActionToken.objects.filter(
                    digest=digest(token),
                    purpose="invite",
                    email=account.email,
                    consumed_at__isnull=True,
                    expires_at__gt=timezone.now(),
                ).first()
                if not item:
                    raise ValidationError(
                        "The invitation is expired, used, or belongs to a different email address."
                    )
                workspace = Workspace.objects.select_for_update().get(pk=item.workspace_id)
                item = ActionToken.objects.select_for_update().get(pk=item.pk)
                if item.consumed_at or item.expires_at <= timezone.now():
                    raise ValidationError("This invitation is no longer available.")
                if not Membership.objects.filter(workspace=workspace, user=request.user).exists():
                    count_limit(
                        Membership.objects.filter(workspace=workspace), "MAX_WORKSPACE_MEMBERS"
                    )
                    count_limit(
                        Membership.objects.filter(user=request.user), "MAX_USER_MEMBERSHIPS"
                    )
                    Membership.objects.create(
                        workspace=workspace, user=request.user, role=item.role
                    )
                item.consumed_at = timezone.now()
                item.save(update_fields=["consumed_at"])
                request.session["workspace_id"] = workspace.pk
                audit(
                    request.user,
                    "membership.accepted",
                    f"workspace:{workspace.pk}",
                    workspace=workspace,
                )
                return redirect("dashboard")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    return page(
        request,
        "Accept invitation",
        confirm=True,
        button="Join workspace",
        detail="You must be signed in with the verified email address that received this invitation. Workspace details become available after acceptance.",
    )


@login_required
@require_POST
def invitation_revoke(request, pk):
    require_coordinator(request.user, request.workspace)
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=request.workspace.pk)
        require_coordinator(request.user, request.workspace)
        get_object_or_404(ActionToken, pk=pk, workspace=request.workspace, purpose="invite")
        ActionToken.objects.filter(pk=pk, workspace=request.workspace).update(
            consumed_at=timezone.now()
        )
        audit(
            request.user,
            "membership.invitation_revoked",
            f"invitation:{pk}",
            workspace=request.workspace,
        )
    messages.success(request, "Invitation revoked.")
    return redirect("workspace_settings")


@login_required
@require_POST
def membership_change(request, pk):
    require_coordinator(request.user, request.workspace)
    target = get_object_or_404(Membership, pk=pk, workspace=request.workspace)
    form = MembershipForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a valid membership action.")
        return redirect("workspace_settings")
    with transaction.atomic():
        Account.objects.select_for_update().get(user_id=target.user_id)
        Workspace.objects.select_for_update().get(pk=request.workspace.pk)
        require_coordinator(request.user, request.workspace)
        target = get_object_or_404(Membership, pk=pk, workspace=request.workspace)
        active_coordinators = Membership.objects.filter(
            workspace=request.workspace,
            role="coordinator",
            user__is_active=True,
            user__account__verified_at__isnull=False,
        )
        if (
            target.role == "coordinator"
            and form.cleaned_data["role"] != "coordinator"
            and active_coordinators.count() <= 1
        ):
            messages.error(
                request,
                "Promote another active, verified coordinator before removing or demoting the last coordinator.",
            )
        else:
            role = form.cleaned_data["role"]
            if role == "remove":
                ActionToken.objects.filter(
                    workspace=request.workspace,
                    email=target.user.account.email,
                    purpose="invite",
                    consumed_at__isnull=True,
                ).update(consumed_at=timezone.now())
                target.delete()
            else:
                target.role = role
                target.save(update_fields=["role"])
            audit(
                request.user,
                "membership.changed",
                f"user:{target.user_id}",
                workspace=request.workspace,
                role=role,
            )
            messages.success(
                request, "Membership updated. Existing package ownership and history are retained."
            )
    return redirect("workspace_settings")


@login_required
@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def deactivate_account(request):
    form = ConfirmPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not request.user.check_password(form.cleaned_data["password"]):
            form.add_error("password", "Check your password.")
        else:
            with transaction.atomic():
                Account.objects.select_for_update().get(user=request.user)
                ids = list(
                    Membership.objects.filter(user=request.user).values_list(
                        "workspace_id", flat=True
                    )
                )
                list(Workspace.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
                blocked = any(
                    not Membership.objects.filter(
                        workspace_id=m.workspace_id,
                        role="coordinator",
                        user__is_active=True,
                        user__account__verified_at__isnull=False,
                    )
                    .exclude(user=request.user)
                    .exists()
                    for m in Membership.objects.filter(user=request.user, role="coordinator")
                )
                if blocked:
                    form.add_error(
                        None,
                        "Transfer coordination of every workspace to another verified member before deactivating your account.",
                    )
                else:
                    get_user_model().objects.filter(pk=request.user.pk).update(is_active=False)
                    Membership.objects.filter(user=request.user).delete()
                    ActionToken.objects.filter(
                        email=request.user.account.email, consumed_at__isnull=True
                    ).update(consumed_at=timezone.now())
                    audit(request.user, "account.deactivated", f"user:{request.user.pk}")
                    logout(request)
                    return redirect("login")
    return page(
        request,
        "Deactivate account",
        form,
        button="Deactivate account",
        detail="This disables access and removes your memberships. Files and review history are retained under each workspace retention policy. Transfer coordination first.",
    )


def csrf_failure(request, reason=""):
    return render(
        request,
        "checker/error.html",
        {
            "title": "Form could not be submitted",
            "detail": "Reload the page and try again. If the problem persists, check that cookies are enabled and use the official site address.",
        },
        status=403,
    )
