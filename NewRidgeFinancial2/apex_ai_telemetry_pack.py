"""
Phase V0 — AI lane health telemetry (Moonshot REAUDIT4 MUST).

Records lane latency/errors without PHI or dollar amounts.
Flag: NR2_AI_TELEMETRY (default OFF until burn-in — Moonshot V0).
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ERROR_RATE_ALERT = 0.25  # 25% errors in window → alert
WINDOW_SEC = 3600
MAX_EVENTS = 500


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def telemetry_enabled() -> bool:
    raw = str(os.getenv("NR2_AI_TELEMETRY") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _store_path() -> Path:
    override = str(os.getenv("NR2_AI_TELEMETRY_STORE") or "").strip()
    if override:
        return Path(override)
    try:
        from document_sync import NR2_DATA_DIR

        return Path(NR2_DATA_DIR) / "ai_lane_telemetry.json"
    except Exception:
        return Path(__file__).resolve().parent / "app_data" / "nr2" / "ai_lane_telemetry.json"


def _load() -> dict[str, Any]:
    path = _store_path()
    if not path.is_file():
        return {"events": [], "updatedAt": None}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {"events": []}
    except Exception:
        return {"events": []}


def _save(data: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updatedAt"] = _utc_now()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _query_fingerprint(query: str) -> str:
    """Non-reversible length+hash — never store query text (may contain $ / PHI)."""
    raw = str(query or "")
    digest = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"qlen:{len(raw)}:h:{digest}"


def record_lane_event(
    *,
    lane: str,
    ok: bool,
    latency_ms: float,
    classify_only: bool = False,
    query: str = "",
    error: str | None = None,
) -> dict[str, Any]:
    if not telemetry_enabled():
        return {"ok": False, "reason": "telemetry_disabled", "recorded": False}

    lane_key = str(lane or "unknown").strip()[:32] or "unknown"
    # Never persist error strings that might echo user content — code only
    err_code = None
    if error:
        err_code = re_safe_error(error)

    event = {
        "ts": time.time(),
        "at": _utc_now(),
        "lane": lane_key,
        "ok": bool(ok),
        "latencyMs": round(max(0.0, float(latency_ms)), 1),
        "classifyOnly": bool(classify_only),
        "q": _query_fingerprint(query),
        "errorCode": err_code,
    }
    data = _load()
    events = data.get("events") if isinstance(data.get("events"), list) else []
    events.append(event)
    data["events"] = events[-MAX_EVENTS:]
    _save(data)
    return {"ok": True, "recorded": True, "event": {k: event[k] for k in ("lane", "ok", "latencyMs", "at")}}


def re_safe_error(error: str) -> str:
    text = str(error or "").lower()
    for token in (
        "timeout",
        "connection",
        "orchestrator_disabled",
        "no_json",
        "schema",
        "phi",
        "ollama",
        "http",
        "disabled",
    ):
        if token in text:
            return token
    return "error"


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    try:
        return float(statistics.quantiles(values, n=100)[max(0, min(98, int(p) - 1))])
    except Exception:
        values_sorted = sorted(values)
        idx = int(round((p / 100.0) * (len(values_sorted) - 1)))
        return float(values_sorted[idx])


def lane_health(*, window_sec: float = WINDOW_SEC) -> dict[str, Any]:
    """Aggregate last-window stats per lane — no PHI/$."""
    now = time.time()
    cutoff = now - max(60.0, float(window_sec))
    data = _load()
    events = [
        e
        for e in (data.get("events") if isinstance(data.get("events"), list) else [])
        if isinstance(e, dict) and float(e.get("ts") or 0) >= cutoff
    ]
    lanes: dict[str, dict[str, Any]] = {}
    for e in events:
        lane = str(e.get("lane") or "unknown")
        slot = lanes.setdefault(
            lane,
            {"calls": 0, "errors": 0, "latencies": []},
        )
        slot["calls"] += 1
        if not e.get("ok"):
            slot["errors"] += 1
        try:
            slot["latencies"].append(float(e.get("latencyMs") or 0))
        except (TypeError, ValueError):
            pass

    out_lanes: dict[str, Any] = {}
    alerts: list[str] = []
    for lane, slot in lanes.items():
        calls = int(slot["calls"])
        errors = int(slot["errors"])
        lats: list[float] = slot["latencies"]
        err_rate = (errors / calls) if calls else 0.0
        summary = {
            "calls_1h": calls,
            "errors_1h": errors,
            "error_rate": round(err_rate, 4),
            "latency_p50_ms": _percentile(lats, 50),
            "latency_p95_ms": _percentile(lats, 95),
        }
        out_lanes[lane] = summary
        if calls >= 4 and err_rate >= DEFAULT_ERROR_RATE_ALERT:
            alerts.append(lane)

    return {
        "ok": True,
        "phase": "V0",
        "enabled": telemetry_enabled(),
        "flag": "NR2_AI_TELEMETRY",
        "windowSec": int(window_sec),
        "lanes": out_lanes,
        "alertLanes": alerts,
        "eventCount": len(events),
        "refreshedAt": _utc_now(),
    }


def maybe_emit_telemetry_alert(health: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Emit alert-banner when error rate high — value null, no $."""
    if not telemetry_enabled():
        return None
    h = health or lane_health()
    alerts = h.get("alertLanes") if isinstance(h.get("alertLanes"), list) else []
    if not alerts:
        return None
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {
        "widget_type": "alert-banner",
        "title": "AI lane health alert",
        "data": {
            "severity": "warn",
            "message": (
                f"Elevated error rate on lane(s): {', '.join(str(a) for a in alerts[:4])}. "
                "Check Ollama / orchestrator — no dollar figures inferred."
            )[:400],
            "value": None,
            "unit": "text",
        },
        "source_refs": [f"nr2:ai_telemetry:{day}"],
        "confidence": "medium",
        "explanation": "V0 telemetry — latency/error counters only; query text not stored.",
        "action_cta": {"label": "Open HAL", "route": "hal"},
    }
    try:
        from apex_structured_insight_pack import ai_insight_widget, save_last_insight, validate_insight

        validated = validate_insight(payload)
        if validated.get("ok") and isinstance(validated.get("insight"), dict):
            save_last_insight(validated["insight"])
            return {
                "ok": True,
                "insight": validated["insight"],
                "insightWidget": ai_insight_widget(validated["insight"]),
            }
        return {"ok": False, "error": validated.get("error")}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def telemetry_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    del bundle
    if not telemetry_enabled():
        return {
            "id": "ai-lane-health",
            "type": "status",
            "label": "AI Lane Health (V0)",
            "size": "full",
            "status": "empty",
            "message": "Telemetry OFF",
            "emptyMessage": "Set NR2_AI_TELEMETRY=1 for burn-in lane metrics.",
            "hint": "Default OFF per Moonshot V0 until burn-in.",
        }
    h = lane_health()
    lanes = h.get("lanes") if isinstance(h.get("lanes"), dict) else {}
    if not lanes:
        return {
            "id": "ai-lane-health",
            "type": "status",
            "label": "AI Lane Health (V0)",
            "size": "full",
            "status": "ok",
            "message": "No lane calls in last hour",
            "hint": "Counters populate after orchestrator runs (no PHI stored).",
        }
    parts = []
    for lane, s in list(lanes.items())[:4]:
        if not isinstance(s, dict):
            continue
        parts.append(
            f"{lane}: p50={s.get('latency_p50_ms')}ms err={s.get('errors_1h')}/{s.get('calls_1h')}"
        )
    return {
        "id": "ai-lane-health",
        "type": "status",
        "label": "AI Lane Health (V0)",
        "size": "full",
        "status": "warn" if h.get("alertLanes") else "ok",
        "message": " · ".join(parts) if parts else "Telemetry active",
        "hint": "Latency/error only — query text redacted to fingerprint.",
        "lanes": lanes,
    }
