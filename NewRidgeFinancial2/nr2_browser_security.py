"""Loopback browser security — Moonshot Phases A, F, D, F2 + SessionVault."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
from typing import Any

import bottle

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = frozenset(
    {
        "127.0.0.1:8765",
        "127.0.0.1:8766",
        "[::1]:8765",
        "[::1]:8766",
        "localhost:8765",
        "localhost:8766",
        "127.0.0.1",
        "localhost",
        "[::1]",
    }
)

CSP_BROWSER = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "connect-src 'self' http://127.0.0.1:* http://localhost:* https://127.0.0.1:* https://localhost:* "
    "ws://127.0.0.1:* ws://localhost:* wss://127.0.0.1:* wss://localhost:*; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)

FINANCIAL_READ_PREFIXES = (
    "/api/import-bundle",
    "/api/financial-reports",
    "/api/apex/widgets",
    "/api/apex/ticker",
    "/api/apex/hal",
    "/api/apex/narratives",
    "/api/apex/claims",
    "/api/apex/claims-aging",
    "/api/apex/tax-returns",
    "/api/apex/scenarios",
    "/api/apex/filing",
    "/api/apex/workpapers",
    "/api/apex/audit",
    "/api/apex/citations",
    "/api/apex/softdent",
    "/api/daily-closeout",
    "/api/posting-queue",
    "/api/financial/post-queue",
    "/api/integration-health",
    "/api/documents-state",
)

FINANCIAL_INTENT_PATTERNS = (
    "revenue",
    "collection",
    "ar ",
    "a/r",
    "receivable",
    "profit",
    "loss",
    "ebitda",
    "tax",
    "posting",
    "ledger",
    "reconcil",
    "month-end",
    "month end",
    "cash flow",
    "project",
    "forecast",
    "production mtd",
    "quickbooks",
    "financial",
    "claim status",
    "aging",
    "owe",
    "balance",
    "paid",
    "bill",
    "money",
    "amount due",
    "outstanding",
    "insurance",
    "eob",
)

FINANCIAL_INTENT_RE = re.compile(
    r"(?i)\b(owe|balance|paid|bill|money|amount\s*due|outstanding|receivable|insurance|eob|era)\b"
)

_TOKEN_ROTATE_SECONDS = 900


class SessionVault:
    """Single-use token rotation — Moonshot: zero grace period."""

    def __init__(self) -> None:
        self._by_token: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def register(self, token: str, *, ua: str = "", role: str | None = None) -> None:
        if not token:
            return
        from nr2_rbac import current_role

        with self._lock:
            existing = self._by_token.get(token)
            if existing:
                if ua:
                    existing["ua"] = ua
                if role is not None:
                    existing["role"] = role
                return
            self._by_token[token] = {
                "ua": ua,
                "issued_at": time.time(),
                "role": role or current_role(),
            }

    def has_session(self, token: str) -> bool:
        with self._lock:
            return token in self._by_token

    def validate(self, token: str, ua: str) -> bool:
        with self._lock:
            sess = self._by_token.get(token)
            if not sess:
                return False
            if sess.get("ua") and ua and sess["ua"] != ua:
                return False
            return True

    def bind_user_agent(self, token: str, ua: str) -> None:
        with self._lock:
            if token in self._by_token:
                self._by_token[token]["ua"] = ua
            else:
                self.register(token, ua=ua)

    def rotate(self, old_token: str) -> str | None:
        with self._lock:
            sess = self._by_token.get(old_token)
            if not sess:
                return None
            if time.time() - float(sess.get("issued_at") or 0) < _TOKEN_ROTATE_SECONDS:
                return None
            self._by_token.pop(old_token, None)
            new_token = secrets.token_hex(32)
            self._by_token[new_token] = {
                "ua": sess.get("ua") or "",
                "issued_at": time.time(),
                "role": sess.get("role"),
            }
            return new_token

    def invalidate(self, token: str) -> None:
        with self._lock:
            self._by_token.pop(token, None)

    def session_role(self, token: str) -> str | None:
        with self._lock:
            sess = self._by_token.get(token)
            return str(sess.get("role")) if sess else None


_session_vault = SessionVault()


def session_vault() -> SessionVault:
    return _session_vault


def token_fingerprint(token: str | None) -> str:
    raw = str(token or "anon")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def normalize_host(host: str) -> str:
    h = str(host or "").strip().lower()
    if h.startswith("[") and "]" in h:
        return h
    if ":" in h and not h.startswith("["):
        return h
    return h


def host_allowed() -> bool:
    raw = bottle.request.headers.get("Host") or ""
    host = normalize_host(raw)
    if not host:
        return False
    if host.endswith(".localhost"):
        logger.warning("NR2 rejected Host (subdomain.localhost): %s", raw)
        return False
    if host in ALLOWED_HOSTS:
        return True
    base = host.split(":", 1)[0]
    if base in {"127.0.0.1", "localhost", "[::1]"}:
        return True
    logger.warning("NR2 rejected Host: %s remote=%s", raw, getattr(bottle.request, "remote_addr", ""))
    return False


def _loopback_origin_allowed(origin_norm: str, host: str) -> bool:
    allowed = {
        "http://127.0.0.1",
        "http://localhost",
        "http://[::1]",
        "https://127.0.0.1",
        "https://localhost",
        "https://[::1]",
    }
    for port in ("8765", "8766"):
        allowed.add(f"http://127.0.0.1:{port}")
        allowed.add(f"http://localhost:{port}")
        allowed.add(f"http://[::1]:{port}")
        allowed.add(f"https://127.0.0.1:{port}")
        allowed.add(f"https://localhost:{port}")
        allowed.add(f"https://[::1]:{port}")
    if host:
        allowed.add(f"http://{host.rstrip('/')}")
        allowed.add(f"https://{host.rstrip('/')}")
    if origin_norm in allowed:
        return True
    return (
        origin_norm.startswith("http://127.0.0.1")
        or origin_norm.startswith("http://localhost")
        or origin_norm.startswith("https://127.0.0.1")
        or origin_norm.startswith("https://localhost")
    )


def origin_allowed_for_mutation() -> bool:
    origin = bottle.request.headers.get("Origin")
    host = normalize_host(bottle.request.headers.get("Host") or "")
    # Opaque "null" Origin is never accepted (CSRF / sandboxed attacker).
    if origin is not None and str(origin).strip().lower() == "null":
        return False
    if origin is not None and str(origin).strip():
        origin_norm = str(origin).strip().lower().rstrip("/")
        return _loopback_origin_allowed(origin_norm, host)
    # Some same-origin POSTs omit Origin; accept matching loopback Referer only.
    referer = str(bottle.request.headers.get("Referer") or "").strip()
    if not referer:
        return False
    try:
        from urllib.parse import urlparse

        parsed = urlparse(referer)
        if parsed.scheme not in ("http", "https"):
            return False
        referer_origin = f"{parsed.scheme}://{parsed.netloc}".lower().rstrip("/")
    except Exception:
        return False
    return _loopback_origin_allowed(referer_origin, host)


def bind_session_user_agent(session_token: str) -> None:
    ua = str(bottle.request.headers.get("User-Agent") or "")
    if session_token:
        _session_vault.bind_user_agent(session_token, ua)


def register_browser_session(session_token: str) -> None:
    ua = str(bottle.request.headers.get("User-Agent") or "")
    _session_vault.register(session_token, ua=ua)


def user_agent_binding_valid(session_token: str) -> bool:
    ua = str(bottle.request.headers.get("User-Agent") or "")
    return _session_vault.validate(session_token, ua)


def mutation_auth_failure_reason(session_token: str | None) -> str | None:
    if not host_allowed():
        return "host_rejected"
    token = str(bottle.request.headers.get("X-NR2-Session-Token") or "").strip()
    if not session_token or token != session_token:
        return "token_invalid"
    if not user_agent_binding_valid(session_token):
        return "binding_invalid"
    # Loopback + matching session token is the CSRF control. Some same-origin POSTs
    # (extensions, privacy tools, certain embeds) omit Origin/Referer and used to 403 HAL.
    if not origin_allowed_for_mutation():
        if host_allowed():
            return None
        return "origin_rejected"
    return None


def maybe_rotate_session_token(current: str) -> tuple[str, bool]:
    new_token = _session_vault.rotate(current)
    if new_token:
        return new_token, True
    return current, False


FINANCIAL_READ_EXEMPT = frozenset(
    {
        "/api/app-info",
        "/api/import-readiness",
        "/api/import-sync-status",
        "/api/import-bundle",
        "/api/hal/import-guard",
        "/api/hal/evaluate-query",
        "/api/settings/cloud-hal",
        "/api/health",
        "/api/ocr-exceptions",
        # Local SQLite posting queue is readable during import sync; writes stay gated.
        "/api/posting-queue",
        "/api/financial/post-queue",
    }
)


def financial_read_path(path: str) -> bool:
    p = path or ""
    if p in FINANCIAL_READ_EXEMPT:
        return False
    return any(p == prefix or p.startswith(prefix + "/") for prefix in FINANCIAL_READ_PREFIXES)


def classify_financial_query(query: str) -> bool:
    q = str(query or "").lower()
    if any(pat in q for pat in FINANCIAL_INTENT_PATTERNS):
        return True
    return bool(FINANCIAL_INTENT_RE.search(q))


def import_guard_response(readiness: dict[str, Any], *, financial_intent: bool = False) -> dict[str, Any]:
    level = str(readiness.get("level") or "unknown")
    ok = bool(readiness.get("ok"))
    if financial_intent and level != "fresh":
        return {
            "blocked": True,
            "error": "HAL_UNAVAILABLE_STALE_DATA",
            "readiness": readiness,
            "message": "Import data is not current. Refresh imports before financial HAL answers.",
        }
    if not ok and financial_intent:
        return {
            "blocked": True,
            "error": "HAL_UNAVAILABLE_STALE_DATA",
            "readiness": readiness,
        }
    return {"blocked": False, "readiness": readiness}


def apply_browser_security_headers(rotated_token: str | None = None) -> None:
    bottle.response.headers["Content-Security-Policy"] = CSP_BROWSER
    bottle.response.headers["X-Content-Type-Options"] = "nosniff"
    bottle.response.headers["X-Frame-Options"] = "DENY"
    if rotated_token:
        bottle.response.headers["X-NR2-Refresh-Token"] = rotated_token


def abort_browser_auth(reason: str, detail: str, *, recovery_token: str | None = None) -> None:
    payload = json.dumps({"ok": False, "error": "browser_mutation_forbidden", "reason": reason, "detail": detail})
    headers = {
        "Content-Type": "application/json",
        "Content-Security-Policy": CSP_BROWSER,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
    if recovery_token and reason in ("token_invalid", "binding_invalid"):
        # Help the UI recover after NR2 restart/rotation without weakening checks.
        headers["X-NR2-Refresh-Token"] = recovery_token
    # HTTPResponse keeps custom headers; bottle.abort() often renders the HTML error page.
    raise bottle.HTTPResponse(body=payload, status=403, headers=headers)


def abort_import_read(readiness: dict[str, Any]) -> None:
    bottle.response.content_type = "application/json"
    bottle.response.set_header("X-NR2-Import-Status", str(readiness.get("level") or "unknown"))
    payload = json.dumps(
        {
            "ok": False,
            "error": "import_read_forbidden",
            "readiness": readiness,
        }
    )
    raise bottle.HTTPResponse(
        body=payload,
        status=403,
        headers={
            "Content-Type": "application/json",
            "X-NR2-Import-Status": str(readiness.get("level") or "unknown"),
            "Content-Security-Policy": CSP_BROWSER,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )
