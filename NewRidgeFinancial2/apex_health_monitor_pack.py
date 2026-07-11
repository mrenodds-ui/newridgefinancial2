"""
Phase S2 — Proactive practice health monitor (SHOULD wave).

Designed for Windows Task Scheduler / CLI. Requires NR2_AI_ORCHESTRATOR=1
to call the deep lane; otherwise returns a clear no-op reason.
Never invents dollars; persists audit metadata to import_health_log.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def monitor_enabled() -> bool:
    raw = str(os.getenv("NR2_HEALTH_MONITOR") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def run_scheduled_health_audit(
    *,
    classify_only: bool = False,
    force_orchestrator: bool | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """
    Daily/weekly practice health audit entrypoint.

    classify_only=True never calls Ollama (unit tests / dry-run).
    """
    if not monitor_enabled():
        return {
            "ok": False,
            "reason": "health_monitor_disabled",
            "hint": "Set NR2_HEALTH_MONITOR=1 (default on) to allow scheduled audits.",
            "refreshedAt": _utc_now(),
        }

    try:
        from apex_orchestrator_pack import orchestrate, orchestrator_enabled
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"orchestrator_import:{exc}", "refreshedAt": _utc_now()}

    enabled = orchestrator_enabled() if force_orchestrator is None else bool(force_orchestrator)
    if not enabled:
        return {
            "ok": False,
            "reason": "orchestrator_disabled",
            "hint": "Set NR2_AI_ORCHESTRATOR=1 for proactive deep-lane audits.",
            "refreshedAt": _utc_now(),
        }

    query = "Run a monthly practice health audit and cross-reference SoftDent with QuickBooks"
    result = orchestrate(
        query,
        classify_only=classify_only,
        force_enabled=True,
        require_structured=True,
    )

    # Persist lightweight audit row (no PHI)
    try:
        from apex_unified_db_pack import open_unified, unified_db_path

        flags = json.dumps(
            [
                "proactive_audit",
                str(result.get("lane") or ""),
                "classify_only" if classify_only else "full",
            ]
        )
        with open_unified(path=db_path) as conn:
            conn.execute(
                """
                INSERT INTO import_health_log (source, export_type, row_count, staleness_hours, gap_flags, detected_at)
                VALUES (?,?,?,?,?,?)
                """,
                ("health_monitor", "proactive_audit", 1, None, flags, _utc_now()),
            )
            conn.commit()
        log_path = str(db_path or unified_db_path())
    except Exception as exc:  # noqa: BLE001
        log_path = f"log_failed:{exc}"

    alert = None
    try:
        from apex_softdent_hardening_pack import assess_collections_gap
        from apex_structured_insight_pack import validate_insight

        gap = assess_collections_gap(None)
        if not gap.get("healthy"):
            payload = {
                "widget_type": "alert-banner",
                "title": "Proactive health: collections gap",
                "data": {
                    "severity": "warn",
                    "message": str(gap.get("gapCode") or "collections gap"),
                    "value": None,
                    "unit": "text",
                },
                "source_refs": ["import:health:" + datetime.now(timezone.utc).strftime("%Y-%m-%d")],
                "confidence": "medium",
                "explanation": "Scheduled audit — empty ≠ $0; fix SoftDent daysheet then Sync.",
            }
            alert = validate_insight(payload)
    except Exception as exc:  # noqa: BLE001
        alert = {"ok": False, "error": str(exc)}

    return {
        "ok": bool(result.get("ok")),
        "phase": "S2",
        "lane": result.get("lane"),
        "classifyOnly": classify_only,
        "orchestrator": result,
        "alert": alert,
        "logDb": log_path,
        "refreshedAt": _utc_now(),
    }
