from django.db import migrations


def seed_widgets_plugin(apps, schema_editor):
    PluginInstall = apps.get_model("core", "PluginInstall")
    PluginInstall.objects.get_or_create(
        name="widgets",
        defaults={
            "django_app": "widgets",
            "label": "Widgets",
            "source_type": "builtin",
            "version": "1.0.0",
        },
    )


def reverse_seed(apps, schema_editor):
    PluginInstall = apps.get_model("core", "PluginInstall")
    PluginInstall.objects.filter(name="widgets", source_type="builtin").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_plugininstall"),
    ]

    operations = [
        migrations.RunPython(seed_widgets_plugin, reverse_code=reverse_seed),
    ]
