"""
NICE — Structured insight SSE / live widget binding.

Pushes last validated HAL insight over text/event-stream so the
hal-ai-insight widget can update without a full page reload.
5s JSON poll fallback when EventSource is unavailable.
Never invents dollars; insight must already be schema-validated.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Iterator

STREAM_PATH = "/api/apex/hal/insight-stream"
LATEST_PATH = "/api/apex/hal/insight-latest"
POLL_FALLBACK_MS = 5000


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def insight_generation(insight: dict[str, Any] | None) -> str:
    if not isinstance(insight, dict):
        return "empty"
    raw = json.dumps(insight, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def insight_latest_payload() -> dict[str, Any]:
    from apex_structured_insight_pack import ai_insight_widget, load_last_insight

    insight = load_last_insight()
    widget = ai_insight_widget(insight)
    return {
        "ok": True,
        "type": "insight_snapshot",
        "phase": "N0",
        "sseStreaming": True,
        "streamPath": STREAM_PATH,
        "pollFallbackMs": POLL_FALLBACK_MS,
        "generation": insight_generation(insight),
        "insight": insight,
        "widget": widget,
        "refreshedAt": _utc_now(),
    }


def format_sse_event(payload: dict[str, Any], *, event: str = "insight") -> str:
    body = json.dumps(payload, default=str)
    return f"event: {event}\ndata: {body}\n\n"


def insight_sse_frames(
    *,
    watch_seconds: float = 0.0,
    poll_interval: float = 0.5,
) -> Iterator[str]:
    """
    Yield SSE frames. First frame is always a snapshot.
    If watch_seconds > 0, poll for generation changes and emit updates.
    """
    first = insight_latest_payload()
    yield format_sse_event(first, event="insight")
    last_gen = str(first.get("generation") or "")
    deadline = time.monotonic() + max(0.0, float(watch_seconds))
    while time.monotonic() < deadline:
        time.sleep(max(0.1, float(poll_interval)))
        cur = insight_latest_payload()
        gen = str(cur.get("generation") or "")
        if gen != last_gen:
            last_gen = gen
            cur["type"] = "insight_update"
            yield format_sse_event(cur, event="insight")
    # Terminal heartbeat so clients know stream ended cleanly
    yield format_sse_event(
        {"ok": True, "type": "stream_end", "generation": last_gen, "refreshedAt": _utc_now()},
        event="end",
    )


def sse_status() -> dict[str, Any]:
    return {
        "ok": True,
        "sseStreaming": True,
        "phase": "N0",
        "streamPath": STREAM_PATH,
        "latestPath": LATEST_PATH,
        "pollFallbackMs": POLL_FALLBACK_MS,
        "note": "EventSource on insight-stream; 5s poll fallback via insight-latest.",
        "refreshedAt": _utc_now(),
    }
