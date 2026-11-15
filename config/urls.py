from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import include, path

from checker import accounts
from checker.account_forms import VerifiedLoginForm, VerifiedPasswordResetForm

base = urlsplit(settings.PUBLIC_BASE_URL)
urlpatterns = [
    path("accounts/signup/", accounts.signup, name="signup"),
    path("accounts/verify/", accounts.verification_required, name="verification_required"),
    path("accounts/verify/<str:token>/", accounts.verify_email, name="verify_email"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(authentication_form=VerifiedLoginForm),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "accounts/password/change/", auth_views.PasswordChangeView.as_view(), name="password_change"
    ),
    path(
        "accounts/password/changed/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path(
        "accounts/password/reset/",
        auth_views.PasswordResetView.as_view(
            form_class=VerifiedPasswordResetForm,
            extra_email_context={"domain": base.netloc, "protocol": base.scheme},
        ),
        name="password_reset",
    ),
    path(
        "accounts/password/sent/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "accounts/password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "accounts/password/complete/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("accounts/deactivate/", accounts.deactivate_account, name="deactivate_account"),
    path("workspaces/", accounts.workspaces, name="workspaces"),
    path("workspaces/new/", accounts.workspace_create, name="workspace_create"),
    path("workspaces/settings/", accounts.workspace_settings, name="workspace_settings"),
    path("workspaces/invite/", accounts.workspace_invite, name="workspace_invite"),
    path(
        "workspaces/invitations/<str:token>/", accounts.invitation_accept, name="invitation_accept"
    ),
    path(
        "workspaces/invitations/<int:pk>/revoke/",
        accounts.invitation_revoke,
        name="invitation_revoke",
    ),
    path("workspaces/members/<int:pk>/", accounts.membership_change, name="membership_change"),
    path("", include("checker.urls")),
]
