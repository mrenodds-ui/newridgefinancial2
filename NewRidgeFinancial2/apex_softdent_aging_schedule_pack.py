"""
Phase T1 — SoftDent patient aging (summary buckets) + scheduling → nr2_unified.

PHI: store bucket totals only — never patient names/DOB.
Honesty: AGING_PENDING / SCHEDULING_PENDING when missing (never $0).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

GAP_OK = "OK"
GAP_AGING_PENDING = "AGING_PENDING"
GAP_SCHEDULING_PENDING = "SCHEDULING_PENDING"

FIX_HINT_AGING = (
    "Drop SoftDent Insurance/Patient Aging *summary* export "
    "(softdent_ar_aging*.csv / patient_aging.csv) — bucket totals only, then Sync. Empty ≠ $0."
)
FIX_HINT_SCHED = (
    "Drop SoftDent appointment/schedule analysis or operatory export, then Sync. Empty ≠ $0."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    return _parse_money(value)


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _period_key(row: dict[str, Any], default: str = "current") -> str:
    return str(row.get("period") or row.get("year_month") or row.get("Period") or default).strip()[:32] or default


def _sd_rows(bundle: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(bundle, dict):
        return []
    try:
        from apex_backend import _section_rows

        rows = _section_rows(bundle, "softdent", key) or []
        return [r for r in rows if isinstance(r, dict)]
    except Exception:
        sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        block = sd.get(key) if isinstance(sd.get(key), dict) else {}
        rows = block.get("rows") if isinstance(block.get("rows"), list) else []
        return [r for r in rows if isinstance(r, dict)]


def _operatory_chairs(bundle: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(bundle, dict):
        return []
    sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    op = sd.get("operatory") if isinstance(sd.get("operatory"), dict) else {}
    chairs = op.get("operatoryChairs") if isinstance(op.get("operatoryChairs"), list) else []
    return [c for c in chairs if isinstance(c, dict)]


def _schedule_source_rows(bundle: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Prefer explicit schedule/operatory rows; else derive from operatoryChairs[] slots."""
    rows = _sd_rows(bundle, "operatory")
    if rows:
        return rows
    chairs = _operatory_chairs(bundle)
    if not chairs:
        return []
    slot_count = 0
    for chair in chairs:
        slots = chair.get("slots")
        if isinstance(slots, list):
            slot_count += len(slots)
    # Capacity unknown from chairs alone — appointments only; fill_rate stays null unless slots>0.
    return [
        {
            "period": "current",
            "Appointments": slot_count,
            "Broken": 0,
            "Capacity": None,
            "Used": None,
            "source": "operatoryChairs",
        }
    ]


def _insurance_pending_total(rows: list[dict[str, Any]]) -> float | None:
    total = 0.0
    found = False
    for row in rows:
        amt = _parse_money(
            row.get("InsPending")
            or row.get("insurance_pending")
            or row.get("InsurancePending")
            or row.get("InsAR")
        )
        if amt is not None:
            total += amt
            found = True
    return total if found else None


def _scheduled_production_total(rows: list[dict[str, Any]]) -> float | None:
    total = 0.0
    found = False
    for row in rows:
        amt = _parse_money(
            row.get("ScheduledProduction")
            or row.get("scheduled_production")
            or row.get("ProdScheduled")
            or row.get("ProductionScheduled")
        )
        if amt is not None:
            total += amt
            found = True
    return total if found else None


