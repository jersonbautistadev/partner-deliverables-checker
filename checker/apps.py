from django.apps import AppConfig


class CheckerConfig(AppConfig):
    name = "checker"

    def ready(self):
        from checker import checks  # noqa: F401
