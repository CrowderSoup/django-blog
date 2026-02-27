import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="micropub.Webmention")
def webmention_to_notifications(sender, instance, **kwargs):
    if instance.status != "accepted":
        return

    from .models import Channel, Entry

    channel = Channel.objects.filter(uid="notifications").first()
    if not channel:
        return

    jf2 = {
        "type": "entry",
        "url": instance.source,
        "published": instance.created_at.isoformat(),
        "content": {"text": ""},
        "author": {"type": "card", "url": instance.source},
    }

    if instance.mention_type == "like":
        jf2["like-of"] = instance.target
    elif instance.mention_type == "reply":
        jf2["in-reply-to"] = instance.target
    elif instance.mention_type == "repost":
        jf2["repost-of"] = instance.target

    try:
        Entry.objects.get_or_create(
            channel=channel,
            uid=instance.source,
            defaults={
                "data": jf2,
                "published": instance.created_at,
                "subscription": None,
            },
        )
    except Exception:
        logger.exception("Failed to create notifications entry for webmention %s", instance.pk)
