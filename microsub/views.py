import hashlib
import hmac
import json
import logging
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from urllib.parse import urljoin as _urljoin

from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.urls import reverse

from .models import Channel, Subscription, Entry, MutedUser, BlockedUser
from .feed_parser import fetch_and_parse_feed, discover_websub_hub

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


def _require_scope(scopes: list[str], required: str) -> bool:
    return required in scopes


def _channel_json(channel: Channel) -> dict:
    unread = channel.entries.filter(is_read=False, is_removed=False).count()
    return {
        "uid": channel.uid,
        "name": channel.name,
        "unread": unread,
    }


def _entry_json(entry: Entry) -> dict:
    data = entry.data.copy() if isinstance(entry.data, dict) else {}
    data["_id"] = str(entry.pk)
    data["_is_read"] = entry.is_read
    # Always use the DB datetime for published so it's a stable ISO 8601 string.
    data["published"] = entry.published.isoformat()
    if entry.subscription:
        data["_source"] = {
            "url": entry.subscription.url,
            "name": entry.subscription.name or entry.subscription.url,
            "photo": entry.subscription.photo,
        }
    return data


def _subscribe_to_websub(subscription: Subscription, request) -> None:
    """Send a WebSub subscribe request to the hub."""
    if not subscription.websub_hub:
        return
    callback_url = request.build_absolute_uri(
        reverse("microsub-websub-callback", kwargs={"subscription_id": subscription.pk})
    )
    secret = secrets.token_hex(32)
    body = urlencode(
        {
            "hub.mode": "subscribe",
            "hub.topic": subscription.url,
            "hub.callback": callback_url,
            "hub.secret": secret,
        }
    ).encode()
    try:
        req = Request(
            subscription.websub_hub,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:
            status = resp.status
        if status in (200, 202):
            subscription.websub_secret = secret
            subscription.websub_subscribed_at = timezone.now()
            subscription.save(update_fields=["websub_secret", "websub_subscribed_at"])
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        logger.warning("WebSub subscribe failed for %s: %s", subscription.url, exc)


def _subscribe_to_websub_with_base_url(subscription: Subscription, base_url: str) -> None:
    """Send a WebSub subscribe request using an explicit base URL (no request object needed)."""
    if not subscription.websub_hub:
        return
    callback_path = reverse(
        "microsub-websub-callback",
        kwargs={"subscription_id": subscription.pk}
    )
    callback_url = base_url.rstrip("/") + callback_path
    secret = secrets.token_hex(32)
    body = urlencode({
        "hub.mode": "subscribe",
        "hub.topic": subscription.url,
        "hub.callback": callback_url,
        "hub.secret": secret,
    }).encode()
    try:
        req = Request(
            subscription.websub_hub,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:
            status = resp.status
        if status in (200, 202):
            subscription.websub_secret = secret
            subscription.websub_subscribed_at = timezone.now()
            subscription.save(update_fields=["websub_secret", "websub_subscribed_at"])
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        logger.warning("WebSub subscribe failed for %s: %s", subscription.url, exc)


def _doctor_entries(channel: Channel, entries: list[dict]) -> int:
    """Re-process already-stored entries with fresh parsed data. Returns update count."""
    from dateutil.parser import parse as parse_dt
    from django.utils import timezone as tz

    updated = 0
    for entry_data in entries:
        uid = entry_data.get("_uid") or entry_data.get("url") or entry_data.get("uid")
        if not uid:
            continue

        published_str = entry_data.get("published")
        published = None
        if published_str:
            try:
                published = parse_dt(published_str)
                if published.tzinfo is None:
                    published = tz.make_aware(published)
            except Exception:
                pass

        author_url = ""
        author = entry_data.get("author", {})
        if isinstance(author, dict):
            author_url = author.get("url", "") or ""

        update_fields = {"data": entry_data, "author_url": author_url}
        if published:
            update_fields["published"] = published

        count = Entry.objects.filter(channel=channel, uid=str(uid)).update(**update_fields)
        updated += count
    return updated


def _store_entries(channel: Channel, subscription: Subscription | None, entries: list[dict]) -> int:
    """Store parsed JF2 entries into the DB. Returns count of new entries."""
    from dateutil.parser import parse as parse_dt
    from django.utils import timezone as tz

    new_count = 0
    for entry_data in entries:
        uid = entry_data.get("_uid") or entry_data.get("url") or entry_data.get("uid")
        if not uid:
            continue
        published_str = entry_data.get("published")
        published = tz.now()
        if published_str:
            try:
                published = parse_dt(published_str)
                if published.tzinfo is None:
                    published = tz.make_aware(published)
            except Exception:
                pass
        author_url = ""
        author = entry_data.get("author", {})
        if isinstance(author, dict):
            author_url = author.get("url", "") or ""

        _, created = Entry.objects.get_or_create(
            channel=channel,
            uid=str(uid),
            defaults={
                "subscription": subscription,
                "data": entry_data,
                "published": published,
                "author_url": author_url,
            },
        )
        if created:
            new_count += 1
    return new_count


@method_decorator(csrf_exempt, name="dispatch")
class MicrosubView(View):
    def dispatch(self, request, *args, **kwargs):
        from micropub.views import _authorized

        authorized, scopes = _authorized(request)
        if not authorized:
            return JsonResponse({"error": "unauthorized"}, status=401)
        request.microsub_scopes = scopes
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        action = request.GET.get("action", "")
        if action == "channels":
            return self._get_channels(request)
        elif action == "follow":
            return self._get_follow(request)
        elif action == "timeline":
            return self._get_timeline(request)
        elif action == "mute":
            return self._get_mute(request)
        elif action == "block":
            return self._get_block(request)
        elif action == "search":
            return self._get_search(request)
        elif action == "preview":
            return self._get_preview(request)
        return JsonResponse({"error": "invalid_request", "error_description": "Unknown action"}, status=400)

    def post(self, request):
        action = request.POST.get("action", "")
        if action == "channels":
            return self._post_channels(request)
        elif action == "follow":
            return self._post_follow(request)
        elif action == "unfollow":
            return self._post_unfollow(request)
        elif action == "timeline":
            return self._post_timeline(request)
        elif action == "mute":
            return self._post_mute(request)
        elif action == "unmute":
            return self._post_unmute(request)
        elif action == "block":
            return self._post_block(request)
        elif action == "unblock":
            return self._post_unblock(request)
        return JsonResponse({"error": "invalid_request", "error_description": "Unknown action"}, status=400)

    # -------------------------------------------------------------------------
    # GET handlers
    # -------------------------------------------------------------------------

    def _get_channels(self, request):
        if not _require_scope(request.microsub_scopes, "read"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        channels = Channel.objects.all()
        return JsonResponse({"channels": [_channel_json(c) for c in channels]})

    def _get_follow(self, request):
        if not _require_scope(request.microsub_scopes, "read"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        channel_uid = request.GET.get("channel", "")
        channel = Channel.objects.filter(uid=channel_uid).first()
        if not channel:
            return JsonResponse({"error": "invalid_request", "error_description": "Channel not found"}, status=400)
        subs = channel.subscriptions.filter(is_active=True)
        return JsonResponse(
            {
                "items": [
                    {
                        "type": "feed",
                        "url": s.url,
                        "name": s.name,
                        "photo": s.photo,
                    }
                    for s in subs
                ]
            }
        )

    def _get_timeline(self, request):
        if not _require_scope(request.microsub_scopes, "read"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        channel_uid = request.GET.get("channel", "")
        channel = Channel.objects.filter(uid=channel_uid).first()
        if not channel:
            return JsonResponse({"error": "invalid_request", "error_description": "Channel not found"}, status=400)

        qs = channel.entries.filter(is_removed=False)

        filter_param = request.GET.get("filter", "")
        if filter_param == "unread":
            qs = qs.filter(is_read=False)

        # Cursor-based paging using entry PKs as stable cursors.
        # We look up the cursor entry to get its (published, id) for a compound filter
        # that handles entries sharing the same published timestamp correctly.
        before_cursor = request.GET.get("before")
        after_cursor = request.GET.get("after")

        if before_cursor:
            try:
                cursor_id = int(before_cursor)
                cursor = channel.entries.filter(pk=cursor_id).values("published", "id").first()
                if cursor:
                    qs = qs.filter(
                        Q(published__lt=cursor["published"])
                        | Q(published=cursor["published"], id__lt=cursor_id)
                    )
            except (ValueError, TypeError):
                pass

        if after_cursor:
            try:
                cursor_id = int(after_cursor)
                cursor = channel.entries.filter(pk=cursor_id).values("published", "id").first()
                if cursor:
                    qs = qs.filter(
                        Q(published__gt=cursor["published"])
                        | Q(published=cursor["published"], id__gt=cursor_id)
                    )
            except (ValueError, TypeError):
                pass

        # Filter by source subscription URL if provided
        source_url = request.GET.get("source", "").strip()
        if source_url:
            qs = qs.filter(subscription__url=source_url)

        # Apply mute/block filters at DB level
        muted_urls = set(MutedUser.objects.filter(
            Q(channel__isnull=True) | Q(channel=channel)
        ).values_list("url", flat=True))
        blocked_urls = set(BlockedUser.objects.filter(
            Q(channel__isnull=True) | Q(channel=channel)
        ).values_list("url", flat=True))
        excluded = muted_urls | blocked_urls
        if excluded:
            qs = qs.exclude(author_url__in=excluded)

        qs = qs.select_related("subscription").order_by("-published", "-id")[:PAGE_SIZE + 1]
        entries_list = list(qs)
        has_more = len(entries_list) > PAGE_SIZE
        entries_list = entries_list[:PAGE_SIZE]

        paging = {}
        if entries_list:
            paging["after"] = str(entries_list[0].pk)
        if has_more:
            paging["before"] = str(entries_list[-1].pk)

        return JsonResponse(
            {
                "items": [_entry_json(e) for e in entries_list],
                "paging": paging,
            }
        )

    def _get_mute(self, request):
        if not _require_scope(request.microsub_scopes, "mute"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        channel_uid = request.GET.get("channel")
        if channel_uid:
            channel = Channel.objects.filter(uid=channel_uid).first()
            if channel is None:
                return JsonResponse({"error": "invalid_request"}, status=400)
            qs = MutedUser.objects.filter(channel=channel)
        else:
            qs = MutedUser.objects.filter(channel__isnull=True)
        return JsonResponse({"items": [{"url": m.url} for m in qs]})

    def _get_block(self, request):
        if not _require_scope(request.microsub_scopes, "block"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        channel_uid = request.GET.get("channel")
        if channel_uid:
            channel = Channel.objects.filter(uid=channel_uid).first()
            if channel is None:
                return JsonResponse({"error": "invalid_request"}, status=400)
            qs = BlockedUser.objects.filter(channel=channel)
        else:
            qs = BlockedUser.objects.filter(channel__isnull=True)
        return JsonResponse({"items": [{"url": b.url} for b in qs]})

    def _get_search(self, request):
        query = request.GET.get("query", "").strip()
        if not query:
            return JsonResponse({"results": []})
        # Attempt to fetch the URL and discover feed links
        results = []
        try:
            from urllib.request import Request as UReq, urlopen as uopen
            from html.parser import HTMLParser

            class _FeedDiscoveryParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.feeds = []

                def handle_starttag(self, tag, attrs):
                    if tag.lower() != "link":
                        return
                    attr_map = {k.lower(): v for k, v in attrs}
                    rels = {r.strip() for r in attr_map.get("rel", "").split()}
                    if "alternate" in rels:
                        ct = attr_map.get("type", "")
                        href = attr_map.get("href", "")
                        title = attr_map.get("title", "")
                        if href and any(f in ct for f in ("rss", "atom", "xml", "json")):
                            self.feeds.append({"url": href, "name": title})

            url = query if query.startswith("http") else f"https://{query}"
            req = UReq(url, headers={"User-Agent": "Webstead Microsub/1.0"})
            with uopen(req, timeout=10) as resp:
                ct = resp.headers.get("Content-Type", "")
                body = resp.read(100_000).decode("utf-8", errors="replace")
            if "html" in ct:
                parser = _FeedDiscoveryParser()
                parser.feed(body)
                for feed in parser.feeds:
                    results.append(
                        {
                            "type": "feed",
                            "url": _urljoin(url, feed["url"]),
                            "name": feed["name"],
                        }
                    )
            else:
                results.append({"type": "feed", "url": url, "name": ""})
        except Exception as exc:
            logger.debug("Feed search failed for %s: %s", query, exc)

        return JsonResponse({"results": results})

    def _get_preview(self, request):
        url = request.GET.get("url", "").strip()
        if not url:
            return JsonResponse({"error": "invalid_request"}, status=400)
        try:
            entries, _, _ = fetch_and_parse_feed(url)
        except Exception as exc:
            return JsonResponse(
                {"error": "fetch_error", "error_description": str(exc)}, status=502
            )
        return JsonResponse({"items": entries[:20]})

    # -------------------------------------------------------------------------
    # POST handlers
    # -------------------------------------------------------------------------

    def _post_channels(self, request):
        if not _require_scope(request.microsub_scopes, "channels"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)

        method = request.POST.get("method", "")
        channel_uid = request.POST.get("channel", "")
        name = request.POST.get("name", "").strip()

        # Check for reorder first (spec sends channels[] with no method=order)
        channels_order = request.POST.getlist("channels[]") or request.POST.getlist("channels")
        if channels_order:
            for i, uid in enumerate(channels_order):
                Channel.objects.filter(uid=uid).update(order=i)
            return JsonResponse({})

        if method == "delete":
            channel = Channel.objects.filter(uid=channel_uid).first()
            if not channel:
                return JsonResponse({"error": "invalid_request"}, status=400)
            if channel.uid == "notifications":
                return JsonResponse(
                    {"error": "forbidden", "error_description": "Cannot delete notifications channel"},
                    status=403,
                )
            channel.delete()
            return JsonResponse({})

        if channel_uid and name:
            # Rename
            channel = Channel.objects.filter(uid=channel_uid).first()
            if not channel:
                return JsonResponse({"error": "invalid_request"}, status=400)
            channel.name = name
            channel.save(update_fields=["name"])
            return JsonResponse(_channel_json(channel))

        if name:
            # Create
            base_slug = slugify(name) or "channel"
            uid = base_slug
            suffix = 1
            while Channel.objects.filter(uid=uid).exists():
                uid = f"{base_slug}-{suffix}"
                suffix += 1
            max_order = Channel.objects.order_by("-order").values_list("order", flat=True).first() or 0
            channel = Channel.objects.create(uid=uid, name=name, order=max_order + 1)
            return JsonResponse(_channel_json(channel), status=200)

        return JsonResponse({"error": "invalid_request"}, status=400)

    def _post_follow(self, request):
        if not _require_scope(request.microsub_scopes, "follow"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        channel_uid = request.POST.get("channel", "")
        url = request.POST.get("url", "").strip()
        if not channel_uid or not url:
            return JsonResponse({"error": "invalid_request"}, status=400)
        channel = Channel.objects.filter(uid=channel_uid).first()
        if not channel:
            return JsonResponse({"error": "invalid_request", "error_description": "Channel not found"}, status=400)

        sub, created = Subscription.objects.get_or_create(
            channel=channel, url=url, defaults={"is_active": True}
        )
        if not created:
            sub.is_active = True
            sub.save(update_fields=["is_active"])

        # Try to discover feed name, photo, and WebSub hub
        if created:
            try:
                entries, hub_url, feed_meta = fetch_and_parse_feed(url)
                update_fields = []
                if feed_meta.get("name") and (not sub.name or sub.name == sub.url):
                    sub.name = feed_meta["name"]
                    update_fields.append("name")
                if feed_meta.get("photo") and not sub.photo:
                    sub.photo = feed_meta["photo"]
                    update_fields.append("photo")
                if hub_url and not sub.websub_hub:
                    sub.websub_hub = hub_url
                    update_fields.append("websub_hub")
                if update_fields:
                    sub.save(update_fields=update_fields)
                if entries:
                    _store_entries(sub.channel, sub, entries)
                if hub_url:
                    _subscribe_to_websub(sub, request)
            except Exception as exc:
                logger.debug("Feed discovery failed for %s: %s", url, exc)

        return JsonResponse(
            {
                "type": "feed",
                "url": sub.url,
                "name": sub.name,
                "photo": sub.photo,
            }
        )

    def _post_unfollow(self, request):
        if not _require_scope(request.microsub_scopes, "follow"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        channel_uid = request.POST.get("channel", "")
        url = request.POST.get("url", "").strip()
        if not channel_uid or not url:
            return JsonResponse({"error": "invalid_request"}, status=400)
        channel = Channel.objects.filter(uid=channel_uid).first()
        if not channel:
            return JsonResponse({"error": "invalid_request"}, status=400)
        Subscription.objects.filter(channel=channel, url=url).update(is_active=False)
        return JsonResponse({})

    def _post_timeline(self, request):
        if not _require_scope(request.microsub_scopes, "read"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        method = request.POST.get("method", "")
        channel_uid = request.POST.get("channel", "")
        entry_ids = request.POST.getlist("entry[]") or request.POST.getlist("entry")
        last_read_entry = request.POST.get("last_read_entry", "")

        if not channel_uid:
            return JsonResponse({"error": "invalid_request"}, status=400)
        channel = Channel.objects.filter(uid=channel_uid).first()
        if not channel:
            return JsonResponse({"error": "invalid_request"}, status=400)

        if entry_ids:
            try:
                entry_ids = [int(x) for x in entry_ids]
            except (ValueError, TypeError):
                return JsonResponse({"error": "invalid_request"}, status=400)

        if method in ("", "mark_read"):
            if last_read_entry:
                try:
                    channel.entries.filter(id__lte=int(last_read_entry)).update(is_read=True)
                except (ValueError, TypeError):
                    pass
            elif entry_ids:
                channel.entries.filter(pk__in=entry_ids).update(is_read=True)
            else:
                channel.entries.all().update(is_read=True)
            return JsonResponse({})
        elif method == "mark_unread":
            if entry_ids:
                channel.entries.filter(pk__in=entry_ids).update(is_read=False)
            return JsonResponse({})
        elif method == "remove":
            if entry_ids:
                channel.entries.filter(pk__in=entry_ids).update(is_removed=True)
            return JsonResponse({})
        else:
            return JsonResponse({"error": "invalid_request"}, status=400)

    def _post_mute(self, request):
        if not _require_scope(request.microsub_scopes, "mute"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        url = request.POST.get("url", "").strip()
        channel_uid = request.POST.get("channel")
        if not url:
            return JsonResponse({"error": "invalid_request"}, status=400)
        channel = Channel.objects.filter(uid=channel_uid).first() if channel_uid else None
        MutedUser.objects.get_or_create(channel=channel, url=url)
        return JsonResponse({})

    def _post_unmute(self, request):
        if not _require_scope(request.microsub_scopes, "mute"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        url = request.POST.get("url", "").strip()
        channel_uid = request.POST.get("channel")
        if not url:
            return JsonResponse({"error": "invalid_request"}, status=400)
        channel = Channel.objects.filter(uid=channel_uid).first() if channel_uid else None
        MutedUser.objects.filter(channel=channel, url=url).delete()
        return JsonResponse({})

    def _post_block(self, request):
        if not _require_scope(request.microsub_scopes, "block"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        url = request.POST.get("url", "").strip()
        channel_uid = request.POST.get("channel")
        if not url:
            return JsonResponse({"error": "invalid_request"}, status=400)
        channel = Channel.objects.filter(uid=channel_uid).first() if channel_uid else None
        BlockedUser.objects.get_or_create(channel=channel, url=url)
        # Remove existing entries from this author
        if channel:
            channel.entries.filter(author_url=url).update(is_removed=True)
        return JsonResponse({})

    def _post_unblock(self, request):
        if not _require_scope(request.microsub_scopes, "block"):
            return JsonResponse({"error": "insufficient_scope"}, status=403)
        url = request.POST.get("url", "").strip()
        channel_uid = request.POST.get("channel")
        if not url:
            return JsonResponse({"error": "invalid_request"}, status=400)
        channel = Channel.objects.filter(uid=channel_uid).first() if channel_uid else None
        BlockedUser.objects.filter(channel=channel, url=url).delete()
        return JsonResponse({})


@method_decorator(csrf_exempt, name="dispatch")
class WebSubCallbackView(View):
    def get(self, request, subscription_id):
        """Hub challenge verification."""
        sub = Subscription.objects.filter(pk=subscription_id).first()
        if not sub:
            return HttpResponse(status=404)
        challenge = request.GET.get("hub.challenge", "")
        mode = request.GET.get("hub.mode", "")
        if mode == "subscribe" and challenge:
            sub.websub_subscribed_at = timezone.now()
            lease_seconds = request.GET.get("hub.lease_seconds")
            if lease_seconds:
                try:
                    sub.websub_expires_at = timezone.now() + timezone.timedelta(
                        seconds=int(lease_seconds)
                    )
                except (ValueError, TypeError):
                    pass
            sub.save(update_fields=["websub_subscribed_at", "websub_expires_at"])
            return HttpResponse(challenge, content_type="text/plain")
        if mode == "unsubscribe" and challenge:
            if not sub.is_active:
                return HttpResponse(challenge, content_type="text/plain")
            return HttpResponse(status=404)
        return HttpResponse(status=400)

    def post(self, request, subscription_id):
        """Incoming WebSub notification."""
        sub = Subscription.objects.filter(pk=subscription_id).first()
        if not sub:
            return HttpResponse(status=404)

        # Verify HMAC signature if we have a secret
        if sub.websub_secret:
            sig_header = request.META.get("HTTP_X_HUB_SIGNATURE_256") or request.META.get(
                "HTTP_X_HUB_SIGNATURE", ""
            )
            if not sig_header:
                return HttpResponse(status=401)
            body = request.body
            # hmac.new is the correct stdlib API; type checkers sometimes incorrectly flag it
            expected = hmac.new(  # type: ignore[attr-defined]
                sub.websub_secret.encode(), body, hashlib.sha256
            ).hexdigest()
            # Strip "sha256=" prefix if present
            provided = sig_header.split("=", 1)[-1]
            if not hmac.compare_digest(expected, provided):
                return HttpResponse(status=401)

        # Parse and store entries
        content_type = request.content_type or ""
        try:
            from .feed_parser import _parse_rss_atom, _parse_json_feed, _parse_hfeed

            if "json" in content_type:
                import json as _json
                data = _json.loads(request.body.decode("utf-8", errors="replace"))
                if isinstance(data.get("version"), str) and "jsonfeed" in data["version"]:
                    entries, _ = _parse_json_feed(data, sub.url)
                else:
                    entries, _ = _parse_rss_atom(request.body, sub.url)
            elif "html" in content_type:
                entries, _ = _parse_hfeed(request.body.decode("utf-8", errors="replace"), sub.url)
            else:
                entries, _ = _parse_rss_atom(request.body, sub.url)

            _store_entries(sub.channel, sub, entries)
        except Exception as exc:
            logger.exception("WebSub notification processing failed for sub %s: %s", subscription_id, exc)
            return HttpResponse(status=500)

        return HttpResponse(status=200)
