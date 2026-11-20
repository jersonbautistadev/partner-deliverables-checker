"""Application writes live here so audit records and changes commit together."""

import logging
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q

from checker.engine import ENGINE_VERSION, MAX_FILE_BYTES, evaluate, fingerprint, inspect_upload
from checker.models import (
    Asset,
    AuditEvent,
    CheckRun,
    Evidence,
    ManualReview,
    Package,
    RequirementRevision,
    Workspace,
)
from checker.security import LimitExceeded, consume_limit, storage_used
from checker.storage import file_exists
from django.conf import settings


logger = logging.getLogger(__name__)


def audit(actor, action, target, workspace=None, **detail):
    AuditEvent.objects.create(
        actor=actor, action=action, target=target, workspace=workspace, detail=detail
    )


def requirement_snapshot(req):
    snapshot = {
        "id": req.id,
        "partner_id": req.partner_id,
        "stage": req.stage,
        "title": req.title,
        "kind": req.kind,
        "slot": req.slot,
        "config": req.config,
        "source": req.source,
        "deadline": req.deadline.isoformat() if req.deadline else None,
        "approved": req.approved,
        "ambiguous": req.ambiguous,
        "revision": req.revision,
    }
    # Additive metadata must not invalidate unchanged legacy file-review fingerprints.
    if req.responsibility != "unspecified" or req.applicability != "required" or req.conditions:
        snapshot.update(
            responsibility=req.responsibility,
            applicability=req.applicability,
            conditions=req.conditions,
        )
    return snapshot


def applicable_requirements(package):
    return package.partner.requirements.filter(Q(stage=package.stage) | Q(stage="all"))


def latest_evidence(package):
    current = {}
    for entry in package.evidence.select_related("actor").order_by("-id"):
        current.setdefault(entry.requirement_id, entry)
    return current


def record_revision(req, actor, reason):
    RequirementRevision.objects.create(
        requirement=req,
        number=req.revision,
        snapshot=requirement_snapshot(req),
        reason=reason,
        actor=actor,
    )
    audit(
        actor,
        "requirement.revised",
        f"requirement:{req.id}",
        workspace=req.partner.workspace,
        revision=req.revision,
        reason=reason,
    )


def current_inputs(package):
    reqs = [requirement_snapshot(r) for r in applicable_requirements(package).order_by("id")]
    assets = [
        {
            "id": a.id,
            "slot": a.slot,
            "sha256": a.sha256,
            "size": a.size,
            "metadata": a.metadata,
            "available": file_exists(a.file),
        }
        for a in package.assets.order_by("slot")
    ]
    rule_ids = {r["id"] for r in reqs if r["kind"] == "evidence"}
    evidence = [
        {
            "id": e.id,
            "requirement_id": e.requirement_id,
            "url": e.url,
            "note": e.note,
            "actor_id": e.actor_id,
        }
        for rid, e in sorted(latest_evidence(package).items())
        if rid in rule_ids
    ]
    return reqs, assets, fingerprint(reqs, assets, evidence=evidence)


@transaction.atomic
def ensure_report(package, force=False):
    # Same package row is locked by uploads/removals/reviews. SQLite serializes writes.
    package = (
        Package.objects.select_for_update(of=("self",)).select_related("partner").get(pk=package.pk)
    )
    reqs, assets, signature = current_inputs(package)
    latest = package.runs.first()
    if latest and latest.fingerprint == signature and not force:
        return latest
    by_slot = {a["slot"]: a for a in assets if a["available"]}
    evidence = latest_evidence(package)
    findings = []
    for rule in reqs:
        finding = evaluate(
            rule,
            evidence.get(rule["id"]) if rule["kind"] == "evidence" else by_slot.get(rule["slot"]),
        )
        if (
            rule["kind"] in {"manual", "evidence"}
            and finding["status"] in {"needs_review", "missing"}
            and rule["approved"]
            and not rule["ambiguous"]
        ):
            review = package.reviews.filter(
                requirement_id=rule["id"], fingerprint=signature
            ).first()
            if review and (finding["status"] != "missing" or review.decision == "not_applicable"):
                status = review.decision or ("passed" if review.passed else "failed")
                finding = {
                    "status": status,
                    "message": f"Manual review by {review.actor.get_username()}: {review.note}",
                }
        findings.append(
            {
                **finding,
                "requirement_id": rule["id"],
                "revision": rule["revision"],
                "title": rule["title"],
                "source": rule["source"],
                "kind": rule["kind"],
                "slot": rule["slot"],
                "approved": rule["approved"],
                "ambiguous": rule["ambiguous"],
                "responsibility": rule.get("responsibility", "unspecified"),
                "applicability": rule.get("applicability", "required"),
                "conditions": rule.get("conditions", ""),
            }
        )
    if not reqs:
        findings = [
            {
                "status": "needs_review",
                "message": "No requirements configured for this stage.",
                "requirement_id": None,
                "title": "Requirements needed",
                "kind": "manual",
            }
        ]
    return CheckRun.objects.create(
        package=package, fingerprint=signature, engine_version=ENGINE_VERSION, findings=findings
    )


