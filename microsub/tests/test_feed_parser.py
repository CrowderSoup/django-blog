"""Tests for microsub/feed_parser.py."""
import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from microsub.feed_parser import (
    _HubLinkParser,
    _author_from_mf2,
    _hentry_to_jf2,
    _parse_json_feed,
    _parse_link_header_for_rel,
    _parse_rss_atom,
    discover_websub_hub,
    fetch_and_parse_feed,
)


class ParseLinkHeaderTests(SimpleTestCase):
    def test_returns_url_for_matching_rel(self):
        header = '<https://hub.example.com/>; rel="hub"'
        result = _parse_link_header_for_rel(header, "hub")
        self.assertEqual(result, "https://hub.example.com/")

    def test_returns_none_when_rel_not_found(self):
        header = '<https://example.com/feed>; rel="self"'
        self.assertIsNone(_parse_link_header_for_rel(header, "hub"))

    def test_multiple_links_returns_correct_one(self):
        header = '<https://self.example.com/>; rel="self", <https://hub.example.com/>; rel="hub"'
        result = _parse_link_header_for_rel(header, "hub")
        self.assertEqual(result, "https://hub.example.com/")

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_link_header_for_rel("", "hub"))

    def test_none_returns_none(self):
        self.assertIsNone(_parse_link_header_for_rel(None, "hub"))

    def test_malformed_segment_skipped(self):
        header = 'no-angle-bracket; rel="hub"'
        self.assertIsNone(_parse_link_header_for_rel(header, "hub"))


class HubLinkParserTests(SimpleTestCase):
    def test_parses_hub_link(self):
        p = _HubLinkParser()
        p.feed('<link rel="hub" href="https://hub.example.com/">')
        self.assertEqual(p.hub_url, "https://hub.example.com/")

    def test_only_first_hub_captured(self):
        p = _HubLinkParser()
        p.feed('<link rel="hub" href="https://hub1.example.com/"><link rel="hub" href="https://hub2.example.com/">')
        self.assertEqual(p.hub_url, "https://hub1.example.com/")

    def test_parses_rss_alternate_feed(self):
        p = _HubLinkParser()
        p.feed('<link rel="alternate" type="application/rss+xml" href="/feed.rss">')
        self.assertEqual(p.feed_url, "/feed.rss")

    def test_ignores_alternate_without_feed_type(self):
        p = _HubLinkParser()
        p.feed('<link rel="alternate" type="text/html" href="/page">')
        self.assertIsNone(p.feed_url)

    def test_non_link_tags_ignored(self):
        p = _HubLinkParser()
        p.feed('<meta name="author" content="foo">')
        self.assertIsNone(p.hub_url)


class DiscoverWebsubHubTests(SimpleTestCase):
    def test_hub_from_link_header(self):
        result = discover_websub_hub(
            "https://example.com/",
            '<https://hub.example.com/>; rel="hub"',
        )
        self.assertEqual(result, "https://hub.example.com/")

    def test_hub_from_html_when_no_link_header(self):
        html = '<link rel="hub" href="https://hub.example.com/">'
        result = discover_websub_hub("https://example.com/", None, html)
        self.assertEqual(result, "https://hub.example.com/")

    def test_relative_hub_url_resolved(self):
        html = '<link rel="hub" href="/websub">'
        result = discover_websub_hub("https://example.com/page", None, html)
        self.assertEqual(result, "https://example.com/websub")

    def test_none_when_no_hub_anywhere(self):
        self.assertIsNone(discover_websub_hub("https://example.com/", None, None))

    def test_link_header_takes_precedence_over_html(self):
        html = '<link rel="hub" href="https://html-hub.example.com/">'
        result = discover_websub_hub(
            "https://example.com/",
            '<https://header-hub.example.com/>; rel="hub"',
            html,
        )
        self.assertEqual(result, "https://header-hub.example.com/")


