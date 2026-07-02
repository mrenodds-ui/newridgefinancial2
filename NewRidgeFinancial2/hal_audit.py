"""HAL audit log for NR2 operator actions and recommendations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = REPO_ROOT / "app_data" / "nr2" / "hal_audit.jsonl"
POLICY_PATH = Path(__file__).resolve().parent / "config" / "hal_policy.yaml"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def append_audit_event(
    *,
    event_type: str,
    actor: str = "HAL",
    detail: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "ts": _utc_now(),
        "type": str(event_type or "event")[:80],
        "actor": str(actor or "HAL")[:120],
        "detail": str(detail or "")[:4000],
        "context": context or {},
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read_recent_audit(limit: int = 40) -> list[dict[str, Any]]:
    if not AUDIT_PATH.is_file():
        return []
    lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    for line in lines[-max(1, int(limit)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_hal_policy_text() -> str:
    if not POLICY_PATH.is_file():
        return ""
    try:
        return POLICY_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""
