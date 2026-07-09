"""Shared HTTP helpers for clearinghouse eligibility clients."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any


def http_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 45.0,
) -> tuple[int, Any, str | None]:
    """Return (status_code, parsed_json_or_text, error_message)."""
    payload = None
    req_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=payload, headers=req_headers, method=str(method or "GET").upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = int(getattr(resp, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        status = int(exc.code or 500)
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
    except urllib.error.URLError as exc:
        return 0, None, str(exc.reason or exc)
    except Exception as exc:
        return 0, None, str(exc)

    if not raw:
        return status, None, None
    try:
        return status, json.loads(raw), None
    except json.JSONDecodeError:
        return status, raw, None


def redact_member_id(member_id: str) -> str:
    value = str(member_id or "").strip()
    if not value:
        return ""
    if value.startswith("***"):
        return value[:32]
    tail = value[-4:] if len(value) >= 4 else value
    return f"***{tail}"


def env_bool(name: str, default: bool = False) -> bool:
    import os

    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")
