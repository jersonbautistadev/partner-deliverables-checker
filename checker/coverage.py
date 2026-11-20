"""Coverage of entered instructions using only the caller's visible report snapshots."""

from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from checker.models import STAGES, Partner, Requirement
from checker.permissions import visible_packages
from checker.worklist import worklist_cards


@login_required
@require_GET
def coverage(request):
    partners = Partner.objects.filter(workspace=request.workspace)
    try:
        partner = (
            get_object_or_404(partners, pk=int(request.GET["partner"]))
            if request.GET.get("partner")
            else None
        )
    except ValueError as exc:
        raise Http404("Partner unavailable.") from exc
    requirements = Requirement.objects.filter(partner__workspace=request.workspace).select_related(
        "partner"
    )
    packages = visible_packages(request.user, request.workspace)
    if partner:
        requirements = requirements.filter(partner=partner)
        packages = packages.filter(partner=partner)
    requirements = list(requirements)
    cards = worklist_cards(packages, requirements)
    by_partner = defaultdict(list)
    for card in cards:
        card["findings_by_requirement"] = (
            {f.get("requirement_id"): f for f in card["run"].findings} if card["run"] else {}
        )
        by_partner[card["package"].partner_id].append(card)
    rows = []
    for rule in requirements:
        checks = []
        for card in by_partner[rule.partner_id]:
            if rule.stage not in {"all", card["package"].stage}:
                continue
            finding = card["findings_by_requirement"].get(rule.pk)
            checks.append(
                {
                    "package": card["package"],
                    "status": "Report needed"
                    if card["needs_report"] or not finding
                    else finding["status"].replace("_", " ").capitalize(),
                    "resolved": bool(
                        not card["needs_report"]
                        and finding
                        and finding["status"] in {"passed", "not_applicable"}
                    ),
                }
            )
        if rule.stage == "all":
            present = {c["package"].stage for c in checks}
            checks.extend(
                {"package": None, "status": f"No {label.lower()} package", "resolved": False}
                for stage, label in STAGES
                if stage not in present
            )
        resolved = bool(
            rule.approved and not rule.ambiguous and checks and all(c["resolved"] for c in checks)
        )
        rows.append({"requirement": rule, "checks": checks, "resolved": resolved})
    resolved_count = sum(row["resolved"] for row in rows)
    rows.sort(
        key=lambda row: (
            row["resolved"],
            row["requirement"].partner.name.casefold(),
            row["requirement"].pk,
        )
    )
    return render(
        request,
        "checker/coverage.html",
        {
            "rows": Paginator(rows, 25).get_page(request.GET.get("page")),
            "total": len(rows),
            "unresolved": len(rows) - resolved_count,
            "resolved": resolved_count,
            "partners": partners,
            "selected_partner": partner,
        },
    )
