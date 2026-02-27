"""Tests for WebSubCallbackView and _subscribe_to_websub."""
import hashlib
import hmac
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from microsub.models import Channel, Entry, Subscription

WEBSUB_URL = "/microsub/websub/callback/{id}/"


def _make_channel_and_sub(**kwargs):
    ch = Channel.objects.create(uid="news", name="News")
    defaults = {"channel": ch, "url": "https://example.com/feed"}
    defaults.update(kwargs)
    return ch, Subscription.objects.create(**defaults)


class WebSubChallengeTests(TestCase):
    def setUp(self):
        self.ch, self.sub = _make_channel_and_sub()

    def _url(self):
        return WEBSUB_URL.format(id=self.sub.pk)

    def test_unknown_subscription_returns_404(self):
        response = self.client.get(WEBSUB_URL.format(id=99999))
        self.assertEqual(response.status_code, 404)

    def test_subscribe_challenge_returns_challenge_text(self):
        response = self.client.get(
            self._url(),
            {"hub.mode": "subscribe", "hub.challenge": "abc123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"abc123")

    def test_subscribe_challenge_saves_subscribed_at(self):
        before = timezone.now()
        self.client.get(self._url(), {"hub.mode": "subscribe", "hub.challenge": "x"})
        self.sub.refresh_from_db()
        self.assertIsNotNone(self.sub.websub_subscribed_at)
        self.assertGreaterEqual(self.sub.websub_subscribed_at, before)

    def test_subscribe_with_lease_seconds_saves_expires_at(self):
        self.client.get(
            self._url(),
            {"hub.mode": "subscribe", "hub.challenge": "x", "hub.lease_seconds": "86400"},
        )
        self.sub.refresh_from_db()
        self.assertIsNotNone(self.sub.websub_expires_at)

    def test_subscribe_with_invalid_lease_seconds_is_ignored(self):
        self.client.get(
            self._url(),
            {"hub.mode": "subscribe", "hub.challenge": "x", "hub.lease_seconds": "bad"},
        )
        self.sub.refresh_from_db()
        self.assertIsNone(self.sub.websub_expires_at)

    def test_unsubscribe_challenge_returns_challenge_text(self):
        response = self.client.get(
            self._url(),
            {"hub.mode": "unsubscribe", "hub.challenge": "xyz789"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"xyz789")

    def test_get_with_no_mode_returns_400(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)


class WebSubNotificationTests(TestCase):
    def setUp(self):
        self.ch, self.sub = _make_channel_and_sub()

    def _url(self):
        return WEBSUB_URL.format(id=self.sub.pk)

    def test_unknown_subscription_returns_404(self):
        response = self.client.post(
            WEBSUB_URL.format(id=99999),
            data=b"<rss/>",
            content_type="application/rss+xml",
        )
        self.assertEqual(response.status_code, 404)

    def test_no_secret_accepts_any_post(self):
        self.assertFalse(self.sub.websub_secret)
        response = self.client.post(
            self._url(), data=b"<rss/>", content_type="application/rss+xml"
        )
        self.assertEqual(response.status_code, 200)

    def test_with_secret_missing_signature_header_returns_401(self):
        self.sub.websub_secret = "mysecret"
        self.sub.save()
        response = self.client.post(
            self._url(), data=b"<rss/>", content_type="application/rss+xml"
        )
        self.assertEqual(response.status_code, 401)

    def test_with_secret_wrong_signature_returns_401(self):
        self.sub.websub_secret = "mysecret"
        self.sub.save()
        response = self.client.post(
            self._url(),
            data=b"<rss/>",
            content_type="application/rss+xml",
            HTTP_X_HUB_SIGNATURE_256="sha256=wrongsig",
        )
        self.assertEqual(response.status_code, 401)

    def test_with_secret_correct_signature_returns_200(self):
        secret = "correctsecret"
        self.sub.websub_secret = secret
        self.sub.save()
        body = b"<rss/>"
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        response = self.client.post(
            self._url(),
            data=body,
            content_type="application/rss+xml",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={sig}",
        )
        self.assertEqual(response.status_code, 200)

    def test_rss_notification_stores_entries(self):
        rss = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>Test</title><link>https://example.com/1</link><guid>https://example.com/1</guid></item>
</channel></rss>"""
        self.client.post(self._url(), data=rss, content_type="application/rss+xml")
        self.assertEqual(Entry.objects.filter(channel=self.ch).count(), 1)

    def test_json_feed_notification_stores_entries(self):
        import json
        payload = json.dumps({
            "version": "https://jsonfeed.org/version/1",
            "title": "Test",
            "items": [{"id": "https://example.com/1", "title": "Hello"}],
        }).encode()
        self.client.post(self._url(), data=payload, content_type="application/json")
        self.assertEqual(Entry.objects.filter(channel=self.ch).count(), 1)

    def test_html_notification_is_handled(self):
        html = b"""<html><div class="h-entry">
            <a class="u-url" href="https://example.com/post">Post</a>
        </div></html>"""
        response = self.client.post(self._url(), data=html, content_type="text/html")
        self.assertEqual(response.status_code, 200)

    def test_parse_error_still_returns_200(self):
        response = self.client.post(
            self._url(), data=b"<<not xml>>", content_type="application/rss+xml"
        )
        self.assertEqual(response.status_code, 200)


class SubscribeToWebsubTests(TestCase):
    def setUp(self):
        ch = Channel.objects.create(uid="news", name="News")
        self.sub = Subscription.objects.create(channel=ch, url="https://example.com/feed")

    def test_no_op_when_no_hub(self):
        from microsub.views import _subscribe_to_websub
        from django.test import RequestFactory
        request = RequestFactory().get("/")
        _subscribe_to_websub(self.sub, request)  # should not raise
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.websub_secret, "")

    @patch("microsub.views.urlopen")
    def test_saves_secret_and_subscribed_at_on_202(self, mock_urlopen):
        from microsub.views import _subscribe_to_websub
        from django.test import RequestFactory

        self.sub.websub_hub = "https://hub.example.com/"
        self.sub.save()

        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 202
        mock_urlopen.return_value = mock_resp

        # 'testserver' is always in ALLOWED_HOSTS during tests
        request = RequestFactory(SERVER_NAME="testserver").get("/")
        _subscribe_to_websub(self.sub, request)

        self.sub.refresh_from_db()
        self.assertNotEqual(self.sub.websub_secret, "")
        self.assertIsNotNone(self.sub.websub_subscribed_at)

    @patch("microsub.views.urlopen")
    def test_network_error_does_not_raise(self, mock_urlopen):
        from urllib.error import URLError
        from microsub.views import _subscribe_to_websub
        from django.test import RequestFactory

        self.sub.websub_hub = "https://hub.example.com/"
        self.sub.save()
        mock_urlopen.side_effect = URLError("refused")

        request = RequestFactory(SERVER_NAME="testserver").get("/")
        _subscribe_to_websub(self.sub, request)  # should not raise
