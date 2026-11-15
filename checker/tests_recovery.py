import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
from unittest import skipUnless

from cryptography.exceptions import InvalidTag
from django.test import SimpleTestCase

from checker.backup import decrypt, encrypt


class RecoveryTests(SimpleTestCase):
    def test_database_url_enforces_tls_without_downgrading_verification(self):
        env = os.environ.copy()
        env.pop("VERCEL", None)
        env.pop("VERCEL_ENV", None)
        env["DJANGO_DEBUG"] = "1"
        for query, enforce, expected in (
            ("?sslmode=verify-full", "1", "verify-full"),
            ("?sslmode=disable", "1", "require"),
            ("", "1", "require"),
            ("", "0", None),
        ):
            with self.subTest(query=query, enforce=enforce):
                env.update(
                    DATABASE_URL="postgresql://fixture:fixture@localhost/fixture" + query,
                    DATABASE_REQUIRE_SSL=enforce,
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import config.settings as s; "
                        "print(s.DATABASES['default']['OPTIONS'].get('sslmode'))",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), str(expected))

    def test_vercel_startup_rejects_missing_secrets_and_production_debug(self):
        env = os.environ.copy()
        for name in ("DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DATABASE_URL", "PRIVATE_S3_BUCKET"):
            env.pop(name, None)
        env.update(VERCEL="1", VERCEL_ENV="production")
        result = subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set a random DJANGO_SECRET_KEY", result.stderr)
        env["DJANGO_DEBUG"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Vercel production must use DJANGO_DEBUG=0", result.stderr)

    def test_encryption_rejects_tampering_and_preserves_existing_destination(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(
                os.environ,
                {"BACKUP_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode()},
            ),
        ):
            root = Path(folder)
            source = root / "source"
            source.write_bytes(b"private fixture" * 1000)
            target = root / "backup"
            encrypt(source, target)
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                encrypt(source, target)
            self.assertEqual(target.read_bytes(), original)
            decrypt(target, root / "plain")
            self.assertEqual((root / "plain").read_bytes(), source.read_bytes())
            data = bytearray(original)
            data[-20] ^= 1
            target.write_bytes(data)
            with self.assertRaises(InvalidTag):
                decrypt(target, root / "tampered")

    def test_legacy_migration_preserves_records(self):
        result = subprocess.run(
            [sys.executable, "scripts/rehearse_migration.py"], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_encrypted_backup_restore_rehearsal(self):
        result = subprocess.run(
            [sys.executable, "scripts/rehearse_recovery.py"], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @skipUnless(
        os.environ.get("POSTGRES_HOST") and os.environ.get("PG_DUMP"),
        "PostgreSQL client tools required.",
    )
    def test_postgresql_encrypted_backup_restore(self):
        result = subprocess.run(
            [sys.executable, "scripts/rehearse_pg_recovery.py"], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
