from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from urllib.parse import urlsplit

from checker.engine import validate_rule
from checker.models import KINDS, SLOTS, STAGES, Package, Partner, Requirement
from checker.permissions import is_coordinator


class PartnerForm(forms.ModelForm):
    def __init__(self, *args, workspace=None, **kwargs):
        self.workspace = workspace
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"]
        if (
            Partner.objects.filter(workspace=self.workspace, name=name)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise ValidationError("A partner with this name already exists in this workspace.")
        return name

    class Meta:
        model = Partner
        fields = ["name", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class RequirementForm(forms.ModelForm):
    slot = forms.ChoiceField(
        choices=[("", "No file slot (linked evidence)")] + SLOTS, required=False
    )
    version = forms.IntegerField(widget=forms.HiddenInput, required=False)
    minimum = forms.IntegerField(min_value=0, max_value=100000, required=False)
    maximum = forms.IntegerField(min_value=0, max_value=100000, required=False)
    width = forms.IntegerField(min_value=1, max_value=20000000, required=False)
    height = forms.IntegerField(min_value=1, max_value=20000000, required=False)
    phrase = forms.CharField(max_length=500, required=False)
    instructions = forms.CharField(
        max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    deadline = forms.DateTimeField(
        required=False,
        label="Deadline · Asia/Manila",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )
    reason = forms.CharField(max_length=500, label="Change reason / approval note")

    class Meta:
        model = Requirement
        fields = [
            "partner",
            "stage",
            "title",
            "kind",
            "slot",
            "responsibility",
            "applicability",
            "conditions",
            "source",
            "deadline",
            "ambiguous",
            "approved",
        ]
        labels = {
            "approved": "I reviewed and approve this requirement",
            "ambiguous": "Needs clarification",
        }

    def __init__(self, *args, **kwargs):
        workspace = kwargs.pop("workspace", None)
        super().__init__(*args, **kwargs)
        self.fields["partner"].queryset = Partner.objects.filter(workspace=workspace)
        for name in ("responsibility", "applicability"):
            self.fields[name].required = False
        self.fields[
            "conditions"
        ].help_text = (
            "State when this obligation applies. Required for an approved conditional obligation."
        )
        self.fields[
            "slot"
        ].help_text = "Choose no file slot for linked evidence; other checks require a file slot."
        self.fields[
            "kind"
        ].help_text = "Fill only the settings used by the selected check type below."
        if self.instance.pk:
            self.fields["partner"].disabled = True
            self.fields["stage"].disabled = self.instance.stage != "unset"
            self.initial.update(
                version=self.instance.revision,
                minimum=self.instance.config.get("min"),
                maximum=self.instance.config.get("max"),
                width=self.instance.config.get("width"),
                height=self.instance.config.get("height"),
                phrase=self.instance.config.get("phrase", ""),
                instructions=self.instance.config.get("instructions", ""),
            )
            if self.instance.deadline:
                self.initial["deadline"] = timezone.localtime(self.instance.deadline)

    def clean(self):
        data = super().clean()
        kind = data.get("kind")
        config = {}
        if kind == "word_count":
            config = {"min": data.get("minimum"), "max": data.get("maximum")}
        elif kind == "dimensions":
            config = {"width": data.get("width"), "height": data.get("height")}
        elif kind == "required_phrase":
            config = {"phrase": data.get("phrase", "")}
        elif kind in {"manual", "evidence"}:
            config = {"instructions": data.get("instructions", "")}
        data["responsibility"] = data.get("responsibility") or "unspecified"
        data["applicability"] = data.get("applicability") or "required"
        if kind != "evidence" and data["applicability"] not in {"required", "unspecified"}:
            self.add_error(
                "applicability",
                "Use linked evidence for optional or conditional work. File checks are required when configured.",
            )
        if (
            data.get("approved")
            and data["applicability"] == "conditional"
            and not data.get("conditions")
        ):
            self.add_error("conditions", "Explain when this conditional obligation applies.")
        if data.get("approved") and data.get("stage") == "unset":
            self.add_error(
                "stage", "Confirm the applicable stage before approving this instruction."
            )
        if data.get("approved") and data["applicability"] == "unspecified":
            self.add_error("applicability", "Confirm whether this obligation is required, optional or conditional before approving it.")
        if kind == "evidence":
            data["slot"] = ""
        if data.get("approved") and data.get("ambiguous"):
            raise ValidationError("Clarify an ambiguous requirement before approving it.")
        # Drafts may remain incomplete, but can never produce an automatic pass.
        if data.get("approved"):
            try:
                validate_rule(kind, data.get("slot"), config)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        data["config"] = config
        return data


class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = ["partner", "stage", "title", "owner"]

    def __init__(self, *args, user, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["partner"].queryset = Partner.objects.filter(workspace=workspace)
        if is_coordinator(user, workspace):
            self.fields["owner"].queryset = get_user_model().objects.filter(
                memberships__workspace=workspace, is_active=True, account__verified_at__isnull=False
            )
            self.fields["owner"].initial = user
        else:
            del self.fields["owner"]


class AssetForm(forms.Form):
    slot = forms.ChoiceField(choices=SLOTS)
    file = forms.FileField(
        help_text="TXT/DOCX for article or caption; JPG/PNG for image or logo. See the upload limit below."
    )


class ReviewForm(forms.Form):
    fingerprint = forms.CharField(max_length=64, widget=forms.HiddenInput)
    decision = forms.ChoiceField(
        choices=[
            ("passed", "Pass"),
            ("failed", "Fail"),
            ("not_applicable", "Not applicable (optional / conditional evidence only)"),
        ]
    )
    note = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Explain what you inspected and why it passes or fails.",
    )


class EvidenceForm(forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    url = forms.URLField(
        max_length=2000,
        required=False,
        label="Evidence URL",
        help_text="Optional HTTPS link. Access is reviewed manually; the app does not fetch it. Do not include passwords, secret tokens or private download links.",
    )
    note = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Evidence explanation",
        help_text="Describe what was completed, where to inspect it, and any limits. An attached screenshot alone does not prove publication or follower totals.",
    )

    def clean_url(self):
        value = self.cleaned_data["url"]
        if value:
            parts = urlsplit(value)
            if parts.scheme != "https" or parts.username or parts.password:
                raise ValidationError("Use an HTTPS link without embedded credentials.")
        return value


def filter_choices():
    return {"stages": STAGES, "kinds": KINDS}
