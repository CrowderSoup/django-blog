from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Channel",
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
                ("uid", models.CharField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="Subscription",
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
                (
                    "channel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to="microsub.channel",
                    ),
                ),
                ("url", models.URLField(max_length=2000)),
                ("name", models.CharField(blank=True, max_length=255)),
                ("photo", models.URLField(blank=True, max_length=2000)),
                ("is_active", models.BooleanField(default=True)),
                ("last_fetched_at", models.DateTimeField(blank=True, null=True)),
                ("fetch_error", models.TextField(blank=True)),
                ("websub_hub", models.URLField(blank=True, max_length=2000)),
                ("websub_secret", models.CharField(blank=True, max_length=255)),
                ("websub_subscribed_at", models.DateTimeField(blank=True, null=True)),
                ("websub_expires_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "unique_together": {("channel", "url")},
            },
        ),
        migrations.CreateModel(
            name="Entry",
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
                (
                    "channel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="microsub.channel",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="entries",
                        to="microsub.subscription",
                    ),
                ),
                ("uid", models.TextField()),
                ("data", models.JSONField()),
                ("published", models.DateTimeField()),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("is_removed", models.BooleanField(db_index=True, default=False)),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-published"],
                "unique_together": {("channel", "uid")},
            },
        ),
        migrations.CreateModel(
            name="MutedUser",
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
                (
                    "channel",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="muted_users",
                        to="microsub.channel",
                    ),
                ),
                ("url", models.URLField(max_length=2000)),
            ],
            options={
                "unique_together": {("channel", "url")},
            },
        ),
        migrations.CreateModel(
            name="BlockedUser",
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
                (
                    "channel",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="blocked_users",
                        to="microsub.channel",
                    ),
                ),
                ("url", models.URLField(max_length=2000)),
            ],
            options={
                "unique_together": {("channel", "url")},
            },
        ),
    ]
