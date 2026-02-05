import json
from urllib.parse import parse_qs

from django.http import RawPostDataException

from core.models import RequestErrorLog

DEFAULT_REDACT_HEADERS = {"authorization", "cookie"}
MAX_LOG_BODY_CHARS = 10000


def _redact_secret(value: str) -> str:
    if not value:
        return value
    if len(value) <= 12:
        return "***"
    return f"{value[:6]}...{value[-4:]}"


def _normalized_key(key: str) -> str:
    normalized = key.lower()
    if normalized.endswith("[]"):
        normalized = normalized[:-2]
    return normalized


def _redact_payload(value, redact_fields: set[str]):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_name = _normalized_key(str(key))
            if key_name in redact_fields:
                redacted[key] = _redact_sensitive(item, redact_fields)
            else:
                redacted[key] = _redact_payload(item, redact_fields)
        return redacted
    if isinstance(value, list):
        return [_redact_payload(item, redact_fields) for item in value]
    return value


def _redact_sensitive(value, redact_fields: set[str]):
    if isinstance(value, str):
        return _redact_secret(value)
    if isinstance(value, list):
        return [
            _redact_secret(item)
            if isinstance(item, str)
            else _redact_payload(item, redact_fields)
            for item in value
        ]
    if isinstance(value, dict):
        return _redact_payload(value, redact_fields)
    return value


def _truncate_body(body: str) -> str:
    if len(body) <= MAX_LOG_BODY_CHARS:
        return body
    return f"{body[:MAX_LOG_BODY_CHARS]}\n...(truncated)"


def capture_request_body(request, *, redact_fields: set[str] | None = None) -> str:
    redact_fields = {field.lower() for field in (redact_fields or set())}
    content_type = request.content_type or ""

    if content_type.startswith("multipart/"):
        fields = {key: request.POST.getlist(key) for key in request.POST.keys()}
        files = {}
        for key, items in request.FILES.lists():
            files[key] = [
                {
                    "name": item.name,
                    "size": item.size,
                    "content_type": item.content_type,
                }
                for item in items
            ]
        payload = {"fields": _redact_payload(fields, redact_fields), "files": files}
        return json.dumps(payload, indent=2, sort_keys=True)

    try:
        body_bytes = request.body or b""
    except RawPostDataException:
        if "application/x-www-form-urlencoded" in content_type:
            parsed = {key: values for key, values in request.POST.lists()}
            return _truncate_body(
                json.dumps(_redact_payload(parsed, redact_fields), indent=2, sort_keys=True)
            )
        return ""

    if not body_bytes:
        if "application/x-www-form-urlencoded" in content_type and request.POST:
            parsed = {key: values for key, values in request.POST.lists()}
            return _truncate_body(
                json.dumps(_redact_payload(parsed, redact_fields), indent=2, sort_keys=True)
            )
        return ""

    body_text = body_bytes.decode("utf-8", errors="replace")

    if "application/json" in content_type:
        try:
            parsed = json.loads(body_text)
        except json.JSONDecodeError:
            return _truncate_body(body_text)
        return _truncate_body(
            json.dumps(_redact_payload(parsed, redact_fields), indent=2, sort_keys=True)
        )

    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body_text, keep_blank_values=True)
        return _truncate_body(
            json.dumps(_redact_payload(parsed, redact_fields), indent=2, sort_keys=True)
        )

    return _truncate_body(body_text)


def capture_request_headers(request, *, redact_headers: set[str] | None = None) -> dict:
    redact_headers = {header.lower() for header in (redact_headers or DEFAULT_REDACT_HEADERS)}
    headers = dict(request.headers)
    redacted = {}
    for key, value in headers.items():
        if key.lower() in redact_headers and isinstance(value, str):
            redacted[key] = _redact_secret(value)
        else:
            redacted[key] = value
    return redacted


def extract_response_error(response) -> tuple[str, str]:
    content_type = response.get("Content-Type", "")
    body = ""
    if hasattr(response, "content"):
        body = response.content.decode("utf-8", errors="replace")
    if "application/json" in content_type and body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return "", body
        if isinstance(payload, dict):
            error = payload.get("error") or payload.get("error_description") or ""
            return str(error), body
    if body and response.status_code >= 400:
        return body.strip(), body
    return "", body


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_request_error(
    source: str,
    request,
    response,
    *,
    error: str | None = None,
    response_body: str | None = None,
    redact_fields: set[str] | None = None,
    redact_headers: set[str] | None = None,
) -> None:
    if response.status_code < 400:
        return

    if error is None or response_body is None:
        extracted_error, extracted_body = extract_response_error(response)
        if error is None:
            error = extracted_error
        if response_body is None:
            response_body = extracted_body

    RequestErrorLog.objects.create(
        source=source,
        method=request.method,
        path=request.path,
        status_code=response.status_code,
        error=error or "",
        request_headers=capture_request_headers(request, redact_headers=redact_headers),
        request_query={key: request.GET.getlist(key) for key in request.GET.keys()},
        request_body=capture_request_body(request, redact_fields=redact_fields),
        response_body=response_body or "",
        remote_addr=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        content_type=request.content_type or "",
    )
