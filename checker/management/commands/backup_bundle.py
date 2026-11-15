from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from checker.backup import make_bundle


class Command(BaseCommand):
    help = "Back up an OFFLINE database and original files into an encrypted bundle."

    def add_arguments(self, parser):
        parser.add_argument("--directory", required=True)
        parser.add_argument("--traffic-paused", action="store_true")
        parser.add_argument("--retention-days", type=int, default=30)

    def handle(self, *args, **options):
        if not options["traffic_paused"] or options["retention_days"] < 1:
            raise CommandError(
                "Stop all web/mail writers first and pass --traffic-paused; retention must be positive."
            )
        folder = Path(options["directory"]).resolve()
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        output = folder / ("pdc-" + timezone.now().strftime("%Y%m%dT%H%M%S%f") + ".pdc")
        try:
            make_bundle(output)
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
