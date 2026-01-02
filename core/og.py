from urllib.parse import urlsplit

import markdown

from django.templatetags.static import static
from django.utils.html import strip_tags
from django.utils.text import Truncator

from files.models import File


def absolute_url(request, url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    if parts.scheme and parts.netloc:
        return url
    return request.build_absolute_uri(url)


def summarize_markdown(content: str, length: int = 200) -> str:
    if not content:
        return ""
    md = markdown.Markdown(extensions=["fenced_code"])
    html = md.convert(content)
    text = strip_tags(html).strip()
    return Truncator(text).chars(length, truncate="...")


def first_attachment_image_url(attachments) -> tuple[str, str]:
    if not attachments:
        return "", ""
    for attachment in attachments:
        asset = getattr(attachment, "asset", None)
        if asset and asset.kind == File.IMAGE and asset.file:
            return asset.file.url, asset.alt_text or ""
    return "", ""


def default_image_url(request, *, settings=None, site_author_hcard=None) -> str:
    if site_author_hcard and site_author_hcard.primary_photo_url:
        return absolute_url(request, site_author_hcard.primary_photo_url)
    if settings and settings.favicon_id and settings.favicon and settings.favicon.file:
        return absolute_url(request, settings.favicon.file.url)
    return absolute_url(request, static("favicon.svg"))
