from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from checker.accounts import queue_verification
from checker.models import Account


class Command(BaseCommand):
    help = "Assign a verified-delivery destination to a legacy account; always requires email confirmation."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("email")

    def handle(self, *args, **options):
        email = options["email"].strip().casefold()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("Invalid email.") from exc
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(username=options["username"])
            account, _ = Account.objects.get_or_create(user=user)
            account.email, account.verified_at = email, None
            account.full_clean()
            account.save()
            user.email = email
            user.save(update_fields=["email"])
            queue_verification(account)
        self.stdout.write("Verification queued. Existing workspace membership is preserved.")
