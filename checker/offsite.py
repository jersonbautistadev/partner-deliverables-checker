"""Operator-only encrypted backup publishing; no credentials belong in the web runtime."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import tempfile

import boto3
from botocore.config import Config

from checker.backup import decrypt


@dataclass(frozen=True)
class BackupStore:
    endpoint: str
    region: str
    bucket: str
    prefix: str
    limit: int

    @classmethod
    def from_environment(cls):
        region = os.environ["BACKUP_S3_REGION"]
        endpoint = os.environ["BACKUP_S3_ENDPOINT_URL"].rstrip("/")
        bucket = os.environ["BACKUP_S3_BUCKET"]
        prefix = os.environ["BACKUP_S3_PREFIX"]
        limit = int(os.environ.get("BACKUP_STORAGE_LIMIT_BYTES", str(3 * 1024**3)))
        if (
            not re.fullmatch(r"[a-z0-9-]+", region)
            or endpoint != f"https://s3.{region}.backblazeb2.com"
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket)
            or not re.fullmatch(r"(?:[a-z0-9_-]+/)+", prefix)
            or not 1 <= limit <= 8 * 1024**3
        ):
            raise ValueError("Invalid private Backblaze backup configuration.")
        return cls(endpoint, region, bucket, prefix, limit)

    def client(self):
        return boto3.client(
            "s3", endpoint_url=self.endpoint, region_name=self.region,
            aws_access_key_id=os.environ["BACKUP_S3_ACCESS_KEY"],
            aws_secret_access_key=os.environ["BACKUP_S3_SECRET_KEY"],
            config=Config(
                signature_version="s3v4", s3={"addressing_style": "path"},
                connect_timeout=10, read_timeout=60, retries={"max_attempts": 2},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )


def preflight(store, client):
    """Require private access and bounded retention before capturing/uploading data."""
    acl = client.get_bucket_acl(Bucket=store.bucket)
    owner = acl.get("Owner", {}).get("ID")
    grants = acl.get("Grants", [])
    if not owner or not grants or any(
        grant.get("Grantee", {}).get("Type") != "CanonicalUser"
        or grant["Grantee"].get("ID") != owner
        for grant in grants
    ):
        raise ValueError("Backup bucket must grant access only to its owner.")
    lifecycle = client.get_bucket_lifecycle_configuration(Bucket=store.bucket)
    matching, markers = [], []
    for rule in lifecycle.get("Rules", []):
        if rule.get("Status") != "Enabled":
            continue
        if "Filter" in rule and set(rule["Filter"]) != {"Prefix"}:
            raise ValueError("Use a simple, unambiguous prefix lifecycle rule for backups.")
        prefix = rule.get("Filter", {}).get("Prefix", rule.get("Prefix"))
        if isinstance(prefix, str) and store.prefix.startswith(prefix):
            # B2 exposes its automatic orphan-marker cleanup as a second S3
            # rule. It must apply to the same prefix as the retention rule.
            if rule.get("Expiration") == {"ExpiredObjectDeleteMarker": True}:
                if set(rule) - {"ID", "Status", "Filter", "Prefix", "Expiration"}:
                    raise ValueError("Unexpected action on backup marker cleanup rule.")
                markers.append(prefix)
            else:
                matching.append(rule)
    if (len(matching) != 1 or matching[0].get("Expiration", {}).get("Days") != 7
            or matching[0].get("NoncurrentVersionExpiration", {}).get("NoncurrentDays") != 1):
        raise ValueError("Configure one 7-day expiry and 1-day hidden-version expiry rule first.")
    expected_prefix = matching[0].get("Filter", {}).get("Prefix", matching[0].get("Prefix"))
    if markers != [expected_prefix]:
        raise ValueError("Configure the paired orphan-marker cleanup for the same backup prefix.")


def retained_bytes(store, client):
    total = count = 0
    pages = client.get_paginator("list_object_versions").paginate(Bucket=store.bucket, Prefix=store.prefix)
    for page in pages:
        for item in page.get("Versions", []):
            if not item["Key"].startswith(store.prefix):
                raise ValueError("Backup inventory returned an unexpected prefix.")
            total += int(item["Size"])
            count += 1
        count += len(page.get("DeleteMarkers", []))
        if count > 10000:
            raise ValueError("Backup inventory exceeds its bounded scan; inspect retention.")
    return total


def publish_backup(path, store, client):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not re.fullmatch(r"pdc-[a-zA-Z0-9-]+\.pdc", path.name):
        raise ValueError("Expected a regular encrypted backup bundle with a generated name.")
    size = path.stat().st_size
    if size > store.limit or size < 34:
        raise ValueError("Backup bundle exceeds the configured storage budget or is incomplete.")
    preflight(store, client)
    if retained_bytes(store, client) + size > store.limit:
        raise ValueError("Backup storage budget reached; previous backups were retained.")
    # Validate the complete authentication tag, not only the bundle magic/header.
    with tempfile.TemporaryDirectory(prefix="pdc-backup-auth-") as folder:
        decrypt(path, Path(folder) / "authenticated.tar.gz")
    signature = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            signature.update(chunk)
    digest = signature.hexdigest()
    key = store.prefix + path.name
    with path.open("rb") as stream:
        uploaded = client.put_object(
            Bucket=store.bucket, Key=key, Body=stream, ContentLength=size,
            ContentType="application/octet-stream", Metadata={"sha256": digest},
        )
    version = uploaded.get("VersionId")
    if not version:
        raise ValueError("Backup upload returned no object version identifier.")
    head = client.head_object(Bucket=store.bucket, Key=key, VersionId=version)
    if head["ContentLength"] != size or head.get("Metadata", {}).get("sha256") != digest:
        raise ValueError("Uploaded backup metadata failed verification; previous backups were retained.")
    downloaded = client.get_object(Bucket=store.bucket, Key=key, VersionId=version)
    remote_signature = hashlib.sha256()
    remaining = size
    with downloaded["Body"] as stream:
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("Uploaded backup was truncated.")
            remaining -= len(chunk)
            remote_signature.update(chunk)
        if stream.read(1):
            raise ValueError("Uploaded backup exceeded its declared length.")
    if remote_signature.hexdigest() != digest:
        raise ValueError("Uploaded backup bytes failed verification; previous backups were retained.")
    # This publishes no decryption key and deliberately deletes no remote versions.
    return {"key": key, "version_id": version, "bytes": size, "sha256": digest}
