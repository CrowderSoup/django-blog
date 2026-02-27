import logging
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

USER_AGENT = "Webstead Microsub/1.0"
FETCH_TIMEOUT = 15


class _HubLinkParser(HTMLParser):
    """Parse <link rel="hub"> from HTML."""

    def __init__(self):
        super().__init__()
        self.hub_url = None
        self.feed_url = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "link":
            return
        attr_map = {k.lower(): v for k, v in attrs}
        rels = {r.strip() for r in attr_map.get("rel", "").split()}
        href = attr_map.get("href", "")
        if "hub" in rels and not self.hub_url:
            self.hub_url = href
        if "alternate" in rels and not self.feed_url:
            ct = attr_map.get("type", "")
            if any(f in ct for f in ("rss", "atom", "xml", "json")):
                self.feed_url = href


def _parse_link_header_for_rel(header_value: str, rel_name: str) -> str | None:
    if not header_value:
        return None
    for part in header_value.split(","):
        segment = part.strip()
        if not segment.startswith("<") or ">" not in segment:
            continue
        url, _, params = segment.partition(">")
        rel = None
        for param in params.split(";"):
            name, _, value = param.strip().partition("=")
            if name.lower() == "rel":
                rel = value.strip('"')
                break
        if rel and rel_name in rel.split():
            return url[1:]
    return None


def discover_websub_hub(url: str, link_header: str | None, html_body: str | None = None) -> str | None:
    """Return WebSub hub URL from Link header or <link rel="hub"> in HTML."""
    if link_header:
        hub = _parse_link_header_for_rel(link_header, "hub")
        if hub:
            return urljoin(url, hub)
    if html_body:
        parser = _HubLinkParser()
        parser.feed(html_body[:50_000])
        if parser.hub_url:
            return urljoin(url, parser.hub_url)
    return None


def _author_from_mf2(author_val, base_url: str) -> dict:
    if isinstance(author_val, str):
        return {"type": "card", "url": author_val}
    if isinstance(author_val, dict):
        props = author_val.get("properties", {})
        card: dict = {"type": "card"}
        name = props.get("name", [])
        if name:
            card["name"] = name[0] if isinstance(name[0], str) else ""
        url = props.get("url", [])
        if url:
            card["url"] = urljoin(base_url, url[0]) if isinstance(url[0], str) else ""
        photo = props.get("photo", [])
        if photo:
            p = photo[0]
            card["photo"] = (p.get("value") or p) if isinstance(p, dict) else p
    return {"type": "card"}


def _hentry_to_jf2(item: dict, base_url: str) -> dict:
    props = item.get("properties", {})

    def _first(key, default=""):
        vals = props.get(key, [])
        if not vals:
            return default
        v = vals[0]
        if isinstance(v, dict):
            return v.get("value", v.get("html", "")) or default
        return v or default

    entry: dict = {"type": "entry"}

    url = _first("url")
    if url:
        entry["url"] = urljoin(base_url, url)

    uid = _first("uid") or entry.get("url", "")
    if uid:
        entry["_uid"] = uid

    name = _first("name")
    if name:
        entry["name"] = name

    content_vals = props.get("content", [])
    if content_vals:
        cv = content_vals[0]
        if isinstance(cv, dict):
            entry["content"] = {
                "html": cv.get("html", ""),
                "text": cv.get("value", ""),
            }
        else:
            entry["content"] = {"text": str(cv)}

    published = _first("published")
    if published:
        entry["published"] = published

    authors = props.get("author", [])
    if authors:
        entry["author"] = _author_from_mf2(authors[0], base_url)

    for prop, jf2_key in [
        ("in-reply-to", "in-reply-to"),
        ("like-of", "like-of"),
        ("repost-of", "repost-of"),
        ("bookmark-of", "bookmark-of"),
    ]:
        vals = props.get(prop, [])
        if vals:
            v = vals[0]
            if isinstance(v, str):
                entry[jf2_key] = urljoin(base_url, v)
            elif isinstance(v, dict):
                inner = v.get("value") or v.get("url", "")
                if inner:
                    entry[jf2_key] = urljoin(base_url, inner)

    return entry


