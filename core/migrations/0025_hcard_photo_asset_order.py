from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0001_initial"),
        ("core", "0024_themeinstall"),
    ]

    operations = [
        migrations.AddField(
            model_name="hcardphoto",
            name="asset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="hcard_photos",
                to="files.file",
            ),
        ),
        migrations.AddField(
            model_name="hcardphoto",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
