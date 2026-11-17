from pathlib import Path
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from checker.backup import make_bundle
from checker.monitoring import ping, validate_ping_url
from checker.offsite import BackupStore, preflight, publish_backup, retained_bytes


class Command(BaseCommand):
    help = "Capture a coordinated PostgreSQL backup, verify its private B2 copy, and signal monitoring."

    def add_arguments(self, parser):
        parser.add_argument("--directory", required=True)

    def handle(self, *args, **options):
        try:
            store = BackupStore.from_environment()
            monitor = os.environ["BACKUP_HEALTHCHECK_URL"]
            validate_ping_url(monitor)
        except (KeyError, ValueError):
            raise CommandError("Configure private backup storage and monitoring before running.") from None

        def notify(state):
            try:
                ping(monitor, state)
                return True
            except Exception:
                # A monitoring outage must not prevent a valid backup. Missing pings
                # remain visible to the independent monitor once it is available.
                self.stderr.write("Backup monitor acknowledgement unavailable.")
                return False

        notify("start")
        try:
            client = store.client()
            preflight(store, client)
            if retained_bytes(store, client) >= store.limit:
                raise ValueError("Backup storage budget reached.")
            folder = Path(options["directory"]).resolve()
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            name = "pdc-" + timezone.now().strftime("%Y%m%dT%H%M%S%f") + ".pdc"
            output = folder / name
            make_bundle(output, lock_assets=True)
            receipt = publish_backup(output, store, client)
            with output.with_suffix(".receipt.json").open("x", encoding="utf-8") as stream:
                os.chmod(stream.name, 0o600)
                json.dump(receipt, stream)
        except Exception as error:
            notify("fail")
            raise CommandError(
                f"Off-site backup failed ({type(error).__name__}); prior remote versions were retained."
            ) from None
        if not notify("success"):
            raise CommandError("Backup verified, but monitoring acknowledgement failed.")
        self.stdout.write(f"Encrypted off-site backup uploaded and downloaded for checksum verification: {name}")
