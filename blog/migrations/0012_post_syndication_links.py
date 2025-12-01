from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0011_post_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='bluesky_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='post',
            name='mastodon_url',
            field=models.URLField(blank=True),
        ),
    ]
