"""In-memory sliding-window rate limiter — Moonshot Sprint 1."""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any

_lock = threading.RLock()
_buckets: dict[tuple[str, str], deque[float]] = {}


def _limit_for_class(route_class: str) -> int:
    env_map = {
        "read": "NR2_RATE_READ_PER_MIN",
        "mutation": "NR2_RATE_MUTATION_PER_MIN",
        "hal": "NR2_RATE_HAL_PER_MIN",
    }
    defaults = {"read": 300, "mutation": 20, "hal": 60}
    raw = os.environ.get(env_map.get(route_class, "NR2_RATE_READ_PER_MIN"), str(defaults.get(route_class, 100)))
    try:
        return max(1, int(raw))
    except ValueError:
        return defaults.get(route_class, 100)


def classify_route(path: str, method: str) -> str:
    p = str(path or "")
    m = str(method or "GET").upper()
    if "/api/hal/" in p or p == "/api/hal/evaluate-query":
        return "hal"
    if m in ("POST", "PUT", "DELETE", "PATCH"):
        return "mutation"
    return "read"


# Boot / import hot path — must not 429 during Financial page paint.
RATE_LIMIT_EXEMPT_PATHS = frozenset(
    {
        "/api/app-info",
        "/api/health",
        "/api/import-bundle",
        "/api/import-readiness",
        "/api/import-sync-status",
        "/api/import-sync-reset",
        "/api/webhooks/website-appointment",
        "/nr2-build.json",
        "/api/apex/widgets",  # Moonshot: prevent 429 warming stall
        "/api/apex/hal/orchestrate",  # Ensure HAL token auth never 429s
        "/api/browser-session",
        "/api/hal/tools/softdent-status",
        "/api/hal/tools/qb-summary",
        "/api/hal/tools/money-beams",
        "/api/hal/actions/pending",
    }
)


def is_rate_limit_exempt(path: str) -> bool:
    p = str(path or "").split("?", 1)[0]
    if p in RATE_LIMIT_EXEMPT_PATHS:
        return True
    # Prefix match for all widget sub-endpoints (e.g., /api/apex/widgets/financial)
    if p.startswith("/api/apex/widgets"):
        return True
    # HAL brains session history reads must not 429 the command center
    if p.startswith("/api/hal/session/") and p.endswith("/history"):
        return True
    return False


def is_allowed(token_fingerprint: str, route_class: str, *, window_sec: int = 60) -> tuple[bool, int]:
    limit = _limit_for_class(route_class)
    key = (str(token_fingerprint or "anon"), route_class)
    now = time.time()
    with _lock:
        dq = _buckets.get(key)
        if dq is None:
            dq = deque()
            _buckets[key] = dq
        while dq and dq[0] <= now - window_sec:
            dq.popleft()
        if len(dq) >= limit:
            retry_after = max(1, int(window_sec - (now - dq[0])) + 1) if dq else window_sec
            return False, retry_after
        dq.append(now)
        return True, 0


def reset_for_tests() -> None:
    with _lock:
        _buckets.clear()
