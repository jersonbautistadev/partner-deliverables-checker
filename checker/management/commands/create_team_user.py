import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from checker.services import audit


class Command(BaseCommand):
    help = "Create a team user. Password is prompted, never passed on the command line."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--role", choices=["Coordinator", "Contributor"], required=True)

    def handle(self, *args, **options):
        user = get_user_model()(username=options["username"])
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm password: "):
            raise CommandError("Passwords do not match.")
        try:
            user.full_clean(exclude=["password"])
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        with transaction.atomic():
            user.set_password(password)
            user.save()
            group, _ = Group.objects.get_or_create(name=options["role"])
            user.groups.add(group)
            audit(user, "account.provisioned", f"user:{user.id}", role=options["role"], via="operator CLI")
        self.stdout.write(self.style.SUCCESS(f"Created {user.username} ({options['role']})."))
