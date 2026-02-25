from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0038_siteconfiguration_default_feed_kinds"),
    ]

    operations = [
        migrations.CreateModel(
            name="PluginInstall",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.SlugField(max_length=255, unique=True)),
                ("django_app", models.CharField(max_length=255)),
                ("label", models.CharField(blank=True, default="", max_length=255)),
                (
                    "source_type",
                    models.CharField(
                        choices=[("builtin", "Built-in"), ("git", "Git")],
                        max_length=16,
                    ),
                ),
                (
                    "source_url",
                    models.URLField(blank=True, default="", max_length=2000),
                ),
                (
                    "source_ref",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("version", models.CharField(blank=True, default="", max_length=255)),
                ("installed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "last_synced_commit",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "last_synced_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "last_sync_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("pending", "Pending"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                        ],
                        default="",
                        max_length=16,
                    ),
                ),
                (
                    "last_sync_error",
                    models.CharField(blank=True, default="", max_length=500),
                ),
            ],
            options={
                "ordering": ("name",),
            },
        ),
    ]
