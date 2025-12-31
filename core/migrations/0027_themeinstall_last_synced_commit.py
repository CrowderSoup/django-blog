from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_alter_hcardphoto_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="themeinstall",
            name="last_synced_commit",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
