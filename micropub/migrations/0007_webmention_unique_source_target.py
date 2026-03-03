# Generated migration
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("micropub", "0006_fix_outgoing_webmention_direction"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="webmention",
            constraint=models.UniqueConstraint(
                fields=["source", "target"], name="unique_webmention_source_target"
            ),
        ),
    ]