class AuthorFromMf2Tests(SimpleTestCase):
    def test_string_author_returns_card_with_url(self):
        result = _author_from_mf2("https://author.example.com/", "https://example.com/")
        self.assertEqual(result, {"type": "card", "url": "https://author.example.com/"})

    def test_dict_author_returns_full_card(self):
        author = {
            "type": ["h-card"],
            "properties": {
                "name": ["Alice"],
                "url": ["https://alice.example.com/"],
            },
        }
        result = _author_from_mf2(author, "https://example.com/")
        self.assertEqual(result["type"], "card")
        self.assertEqual(result["name"], "Alice")
        self.assertEqual(result["url"], "https://alice.example.com/")


class HentryToJf2Tests(SimpleTestCase):
    def _make_hentry(self, props):
        return {"type": ["h-entry"], "properties": props}

    def test_url_is_included(self):
        item = self._make_hentry({"url": ["https://example.com/post"]})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertEqual(result["url"], "https://example.com/post")

    def test_relative_url_resolved(self):
        item = self._make_hentry({"url": ["/post/1"]})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertTrue(result["url"].startswith("https://example.com"))

    def test_uid_falls_back_to_url(self):
        item = self._make_hentry({"url": ["https://example.com/post"]})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertIn("_uid", result)

    def test_name_included(self):
        item = self._make_hentry({"name": ["My Post"], "url": ["https://example.com/"]})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertEqual(result["name"], "My Post")

    def test_content_dict_with_html(self):
        item = self._make_hentry({"content": [{"html": "<b>hi</b>", "value": "hi"}]})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertEqual(result["content"]["html"], "<b>hi</b>")
        self.assertEqual(result["content"]["text"], "hi")

    def test_content_plain_string(self):
        item = self._make_hentry({"content": ["plain text"]})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertEqual(result["content"]["text"], "plain text")

    def test_in_reply_to_included(self):
        item = self._make_hentry({"in-reply-to": ["https://target.example.com/"]})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertIn("in-reply-to", result)

    def test_like_of_included(self):
        item = self._make_hentry({"like-of": ["https://liked.example.com/"]})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertIn("like-of", result)

    def test_repost_of_included(self):
        item = self._make_hentry({"repost-of": ["https://reposted.example.com/"]})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertIn("repost-of", result)

    def test_empty_props_returns_type_entry(self):
        item = self._make_hentry({})
        result = _hentry_to_jf2(item, "https://example.com/")
        self.assertEqual(result["type"], "entry")


class ParseJsonFeedTests(SimpleTestCase):
    def _make_data(self, items):
        return {
            "version": "https://jsonfeed.org/version/1",
            "title": "Test",
            "items": items,
        }

    def test_basic_item_parsed(self):
        data = self._make_data([{
            "id": "https://example.com/1",
            "title": "Hello",
            "url": "https://example.com/1",
        }])
        entries, meta = _parse_json_feed(data, "https://example.com/")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["_uid"], "https://example.com/1")
        self.assertEqual(entries[0]["name"], "Hello")

    def test_feed_meta_title_extracted(self):
        data = self._make_data([])
        _, meta = _parse_json_feed(data, "https://example.com/")
        self.assertEqual(meta["name"], "Test")

    def test_external_url_used_when_url_absent(self):
        data = self._make_data([{
            "id": "1",
            "external_url": "https://external.example.com/",
        }])
        entries, _ = _parse_json_feed(data, "https://example.com/")
        self.assertEqual(entries[0]["url"], "https://external.example.com/")

    def test_content_html_and_text_included(self):
        data = self._make_data([{
            "id": "1",
            "content_html": "<p>hi</p>",
            "content_text": "hi",
        }])
        entries, _ = _parse_json_feed(data, "https://example.com/")
        self.assertEqual(entries[0]["content"]["html"], "<p>hi</p>")
        self.assertEqual(entries[0]["content"]["text"], "hi")

    def test_date_modified_used_when_date_published_absent(self):
        data = self._make_data([{
            "id": "1",
            "date_modified": "2024-01-01T00:00:00Z",
        }])
        entries, _ = _parse_json_feed(data, "https://example.com/")
        self.assertEqual(entries[0]["published"], "2024-01-01T00:00:00Z")

    def test_author_from_authors_array(self):
        data = self._make_data([{
            "id": "1",
            "authors": [{"name": "Alice", "url": "https://alice.example.com/"}],
        }])
        entries, _ = _parse_json_feed(data, "https://example.com/")
        self.assertEqual(entries[0]["author"]["name"], "Alice")

    def test_empty_items_returns_empty_list(self):
        data = self._make_data([])
        entries, _ = _parse_json_feed(data, "https://example.com/")
        self.assertEqual(entries, [])


