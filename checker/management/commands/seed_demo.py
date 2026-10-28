import io
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image

from checker.models import Package, Partner, Requirement
from checker.services import audit, ensure_report, record_revision, store_asset


class Command(BaseCommand):
    help = "Seed fictional examples in an empty LOCAL development database."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo seeding is disabled when DJANGO_DEBUG=0.")
        if Partner.objects.exists() or get_user_model().objects.exists():
            raise CommandError("Seed only an empty database; existing data was left unchanged.")
        with transaction.atomic():
            coord = get_user_model().objects.create_user("demo_coordinator", password="Demo-Only-2026!")
            alex = get_user_model().objects.create_user("demo_alex", password="Demo-Only-2026!")
            sam = get_user_model().objects.create_user("demo_sam", password="Demo-Only-2026!")
            for user, name in [(coord, "Coordinator"), (alex, "Contributor"), (sam, "Contributor")]:
                group, _ = Group.objects.get_or_create(name=name)
                user.groups.add(group)
                audit(user, "account.provisioned", f"user:{user.id}", role=name, fictional=True)
            campus = Partner.objects.create(name="Campus Current", notes="Fictional student news partner. Sample instructions only.")
            signal = Partner.objects.create(name="Signal Student Network", notes="Fictional campus media partner.")
            dev = Partner.objects.create(name="DevLoop Journal", notes="Fictional technology publication.")
            now = timezone.now().replace(second=0, microsecond=0)

            def requirement(partner, title, kind, slot, config, days, stage="pre", ambiguous=False):
                req = Requirement.objects.create(partner=partner, title=title, kind=kind, slot=slot,
                                                  config=config, stage=stage, ambiguous=ambiguous,
                                                  approved=not ambiguous, deadline=now + timedelta(days=days),
                                                  source="FICTIONAL · Demo partnership brief v1 · Publishing instructions")
                record_revision(req, coord, "Fictional source reviewed for this demonstration." if not ambiguous else "Exact deliverable is unclear; clarification required.")
                return req

            requirement(campus, "Press release file", "required_file", "article", {}, 2)
            requirement(campus, "Press release: 300–500 words", "word_count", "article", {"min": 300, "max": 500}, 2)
            requirement(campus, "Mention the event name", "required_phrase", "article", {"phrase": "CS Expo 2026"}, 2)
            requirement(campus, "Square promotional image", "dimensions", "image", {"width": 1080, "height": 1080}, 2)
            requirement(campus, "Partner logo placement", "manual", "image", {"instructions": "Inspect the partner logo in the lower-right corner and confirm legibility."}, 2)
            requirement(campus, "Social caption file", "required_file", "caption", {}, 2)
            requirement(signal, "Caption: at most 50 words", "word_count", "caption", {"max": 50}, 4)
            requirement(signal, "Include campaign hashtag", "required_phrase", "caption", {"phrase": "#CSExpo2026"}, 4)
            requirement(signal, "Landscape cover image", "dimensions", "image", {"width": 1200, "height": 630}, 4)
            requirement(dev, "Article: 200–400 words", "word_count", "article", {"min": 200, "max": 400}, 7)
            requirement(dev, "Event name in article", "required_phrase", "article", {"phrase": "CS Expo 2026"}, 7)
            requirement(campus, "Post-event reach report format", "manual", "article", {}, 14, stage="post", ambiguous=True)
            p1 = Package.objects.create(partner=campus, stage="pre", title="Launch press kit", owner=alex)
            p2 = Package.objects.create(partner=signal, stage="pre", title="Social announcement", owner=alex)
            p3 = Package.objects.create(partner=dev, stage="pre", title="Developer spotlight", owner=sam)
            for p in [p1, p2, p3]:
                audit(coord, "package.created", f"package:{p.id}", owner_id=p.owner_id, fictional=True)
            article = "CS Expo 2026\n" + " ".join(["Students build thoughtful software and share practical engineering lessons."] * 37)
            spotlight = "CS Expo 2026\n" + " ".join(["Student developers demonstrate useful projects and explain their engineering decisions."] * 23)
            store_asset(p1, alex, "article", SimpleUploadedFile("press-release.txt", article.encode()))
            buffer = io.BytesIO()
            Image.new("RGB", (1000, 1000), "#d9ebe2").save(buffer, "PNG")
            store_asset(p1, alex, "image", SimpleUploadedFile("poster-wrong-size.png", buffer.getvalue()))
            store_asset(p2, alex, "caption", SimpleUploadedFile("caption.txt", b"Discover student-built software at CS Expo 2026. Join the conversation! #CSExpo2026"))
            store_asset(p3, sam, "article", SimpleUploadedFile("spotlight.txt", spotlight.encode()))
            for p in [p1, p2, p3]:
                ensure_report(p)
        self.stdout.write(self.style.SUCCESS("Fictional demo created. Users: demo_coordinator, demo_alex, demo_sam. Password: Demo-Only-2026!"))
