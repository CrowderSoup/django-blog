from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0034_requesterrorlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="developer_tools_enabled",
            field=models.BooleanField(default=False, verbose_name="Developer tools enabled"),
        ),
    ]
