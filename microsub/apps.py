from django.apps import AppConfig


class MicrosubConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "microsub"

    def ready(self):
        import microsub.signals  # noqa
