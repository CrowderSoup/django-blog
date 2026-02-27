"""Tests for microsub/opml.py."""
from django.test import SimpleTestCase

from microsub.opml import parse_opml


class ParseOpmlTests(SimpleTestCase):
    def _opml(self, body_content):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <head><title>Test</title></head>
  <body>{body_content}</body>
</opml>"""

    def test_top_level_feed_goes_to_uncategorized(self):
        opml = self._opml('<outline xmlUrl="https://example.com/feed" text="Example"/>')
        result = parse_opml(opml)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Uncategorized")
        self.assertEqual(result[0]["feeds"][0]["url"], "https://example.com/feed")

    def test_category_folder_creates_named_channel(self):
        opml = self._opml("""
        <outline text="Tech">
          <outline xmlUrl="https://tech.example.com/feed" text="Tech Feed"/>
        </outline>""")
        result = parse_opml(opml)
        self.assertEqual(result[0]["name"], "Tech")

    def test_title_attr_preferred_over_text(self):
        opml = self._opml('<outline xmlUrl="https://example.com/" title="Title" text="Text"/>')
        result = parse_opml(opml)
        self.assertEqual(result[0]["feeds"][0]["name"], "Title")

    def test_text_attr_used_when_no_title(self):
        opml = self._opml('<outline xmlUrl="https://example.com/" text="Text Only"/>')
        result = parse_opml(opml)
        self.assertEqual(result[0]["feeds"][0]["name"], "Text Only")

    def test_url_used_as_fallback_name(self):
        opml = self._opml('<outline xmlUrl="https://example.com/"/>')
        result = parse_opml(opml)
        self.assertEqual(result[0]["feeds"][0]["name"], "https://example.com/")

    def test_outline_without_xml_url_skipped(self):
        opml = self._opml('<outline text="No URL"/>')
        result = parse_opml(opml)
        self.assertEqual(result, [])

    def test_empty_category_omitted(self):
        opml = self._opml("""
        <outline text="Empty Category">
          <outline text="No URL child"/>
        </outline>""")
        result = parse_opml(opml)
        self.assertEqual(result, [])

    def test_bytes_input_decoded(self):
        opml = self._opml('<outline xmlUrl="https://example.com/" text="Feed"/>').encode("utf-8")
        result = parse_opml(opml)
        self.assertEqual(len(result), 1)

    def test_invalid_xml_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_opml("<<not xml>>")

    def test_non_opml_root_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_opml('<rss version="2.0"><channel/></rss>')

    def test_missing_body_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_opml('<opml version="1.0"><head/></opml>')

    def test_multiple_categories_preserved_in_order(self):
        opml = self._opml("""
        <outline text="A"><outline xmlUrl="https://a.example.com/" text="A Feed"/></outline>
        <outline text="B"><outline xmlUrl="https://b.example.com/" text="B Feed"/></outline>
        """)
        result = parse_opml(opml)
        self.assertEqual(result[0]["name"], "A")
        self.assertEqual(result[1]["name"], "B")

    def test_mixed_top_level_and_category_feeds(self):
        opml = self._opml("""
        <outline xmlUrl="https://top.example.com/" text="Top Level"/>
        <outline text="Tech">
          <outline xmlUrl="https://tech.example.com/" text="Tech Feed"/>
        </outline>
        """)
        result = parse_opml(opml)
        names = [c["name"] for c in result]
        self.assertIn("Uncategorized", names)
        self.assertIn("Tech", names)
