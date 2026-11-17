from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from checker.backup import make_bundle


class Command(BaseCommand):
    help = "Back up a paused application, or lock PostgreSQL file records while capturing a bundle."

    def add_arguments(self, parser):
        parser.add_argument("--directory", required=True)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--traffic-paused", action="store_true")
        mode.add_argument("--lock-assets", action="store_true")
        parser.add_argument("--retention-days", type=int, default=30)

    def handle(self, *args, **options):
        if options["retention_days"] < 1:
            raise CommandError(
                "Retention must be positive."
            )
        if options["lock_assets"] and connection.vendor != "postgresql":
            raise CommandError("--lock-assets requires PostgreSQL; use --traffic-paused for SQLite.")
        folder = Path(options["directory"]).resolve()
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        output = folder / ("pdc-" + timezone.now().strftime("%Y%m%dT%H%M%S%f") + ".pdc")
        try:
            make_bundle(output, lock_assets=options["lock_assets"])
        except Exception as exc:
            raise CommandError(
                f"Backup failed ({type(exc).__name__}); no valid bundle produced."
            ) from exc
        cutoff = (timezone.now() - timedelta(days=options["retention_days"])).timestamp()
        for old in folder.glob("pdc-*.pdc"):
            if (
                old.is_file()
                and not old.is_symlink()
                and old.resolve().parent == folder
                and old.stat().st_mtime < cutoff
            ):
                old.unlink()
        self.stdout.write(f"Encrypted backup created: {output.name}")
