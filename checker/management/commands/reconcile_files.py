from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from checker.models import Asset


class Command(BaseCommand):
    help = "Find unreferenced files older than one day. Dry-run unless --delete is explicit."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true")

    def handle(self, *args, **options):
        referenced = set(Asset.objects.values_list("file", flat=True))
        cutoff = timezone.now() - timedelta(days=1)
        candidates = 0

        def walk(prefix=""):
            directories, files = default_storage.listdir(prefix)
            for name in files:
                yield f"{prefix}/{name}".lstrip("/")
            for directory in directories:
                path = f"{prefix}/{directory}".lstrip("/")
                if isinstance(default_storage, FileSystemStorage):
                    root = Path(settings.MEDIA_ROOT).resolve()
                    target = Path(default_storage.path(path))
                    if target.is_symlink() or not target.resolve().is_relative_to(root):
                        raise CommandError("Unsafe storage directory encountered.")
                yield from walk(path)

        for name in walk():
            if name not in referenced and default_storage.get_modified_time(name) < cutoff:
                if isinstance(default_storage, FileSystemStorage):
                    target = Path(default_storage.path(name))
                    if target.is_symlink() or not target.resolve().is_relative_to(
                        Path(settings.MEDIA_ROOT).resolve()
                    ):
                        raise CommandError("Unsafe stored path encountered.")
                candidates += 1
                if options["delete"]:
                    default_storage.delete(name)
        self.stdout.write(
            f"{candidates} old unreferenced file(s); deletion enabled: {options['delete']}."
        )
