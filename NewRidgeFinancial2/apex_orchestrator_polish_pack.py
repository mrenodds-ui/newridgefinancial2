"""
Phase S3 — Orchestrator opt-in GA polish (SHOULD wave closeout).

Keeps NR2_AI_ORCHESTRATOR default OFF. Documents burn-in checklist and
exposes shouldWaveComplete status. No SSE in this phase (NICE deferred).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

BURN_IN_CHECKLIST = [
    "Set NR2_AI_ORCHESTRATOR=1 on the workstation and restart NR2.",
    "GET /api/apex/hal/orchestrator → enabled=true, phase includes S3.",
    "POST /api/apex/hal/orchestrate classifyOnly on a deep query → escalate30b.",
    "Confirm board-actions still win over LLM for sync/nav/focus.",
    "Confirm Collections/payroll empty widgets still show pending (not $0).",
    "Run 48h burn-in; rollback anytime with NR2_AI_ORCHESTRATOR=0.",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def should_wave_status() -> dict[str, Any]:
    try:
        from apex_orchestrator_pack import orchestrator_enabled, orchestrator_status

        orch = orchestrator_status()
        enabled = orchestrator_enabled()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "refreshedAt": _utc_now()}

    return {
        "ok": True,
        "phase": "S3",
        "shouldWaveComplete": True,
        "phases": ["S0", "S1", "S2", "S3"],
        "orchestratorDefault": "OFF",
        "orchestratorEnabled": enabled,
        "orchestrator": orch,
        "burnInChecklist": BURN_IN_CHECKLIST,
        "sseStreaming": False,
        "note": (
            "SHOULD wave complete. Orchestrator remains opt-in (default OFF). "
            "Flip default ON only with explicit operator approval after burn-in."
        ),
        "refreshedAt": _utc_now(),
    }


def merge_orchestrator_status(base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Enrich orchestrator_status with SHOULD-wave markers."""
    out = dict(base) if isinstance(base, dict) else {}
    out["phase"] = "S3"
    out["shouldWaveComplete"] = True
    out["mustWaveComplete"] = True
    out["shouldPhases"] = ["S0", "S1", "S2", "S3"]
    out["orchestratorDefault"] = "OFF"
    out["burnInChecklist"] = BURN_IN_CHECKLIST
    out["note"] = (
        "When enabled, Apex HAL chat uses /api/apex/hal/orchestrate after board-actions. "
        "SHOULD wave S0–S3 complete; flag default remains OFF until explicit GA flip."
    )
    return out
