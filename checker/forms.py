from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from checker.engine import validate_rule
from checker.models import KINDS, SLOTS, STAGES, Package, Partner, Requirement
from checker.permissions import is_coordinator


class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = ["name", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class RequirementForm(forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput, required=False)
    minimum = forms.IntegerField(min_value=0, max_value=100000, required=False)
    maximum = forms.IntegerField(min_value=0, max_value=100000, required=False)
    width = forms.IntegerField(min_value=1, max_value=20000000, required=False)
    height = forms.IntegerField(min_value=1, max_value=20000000, required=False)
    phrase = forms.CharField(max_length=500, required=False)
    instructions = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    deadline = forms.DateTimeField(
        required=False, label="Deadline · Asia/Manila",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )
    reason = forms.CharField(max_length=500, label="Change reason / approval note")

    class Meta:
        model = Requirement
        fields = ["partner", "stage", "title", "kind", "slot", "source", "deadline", "ambiguous", "approved"]
        labels = {"approved": "I reviewed and approve this requirement", "ambiguous": "Needs clarification"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].help_text = "Fill only the settings used by the selected check type below."
        if self.instance.pk:
            self.fields["partner"].disabled = True
            self.fields["stage"].disabled = True
            self.initial.update(version=self.instance.revision,
                                minimum=self.instance.config.get("min"),
                                maximum=self.instance.config.get("max"),
                                width=self.instance.config.get("width"),
                                height=self.instance.config.get("height"),
                                phrase=self.instance.config.get("phrase", ""),
                                instructions=self.instance.config.get("instructions", ""))
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
        elif kind == "manual":
            config = {"instructions": data.get("instructions", "")}
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

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        if is_coordinator(user):
            self.fields["owner"].queryset = get_user_model().objects.filter(
                Q(groups__name__in=["Coordinator", "Contributor"]) | Q(is_superuser=True),
                is_active=True,
            ).distinct()
            self.fields["owner"].initial = user
        else:
            del self.fields["owner"]


class AssetForm(forms.Form):
    slot = forms.ChoiceField(choices=SLOTS)
    file = forms.FileField(help_text="TXT/DOCX for article or caption; JPG/PNG for image or logo. Up to 5 MiB.")


class ReviewForm(forms.Form):
    fingerprint = forms.CharField(max_length=64, widget=forms.HiddenInput)
    decision = forms.ChoiceField(choices=[("passed", "Pass"), ("failed", "Fail")])
    note = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 2}),
                           help_text="Explain what you inspected and why it passes or fails.")


def filter_choices():
    return {"stages": STAGES, "kinds": KINDS}
