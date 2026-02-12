from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0005_visit_user_agent_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="visit",
            name="is_suspected_bot",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="visit",
            name="suspected_bot_pattern_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="UserAgentBotRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pattern", models.TextField(blank=True, default="")),
                ("enabled", models.BooleanField(default=False)),
                ("version", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "User agent bot rule",
                "verbose_name_plural": "User agent bot rule",
            },
        ),
        migrations.CreateModel(
            name="UserAgentFalsePositive",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_agent", models.TextField(unique=True)),
                ("note", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("user_agent", "id"),
            },
        ),
    ]
