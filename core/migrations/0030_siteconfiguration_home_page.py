from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0029_siteconfiguration_theme_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="home_page",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional page to display on the site homepage.",
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="site_home_pages",
                to="core.page",
            ),
        ),
    ]
