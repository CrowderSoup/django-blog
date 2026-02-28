"""Tests for MicrosubView GET handlers."""
import datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from microsub.models import BlockedUser, Channel, Entry, MutedUser, Subscription

MICROSUB_URL = "/microsub"
ALL_SCOPES = ["read", "follow", "channels", "mute", "block"]
authorized = patch("micropub.views._authorized", return_value=(True, ALL_SCOPES))


class MicrosubViewAuthTests(TestCase):
    def test_no_token_returns_401(self):
        response = self.client.get(MICROSUB_URL)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    @patch("micropub.views._authorized", return_value=(False, []))
    def test_invalid_token_returns_401(self, _auth):
        response = self.client.get(MICROSUB_URL, HTTP_AUTHORIZATION="Bearer bad")
        self.assertEqual(response.status_code, 401)

    @authorized
    def test_unknown_get_action_returns_400(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "bogus"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 400)

    @authorized
    def test_unknown_post_action_returns_400(self, _auth):
        response = self.client.post(
            MICROSUB_URL, {"action": "bogus"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 400)


class GetChannelsTests(TestCase):
    @patch("micropub.views._authorized", return_value=(True, []))
    def test_missing_read_scope_returns_403(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "channels"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "insufficient_scope")

    @authorized
    def test_returns_all_channels(self, _auth):
        Channel.objects.create(uid="news", name="News", order=1)
        Channel.objects.create(uid="tech", name="Tech", order=2)
        response = self.client.get(
            MICROSUB_URL, {"action": "channels"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("channels", data)
        # Seed migration creates 'notifications'; our two plus that = 3
        self.assertEqual(len(data["channels"]), 3)

    @authorized
    def test_empty_channel_list_contains_seed_channel(self, _auth):
        # Seed migration always creates 'notifications'; expect at least that one
        response = self.client.get(
            MICROSUB_URL, {"action": "channels"}, HTTP_AUTHORIZATION="Bearer token"
        )
        uids = [c["uid"] for c in response.json()["channels"]]
        self.assertIn("notifications", uids)

    @authorized
    def test_channel_json_shape(self, _auth):
        Channel.objects.create(uid="news", name="News")
        response = self.client.get(
            MICROSUB_URL, {"action": "channels"}, HTTP_AUTHORIZATION="Bearer token"
        )
        ch = response.json()["channels"][0]
        self.assertIn("uid", ch)
        self.assertIn("name", ch)
        self.assertIn("unread", ch)


class GetFollowTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(uid="news", name="News")

    @patch("micropub.views._authorized", return_value=(True, []))
    def test_missing_read_scope_returns_403(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "follow", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 403)

    @authorized
    def test_unknown_channel_returns_400(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "follow", "channel": "nope"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 400)

    @authorized
    def test_returns_active_subscriptions(self, _auth):
        Subscription.objects.create(channel=self.channel, url="https://a.example.com/feed", is_active=True)
        Subscription.objects.create(channel=self.channel, url="https://b.example.com/feed", is_active=False)
        response = self.client.get(
            MICROSUB_URL, {"action": "follow", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://a.example.com/feed")

    @authorized
    def test_each_item_has_required_fields(self, _auth):
        Subscription.objects.create(
            channel=self.channel, url="https://a.example.com/feed", name="A Feed", photo=""
        )
        response = self.client.get(
            MICROSUB_URL, {"action": "follow", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        item = response.json()["items"][0]
        self.assertEqual(item["type"], "feed")
        self.assertIn("url", item)
        self.assertIn("name", item)
        self.assertIn("photo", item)

    @authorized
    def test_empty_channel_returns_empty_items(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "follow", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.json(), {"items": []})


class GetTimelineTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(uid="news", name="News")
        now = timezone.now()
        self.e1 = Entry.objects.create(
            channel=self.channel, uid="e1",
            data={"type": "entry", "author": {"url": "https://author.example.com/"}},
            published=now,
        )
        self.e2 = Entry.objects.create(
            channel=self.channel, uid="e2",
            data={"type": "entry"},
            published=now + datetime.timedelta(seconds=1),
        )

    @patch("micropub.views._authorized", return_value=(True, []))
    def test_missing_read_scope_returns_403(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 403)

    @authorized
    def test_unknown_channel_returns_400(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "nope"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 400)

    @authorized
    def test_returns_entries_with_injected_fields(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertIn("_id", item)
            self.assertIn("_is_read", item)

    @authorized
    def test_removed_entries_excluded(self, _auth):
        self.e1.is_removed = True
        self.e1.save()
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        items = response.json()["items"]
        ids = [i["_id"] for i in items]
        self.assertNotIn(str(self.e1.pk), ids)
        self.assertIn(str(self.e2.pk), ids)

    @authorized
    def test_site_wide_muted_author_excluded(self, _auth):
        MutedUser.objects.create(channel=None, url="https://author.example.com/")
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["_id"], str(self.e2.pk))

    @authorized
    def test_channel_specific_muted_author_excluded(self, _auth):
        MutedUser.objects.create(channel=self.channel, url="https://author.example.com/")
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        items = response.json()["items"]
        self.assertEqual(len(items), 1)

    @authorized
    def test_blocked_author_excluded(self, _auth):
        BlockedUser.objects.create(channel=None, url="https://author.example.com/")
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        items = response.json()["items"]
        self.assertEqual(len(items), 1)

    @authorized
    def test_before_cursor_filters_by_published_lt(self, _auth):
        # "before" cursor is the entry PK of the oldest entry on the current page;
        # the response should contain entries older than that entry.
        response = self.client.get(
            MICROSUB_URL,
            {"action": "timeline", "channel": "news", "before": str(self.e2.pk)},
            HTTP_AUTHORIZATION="Bearer token",
        )
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["_id"], str(self.e1.pk))

    @authorized
    def test_after_cursor_filters_by_published_gt(self, _auth):
        # "after" cursor is the entry PK of the newest entry on the current page;
        # the response should contain entries newer than that entry.
        response = self.client.get(
            MICROSUB_URL,
            {"action": "timeline", "channel": "news", "after": str(self.e1.pk)},
            HTTP_AUTHORIZATION="Bearer token",
        )
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["_id"], str(self.e2.pk))

    @authorized
    def test_invalid_cursor_is_ignored(self, _auth):
        response = self.client.get(
            MICROSUB_URL,
            {"action": "timeline", "channel": "news", "before": "not-an-integer"},
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 2)

    @authorized
    def test_paging_keys_present_when_entries_exist(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        paging = response.json()["paging"]
        self.assertIn("before", paging)
        self.assertIn("after", paging)

    @authorized
    def test_paging_empty_when_no_entries(self, _auth):
        Entry.objects.all().delete()
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.json()["paging"], {})

    @authorized
    def test_paging_after_is_newest_entry_pk(self, _auth):
        # Items ordered newest-first: e2 (newer) then e1 (older).
        # "after" cursor should be the PK of the newest entry so clients can poll for new entries.
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        paging = response.json()["paging"]
        self.assertEqual(paging["after"], str(self.e2.pk))

    @authorized
    def test_paging_before_is_oldest_entry_pk(self, _auth):
        # "before" cursor should be the PK of the oldest entry so clients can fetch older entries.
        response = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        paging = response.json()["paging"]
        self.assertEqual(paging["before"], str(self.e1.pk))

    @authorized
    def test_paging_before_cursor_fetches_next_older_page(self, _auth):
        # Regression: requesting ?before=<paging.before> must return entries
        # OLDER than the current page, not overlap with it.
        now = timezone.now()
        # Create PAGE_SIZE + 2 entries so there are multiple pages.
        from microsub.views import PAGE_SIZE
        older_entries = []
        for i in range(PAGE_SIZE):
            e = Entry.objects.create(
                channel=self.channel,
                uid=f"old-{i}",
                data={},
                published=now - datetime.timedelta(hours=i + 1),
            )
            older_entries.append(e)

        # Get the first page (newest entries).
        page1 = self.client.get(
            MICROSUB_URL, {"action": "timeline", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        ).json()
        before_cursor = page1["paging"]["before"]
        page1_ids = {item["_id"] for item in page1["items"]}

        # Get the second page using the before cursor.
        page2 = self.client.get(
            MICROSUB_URL,
            {"action": "timeline", "channel": "news", "before": before_cursor},
            HTTP_AUTHORIZATION="Bearer token",
        ).json()
        page2_ids = {item["_id"] for item in page2["items"]}

        # Pages must not overlap.
        self.assertEqual(page1_ids & page2_ids, set(), "Pages overlap — paging cursor is wrong")


class GetMuteTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(uid="news", name="News")

    @patch("micropub.views._authorized", return_value=(True, ["read"]))
    def test_missing_mute_scope_returns_403(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "mute"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 403)

    @authorized
    def test_returns_site_wide_mutes_when_no_channel(self, _auth):
        MutedUser.objects.create(channel=None, url="https://spammer.example.com/")
        MutedUser.objects.create(channel=self.channel, url="https://other.example.com/")
        response = self.client.get(
            MICROSUB_URL, {"action": "mute"}, HTTP_AUTHORIZATION="Bearer token"
        )
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://spammer.example.com/")

    @authorized
    def test_returns_channel_mutes_when_channel_given(self, _auth):
        MutedUser.objects.create(channel=None, url="https://spammer.example.com/")
        MutedUser.objects.create(channel=self.channel, url="https://other.example.com/")
        response = self.client.get(
            MICROSUB_URL, {"action": "mute", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://other.example.com/")


class GetBlockTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(uid="news", name="News")

    @patch("micropub.views._authorized", return_value=(True, ["read"]))
    def test_missing_block_scope_returns_403(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "block"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 403)

    @authorized
    def test_returns_site_wide_blocks(self, _auth):
        BlockedUser.objects.create(channel=None, url="https://troll.example.com/")
        response = self.client.get(
            MICROSUB_URL, {"action": "block"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(len(response.json()["items"]), 1)

    @authorized
    def test_returns_channel_blocks(self, _auth):
        BlockedUser.objects.create(channel=self.channel, url="https://troll.example.com/")
        response = self.client.get(
            MICROSUB_URL, {"action": "block", "channel": "news"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(len(response.json()["items"]), 1)


class GetSearchTests(TestCase):
    @authorized
    def test_empty_query_returns_empty_results(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "search", "query": ""}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.json(), {"results": []})

    @authorized
    def test_missing_query_returns_empty_results(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "search"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.json(), {"results": []})

    @authorized
    @patch("urllib.request.urlopen")
    def test_non_http_query_prepends_https(self, mock_urlopen, _auth):
        from io import BytesIO
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers.get.side_effect = lambda k, d="": "application/rss+xml" if k == "Content-Type" else d
        mock_resp.read.return_value = b""
        mock_urlopen.return_value = mock_resp

        self.client.get(
            MICROSUB_URL, {"action": "search", "query": "example.com"}, HTTP_AUTHORIZATION="Bearer token"
        )
        call_args = mock_urlopen.call_args
        req_obj = call_args[0][0]
        self.assertTrue(req_obj.full_url.startswith("https://"))

    @authorized
    @patch("urllib.request.urlopen")
    def test_network_error_returns_empty_results(self, mock_urlopen, _auth):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("connection refused")
        response = self.client.get(
            MICROSUB_URL,
            {"action": "search", "query": "https://example.com"},
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": []})

    @authorized
    @patch("urllib.request.urlopen")
    def test_non_html_response_returns_url_as_feed(self, mock_urlopen, _auth):
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers.get.side_effect = lambda k, d="": "application/rss+xml" if k == "Content-Type" else d
        mock_resp.read.return_value = b"<rss/>"
        mock_urlopen.return_value = mock_resp

        response = self.client.get(
            MICROSUB_URL,
            {"action": "search", "query": "https://example.com/feed"},
            HTTP_AUTHORIZATION="Bearer token",
        )
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/feed")

    @authorized
    @patch("urllib.request.urlopen")
    def test_html_response_discovers_alternate_feeds(self, mock_urlopen, _auth):
        from unittest.mock import MagicMock

        html = b'<html><head><link rel="alternate" type="application/rss+xml" href="/feed.rss" title="RSS Feed"></head></html>'
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers.get.side_effect = lambda k, d="": "text/html; charset=utf-8" if k == "Content-Type" else d
        mock_resp.read.return_value = html
        mock_urlopen.return_value = mock_resp

        response = self.client.get(
            MICROSUB_URL,
            {"action": "search", "query": "https://example.com"},
            HTTP_AUTHORIZATION="Bearer token",
        )
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "feed")


class GetPreviewTests(TestCase):
    @authorized
    def test_missing_url_returns_400(self, _auth):
        response = self.client.get(
            MICROSUB_URL, {"action": "preview"}, HTTP_AUTHORIZATION="Bearer token"
        )
        self.assertEqual(response.status_code, 400)

    @authorized
    @patch("microsub.views.fetch_and_parse_feed", return_value=([{"type": "entry"}], None))
    def test_returns_items_on_success(self, mock_fetch, _auth):
        response = self.client.get(
            MICROSUB_URL,
            {"action": "preview", "url": "https://example.com/feed"},
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())

    @authorized
    @patch("microsub.views.fetch_and_parse_feed", return_value=([{"type": "entry"}] * 25, None))
    def test_returns_at_most_20_items(self, mock_fetch, _auth):
        response = self.client.get(
            MICROSUB_URL,
            {"action": "preview", "url": "https://example.com/feed"},
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertLessEqual(len(response.json()["items"]), 20)

    @authorized
    @patch("microsub.views.fetch_and_parse_feed", side_effect=RuntimeError("could not fetch"))
    def test_fetch_error_returns_502(self, mock_fetch, _auth):
        response = self.client.get(
            MICROSUB_URL,
            {"action": "preview", "url": "https://example.com/feed"},
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"], "fetch_error")
