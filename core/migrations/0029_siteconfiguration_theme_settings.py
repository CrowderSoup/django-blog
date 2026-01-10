from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_siteconfiguration_favicon"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="theme_settings",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
