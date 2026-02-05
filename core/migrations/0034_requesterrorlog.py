from django.db import migrations, models


BATCH_SIZE = 500


def _copy_logs(source_value, source_queryset, target_model):
    batch = []
    for log in source_queryset.iterator():
        batch.append(
            target_model(
                source=source_value,
                method=log.method,
                path=log.path,
                status_code=log.status_code,
                error=log.error,
                request_headers=log.request_headers,
                request_query=log.request_query,
                request_body=log.request_body,
                response_body=log.response_body,
                remote_addr=log.remote_addr,
                user_agent=log.user_agent,
                content_type=log.content_type,
                created_at=log.created_at,
            )
        )
        if len(batch) >= BATCH_SIZE:
            target_model.objects.bulk_create(batch)
            batch = []
    if batch:
        target_model.objects.bulk_create(batch)


def forwards(apps, schema_editor):
    RequestErrorLog = apps.get_model("core", "RequestErrorLog")
    MicropubRequestLog = apps.get_model("micropub", "MicropubRequestLog")
    IndieAuthRequestLog = apps.get_model("indieauth", "IndieAuthRequestLog")

    _copy_logs("micropub", MicropubRequestLog.objects.all(), RequestErrorLog)
    _copy_logs("indieauth", IndieAuthRequestLog.objects.all(), RequestErrorLog)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_siteconfiguration_comments_enabled"),
        ("micropub", "0003_micropubrequestlog"),
        ("indieauth", "0002_indieauthrequestlog"),
    ]

    operations = [
        migrations.CreateModel(
            name="RequestErrorLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source",
                    models.CharField(
                        choices=[("micropub", "Micropub"), ("indieauth", "IndieAuth")],
                        max_length=32,
                    ),
                ),
                ("method", models.CharField(max_length=10)),
                ("path", models.CharField(max_length=255)),
                ("status_code", models.PositiveSmallIntegerField()),
                ("error", models.TextField(blank=True)),
                ("request_headers", models.JSONField(default=dict)),
                ("request_query", models.JSONField(default=dict)),
                ("request_body", models.TextField(blank=True)),
                ("response_body", models.TextField(blank=True)),
                ("remote_addr", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("content_type", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.RunPython(forwards, backwards),
    ]
