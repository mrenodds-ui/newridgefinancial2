"""Shared HTTP helpers for clearinghouse eligibility clients."""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def read_user_env(name: str) -> str:
    """Read a Windows User environment variable when process env lacks it."""
    if sys.platform != "win32":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value or "").strip()
    except OSError:
        return ""
    except Exception:
        return ""


def resolve_env(name: str, default: str = "") -> str:
    """Prefer process env; fall back to Windows User env for keys set outside the shell."""
    if name in os.environ:
        return str(os.environ.get(name) or "").strip() or default
    return read_user_env(name) or default


def http_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    form: dict[str, Any] | None = None,
    timeout: float = 45.0,
) -> tuple[int, Any, str | None]:
    """Return (status_code, parsed_json_or_text, error_message).

    Pass ``body`` for JSON or ``form`` for application/x-www-form-urlencoded.
    """
    payload = None
    req_headers = dict(headers or {})
    if form is not None:
        encoded: list[tuple[str, str]] = []
        for key, value in form.items():
            if value is None or value == "":
                continue
            if isinstance(value, (list, tuple)):
                for item in value:
                    encoded.append((str(key), str(item)))
            else:
                encoded.append((str(key), str(value)))
        payload = urllib.parse.urlencode(encoded).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif body is not None:
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
    if name in os.environ:
        raw = os.environ.get(name)
    else:
        raw = read_user_env(name) or None
        if not raw:
            return default
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")
