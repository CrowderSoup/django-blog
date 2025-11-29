import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils.text import Truncator

from .models import Post

logger = logging.getLogger(__name__)


@dataclass
class SyndicationTarget:
    uid: str
    name: str

    def is_configured(self) -> bool:
        return False

    def should_syndicate(self, post: Post) -> bool:
        return post.kind in (Post.NOTE, Post.PHOTO)

    def _compose_status(self, post: Post, canonical_url: str, limit: int) -> str:
        summary_with_link = f"{post.summary()} {canonical_url}".strip()
        return Truncator(summary_with_link).chars(limit, truncate="")

    def syndicate(self, post: Post, canonical_url: str) -> str | None:  # pragma: no cover - interface
        raise NotImplementedError


class MastodonTarget(SyndicationTarget):
    def __init__(self):
        super().__init__(uid="mastodon", name="Mastodon")
        self.base_url = getattr(settings, "MASTODON_BASE_URL", "").rstrip("/")
        self.access_token = getattr(settings, "MASTODON_ACCESS_TOKEN", "")

    def is_configured(self) -> bool:
        return bool(self.base_url and self.access_token)

    def syndicate(self, post: Post, canonical_url: str) -> str | None:
        if not self.is_configured() or not self.should_syndicate(post):
            return None

        status = self._compose_status(post, canonical_url, limit=470)
        payload = json.dumps({"status": status}).encode("utf-8")
        endpoint = f"{self.base_url}/api/v1/statuses"
        request = Request(
            endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=10) as response:
                body = response.read().decode()
                if response.status >= 400:
                    logger.error("Mastodon syndication failed with status %s: %s", response.status, body)
                    return None
        except (HTTPError, URLError, TimeoutError) as exc:  # pragma: no cover - network
            logger.exception("Error posting to Mastodon: %s", exc)
            return None

        try:
            data = json.loads(body or "{}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON from Mastodon response")
            return None

        url = data.get("url")
        if isinstance(url, str):
            return url
        logger.error("Mastodon response missing status URL")
        return None


class BlueskyTarget(SyndicationTarget):
    def __init__(self):
        super().__init__(uid="bluesky", name="Bluesky")
        self.service = getattr(settings, "BLUESKY_SERVICE", "https://bsky.social").rstrip("/")
        self.handle = getattr(settings, "BLUESKY_HANDLE", "")
        self.app_password = getattr(settings, "BLUESKY_APP_PASSWORD", "")

    def is_configured(self) -> bool:
        return bool(self.handle and self.app_password)

    def _create_session(self) -> Mapping[str, str] | None:
        payload = json.dumps({"identifier": self.handle, "password": self.app_password}).encode("utf-8")
        endpoint = f"{self.service}/xrpc/com.atproto.server.createSession"
        request = Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                body = response.read().decode()
                if response.status >= 400:
                    logger.error("Bluesky session failed with status %s: %s", response.status, body)
                    return None
        except (HTTPError, URLError, TimeoutError) as exc:  # pragma: no cover - network
            logger.exception("Error creating Bluesky session: %s", exc)
            return None

        try:
            session = json.loads(body or "{}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON from Bluesky session response")
            return None

        if not isinstance(session.get("accessJwt"), str) or not isinstance(session.get("did"), str):
            logger.error("Bluesky session missing credentials")
            return None
        return session

    def syndicate(self, post: Post, canonical_url: str) -> str | None:
        if not self.is_configured() or not self.should_syndicate(post):
            return None

        session = self._create_session()
        if not session:
            return None

        text = self._compose_status(post, canonical_url, limit=280)
        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        payload = json.dumps({"repo": session.get("did"), "collection": "app.bsky.feed.post", "record": record}).encode("utf-8")
        endpoint = f"{self.service}/xrpc/com.atproto.repo.createRecord"
        request = Request(
            endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {session.get('accessJwt')}",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=10) as response:
                body = response.read().decode()
                if response.status >= 400:
                    logger.error("Bluesky syndication failed with status %s: %s", response.status, body)
                    return None
        except (HTTPError, URLError, TimeoutError) as exc:  # pragma: no cover - network
            logger.exception("Error posting to Bluesky: %s", exc)
            return None

        try:
            data = json.loads(body or "{}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON from Bluesky response")
            return None

        uri = data.get("uri", "")
        if not isinstance(uri, str) or not uri:
            logger.error("Bluesky response missing URI")
            return None

        rkey = uri.split("/")[-1]
        if not rkey:
            return None

        return f"https://bsky.app/profile/{self.handle}/post/{rkey}"


def _all_targets() -> List[SyndicationTarget]:
    return [MastodonTarget(), BlueskyTarget()]


def available_targets() -> List[SyndicationTarget]:
    return [target for target in _all_targets() if target.is_configured()]


def syndicate_post(post: Post, canonical_url: str, target_ids: Iterable[str] | None = None) -> dict[str, str]:
    requested = set(target_ids or [])
    results: dict[str, str] = {}

    for target in available_targets():
        if requested and target.uid not in requested:
            continue
        try:
            url = target.syndicate(post, canonical_url)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected error syndicating to %s", target.uid)
            continue

        if url:
            results[target.uid] = url
    return results
