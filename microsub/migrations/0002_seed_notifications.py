from django.db import migrations


def seed_notifications_channel(apps, schema_editor):
    Channel = apps.get_model("microsub", "Channel")
    Channel.objects.get_or_create(
        uid="notifications",
        defaults={"name": "Notifications", "order": 0},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("microsub", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_notifications_channel, migrations.RunPython.noop),
    ]
