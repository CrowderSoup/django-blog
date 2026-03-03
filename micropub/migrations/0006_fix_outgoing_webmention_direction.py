from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations


def fix_is_incoming_and_deduplicate(apps, schema_editor):
    Webmention = apps.get_model("micropub", "Webmention")

    # Step 1: deduplicate (source, target) pairs — keep most-recently updated row.
    from django.db.models import Count

    duplicates = (
        Webmention.objects.values("source", "target")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )
    for dup in duplicates:
        rows = list(
            Webmention.objects.filter(source=dup["source"], target=dup["target"]).order_by("-updated_at")
        )
        # Keep the first (most-recently updated), delete the rest.
        for row in rows[1:]:
            row.delete()

    # Step 2: mark old outgoing rows correctly.
    allowed_hosts = {h for h in getattr(settings, "ALLOWED_HOSTS", []) if h != "*"}

    for wm in Webmention.objects.filter(is_incoming=True):
        host = urlparse(wm.source).hostname or ""
        if host in allowed_hosts:
            wm.is_incoming = False
            wm.save(update_fields=["is_incoming"])


class Migration(migrations.Migration):

    dependencies = [
        ("micropub", "0005_webmention_is_incoming_and_bookmark"),
    ]

    operations = [
        migrations.RunPython(fix_is_incoming_and_deduplicate, migrations.RunPython.noop),
    ]