class ParseRssAtomTests(SimpleTestCase):
    RSS_FEED = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Item One</title>
      <link>https://example.com/1</link>
      <guid>https://example.com/1</guid>
      <pubDate>Mon, 15 Jan 2024 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

    def test_parses_rss_item(self):
        entries, meta = _parse_rss_atom(self.RSS_FEED, "https://example.com/")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["_uid"], "https://example.com/1")
        self.assertEqual(entries[0]["name"], "Item One")

    def test_rss_feed_meta_title_extracted(self):
        _, meta = _parse_rss_atom(self.RSS_FEED, "https://example.com/")
        self.assertEqual(meta["name"], "Test Feed")

    def test_empty_feed_returns_empty_list(self):
        empty_rss = b"<?xml version='1.0'?><rss version='2.0'><channel></channel></rss>"
        entries, _ = _parse_rss_atom(empty_rss, "https://example.com/")
        self.assertEqual(entries, [])


class FetchAndParseFeedTests(SimpleTestCase):
    def _mock_urlopen(self, content_type, body):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers.get.side_effect = lambda k, d=None: {
            "Content-Type": content_type,
            "Link": None,
        }.get(k, d)
        mock_resp.read.return_value = body
        return mock_resp

    @patch("microsub.feed_parser.urlopen")
    def test_network_error_raises_runtime_error(self, mock_urlopen):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("no route")
        with self.assertRaises(RuntimeError):
            fetch_and_parse_feed("https://example.com/feed")

    @patch("microsub.feed_parser.urlopen")
    def test_json_feed_parsed_for_jsonfeed_content(self, mock_urlopen):
        data = json.dumps({
            "version": "https://jsonfeed.org/version/1",
            "title": "Test",
            "items": [{"id": "1", "title": "Post"}],
        }).encode()
        mock_urlopen.return_value = self._mock_urlopen("application/json", data)
        entries, hub, meta = fetch_and_parse_feed("https://example.com/feed")
        self.assertEqual(len(entries), 1)

    @patch("microsub.feed_parser.urlopen")
    def test_rss_parsed_for_xml_content_type(self, mock_urlopen):
        rss = b"""<?xml version="1.0"?><rss version="2.0"><channel>
          <item><guid>1</guid><link>https://example.com/1</link></item>
        </channel></rss>"""
        mock_urlopen.return_value = self._mock_urlopen("application/rss+xml", rss)
        entries, hub, meta = fetch_and_parse_feed("https://example.com/feed")
        self.assertEqual(len(entries), 1)

    @patch("microsub.feed_parser.urlopen")
    def test_hub_url_extracted_from_link_header(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers.get.side_effect = lambda k, d=None: {
            "Content-Type": "application/rss+xml",
            "Link": '<https://hub.example.com/>; rel="hub"',
        }.get(k, d)
        mock_resp.read.return_value = b"<rss version='2.0'><channel></channel></rss>"
        mock_urlopen.return_value = mock_resp
        _, hub, _ = fetch_and_parse_feed("https://example.com/feed")
        self.assertEqual(hub, "https://hub.example.com/")

    @patch("microsub.feed_parser.urlopen")
    def test_no_hub_returns_none(self, mock_urlopen):
        rss = b"<rss version='2.0'><channel></channel></rss>"
        mock_urlopen.return_value = self._mock_urlopen("application/rss+xml", rss)
        _, hub, _ = fetch_and_parse_feed("https://example.com/feed")
        self.assertIsNone(hub)

    @patch("microsub.feed_parser.urlopen")
    def test_correct_user_agent_sent(self, mock_urlopen):
        rss = b"<rss version='2.0'><channel></channel></rss>"
        mock_urlopen.return_value = self._mock_urlopen("application/rss+xml", rss)
        fetch_and_parse_feed("https://example.com/feed")
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("User-agent"), "Webstead Microsub/1.0")
