"""Application writes live here so audit records and changes commit together."""

from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from checker.engine import ENGINE_VERSION, MAX_FILE_BYTES, evaluate, fingerprint, inspect_upload
from checker.models import Asset, AuditEvent, CheckRun, ManualReview, Package, RequirementRevision


def audit(actor, action, target, **detail):
    AuditEvent.objects.create(actor=actor, action=action, target=target, detail=detail)


def requirement_snapshot(req):
    return {
        "id": req.id, "partner_id": req.partner_id, "stage": req.stage,
        "title": req.title, "kind": req.kind, "slot": req.slot, "config": req.config,
        "source": req.source, "deadline": req.deadline.isoformat() if req.deadline else None,
        "approved": req.approved, "ambiguous": req.ambiguous, "revision": req.revision,
    }


def record_revision(req, actor, reason):
    RequirementRevision.objects.create(
        requirement=req, number=req.revision, snapshot=requirement_snapshot(req),
        reason=reason, actor=actor,
    )
    audit(actor, "requirement.revised", f"requirement:{req.id}", revision=req.revision, reason=reason)


def current_inputs(package):
    reqs = [requirement_snapshot(r) for r in package.partner.requirements.filter(stage=package.stage).order_by("id")]
    assets = [{"id": a.id, "slot": a.slot, "sha256": a.sha256, "size": a.size,
               "metadata": a.metadata, "available": a.file.storage.exists(a.file.name)}
              for a in package.assets.order_by("slot")]
    return reqs, assets, fingerprint(reqs, assets)


@transaction.atomic
def ensure_report(package, force=False):
    # Same package row is locked by uploads/removals/reviews. SQLite serializes writes.
    package = Package.objects.select_for_update(of=("self",)).select_related("partner").get(pk=package.pk)
    reqs, assets, signature = current_inputs(package)
    latest = package.runs.first()
    if latest and latest.fingerprint == signature and not force:
        return latest
    by_slot = {a["slot"]: a for a in assets if a["available"]}
    findings = []
    for rule in reqs:
        finding = evaluate(rule, by_slot.get(rule["slot"]))
        if rule["kind"] == "manual" and finding["status"] == "needs_review" and rule["approved"] and not rule["ambiguous"]:
            review = package.reviews.filter(requirement_id=rule["id"], fingerprint=signature).first()
            if review:
                finding = {"status": "passed" if review.passed else "failed",
                           "message": f"Manual review by {review.actor.get_username()}: {review.note}"}
        findings.append({**finding, "requirement_id": rule["id"], "revision": rule["revision"],
                         "title": rule["title"], "source": rule["source"], "kind": rule["kind"],
                         "slot": rule["slot"], "approved": rule["approved"], "ambiguous": rule["ambiguous"]})
    if not reqs:
        findings = [{"status": "needs_review", "message": "No requirements configured for this stage.",
                     "requirement_id": None, "title": "Requirements needed", "kind": "manual"}]
    return CheckRun.objects.create(package=package, fingerprint=signature,
                                   engine_version=ENGINE_VERSION, findings=findings)


def refresh_partner(partner, stage):
    # The team is intentionally small; no task queue needed for four slots/package.
    for package in partner.packages.filter(stage=stage).order_by("id"):
        ensure_report(package)


def store_asset(package, actor, slot, upload):
    data = upload.read(MAX_FILE_BYTES + 1)
    inspected = inspect_upload(upload.name, data, slot)
    stored = None
    try:
        with transaction.atomic():
            package = Package.objects.select_for_update().get(pk=package.pk)
            previous = Asset.objects.filter(package=package, slot=slot).first()
            if previous:
                old_file = previous.file
                previous.delete()
                transaction.on_commit(lambda: old_file.delete(save=False), robust=True)
            stored = Asset(package=package, slot=slot, original_name=Path(upload.name).name[:255],
                           uploaded_by=actor, **inspected)
            stored.file.save(upload.name, ContentFile(data), save=False)
            stored.save()
            package.save(update_fields=["updated_at"])
            audit(actor, "asset.uploaded", f"package:{package.id}", slot=slot,
                  sha256=inspected["sha256"], size=len(data), replaces=bool(previous))
            ensure_report(package)
    except Exception:
        if stored and stored.file.name:
            stored.file.delete(save=False)
        raise
    return stored


@transaction.atomic
def remove_asset(package, actor, asset_id):
    package = Package.objects.select_for_update().get(pk=package.pk)
    asset = package.assets.get(pk=asset_id)
    old_file, slot = asset.file, asset.slot
    asset.delete()
    transaction.on_commit(lambda: old_file.delete(save=False), robust=True)
    package.save(update_fields=["updated_at"])
    audit(actor, "asset.removed", f"package:{package.id}", slot=slot, sha256=asset.sha256)
    ensure_report(package)


@transaction.atomic
def record_review(package, requirement, actor, signature, passed, note):
    package = Package.objects.select_for_update(of=("self",)).select_related("partner").get(pk=package.pk)
    run = ensure_report(package)
    if run.fingerprint != signature:
        raise ValidationError("Files or requirements changed. Reload the report before reviewing.")
    eligible = [f for f in run.findings if f["requirement_id"] == requirement.id and
                f["kind"] == "manual" and f.get("approved") and not f.get("ambiguous") and
                f["status"] != "missing"]
    if not eligible:
        raise ValidationError("Only approved manual requirements with an uploaded file can be reviewed.")
    ManualReview.objects.create(package=package, requirement=requirement, actor=actor,
                                fingerprint=signature, passed=passed, note=note)
    audit(actor, "review.recorded", f"package:{package.id}", requirement_id=requirement.id,
          fingerprint=signature, passed=passed)
    return ensure_report(package, force=True)
