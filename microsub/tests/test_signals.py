"""Tests for microsub/signals.py — webmention_to_notifications."""
from django.test import TestCase

from micropub.models import Webmention
from microsub.models import Channel, Entry


def _make_webmention(status="accepted", mention_type="mention", **kwargs):
    defaults = {
        "source": "https://source.example.com/post",
        "target": "https://mysite.example.com/blog/hello/",
        "status": status,
        "mention_type": mention_type,
    }
    defaults.update(kwargs)
    return Webmention.objects.create(**defaults)


class WebmentionToNotificationsTests(TestCase):
    def setUp(self):
        # The seed migration already creates the notifications channel; fetch or create it.
        self.notifications, _ = Channel.objects.get_or_create(
            uid="notifications", defaults={"name": "Notifications"}
        )

    def test_non_accepted_status_creates_no_entry(self):
        _make_webmention(status="pending")
        self.assertEqual(Entry.objects.count(), 0)

    def test_rejected_status_creates_no_entry(self):
        _make_webmention(status="rejected")
        self.assertEqual(Entry.objects.count(), 0)

    def test_accepted_mention_creates_entry(self):
        _make_webmention(status="accepted", mention_type="mention")
        self.assertEqual(Entry.objects.count(), 1)

    def test_no_notifications_channel_creates_no_entry(self):
        self.notifications.delete()
        _make_webmention(status="accepted")
        self.assertEqual(Entry.objects.count(), 0)

    def test_like_sets_like_of(self):
        wm = _make_webmention(status="accepted", mention_type="like")
        entry = Entry.objects.get(channel=self.notifications)
        self.assertEqual(entry.data.get("like-of"), wm.target)
        self.assertNotIn("in-reply-to", entry.data)
        self.assertNotIn("repost-of", entry.data)

    def test_reply_sets_in_reply_to(self):
        wm = _make_webmention(status="accepted", mention_type="reply")
        entry = Entry.objects.get(channel=self.notifications)
        self.assertEqual(entry.data.get("in-reply-to"), wm.target)

    def test_repost_sets_repost_of(self):
        wm = _make_webmention(status="accepted", mention_type="repost")
        entry = Entry.objects.get(channel=self.notifications)
        self.assertEqual(entry.data.get("repost-of"), wm.target)

    def test_plain_mention_has_no_interaction_keys(self):
        _make_webmention(status="accepted", mention_type="mention")
        entry = Entry.objects.get(channel=self.notifications)
        self.assertNotIn("like-of", entry.data)
        self.assertNotIn("in-reply-to", entry.data)
        self.assertNotIn("repost-of", entry.data)

    def test_entry_uid_equals_source(self):
        wm = _make_webmention(status="accepted")
        entry = Entry.objects.get(channel=self.notifications)
        self.assertEqual(entry.uid, wm.source)

    def test_duplicate_webmention_does_not_create_duplicate_entry(self):
        source = "https://source.example.com/post"
        _make_webmention(status="accepted", source=source)
        _make_webmention(
            status="accepted",
            source=source,
            target="https://mysite.example.com/blog/other/",
        )
        self.assertEqual(Entry.objects.filter(channel=self.notifications, uid=source).count(), 1)

    def test_subscription_is_none(self):
        _make_webmention(status="accepted")
        entry = Entry.objects.get(channel=self.notifications)
        self.assertIsNone(entry.subscription)

    def test_entry_url_equals_source(self):
        wm = _make_webmention(status="accepted")
        entry = Entry.objects.get(channel=self.notifications)
        self.assertEqual(entry.data.get("url"), wm.source)

    def test_entry_author_url_equals_source(self):
        wm = _make_webmention(status="accepted")
        entry = Entry.objects.get(channel=self.notifications)
        self.assertEqual(entry.data["author"]["url"], wm.source)
