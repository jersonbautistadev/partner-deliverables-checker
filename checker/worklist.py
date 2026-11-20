"""Read-only dashboard snapshots. Explicit reports perform authoritative file checks."""

from collections import Counter

from django.db.models import OuterRef, Subquery

from checker.engine import ENGINE_VERSION
from checker.models import CheckRun


def worklist_cards(packages, requirements):
    latest = CheckRun.objects.filter(package_id=OuterRef("pk")).order_by("-pk")
    packages = list(packages.annotate(last_run_id=Subquery(latest.values("pk")[:1])))
    runs = CheckRun.objects.in_bulk(p.last_run_id for p in packages if p.last_run_id)
    changed_at = {}
    for requirement in requirements:
        key = (requirement.partner_id, requirement.stage)
        changed_at[key] = max(changed_at.get(key, requirement.updated_at), requirement.updated_at)
    cards = []
    for package in packages:
        run = runs.get(package.last_run_id)
        rule_changed = max(
            filter(
                None,
                [
                    changed_at.get((package.partner_id, package.stage)),
                    changed_at.get((package.partner_id, "all")),
                ],
            ),
            default=None,
        )
        needs_report = (
            run is None
            or run.engine_version != ENGINE_VERSION
            or package.updated_at > run.created_at
            or (rule_changed is not None and rule_changed > run.created_at)
        )
        counts = Counter() if needs_report else Counter(f["status"] for f in run.findings)
        cards.append(
            {
                "package": package,
                "run": run,
                "needs_report": bool(needs_report),
                "counts": counts,
                "ready": bool(
                    run
                    and run.findings
                    and not needs_report
                    and counts["passed"] + counts["not_applicable"] == len(run.findings)
                ),
            }
        )
    return cards
