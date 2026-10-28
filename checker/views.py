from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from checker.engine import InvalidUpload
from checker.forms import AssetForm, PackageForm, PartnerForm, RequirementForm, ReviewForm
from checker.models import Asset, AuditEvent, Partner, Requirement
from checker.permissions import require_coordinator, require_member, visible_packages
from checker.services import (
    audit,
    ensure_report,
    record_review,
    record_revision,
    refresh_partner,
    remove_asset,
    store_asset,
)


def package_for(user, pk):
    return get_object_or_404(visible_packages(user), pk=pk)


def package_card(package):
    run = ensure_report(package)
    counts = Counter(f["status"] for f in run.findings)
    ready = bool(run.findings) and counts["passed"] == len(run.findings)
    return {"package": package, "run": run, "counts": counts,
            "ready": ready, "status": "Ready for submission" if ready else "Action needed"}


def deadline_groups(queryset):
    groups = {}
    for req in queryset:
        key = (req.partner_id, req.stage, req.deadline)
        if key not in groups:
            groups[key] = {"partner": req.partner, "stage": req.get_stage_display(),
                           "deadline": req.deadline, "requirement_id": req.id,
                           "count": 0, "approved": True}
        groups[key]["count"] += 1
        groups[key]["approved"] &= req.approved and not req.ambiguous
    return list(groups.values())


@login_required
@require_GET
def dashboard(request):
    packages = visible_packages(request.user)
    cards = [package_card(p) for p in packages]
    now = timezone.now()
    deadlines = Requirement.objects.filter(deadline__gte=now).select_related("partner").order_by("deadline")
    overdue = Requirement.objects.filter(deadline__lt=now).select_related("partner").order_by("deadline")
    # Contributors can see shared instructions/deadlines, including stages with no package yet.
    stages = {(p.partner_id, p.stage) for p in packages}
    missing_stages = []
    for r in Requirement.objects.select_related("partner").order_by("partner__name", "stage"):
        key = (r.partner_id, r.stage)
        if key not in stages and key not in {(x.partner_id, x.stage) for x in missing_stages}:
            missing_stages.append(r)
    return render(request, "checker/dashboard.html", {
        "cards": cards, "partner_count": Partner.objects.count(),
        "incomplete": sum(not c["ready"] for c in cards),
        "review_count": sum(c["counts"]["needs_review"] for c in cards),
        "ready_count": sum(c["ready"] for c in cards),
        "deadlines": deadline_groups(deadlines), "overdue": deadline_groups(overdue),
        "missing_stages": missing_stages, "now": now,
    })


@login_required
@require_GET
def partners(request):
    require_member(request.user)
    return render(request, "checker/partners.html", {"partners": Partner.objects.prefetch_related("requirements")})


@login_required
@require_http_methods(["GET", "POST"])
def partner_new(request):
    require_coordinator(request.user)
    form = PartnerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            partner = form.save()
            audit(request.user, "partner.created", f"partner:{partner.id}", name=partner.name)
        return redirect("partners")
    return render(request, "checker/form.html", {"form": form, "title": "Add a partner"})


@login_required
@require_http_methods(["GET", "POST"])
def requirement_edit(request, pk=None):
    require_coordinator(request.user)
    # Lock only on POST; stale forms also carry an explicit revision check.
    with transaction.atomic():
        queryset = Requirement.objects.select_for_update() if request.method == "POST" else Requirement.objects.all()
        instance = get_object_or_404(queryset, pk=pk) if pk else None
        form = RequirementForm(request.POST or None, instance=instance)
        if request.method == "POST" and form.is_valid():
            if instance and form.cleaned_data["version"] != instance.revision:
                form.add_error(None, "This requirement changed while you were editing. Reload before saving.")
            else:
                req = form.save(commit=False)
                req.config = form.cleaned_data["config"]
                req.revision = instance.revision + 1 if instance else 1
                req.save()
                record_revision(req, request.user, form.cleaned_data["reason"])
                refresh_partner(req.partner, req.stage)
                return redirect("requirement_detail", pk=req.pk)
    return render(request, "checker/form.html", {
        "form": form, "title": "Revise requirement" if pk else "Add a requirement",
        "intro": "Copy only team-approved publishing instructions. Save uncertain instructions as unapproved and needing clarification. Bounds are inclusive; dimensions are exact pixels.",
    })


