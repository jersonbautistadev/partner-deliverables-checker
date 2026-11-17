import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import json
import tarfile
import threading
from types import SimpleNamespace
from unittest.mock import patch
from unittest import skipUnless

from cryptography.exceptions import InvalidTag
from django.core.management import call_command, CommandError
from django.db import connection, connections, DatabaseError, transaction
from django.test import SimpleTestCase, TransactionTestCase

from checker.backup import decrypt, encrypt, make_bundle, pg_environment, pg_application_tables, postgres_asset_snapshot


class RecoveryTests(SimpleTestCase):
    def test_online_backup_mode_refuses_sqlite_before_writing(self):
        with tempfile.TemporaryDirectory() as folder, patch(
            "checker.management.commands.backup_bundle.connection", SimpleNamespace(vendor="sqlite")
        ):
            with self.assertRaisesMessage(CommandError, "requires PostgreSQL"):
                call_command("backup_bundle", "--lock-assets", "--directory", folder)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_legacy_whole_postgres_backup_is_rejected_before_restore_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"version":1,"database":"postgresql","assets":[]}), encoding="utf-8")
            with tarfile.open(root / "legacy.tar.gz", "w:gz") as bundle:
                bundle.add(manifest, arcname="manifest.json")
            with (
                patch.dict(os.environ, {"BACKUP_ENCRYPTION_KEY":base64.urlsafe_b64encode(os.urandom(32)).decode()}),
                patch("checker.backup.get_user_model") as user_model,
                patch("checker.backup.Workspace") as workspace,
                patch("checker.backup.connection", SimpleNamespace(vendor="postgresql")),
                patch("checker.backup.subprocess.run") as restore,
            ):
                user_model.return_value.objects.exists.return_value = False
                workspace.objects.exists.return_value = False
                encrypt(root / "legacy.tar.gz", root / "legacy.pdc")
                from checker.backup import restore_bundle

                with self.assertRaisesMessage(ValueError, "application-scoped PostgreSQL backup"):
                    restore_bundle(root / "legacy.pdc")
                restore.assert_not_called()

    def test_postgresql_dump_includes_only_installed_django_tables_and_migrations(self):
        from unittest.mock import Mock

        fake = Mock()
        fake.introspection.django_table_names.return_value = ["auth_user", "checker_workspace"]
        fake.ops.quote_name.side_effect = lambda name: '"' + name + '"'
        with patch("checker.backup.connection", fake):
            args = pg_application_tables()
        self.assertEqual(args, ["--strict-names", "--table", '"public"."auth_user"', "--table", '"public"."checker_workspace"', "--table", '"public"."django_migrations"'])

    def preview_environment(self):
        env = os.environ.copy()
        for key in ("DJANGO_ALLOWED_HOSTS", "PUBLIC_BASE_URL", "CSRF_TRUSTED_ORIGINS"):
            env.pop(key, None)
        env.update(
            DJANGO_DEBUG="0", VERCEL="1", VERCEL_ENV="preview",
            DJANGO_SECRET_KEY="fixture-only-not-production-preview-key-at-least-fifty-characters-7294",
            VERCEL_BRANCH_URL="fixture-git-review-fixture.vercel.app",
            VERCEL_URL="fixture-deployment-fixture.vercel.app",
            DATABASE_URL="postgresql://fixture:fixture@localhost/fixture",
            PRIVATE_S3_BUCKET="fixture-private",
        )
        return env

    def test_preview_urls_use_exact_platform_hosts_and_https(self):
        result = subprocess.run([
            sys.executable, "-c",
            "import config.settings as s; "
            "assert s.ALLOWED_HOSTS==['fixture-git-review-fixture.vercel.app','fixture-deployment-fixture.vercel.app']; "
            "assert s.CSRF_TRUSTED_ORIGINS==['https://fixture-git-review-fixture.vercel.app','https://fixture-deployment-fixture.vercel.app']; "
            "assert s.PUBLIC_BASE_URL=='https://fixture-git-review-fixture.vercel.app'; "
            "assert not s.DEBUG",
        ], env=self.preview_environment(), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_preview_rejects_invalid_or_missing_platform_hostnames(self):
        for hostname in ("", "https://fixture.vercel.app", "fixture.vercel.app.evil.test", "fixture.vercel.app/path"):
            env = self.preview_environment()
            env["VERCEL_BRANCH_URL"] = hostname
            env["VERCEL_URL"] = ""
            with self.subTest(hostname=hostname):
                result = subprocess.run([sys.executable, "-c", "import config.settings"], env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)

    def test_preview_preserves_explicit_origin_configuration(self):
        env = self.preview_environment()
        env.update(DJANGO_ALLOWED_HOSTS="staging.example.test", PUBLIC_BASE_URL="https://staging.example.test", CSRF_TRUSTED_ORIGINS="https://staging.example.test")
        result = subprocess.run([
            sys.executable, "-c", "import config.settings as s; "
            "assert s.ALLOWED_HOSTS==['staging.example.test']; "
            "assert s.CSRF_TRUSTED_ORIGINS==['https://staging.example.test']; "
            "assert s.PUBLIC_BASE_URL=='https://staging.example.test'",
        ], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backup_clients_use_configured_ca_and_preserve_verification(self):
        database = {
            "HOST": "database.example.test", "USER": "backup", "PASSWORD": "fixture",
            "OPTIONS": {"sslmode": "verify-full", "sslrootcert": Path("/fixture/provider.crt")},
        }
        with (
            patch("checker.backup.settings", SimpleNamespace(DATABASES={"default": database})),
            patch.dict(os.environ, {"PGSSLROOTCERT": "/wrong/inherited.crt"}, clear=True),
        ):
            env, args = pg_environment()
        self.assertEqual(env["PGSSLROOTCERT"], str(Path("/fixture/provider.crt")))
        self.assertEqual(env["PGSSLMODE"], "verify-full")
        self.assertIn("database.example.test", args)
        self.assertNotIn("fixture", args)

    def test_backup_clients_allow_libpq_ca_when_not_overridden(self):
        database = {"USER": "backup", "OPTIONS": {"sslmode": "verify-full"}}
        with (
            patch("checker.backup.settings", SimpleNamespace(DATABASES={"default": database})),
            patch.dict(os.environ, {"PGSSLROOTCERT": "/fixture/runner.crt"}, clear=True),
        ):
            env, _ = pg_environment()
        self.assertEqual(env["PGSSLROOTCERT"], "/fixture/runner.crt")

    def test_provider_ca_and_s3_path_style_reach_client_configuration(self):
        env = os.environ.copy()
        env.pop("VERCEL", None)
        env.pop("VERCEL_ENV", None)
        env.update(
            DJANGO_DEBUG="1",
            DATABASE_URL="postgresql://fixture:fixture@localhost/fixture?sslmode=verify-full",
            DATABASE_SSL_ROOT_CERT="deploy/supabase-root-ca.crt",
            PRIVATE_S3_BUCKET="fixture-private",
            PRIVATE_S3_ACCESS_KEY="fixture",
            PRIVATE_S3_SECRET_KEY="fixture",
            PRIVATE_S3_ENDPOINT_URL="https://fixture.storage.supabase.co/storage/v1/s3",
            PRIVATE_S3_ADDRESSING_STYLE="path",
        )
        code = (
            "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); "
            "import django; django.setup(); "
            "from django.conf import settings; from pathlib import Path; "
            "from django.core.files.storage import default_storage; "
            "from urllib.parse import urlsplit; "
            "assert settings.DATABASES['default']['OPTIONS']['sslmode']=='verify-full'; "
            "assert Path(settings.DATABASES['default']['OPTIONS']['sslrootcert'])"
            "==settings.BASE_DIR/'deploy/supabase-root-ca.crt'; "
            "assert default_storage.connection.meta.client.meta.config.s3['addressing_style']=='path'; "
            "u=urlsplit(default_storage.url('probe.txt')); "
            "assert u.hostname=='fixture.storage.supabase.co'; "
            "assert u.path=='/storage/v1/s3/fixture-private/originals/probe.txt'"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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


@skipUnless(connection.vendor == "postgresql", "PostgreSQL table locking required.")
class PostgresAssetSnapshotTests(TransactionTestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from checker.models import Asset, Package, Partner, Workspace

        user = get_user_model().objects.create_user("snapshot_fixture")
        workspace = Workspace.objects.create(name="Snapshot fixture", created_by=user)
        partner = Partner.objects.create(workspace=workspace, name="Snapshot fixture partner")
        package = Package.objects.create(partner=partner, owner=user, stage="pre", title="Snapshot fixture")
        self.asset = Asset.objects.create(
            package=package, slot="article", file="snapshot-fixture.txt",
            original_name="original.txt", sha256="0" * 64, size=1, metadata={}, uploaded_by=user,
        )

    def test_snapshot_allows_reads_blocks_changes_and_releases_lock(self):
        from checker.models import Asset

        observed = {}

        def writer():
            try:
                observed["read"] = Asset.objects.get(pk=self.asset.pk).original_name
                with transaction.atomic():
                    with connections["default"].cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '100ms'")
                    Asset.objects.filter(pk=self.asset.pk).update(original_name="concurrent.txt")
                observed["changed"] = True
            except DatabaseError as error:
                observed["sqlstate"] = getattr(error.__cause__, "sqlstate", None)
            finally:
                connections["default"].close()

        with postgres_asset_snapshot():
            worker = threading.Thread(target=writer)
            worker.start()
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(observed, {"read": "original.txt", "sqlstate": "55P03"})
            self.asset.refresh_from_db()
            self.assertEqual(self.asset.original_name, "original.txt")
        Asset.objects.filter(pk=self.asset.pk).update(original_name="after-backup.txt")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.original_name, "after-backup.txt")

    def test_failed_snapshot_releases_its_lock(self):
        from checker.models import Asset

        with self.assertRaisesMessage(RuntimeError, "capture failed"):
            with postgres_asset_snapshot():
                raise RuntimeError("capture failed")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_locks WHERE pid = pg_backend_pid() "
                "AND relation = %s::regclass AND mode = 'ShareLock' AND granted",
                [Asset._meta.db_table],
            )
            self.assertEqual(cursor.fetchone()[0], 0)
        Asset.objects.filter(pk=self.asset.pk).update(original_name="after-failure.txt")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.original_name, "after-failure.txt")

    def test_snapshot_refuses_an_ambient_transaction(self):
        with transaction.atomic():
            with self.assertRaisesMessage(ValueError, "outside an existing transaction"):
                with postgres_asset_snapshot():
                    self.fail("A nested snapshot must not start.")

    def test_lost_database_session_cannot_publish_a_bundle(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {"BACKUP_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode()}),
            patch("checker.backup.write_archive", side_effect=lambda *args: connection.close()),
        ):
            target = Path(folder) / "lost-session.pdc"
            with self.assertRaises(DatabaseError):
                make_bundle(target, lock_assets=True)
            self.assertFalse(target.exists())
