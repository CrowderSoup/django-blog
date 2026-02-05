from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IndieAuthClient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_id", models.URLField(max_length=2000, unique=True)),
                ("name", models.CharField(blank=True, default="", max_length=255)),
                ("logo_url", models.URLField(blank=True, default="", max_length=2000)),
                ("redirect_uris", models.JSONField(blank=True, default=list)),
                ("last_fetched_at", models.DateTimeField(blank=True, null=True)),
                ("fetch_error", models.TextField(blank=True, default="")),
            ],
        ),
        migrations.CreateModel(
            name="IndieAuthAccessToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("client_id", models.URLField(max_length=2000)),
                ("me", models.URLField(max_length=2000)),
                ("scope", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="IndieAuthAuthorizationCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code_hash", models.CharField(max_length=64, unique=True)),
                ("code_challenge", models.CharField(max_length=255)),
                ("code_challenge_method", models.CharField(default="S256", max_length=32)),
                ("client_id", models.URLField(max_length=2000)),
                ("redirect_uri", models.URLField(max_length=2000)),
                ("me", models.URLField(max_length=2000)),
                ("scope", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="IndieAuthConsent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_id", models.URLField(max_length=2000)),
                ("scope", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("user", "client_id", "scope")},
            },
        ),
    ]
