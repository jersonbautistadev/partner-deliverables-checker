from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, UserCreationForm

from checker.models import Account, ROLES
from checker.permissions import is_verified


class SignupForm(UserCreationForm):
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def clean_username(self):
        # Do not expose account existence during signup. The unique database
        # constraint and atomic handler return the same acknowledgement on a race.
        return self.cleaned_data["username"]

    def validate_unique(self):
        """Return duplicates through the atomic signup handler, not field errors."""

    def clean_email(self):
        return self.cleaned_data["email"].strip().casefold()


class VerifiedLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not is_verified(user):
            raise self.get_invalid_login_error()


class VerifiedPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        for account in Account.objects.filter(
            email=email.strip().casefold(), verified_at__isnull=False, user__is_active=True
        ).select_related("user"):
            if account.user.has_usable_password():
                yield account.user


class EmailForm(forms.Form):
    email = forms.EmailField()


class WorkspaceForm(forms.Form):
    name = forms.CharField(max_length=120, label="Workspace name")


class InviteForm(EmailForm):
    role = forms.ChoiceField(choices=ROLES, initial="contributor")


class MembershipForm(forms.Form):
    role = forms.ChoiceField(choices=ROLES + [("remove", "Remove membership")])


class ConfirmPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, max_length=1024)


class WorkspaceSelectionForm(forms.Form):
    workspace = forms.IntegerField(min_value=1, max_value=9223372036854775807)
