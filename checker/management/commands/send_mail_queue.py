import time

from django.core.management.base import BaseCommand
from checker.mail import deliver_batch


class Command(BaseCommand):
    help = "Deliver queued account email. Use --once for an external scheduler."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            self.stdout.write(f"Delivered {deliver_batch()} queued messages.")
            if options["once"]:
                break
            time.sleep(5)
