"""
Phase W0 — SoftDent extended metrics views/widgets (Moonshot REAUDIT5 MUST).

Exposes v_case_acceptance, v_patient_aging, v_scheduling_efficiency over T0/T1 tables.
Honesty: empty ≠ $0; gap codes when views empty. No SoftDent write-back. No patient PHI.
Flag: NR2_EXTENDED_METRICS (default ON; set 0 to hide W0 widgets).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GAP_AGING_DATA_PENDING = "AGING_DATA_PENDING"
GAP_CASE_ACCEPT_DATA_PENDING = "CASE_ACCEPT_DATA_PENDING"
GAP_SCHEDULE_DATA_PENDING = "SCHEDULE_DATA_PENDING"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def extended_metrics_enabled() -> bool:
    raw = str(os.getenv("NR2_EXTENDED_METRICS") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def calculate_case_acceptance(
    treatment_planned: float | None,
    treatment_accepted: float | None,
) -> dict[str, Any]:
    """Ratio 0–1; null + gap when inputs empty. Never invent dollars."""
    if treatment_planned is None or treatment_accepted is None:
        return {
            "ok": True,
            "acceptanceRate": None,
            "confidence": "none",
            "gapCode": GAP_CASE_ACCEPT_DATA_PENDING,
            "honesty": "empty_not_zero",
        }
    planned = float(treatment_planned)
    accepted = float(treatment_accepted)
    if planned <= 0:
        return {
            "ok": True,
            "acceptanceRate": None,
            "confidence": "low",
            "gapCode": GAP_CASE_ACCEPT_DATA_PENDING,
            "treatmentPlanned": planned,
            "treatmentAccepted": accepted,
            "honesty": "empty_not_zero",
        }
    rate = round(accepted / planned, 4)
    return {
        "ok": True,
        "acceptanceRate": rate,
        "confidence": "low" if planned < 5000 else "high",
        "treatmentPlanned": planned,
        "treatmentAccepted": accepted,
        "gapCode": None,
    }


def build_scheduling_efficiency(
    scheduled_production: float | None,
    actual_production: float | None,
) -> dict[str, Any]:
    """Schedule accuracy = actual / scheduled when both present."""
    if scheduled_production is None or actual_production is None:
        return {
            "ok": True,
            "scheduleAccuracy": None,
            "gapCode": GAP_SCHEDULE_DATA_PENDING,
            "honesty": "empty_not_zero",
            "scheduledProduction": scheduled_production,
            "actualProduction": actual_production,
        }
    sched = float(scheduled_production)
    actual = float(actual_production)
    if sched <= 0:
        return {
            "ok": True,
            "scheduleAccuracy": None,
            "gapCode": GAP_SCHEDULE_DATA_PENDING,
            "honesty": "empty_not_zero",
            "scheduledProduction": sched,
            "actualProduction": actual,
        }
    return {
        "ok": True,
        "scheduleAccuracy": round(actual / sched, 4),
        "scheduledProduction": sched,
        "actualProduction": actual,
        "gapCode": None,
    }


def extended_metrics_status(*, db_path: Path | None = None) -> dict[str, Any]:
    from apex_unified_db_pack import (
        list_case_acceptance,
        list_patient_aging,
        list_scheduling_efficiency,
    )

    case_rows = list_case_acceptance(limit=3, db_path=db_path)
    aging_rows = list_patient_aging(limit=3, db_path=db_path)
    sched_rows = list_scheduling_efficiency(limit=3, db_path=db_path)
    return {
        "ok": True,
        "phase": "W0",
        "enabled": extended_metrics_enabled(),
        "flag": "NR2_EXTENDED_METRICS",
        "views": {
            "v_case_acceptance": len(case_rows),
            "v_patient_aging": len(aging_rows),
            "v_scheduling_efficiency": len(sched_rows),
        },
        "softDentWriteBack": False,
        "refreshedAt": _utc_now(),
    }


def extended_metrics_widgets(
    bundle: dict[str, Any] | None = None,
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    del bundle
    if not extended_metrics_enabled():
        return [
            {
                "id": "softdent-extended-metrics",
                "type": "status",
                "label": "SoftDent Extended (W0)",
                "size": "full",
                "status": "empty",
                "message": "Extended metrics disabled",
                "hint": "Set NR2_EXTENDED_METRICS=1 (default on).",
            }
        ]

    from apex_unified_db_pack import (
        list_case_acceptance,
        list_patient_aging,
        list_scheduling_efficiency,
    )

    out: list[dict[str, Any]] = []
    case_rows = list_case_acceptance(limit=5, db_path=db_path)
    if not case_rows:
        out.append(
            {
                "id": "v-case-acceptance",
                "type": "status",
                "label": "Case Acceptance (W0)",
                "size": "full",
                "status": "empty",
                "gapCode": GAP_CASE_ACCEPT_DATA_PENDING,
                "message": GAP_CASE_ACCEPT_DATA_PENDING,
                "emptyMessage": "No case acceptance rows — empty ≠ $0.",
                "hint": "Import case_acceptance*.csv then Sync → v_case_acceptance.",
            }
        )
    else:
        latest = case_rows[0]
        rate = latest.get("acceptanceRate")
        out.append(
            {
                "id": "v-case-acceptance",
                "type": "status",
                "label": "Case Acceptance (W0)",
                "size": "full",
                "status": "ok",
                "message": (
                    f"{latest.get('period')}: rate={rate} "
                    f"planned={latest.get('treatmentPlanned')} "
                    f"accepted={latest.get('treatmentAccepted')} "
                    f"({latest.get('confidence')})"
                ),
                "hint": "From v_case_acceptance (import-mirrored).",
                "rows": case_rows,
            }
        )

    aging_rows = list_patient_aging(limit=5, db_path=db_path)
    if not aging_rows:
        out.append(
            {
                "id": "v-patient-aging",
                "type": "status",
                "label": "Patient Aging (W0)",
                "size": "full",
                "status": "empty",
                "gapCode": GAP_AGING_DATA_PENDING,
                "message": GAP_AGING_DATA_PENDING,
                "emptyMessage": "No aging summary — empty ≠ $0. Bucket totals only (no PHI).",
                "hint": "Import softdent_ar_aging*.csv then Sync → v_patient_aging.",
            }
        )
    else:
        latest = aging_rows[0]
        out.append(
            {
                "id": "v-patient-aging",
                "type": "status",
                "label": "Patient Aging (W0)",
                "size": "full",
                "status": "ok",
                "message": (
                    f"{latest.get('period')}: totalAR={latest.get('totalAr')} "
                    f"0-30={latest.get('bucket0_30')} 31-60={latest.get('bucket31_60')} "
                    f"61-90={latest.get('bucket61_90')} 90+={latest.get('bucket90Plus')}"
                ),
                "hint": "From v_patient_aging — summary buckets only.",
                "rows": aging_rows,
            }
        )

    sched_rows = list_scheduling_efficiency(limit=5, db_path=db_path)
    if not sched_rows:
        out.append(
            {
                "id": "v-scheduling-efficiency",
                "type": "status",
                "label": "Scheduling Efficiency (W0)",
                "size": "full",
                "status": "empty",
                "gapCode": GAP_SCHEDULE_DATA_PENDING,
                "message": GAP_SCHEDULE_DATA_PENDING,
                "emptyMessage": "No scheduling rows — empty ≠ $0.",
                "hint": "Import operatory/schedule (rows or operatoryChairs[]) then Sync.",
            }
        )
    else:
        latest = sched_rows[0]
        acc = latest.get("scheduleAccuracy")
        fill = latest.get("fillRate")
        out.append(
            {
                "id": "v-scheduling-efficiency",
                "type": "status",
                "label": "Scheduling Efficiency (W0)",
                "size": "full",
                "status": "ok",
                "message": (
                    f"{latest.get('period')}: fill={fill} "
                    f"accuracy={acc if acc is not None else '—'} "
                    f"appts={latest.get('totalAppointments')}"
                ),
                "hint": (
                    "From v_scheduling_efficiency — accuracy needs ScheduledProduction; "
                    "fill may be null when capacity unknown (chairs-only)."
                ),
                "rows": sched_rows,
            }
        )

    return out
