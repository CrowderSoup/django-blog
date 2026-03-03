"""Parse OPML files into structured channel/feed data."""
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError


def parse_opml(file_content: bytes | str) -> list[dict]:
    """Parse an OPML file and return structured channel/feed data.

    Returns a list of dicts:
        [{"name": str, "feeds": [{"url": str, "name": str}]}]

    Top-level feeds with no enclosing category folder are placed into a
    channel named "Uncategorized".  Empty channels (no valid xmlUrl feeds)
    are omitted from the result.
    """
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8", errors="replace")

    try:
        root = ET.fromstring(file_content)
    except ParseError as exc:
        raise ValueError(f"Invalid OPML file: {exc}") from exc

    if root.tag != "opml":
        raise ValueError("Not a valid OPML file (missing <opml> root element)")

    body = root.find("body")
    if body is None:
        raise ValueError("OPML file has no <body> element")

    # Preserve insertion order so channels appear in file order.
    channels: dict[str, list[dict]] = {}

    def _feed_entry(outline: ET.Element) -> dict | None:
        url = (outline.get("xmlUrl") or "").strip()
        if not url:
            return None
        name = (outline.get("title") or outline.get("text") or url).strip()
        return {"url": url, "name": name}

    def _add_to_channel(channel_name: str, feed: dict) -> None:
        channels.setdefault(channel_name, []).append(feed)

    for outline in body:
        feed = _feed_entry(outline)
        if feed:
            # Top-level feed with no category folder.
            _add_to_channel("Uncategorized", feed)
        else:
            # Category / folder — iterate children.
            channel_name = (
                outline.get("title") or outline.get("text") or "Uncategorized"
            ).strip()
            for child in outline:
                child_feed = _feed_entry(child)
                if child_feed:
                    _add_to_channel(channel_name, child_feed)

    return [{"name": name, "feeds": feeds} for name, feeds in channels.items() if feeds]
