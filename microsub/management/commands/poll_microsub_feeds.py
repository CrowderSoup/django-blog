import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from microsub.models import Subscription
from microsub.feed_parser import fetch_and_parse_feed
from microsub.views import _store_entries, _subscribe_to_websub

logger = logging.getLogger(__name__)

REFETCH_INTERVAL_SECONDS = 900  # 15 minutes


class Command(BaseCommand):
    help = "Poll active Microsub feed subscriptions for new entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--channel",
            dest="channel",
            default=None,
            help="Only poll subscriptions in this channel uid.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Re-poll even recently-fetched feeds.",
        )

    def handle(self, *args, **options):
        channel_uid = options["channel"]
        force = options["force"]

        qs = Subscription.objects.filter(is_active=True).select_related("channel")
        if channel_uid:
            qs = qs.filter(channel__uid=channel_uid)

        now = timezone.now()
        total_new = 0
        total_subs = 0

        for sub in qs:
            if not force and sub.last_fetched_at:
                elapsed = (now - sub.last_fetched_at).total_seconds()
                if elapsed < REFETCH_INTERVAL_SECONDS:
                    continue

            self.stdout.write(f"Polling {sub.url} ...")
            try:
                entries, hub_url, feed_meta = fetch_and_parse_feed(sub.url)
            except Exception as exc:
                sub.fetch_error = str(exc)
                sub.last_fetched_at = now
                sub.save(update_fields=["fetch_error", "last_fetched_at"])
                self.stdout.write(self.style.WARNING(f"  Error: {exc}"))
                continue

            # Update feed name/photo and WebSub hub if newly discovered
            meta_fields = []
            if feed_meta.get("name") and (not sub.name or sub.name == sub.url):
                sub.name = feed_meta["name"]
                meta_fields.append("name")
            if feed_meta.get("photo") and not sub.photo:
                sub.photo = feed_meta["photo"]
                meta_fields.append("photo")
            if hub_url and not sub.websub_hub:
                sub.websub_hub = hub_url
                meta_fields.append("websub_hub")
            if meta_fields:
                sub.save(update_fields=meta_fields)

            # Subscribe to WebSub hub if we haven't yet
            if sub.websub_hub and not sub.websub_subscribed_at:
                # Build a fake request-like object for URL building
                # We skip websub subscribe during management command since we have no request
                pass

            new_count = _store_entries(sub.channel, sub, entries)
            sub.fetch_error = ""
            sub.last_fetched_at = now
            sub.save(update_fields=["fetch_error", "last_fetched_at"])
            total_new += new_count
            total_subs += 1
            self.stdout.write(f"  {new_count} new entries")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Polled {total_subs} subscriptions, {total_new} total new entries."
            )
        )
