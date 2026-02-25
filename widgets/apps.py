from django.apps import AppConfig


class WidgetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "widgets"

    def ready(self):
        from core.plugins import registry
        from .plugin import WidgetsPlugin
        registry.register(WidgetsPlugin())
