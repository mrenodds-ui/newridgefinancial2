"""
Phase T0 — SoftDent production + case acceptance → nr2_unified (Moonshot REAUDIT2).

Honesty: missing export → PRODUCTION_PENDING / CASE_ACCEPTANCE_PENDING (never $0).
No SoftDent write-back.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

GAP_OK = "OK"
GAP_PRODUCTION_PENDING = "PRODUCTION_PENDING"
GAP_CASE_ACCEPTANCE_PENDING = "CASE_ACCEPTANCE_PENDING"

FIX_HINT_PRODUCTION = (
    "Drop SoftDent Production by Provider / procedures export "
    "(production_*.csv / softdent_procedures_*.csv), then Sync. Empty ≠ $0."
)
FIX_HINT_CASE = (
    "Drop SoftDent case acceptance export (case_acceptance*.csv), then Sync. Empty ≠ $0."
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


def assess_production_gap(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    prod = _sd_rows(bundle, "procedures") or _sd_rows(bundle, "production")
    case = _sd_rows(bundle, "caseAcceptance")
    issues: list[str] = []
    if not prod:
        issues.append("SoftDent production/procedures export not in bundle.")
    if not case:
        issues.append("SoftDent case acceptance export not in bundle.")
    gap = GAP_OK
    if not prod and not case:
        gap = GAP_PRODUCTION_PENDING
    elif not prod:
        gap = GAP_PRODUCTION_PENDING
    elif not case:
        gap = GAP_CASE_ACCEPTANCE_PENDING
    return {
        "ok": True,
        "gapCode": gap,
        "healthy": gap == GAP_OK,
        "productionPending": not bool(prod),
        "caseAcceptancePending": not bool(case),
        "productionRowCount": len(prod),
        "caseAcceptanceRowCount": len(case),
        "fixHint": None if gap == GAP_OK else (FIX_HINT_PRODUCTION if not prod else FIX_HINT_CASE),
        "issues": issues,
        "honesty": "empty_not_zero" if gap != GAP_OK else "reported",
        "checkedAt": _utc_now(),
    }


def ingest_softdent_production_into_conn(
    conn: Any,
    bundle: dict[str, Any] | None,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    stamp = now or _utc_now()
    prod_rows = _sd_rows(bundle, "procedures") or _sd_rows(bundle, "production")
    case_rows = _sd_rows(bundle, "caseAcceptance")
    prod_n = 0
    case_n = 0

    if prod_rows:
        conn.execute("DELETE FROM softdent_production WHERE source = ?", ("import_bundle",))
        for row in prod_rows[:2000]:
            amount = _parse_money(
                row.get("production_amount")
                or row.get("Production")
                or row.get("Amount")
                or row.get("Fee")
                or row.get("Total")
            )
            if amount is None:
                continue
            period = _period_key(row)
            provider = str(row.get("provider_id") or row.get("Provider") or row.get("provider") or "")[:80] or None
            code = str(row.get("procedure_code") or row.get("ProcCode") or row.get("Code") or "")[:40] or None
            desc = str(row.get("procedure_description") or row.get("Description") or row.get("AdaCode") or "")[:120] or None
            qty = _parse_int(row.get("quantity") or row.get("Qty") or row.get("Count"))
            posted = str(row.get("posted_date") or row.get("Date") or row.get("Posted") or "")[:32] or None
            conn.execute(
                """
                INSERT INTO softdent_production (
                    period, provider_id, procedure_code, procedure_description,
                    production_amount, quantity, posted_date, source_file, source, ingested_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (period, provider, code, desc, amount, qty, posted, None, "import_bundle", stamp),
            )
            prod_n += 1

    if case_rows:
        conn.execute("DELETE FROM softdent_case_acceptance WHERE source = ?", ("import_bundle",))
        for row in case_rows[:500]:
            planned = _parse_money(
                row.get("treatment_planned_amount")
                or row.get("Presented")
                or row.get("Planned")
                or row.get("TreatmentPlanned")
            )
            accepted = _parse_money(
                row.get("accepted_amount") or row.get("Accepted") or row.get("TreatmentAccepted")
            )
            if planned is None and accepted is None:
                continue
            rate = None
            if planned and planned > 0 and accepted is not None:
                rate = round(float(accepted) / float(planned), 4)
            elif row.get("acceptance_rate") is not None:
                try:
                    rate = float(row.get("acceptance_rate"))
                except (TypeError, ValueError):
                    rate = None
            period = _period_key(row)
            provider = str(row.get("provider_id") or row.get("Provider") or "")[:80] or None
            conn.execute(
                """
                INSERT INTO softdent_case_acceptance (
                    period, provider_id, treatment_planned_amount, accepted_amount,
                    acceptance_rate, source_file, source, ingested_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (period, provider, planned, accepted, rate, None, "import_bundle", stamp),
            )
            case_n += 1

    gap = assess_production_gap(bundle)
    return {
        "ok": True,
        "productionRows": prod_n,
        "caseAcceptanceRows": case_n,
        "gapCode": gap.get("gapCode"),
        "productionPending": gap.get("productionPending"),
        "caseAcceptancePending": gap.get("caseAcceptancePending"),
    }


def production_widgets(bundle: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    gap = assess_production_gap(bundle)
    out: list[dict[str, Any]] = []
    if gap.get("productionPending"):
        out.append(
            {
                "id": "softdent-production-gap",
                "type": "status",
                "label": "Production Import (T0)",
                "size": "full",
                "status": "empty",
                "gapCode": GAP_PRODUCTION_PENDING,
                "message": "Production export pending",
                "emptyMessage": "No SoftDent production/procedures rows — empty ≠ $0.",
                "hint": FIX_HINT_PRODUCTION,
            }
        )
    else:
        out.append(
            {
                "id": "softdent-production-gap",
                "type": "status",
                "label": "Production Import (T0)",
                "size": "full",
                "status": "ok",
                "gapCode": GAP_OK,
                "message": f"{gap.get('productionRowCount')} production row(s) imported",
                "hint": "Mirrored into nr2_unified.db softdent_production on Sync.",
            }
        )
    if gap.get("caseAcceptancePending"):
        out.append(
            {
                "id": "softdent-case-acceptance-gap",
                "type": "status",
                "label": "Case Acceptance (T0)",
                "size": "full",
                "status": "empty",
                "gapCode": GAP_CASE_ACCEPTANCE_PENDING,
                "message": "Case acceptance export pending",
                "emptyMessage": "No case acceptance rows — empty ≠ $0.",
                "hint": FIX_HINT_CASE,
            }
        )
    else:
        out.append(
            {
                "id": "softdent-case-acceptance-gap",
                "type": "status",
                "label": "Case Acceptance (T0)",
                "size": "full",
                "status": "ok",
                "gapCode": GAP_OK,
                "message": f"{gap.get('caseAcceptanceRowCount')} case acceptance row(s)",
                "hint": "Mirrored into nr2_unified.db softdent_case_acceptance on Sync.",
            }
        )
    return out