@login_required
@require_GET
def requirement_detail(request, pk):
    require_member(request.user)
    req = get_object_or_404(Requirement.objects.select_related("partner"), pk=pk)
    return render(request, "checker/requirement.html", {
        "requirement": req, "history": req.history.select_related("actor"),
    })


@login_required
@require_http_methods(["GET", "POST"])
def package_new(request):
    require_member(request.user)
    form = PackageForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            package = form.save(commit=False)
            package.owner = form.cleaned_data.get("owner", request.user)
            package.save()
            audit(request.user, "package.created", f"package:{package.id}", owner_id=package.owner_id)
            ensure_report(package)
        return redirect("package_detail", pk=package.pk)
    return render(request, "checker/form.html", {"form": form, "title": "New submission package"})


@login_required
@require_GET
def package_detail(request, pk):
    package = package_for(request.user, pk)
    card = package_card(package)
    return render(request, "checker/package.html", {
        **card, "assets": package.assets.all(), "upload_form": AssetForm(),
        "review_form": ReviewForm(initial={"fingerprint": card["run"].fingerprint}),
    })


@login_required
@require_POST
def asset_upload(request, pk):
    package = package_for(request.user, pk)
    form = AssetForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            store_asset(package, request.user, form.cleaned_data["slot"], form.cleaned_data["file"])
            messages.success(request, "File saved. The report now reflects the current package.")
        except InvalidUpload as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Choose one supported file and slot. Files over 5 MiB are rejected.")
    return redirect("package_detail", pk=pk)


@login_required
@require_POST
def asset_remove(request, pk, asset_id):
    package = package_for(request.user, pk)
    get_object_or_404(Asset, pk=asset_id, package=package)
    remove_asset(package, request.user, asset_id)
    messages.success(request, "File removed and report refreshed.")
    return redirect("package_detail", pk=pk)


@login_required
@require_GET
def asset_download(request, pk, asset_id):
    package = package_for(request.user, pk)
    asset = get_object_or_404(Asset, pk=asset_id, package=package)
    try:
        handle = asset.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("Stored file unavailable. Ask the coordinator to restore or replace it.") from exc
    audit(request.user, "asset.downloaded", f"package:{pk}", asset_id=asset.id)
    # Originals are attachments, never rendered as same-origin web documents.
    return FileResponse(handle, as_attachment=True, filename=asset.original_name,
                        content_type="application/octet-stream")


@login_required
@require_POST
def manual_review(request, pk, requirement_id):
    require_coordinator(request.user)
    package = package_for(request.user, pk)
    requirement = get_object_or_404(Requirement, pk=requirement_id, partner=package.partner, stage=package.stage)
    form = ReviewForm(request.POST)
    if not form.is_valid():
        return HttpResponse("A decision, report fingerprint and review note are required.", status=400)
    try:
        record_review(package, requirement, request.user, form.cleaned_data["fingerprint"],
                      form.cleaned_data["decision"] == "passed", form.cleaned_data["note"])
    except ValidationError as exc:
        return HttpResponse("; ".join(exc.messages), status=409, content_type="text/plain")
    messages.success(request, "Review recorded for this exact version of the package.")
    return redirect("package_detail", pk=pk)


@login_required
@require_GET
def audit_log(request):
    require_coordinator(request.user)
    events = AuditEvent.objects.select_related("actor")
    query = request.GET.get("q", "")[:120]
    if query:
        events = events.filter(Q(target__icontains=query) | Q(action__icontains=query))
    return render(request, "checker/audit.html", {"events": events[:200], "query": query})


@login_required
@require_GET
def api_packages(request):
    return JsonResponse({"packages": [{"id": p.id, "title": p.title, "partner_id": p.partner_id,
                                      "stage": p.stage, "owner_id": p.owner_id}
                                     for p in visible_packages(request.user)]})


@login_required
@require_GET
def api_report(request, pk):
    package = package_for(request.user, pk)
    run = ensure_report(package)
    return JsonResponse({"package_id": pk, "run_id": run.id, "fingerprint": run.fingerprint,
                         "engine_version": run.engine_version, "checked_at": run.created_at.isoformat(),
                         "findings": run.findings})


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})
