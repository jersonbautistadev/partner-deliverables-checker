from django.core.management.base import BaseCommand, CommandError
from checker.backup import restore_bundle


class Command(BaseCommand):
    help = "Restore an encrypted bundle into a fresh offline database and storage prefix."

    def add_arguments(self, parser):
        parser.add_argument("bundle")
        parser.add_argument("--confirm-empty", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm_empty"]:
            raise CommandError("Use a fresh isolated migrated database and pass --confirm-empty.")
        try:
            restore_bundle(options["bundle"])
        except Exception as exc:
            raise CommandError(
                f"Restore failed ({type(exc).__name__}). Keep the target offline and retry into a fresh target."
            ) from exc
        self.stdout.write(
            "Database and original files restored. Verify both roles and downloads before admitting traffic."
        )
