import threading
from typing import Any, Optional

import requests
from django.db import close_old_connections

from .models import Visit

API_URL = "https://api.apicagent.com"
REQUEST_TIMEOUT_SECONDS = 2


def _fetch_user_agent_details(user_agent: str) -> Optional[dict[str, Any]]:
    if not user_agent:
        return None

    try:
        response = requests.get(
            API_URL,
            params={"ua": user_agent},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _persist_user_agent_details(visit_id: int, user_agent: str) -> None:
    close_old_connections()
    try:
        details = _fetch_user_agent_details(user_agent)
        if details:
            Visit.objects.filter(id=visit_id).update(user_agent_details=details)
    finally:
        close_old_connections()


def enqueue_user_agent_lookup(visit_id: int, user_agent: str) -> None:
    """Fire-and-forget user agent lookup to avoid blocking responses."""
    if not visit_id or not user_agent:
        return

    thread = threading.Thread(
        target=_persist_user_agent_details, args=(visit_id, user_agent), daemon=True
    )
    thread.start()
