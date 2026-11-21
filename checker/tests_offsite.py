import base64
from dataclasses import replace
import hashlib
import io
import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

from cryptography.exceptions import InvalidTag
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase

from checker.backup import encrypt
from checker.offsite import BackupStore, preflight, publish_backup
from checker.monitoring import ping


class MemoryStore:
    """Boundary double only; live B2 acceptance is recorded separately."""

    def __init__(self):
        self.public = self.corrupt_download = False
        self.put_count = 0
        self.versions = []
        self.lifecycle = [{"Status": "Enabled", "Filter": {"Prefix": "staging/"},
                           "Expiration": {"Days": 7}, "NoncurrentVersionExpiration": {"NoncurrentDays": 1}},
                          {"Status": "Enabled", "Filter": {"Prefix": "staging/"},
                           "Expiration": {"ExpiredObjectDeleteMarker": True}}]

    def get_bucket_acl(self, **kwargs):
        grants = [{"Grantee": {"Type": "CanonicalUser", "ID": "owner"}, "Permission": "FULL_CONTROL"}]
        if self.public:
            grants.append({"Grantee": {"Type": "Group", "URI": "public"}, "Permission": "READ"})
        return {"Owner": {"ID": "owner"}, "Grants": grants}

    def get_bucket_lifecycle_configuration(self, **kwargs):
        return {"Rules": self.lifecycle}

    def get_paginator(self, name):
        return self

    def paginate(self, **kwargs):
        yield {"Versions": self.versions}

    def put_object(self, **kwargs):
        self.put_count += 1
        self.stored = kwargs["Body"].read()
        self.metadata = kwargs["Metadata"]
        return {"VersionId": "version-fixture"}

    def head_object(self, **kwargs):
        return {"ContentLength": len(self.stored), "Metadata": self.metadata}

    def get_object(self, **kwargs):
        data = self.stored
        if self.corrupt_download:
            data = bytes([data[0] ^ 1]) + data[1:]
        return {"Body": io.BytesIO(data)}