def store_asset(package, actor, slot, upload):
    limit = min(MAX_FILE_BYTES, settings.UPLOAD_MAX_BYTES)
    data = upload.read(limit + 1)
    if len(data) > limit:
        raise LimitExceeded(f"File exceeds the {limit // 1048576} MiB upload limit.")
    inspected = inspect_upload(upload.name, data, slot)
    stored = None
    try:
        with transaction.atomic():
            workspace = Workspace.objects.select_for_update().get(pk=package.partner.workspace_id)
            if not consume_limit(f"upload:{workspace.pk}", settings.MAX_UPLOADS_PER_HOUR, 3600):
                raise LimitExceeded("Workspace upload limit reached. Try again later.")
            package = Package.objects.select_for_update().get(pk=package.pk)
            previous = Asset.objects.filter(package=package, slot=slot).first()
            if (
                storage_used(workspace) - (previous.size if previous else 0) + len(data)
                > workspace.storage_limit
            ):
                raise LimitExceeded(
                    "Workspace storage limit reached. Remove unused files or contact the operator."
                )
            if previous:
                old_file = previous.file
                previous.delete()
                transaction.on_commit(lambda: old_file.delete(save=False), robust=True)
            stored = Asset(
                package=package,
                slot=slot,
                original_name=Path(upload.name).name[:255],
                uploaded_by=actor,
                **inspected,
            )
            stored.file.save(upload.name, ContentFile(data), save=False)
            stored.save()
            package.save(update_fields=["updated_at"])
            audit(
                actor,
                "asset.uploaded",
                f"package:{package.id}",
                workspace=workspace,
                slot=slot,
                sha256=inspected["sha256"],
                size=len(data),
                replaces=bool(previous),
            )
            ensure_report(package)
    except Exception:
        if stored and stored.file.name:
            try:
                stored.file.delete(save=False)
            except Exception:
                logger.error("orphan_file_cleanup_failed package_id=%s", package.pk)
        raise
    return stored


@transaction.atomic
def remove_asset(package, actor, asset_id):
    Workspace.objects.select_for_update().get(pk=package.partner.workspace_id)
    package = Package.objects.select_for_update().get(pk=package.pk)
    asset = package.assets.get(pk=asset_id)
    old_file, slot = asset.file, asset.slot
    asset.delete()
    transaction.on_commit(lambda: old_file.delete(save=False), robust=True)
    package.save(update_fields=["updated_at"])
    audit(
        actor,
        "asset.removed",
        f"package:{package.id}",
        workspace=package.partner.workspace,
        slot=slot,
        sha256=asset.sha256,
    )
    ensure_report(package)


@transaction.atomic
def record_review(package, requirement, actor, signature, passed, note, decision=None):
    package = (
        Package.objects.select_for_update(of=("self",)).select_related("partner").get(pk=package.pk)
    )
    run = ensure_report(package)
    if run.fingerprint != signature:
        raise ValidationError(
            "Files, evidence or requirements changed. Reload the report before reviewing."
        )
    decision = decision or ("passed" if passed else "failed")
    if decision not in {"passed", "failed", "not_applicable"}:
        raise ValidationError("Choose a supported review decision.")
    passed = decision == "passed"
    can_exclude = requirement.kind == "evidence" and requirement.applicability in {
        "optional",
        "conditional",
    }
    if decision == "not_applicable" and not can_exclude:
        raise ValidationError(
            "Only optional or conditional evidence obligations may be marked not applicable."
        )
    eligible = [
        f
        for f in run.findings
        if f["requirement_id"] == requirement.id
        and f["kind"] in {"manual", "evidence"}
        and f.get("approved")
        and not f.get("ambiguous")
        and (f["status"] != "missing" or (decision == "not_applicable" and can_exclude))
    ]
    if not eligible:
        raise ValidationError(
            "Approve and clarify the instruction, then supply its file or evidence before reviewing."
        )
    ManualReview.objects.create(
        package=package,
        requirement=requirement,
        actor=actor,
        fingerprint=signature,
        passed=passed,
        decision=decision,
        note=note,
    )
    audit(
        actor,
        "review.recorded",
        f"package:{package.id}",
        workspace=package.partner.workspace,
        requirement_id=requirement.id,
        fingerprint=signature,
        passed=passed,
        decision=decision,
    )
    return ensure_report(package, force=True)


@transaction.atomic
def submit_evidence(package, requirement, actor, version, url, note):
    Workspace.objects.select_for_update().get(pk=package.partner.workspace_id)
    package = Package.objects.select_for_update().get(pk=package.pk)
    if not applicable_requirements(package).filter(pk=requirement.pk, kind="evidence").exists():
        raise ValidationError("This evidence requirement no longer applies to this package.")
    current = package.evidence.filter(requirement=requirement).first()
    if version != (current.pk if current else 0):
        raise ValidationError(
            "Evidence changed while you were editing. Reload before saving.", code="stale"
        )
    from checker.security import count_limit

    count_limit(
        Evidence.objects.filter(package__partner__workspace=package.partner.workspace_id),
        "MAX_EVIDENCE_REVISIONS",
    )
    entry = Evidence(package=package, requirement=requirement, actor=actor, url=url, note=note)
    entry.full_clean()
    entry.save()
    package.save(update_fields=["updated_at"])
    audit(
        actor,
        "evidence.submitted",
        f"package:{package.pk}",
        workspace=package.partner.workspace,
        requirement_id=requirement.pk,
        evidence_id=entry.pk,
    )
    ensure_report(package)
    return entry
