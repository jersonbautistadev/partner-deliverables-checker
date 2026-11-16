"""Offline backup bundles. Authentication completes before database/original-file restore writes."""

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.storage import default_storage
from django.db import connection

from checker.models import Asset, Workspace

MAGIC = b"PDCBK1"


def encryption_key():
    raw = base64.urlsafe_b64decode(os.environ["BACKUP_ENCRYPTION_KEY"])
    if len(raw) != 32:
        raise ValueError("BACKUP_ENCRYPTION_KEY must encode 32 random bytes.")
    return raw


def encrypt(source, destination):
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(encryption_key()), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    output = open(destination, "xb")
    try:
        with output as out, open(source, "rb") as inp:
            os.chmod(destination, 0o600)
            out.write(MAGIC + nonce)
            for chunk in iter(lambda: inp.read(1024 * 1024), b""):
                out.write(encryptor.update(chunk))
            out.write(encryptor.finalize())
            out.write(encryptor.tag)
    except Exception:
        Path(destination).unlink(missing_ok=True)
        raise


def decrypt(source, destination):
    size = Path(source).stat().st_size
    with open(source, "rb") as inp, open(destination, "xb") as out:
        os.chmod(destination, 0o600)
        if inp.read(len(MAGIC)) != MAGIC or size < len(MAGIC) + 28:
            raise ValueError("Invalid backup format.")
        nonce = inp.read(12)
        inp.seek(-16, 2)
        tag = inp.read(16)
        inp.seek(len(MAGIC) + 12)
        decryptor = Cipher(algorithms.AES(encryption_key()), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(MAGIC)
        remaining = size - len(MAGIC) - 28
        while remaining:
            chunk = inp.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("Truncated backup.")
            remaining -= len(chunk)
            out.write(decryptor.update(chunk))
        out.write(decryptor.finalize())


def pg_environment():
    db = settings.DATABASES["default"]
    env = dict(
        os.environ,
        PGPASSWORD=db.get("PASSWORD", ""),
        PGSSLMODE=db.get("OPTIONS", {}).get("sslmode", "prefer"),
    )
    root_cert = db.get("OPTIONS", {}).get("sslrootcert")
    if root_cert is not None:
        env["PGSSLROOTCERT"] = str(root_cert)
    args = [
        "-h",
        db.get("HOST") or "localhost",
        "-p",
        str(db.get("PORT") or 5432),
        "-U",
        db["USER"],
    ]
    return env, args


def make_bundle(destination):
    encryption_key()
    vendor = connection.vendor
    if vendor not in {"sqlite", "postgresql"}:
        raise ValueError("Unsupported database.")
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        dbfile = root / "database.dump"
        if vendor == "sqlite":
            connection.ensure_connection()
            backup = sqlite3.connect(dbfile)
            try:
                connection.connection.backup(backup)
            finally:
                backup.close()
        else:
            env, args = pg_environment()
            subprocess.run(
                [
                    os.environ.get("PG_DUMP", "pg_dump"),
                    *args,
                    "-Fc",
                    "-f",
                    str(dbfile),
                    settings.DATABASES["default"]["NAME"],
                ],
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        manifest = {"version": 1, "database": vendor, "assets": []}
        with tarfile.open(root / "bundle.tar.gz", "w:gz") as bundle:
            bundle.add(dbfile, arcname="database.dump")
            for asset in Asset.objects.order_by("pk"):
                target = root / "asset"
                signature = hashlib.sha256()
                with asset.file.open("rb") as inp, target.open("wb") as out:
                    for chunk in iter(lambda: inp.read(1024 * 1024), b""):
                        signature.update(chunk)
                        out.write(chunk)
                if signature.hexdigest() != asset.sha256:
                    raise ValueError("Original file digest does not match the database.")
                member = f"objects/{asset.pk}"
                bundle.add(target, arcname=member)
                manifest["assets"].append(
                    {
                        "id": asset.pk,
                        "path": asset.file.name,
                        "sha256": asset.sha256,
                        "member": member,
                    }
                )
            metadata = root / "manifest.json"
            metadata.write_text(json.dumps(manifest), encoding="utf-8")
            bundle.add(metadata, arcname="manifest.json")
        encrypt(root / "bundle.tar.gz", destination)


def restore_bundle(source):
    if get_user_model().objects.exists() or Workspace.objects.exists():
        raise ValueError("Restore only into a fresh migrated database with no users or workspaces.")
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        # Authentication is verified before the tar is read or database/storage is touched.
        decrypt(source, root / "bundle.tar.gz")
        with tarfile.open(root / "bundle.tar.gz", "r:gz") as bundle:
            manifest = json.load(bundle.extractfile("manifest.json"))
            if manifest.get("version") != 1 or manifest.get("database") != connection.vendor:
                raise ValueError("Backup and target database types must match.")
            for asset in manifest["assets"]:
                name = PurePosixPath(asset["path"])
                if name.is_absolute() or ".." in name.parts or "\\" in asset["path"]:
                    raise ValueError("Unsafe stored file path.")
                if default_storage.exists(asset["path"]):
                    raise ValueError("Use a fresh private storage directory or prefix.")
                member = bundle.getmember(asset["member"])
                if not member.isfile():
                    raise ValueError("Expected an original file.")
                signature = hashlib.sha256()
                with bundle.extractfile(member) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        signature.update(chunk)
                if signature.hexdigest() != asset["sha256"]:
                    raise ValueError("Invalid original-file checksum.")
            with open(root / "database.dump", "wb") as out:
                shutil.copyfileobj(bundle.extractfile("database.dump"), out)
            vendor = connection.vendor
            connection.close()
            if vendor == "sqlite":
                shutil.copyfile(root / "database.dump", settings.DATABASES["default"]["NAME"])
            else:
                env, args = pg_environment()
                subprocess.run(
                    [
                        os.environ.get("PG_RESTORE", "pg_restore"),
                        *args,
                        "--clean",
                        "--if-exists",
                        "--no-owner",
                        "--no-acl",
                        "--exit-on-error",
                        "-d",
                        settings.DATABASES["default"]["NAME"],
                        str(root / "database.dump"),
                    ],
                    env=env,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            for entry in manifest["assets"]:
                asset = Asset.objects.get(
                    pk=entry["id"], file=entry["path"], sha256=entry["sha256"]
                )
                with bundle.extractfile(entry["member"]) as stream:
                    saved = default_storage.save(asset.file.name, File(stream))
                if saved != asset.file.name:
                    raise ValueError(
                        "Storage changed an original path. Keep this partial restore offline."
                    )