class OffsiteTests(SimpleTestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.env = patch.dict(os.environ, {"BACKUP_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode()})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.root = Path(self.scratch.name)
        source = self.root / "source"
        source.write_bytes(b"fictional private backup payload")
        self.bundle = self.root / "pdc-fixture.pdc"
        encrypt(source, self.bundle)
        self.store = BackupStore("https://s3.us-west-004.backblazeb2.com", "us-west-004", "pdc-fixture", "staging/", 1024**2)
        self.client = MemoryStore()

    def test_authenticated_ciphertext_round_trip_is_verified(self):
        receipt = publish_backup(self.bundle, self.store, self.client)
        self.assertEqual(receipt["sha256"], hashlib.sha256(self.bundle.read_bytes()).hexdigest())
        self.assertEqual(receipt["bytes"], self.bundle.stat().st_size)
        self.assertEqual(self.client.stored, self.bundle.read_bytes())
        self.assertNotIn(b"fictional private backup payload", self.client.stored)

    def test_corrupt_bundle_is_never_uploaded(self):
        data = bytearray(self.bundle.read_bytes())
        data[-1] ^= 1
        self.bundle.write_bytes(data)
        with self.assertRaises(InvalidTag):
            publish_backup(self.bundle, self.store, self.client)
        self.assertEqual(self.client.put_count, 0)

    def test_public_bucket_is_refused_before_upload(self):
        self.client.public = True
        with self.assertRaisesMessage(ValueError, "only to its owner"):
            publish_backup(self.bundle, self.store, self.client)
        self.assertEqual(self.client.put_count, 0)

    def test_budget_includes_hidden_versions(self):
        self.client.versions = [{"Key": "staging/pdc-old.pdc", "IsLatest": False, "Size": 1024}]
        store = replace(self.store, limit=1024 + self.bundle.stat().st_size - 1)
        with self.assertRaisesMessage(ValueError, "storage budget reached"):
            publish_backup(self.bundle, store, self.client)
        self.assertEqual(self.client.put_count, 0)

    def test_missing_or_ambiguous_retention_is_refused(self):
        valid = self.client.lifecycle[0]
        for rules in [[], [valid, {**valid, "Filter": {"Prefix": ""}}]]:
            with self.subTest(rules=len(rules)):
                self.client.lifecycle = rules
                with self.assertRaises(ValueError):
                    preflight(self.store, self.client)
        self.assertEqual(self.client.put_count, 0)

    def test_remote_corruption_does_not_report_success(self):
        self.client.corrupt_download = True
        with self.assertRaisesMessage(ValueError, "bytes failed verification"):
            publish_backup(self.bundle, self.store, self.client)

    def test_orphan_marker_cleanup_must_match_retention_prefix(self):
        for prefix in ("", "unrelated/"):
            with self.subTest(prefix=prefix):
                self.client.lifecycle[1]["Filter"]["Prefix"] = prefix
                with self.assertRaisesMessage(ValueError, "paired orphan-marker"):
                    preflight(self.store, self.client)

    def test_destination_requires_exact_https_provider_and_safe_prefix(self):
        values = {"BACKUP_S3_REGION": "us-west-004", "BACKUP_S3_ENDPOINT_URL": "http://s3.us-west-004.backblazeb2.com",
                  "BACKUP_S3_BUCKET": "pdc-fixture", "BACKUP_S3_PREFIX": "staging/"}
        with patch.dict(os.environ, values):
            with self.assertRaises(ValueError):
                BackupStore.from_environment()
        values["BACKUP_S3_ENDPOINT_URL"] = "https://s3.us-west-004.backblazeb2.com"
        values["BACKUP_S3_PREFIX"] = "../production/"
        with patch.dict(os.environ, values):
            with self.assertRaises(ValueError):
                BackupStore.from_environment()

    def test_missing_monitor_configuration_prevents_capture(self):
        values = {"BACKUP_S3_REGION": "us-west-004", "BACKUP_S3_ENDPOINT_URL": "https://s3.us-west-004.backblazeb2.com",
                  "BACKUP_S3_BUCKET": "pdc-fixture", "BACKUP_S3_PREFIX": "staging/"}
        with patch.dict(os.environ, values, clear=True), patch(
            "checker.management.commands.backup_offsite.make_bundle"
        ) as capture:
            with self.assertRaisesMessage(CommandError, "Configure private backup storage and monitoring"):
                call_command("backup_offsite", "--directory", self.scratch.name)
            capture.assert_not_called()


class MonitoringTests(SimpleTestCase):
    url = "https://hc-ping.com/00000000-0000-0000-0000-000000000001"

    def test_ping_contains_no_application_payload(self):
        with patch("checker.monitoring.build_opener") as builder:
            response = MagicMock(status=200)
            response.read.return_value = b"OK"
            builder.return_value.open.return_value.__enter__.return_value = response
            ping(self.url, "start")
            request = builder.return_value.open.call_args.args[0]
            self.assertEqual(request.data, b"")
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request.full_url, self.url + "/start")

    def test_http_200_for_unknown_check_is_not_success(self):
        with patch("checker.monitoring.build_opener") as builder:
            response = MagicMock(status=200)
            response.read.return_value = b"not found"
            builder.return_value.open.return_value.__enter__.return_value = response
            with self.assertRaisesMessage(ValueError, "did not acknowledge") as error:
                ping(self.url)
            self.assertNotIn(self.url, str(error.exception))

    def test_insecure_or_redirector_configuration_never_makes_a_request(self):
        with patch("checker.monitoring.build_opener") as builder:
            for url in [self.url.replace("https:", "http:"), self.url + "?secret=fixture", self.url.replace("hc-ping.com", "example.invalid")]:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    ping(url)
            builder.assert_not_called()