def _parse_hfeed(html: str, base_url: str) -> list[dict]:
    try:
        import mf2py
    except ImportError:
        logger.warning("mf2py not installed; skipping h-feed parsing")
        return []

    parsed = mf2py.parse(doc=html, url=base_url)
    items = parsed.get("items", [])

    # Find h-feed and use its children, or fall back to bare h-entries
    for item in items:
        if "h-feed" in item.get("type", []):
            children = item.get("children", [])
            return [
                _hentry_to_jf2(child, base_url)
                for child in children
                if "h-entry" in child.get("type", [])
            ]

    # Bare h-entries
    return [
        _hentry_to_jf2(item, base_url)
        for item in items
        if "h-entry" in item.get("type", [])
    ]


def _parse_rss_atom(content: bytes, url: str) -> list[dict]:
    try:
        import feedparser
    except ImportError:
        logger.warning("feedparser not installed; skipping RSS/Atom parsing")
        return []

    feed = feedparser.parse(content)
    entries = []
    for e in feed.entries:
        entry: dict = {"type": "entry"}
        uid = getattr(e, "id", None) or getattr(e, "link", None)
        if uid:
            entry["_uid"] = uid
        link = getattr(e, "link", None)
        if link:
            entry["url"] = link
        title = getattr(e, "title", None)
        if title:
            entry["name"] = title
        # content
        content_list = getattr(e, "content", None)
        summary = getattr(e, "summary", None)
        if content_list:
            c = content_list[0]
            entry["content"] = {"html": c.get("value", ""), "text": c.get("value", "")}
        elif summary:
            entry["content"] = {"text": summary}
        # published / updated
        pub = getattr(e, "published", None) or getattr(e, "updated", None)
        if pub:
            entry["published"] = pub
        # author
        author = getattr(e, "author_detail", None) or getattr(e, "author", None)
        if author:
            if isinstance(author, str):
                entry["author"] = {"type": "card", "name": author}
            else:
                card: dict = {"type": "card"}
                if getattr(author, "name", None):
                    card["name"] = author.name
                if getattr(author, "href", None):
                    card["url"] = author.href
                entry["author"] = card
        entries.append(entry)
    return entries


def _parse_json_feed(data: dict, base_url: str) -> list[dict]:
    items = data.get("items", [])
    entries = []
    for item in items:
        entry: dict = {"type": "entry"}
        uid = item.get("id")
        if uid:
            entry["_uid"] = str(uid)
        url = item.get("url") or item.get("external_url")
        if url:
            entry["url"] = url
        title = item.get("title")
        if title:
            entry["name"] = title
        content_html = item.get("content_html", "")
        content_text = item.get("content_text", "")
        if content_html or content_text:
            entry["content"] = {"html": content_html, "text": content_text}
        published = item.get("date_published") or item.get("date_modified")
        if published:
            entry["published"] = published
        author_data = item.get("author") or (item.get("authors") or [None])[0]
        if author_data and isinstance(author_data, dict):
            card: dict = {"type": "card"}
            if author_data.get("name"):
                card["name"] = author_data["name"]
            if author_data.get("url"):
                card["url"] = author_data["url"]
            if author_data.get("avatar"):
                card["photo"] = author_data["avatar"]
            entry["author"] = card
        entries.append(entry)
    return entries


def fetch_and_parse_feed(url: str) -> tuple[list[dict], str | None]:
    """Fetch a URL and return (jf2_entries, websub_hub_url)."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=FETCH_TIMEOUT) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            link_header = response.headers.get("Link")
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc

    hub_url = discover_websub_hub(url, link_header)

    # Detect format
    if "json" in content_type:
        try:
            import json
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            data = {}
        # JSON Feed has a "version" key starting with "https://jsonfeed.org/"
        if isinstance(data.get("version"), str) and "jsonfeed" in data["version"]:
            entries = _parse_json_feed(data, url)
        else:
            entries = _parse_rss_atom(raw, url)
    elif "html" in content_type:
        html_str = raw.decode("utf-8", errors="replace")
        entries = _parse_hfeed(html_str, url)
        if not entries:
            # Also try to discover hub from HTML
            hub_url = discover_websub_hub(url, link_header, html_str) or hub_url
    else:
        # Try RSS/Atom (XML)
        entries = _parse_rss_atom(raw, url)

    return entries, hub_url
