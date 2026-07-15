"""Period-close OPS desk alerts via HAL hub (BlueNote has no programmatic send).

Fires when close is stalled/blocked or completes with attest_only fallback.
Cites JSONL status only — empty ≠ $0 · no SoftDent write-back.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_DIR = REPO_ROOT / "app_data" / "nr2" / "ops"
NOTIFY_STATE_PATH = OPS_DIR / "period_close_notify_state.json"

# Desk copy must stay short (hub popup + voice clip).
_KIND_LINES = {
    "stalled": "Period close stalled. Use Force Close on Pages Hub.",
    "blocked": "Period close blocked by lasers. SoftDent aging pull via Force Close.",
    "attest_only": "Period close attest-only. SoftDent GUI export failed — beams may be stale.",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_ops() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)


def _read_state() -> dict[str, Any]:
    _ensure_ops()
    if not NOTIFY_STATE_PATH.is_file():
        return {"lastKeys": []}
    try:
        raw = json.loads(NOTIFY_STATE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {"lastKeys": []}
    except Exception:
        return {"lastKeys": []}


def _write_state(state: dict[str, Any]) -> None:
    _ensure_ops()
    NOTIFY_STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def classify_period_close_trouble(result: dict[str, Any] | None) -> str | None:
    """Return trouble kind: stalled | blocked | attest_only — else None."""
    if not isinstance(result, dict):
        return None
    status = str(result.get("status") or "").lower()
    if status == "stalled":
        return "stalled"
    if status == "blocked":
        return "blocked"
    if status == "completed" and str(result.get("fallback") or "").lower() == "attest_only":
        return "attest_only"
    return None


def notify_dedupe_key(kind: str, result: dict[str, Any]) -> str:
    stamp = str(result.get("completedAt") or result.get("startedAt") or "")[:19]
    beam = str(result.get("beamHash") or "")[:12]
    return f"{kind}|{stamp}|{beam}|{result.get('actor') or ''}"


def period_close_trouble_line(kind: str, result: dict[str, Any] | None = None) -> str:
    base = _KIND_LINES.get(kind) or f"Period close trouble: {kind}."
    result = result if isinstance(result, dict) else {}
    beam = str(result.get("beamHash") or "").strip()
    if beam:
        return f"{base} Hash {beam[:8]}."
    return base


def notify_period_close_trouble(
    result: dict[str, Any] | None,
    *,
    speak: bool = True,
    store: Any | None = None,
) -> dict[str, Any]:
    """HAL hub office alert + optional browser toast. No BlueNote network send exists."""
    kind = classify_period_close_trouble(result)
    if not kind:
        return {"ok": True, "skipped": True, "reason": "not_trouble"}

    if os.environ.get("NR2_PERIOD_CLOSE_OPS_NOTIFY", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return {"ok": True, "skipped": True, "reason": "disabled"}

    assert isinstance(result, dict)
    key = notify_dedupe_key(kind, result)
    state = _read_state()
    keys = [str(k) for k in (state.get("lastKeys") or []) if k]
    if key in keys:
        return {"ok": True, "skipped": True, "reason": "deduped", "key": key, "kind": kind}

    line = period_close_trouble_line(kind, result)
    hub: dict[str, Any] = {"ok": False}
    alert: dict[str, Any] | None = None

    try:
        from hal_hub import process_pending, submit_inbound

        submit_inbound(
            "HAL Close",
            ["Office Manager", "all"],
            line,
            speak=bool(speak),
            role="hal",
            type_="period_close_ops",
        )
        hub = process_pending()
        hub["ok"] = True
        hub["line"] = line
    except Exception as exc:  # noqa: BLE001
        hub = {"ok": False, "error": str(exc)[:240]}

    if store is not None:
        try:
            from hal_alerts import create_alert

            conn = store._connect() if hasattr(store, "_connect") else None
            if conn is not None:
                titles = {
                    "stalled": "Period close stalled",
                    "blocked": "Period close blocked",
                    "attest_only": "Period close attest-only",
                }
                title = titles.get(kind, "Period close trouble")
                alert = create_alert(
                    conn,
                    alert_type="period_close",
                    severity="high" if kind in ("stalled", "blocked") else "medium",
                    title=title,
                    body=line,
                    meta={
                        "kind": kind,
                        "status": result.get("status"),
                        "fallback": result.get("fallback"),
                        "beamHash": result.get("beamHash"),
                        "emptyNotZero": True,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            alert = {"ok": False, "error": str(exc)[:240]}

    keys = ([key] + keys)[:20]
    _write_state({"lastKeys": keys, "lastKind": kind, "lastAt": _iso_now(), "lastLine": line})
    return {
        "ok": bool(hub.get("ok")),
        "kind": kind,
        "key": key,
        "line": line,
        "hub": hub,
        "alert": alert,
        "emptyNotZero": True,
    }