def _bucket_from_aging_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Roll detail or summary rows into aging buckets — amounts only."""
    buckets = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    for row in rows:
        # Summary-style columns
        for key, bucket in (
            ("bucket_0_30", "0-30"),
            ("Bucket0_30", "0-30"),
            ("Current", "0-30"),
            ("0-30", "0-30"),
            ("bucket_31_60", "31-60"),
            ("31-60", "31-60"),
            ("bucket_61_90", "61-90"),
            ("61-90", "61-90"),
            ("bucket_90_plus", "90+"),
            ("90+", "90+"),
            ("Over90", "90+"),
        ):
            amt = _parse_money(row.get(key))
            if amt is not None:
                buckets[bucket] += amt
        # Detail-style: Balance + Age/Days
        bal = _parse_money(row.get("Balance") or row.get("Outstanding") or row.get("Amount"))
        age = _parse_int(row.get("Age") or row.get("Days") or row.get("AgingDays"))
        if bal is None:
            continue
        label = str(row.get("Bucket") or row.get("AgingBucket") or row.get("Range") or "").lower()
        if "90" in label or "over" in label:
            buckets["90+"] += bal
        elif "61" in label or "60-90" in label:
            buckets["61-90"] += bal
        elif "31" in label:
            buckets["31-60"] += bal
        elif "0-30" in label or "current" in label:
            buckets["0-30"] += bal
        elif age is not None:
            if age <= 30:
                buckets["0-30"] += bal
            elif age <= 60:
                buckets["31-60"] += bal
            elif age <= 90:
                buckets["61-90"] += bal
            else:
                buckets["90+"] += bal
    return buckets


def assess_aging_schedule_gap(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    aging = _sd_rows(bundle, "ar")
    sched = _schedule_source_rows(bundle)
    issues: list[str] = []
    if not aging:
        issues.append("SoftDent A/R / patient aging summary not in bundle.")
    if not sched:
        issues.append("SoftDent scheduling/operatory export not in bundle.")
    if not aging and not sched:
        gap = GAP_AGING_PENDING
    elif not aging:
        gap = GAP_AGING_PENDING
    elif not sched:
        gap = GAP_SCHEDULING_PENDING
    else:
        gap = GAP_OK
    return {
        "ok": True,
        "gapCode": gap,
        "healthy": gap == GAP_OK,
        "agingPending": not bool(aging),
        "schedulingPending": not bool(sched),
        "agingRowCount": len(aging),
        "schedulingRowCount": len(sched),
        "fromOperatoryChairs": bool(_operatory_chairs(bundle)) and not bool(_sd_rows(bundle, "operatory")),
        "fixHint": None if gap == GAP_OK else (FIX_HINT_AGING if not aging else FIX_HINT_SCHED),
        "issues": issues,
        "honesty": "empty_not_zero" if gap != GAP_OK else "reported",
        "checkedAt": _utc_now(),
    }


def ingest_aging_schedule_into_conn(
    conn: Any,
    bundle: dict[str, Any] | None,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    stamp = now or _utc_now()
    aging_rows = _sd_rows(bundle, "ar")
    sched_rows = _schedule_source_rows(bundle)
    aging_n = 0
    sched_n = 0

    if aging_rows:
        buckets = _bucket_from_aging_rows(aging_rows)
        total = sum(buckets.values())
        ins_pending = _insurance_pending_total(aging_rows)
        # Prefer period on first row
        period = _period_key(aging_rows[0]) if aging_rows else "current"
        conn.execute("DELETE FROM softdent_patient_aging WHERE period = ? AND source = ?", (period, "import_bundle"))
        conn.execute(
            """
            INSERT INTO softdent_patient_aging (
                period, bucket_0_30, bucket_31_60, bucket_61_90, bucket_90_plus,
                total_ar, insurance_pending, source_file, source, ingested_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                period,
                buckets["0-30"],
                buckets["31-60"],
                buckets["61-90"],
                buckets["90+"],
                total if total else None,
                ins_pending,
                None,
                "import_bundle",
                stamp,
            ),
        )
        aging_n = 1

    if sched_rows:
        # Aggregate operatory/schedule rows into one period summary
        period = _period_key(sched_rows[0]) if sched_rows else "current"
        total_appts = 0
        broken = 0
        capacity = 0.0
        used = 0.0
        for row in sched_rows[:500]:
            total_appts += _parse_int(row.get("total_appointments") or row.get("Appointments") or row.get("Slots")) or 0
            broken += _parse_int(row.get("broken_appointments") or row.get("Broken") or row.get("NoShow")) or 0
            capacity += _parse_float(row.get("capacity_hours") or row.get("Capacity") or row.get("AvailableHours")) or 0.0
            used += _parse_float(row.get("used_hours") or row.get("Used") or row.get("BookedHours")) or 0.0
            # Chair util style: UtilPct
            util = _parse_float(row.get("UtilPct") or row.get("fill_rate") or row.get("Utilization"))
            if util is not None and capacity <= 0 and used <= 0:
                # treat as fill rate percent on synthetic capacity
                capacity += 100.0
                used += float(util) if util <= 1 else float(util)
        fill = None
        from_chairs = any(str(row.get("source") or "") == "operatoryChairs" for row in sched_rows)
        if capacity > 0:
            fill = round(used / capacity, 4) if used <= capacity * 2 else round(min(used, 100) / 100.0, 4)
        elif total_appts > 0 and not from_chairs:
            fill = round(max(0.0, (total_appts - broken) / float(total_appts)), 4)
        scheduled_prod = _scheduled_production_total(sched_rows)
        conn.execute("DELETE FROM softdent_scheduling WHERE period = ? AND source = ?", (period, "import_bundle"))
        conn.execute(
            """
            INSERT INTO softdent_scheduling (
                period, total_appointments, broken_appointments, fill_rate,
                capacity_hours, used_hours, scheduled_production, source_file, source, ingested_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                period,
                total_appts or None,
                broken or None,
                fill,
                capacity or None,
                used or None,
                scheduled_prod,
                None,
                "import_bundle",
                stamp,
            ),
        )
        sched_n = 1

    gap = assess_aging_schedule_gap(bundle)
    return {
        "ok": True,
        "agingPeriods": aging_n,
        "schedulingPeriods": sched_n,
        "gapCode": gap.get("gapCode"),
        "agingPending": gap.get("agingPending"),
        "schedulingPending": gap.get("schedulingPending"),
        "fromOperatoryChairs": gap.get("fromOperatoryChairs"),
    }


def aging_schedule_widgets(bundle: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    gap = assess_aging_schedule_gap(bundle)
    out: list[dict[str, Any]] = []
    if gap.get("agingPending"):
        out.append(
            {
                "id": "softdent-aging-gap",
                "type": "status",
                "label": "Patient Aging (T1)",
                "size": "full",
                "status": "empty",
                "gapCode": GAP_AGING_PENDING,
                "message": "Aging summary pending",
                "emptyMessage": "No SoftDent aging summary — empty ≠ $0. Summary buckets only (no patient PHI).",
                "hint": FIX_HINT_AGING,
            }
        )
    else:
        out.append(
            {
                "id": "softdent-aging-gap",
                "type": "status",
                "label": "Patient Aging (T1)",
                "size": "full",
                "status": "ok",
                "gapCode": GAP_OK,
                "message": f"{gap.get('agingRowCount')} aging row(s) → bucket totals",
                "hint": "Bucket totals only in nr2_unified.db softdent_patient_aging.",
            }
        )
    if gap.get("schedulingPending"):
        out.append(
            {
                "id": "softdent-scheduling-gap",
                "type": "status",
                "label": "Scheduling (T1)",
                "size": "full",
                "status": "empty",
                "gapCode": GAP_SCHEDULING_PENDING,
                "message": "Scheduling export pending",
                "emptyMessage": "No scheduling/operatory rows — empty ≠ $0.",
                "hint": FIX_HINT_SCHED,
            }
        )
    else:
        out.append(
            {
                "id": "softdent-scheduling-gap",
                "type": "status",
                "label": "Scheduling (T1)",
                "size": "full",
                "status": "ok",
                "gapCode": GAP_OK,
                "message": f"{gap.get('schedulingRowCount')} schedule row(s)",
                "hint": "Mirrored into softdent_scheduling on Sync.",
            }
        )
    return out
