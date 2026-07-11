"""
Phase W1 — Import data-quality gates (Moonshot REAUDIT5 SHOULD).

Validate SoftDent/QB bundle rows before unified merge. Never invent or auto-correct
dollars — reject/quarantine only. No SoftDent write-back. No PHI in violation logs.
Flag: NR2_IMPORT_DQ (default ON).
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone
from typing import Any

GAP_DQ_BLOCKED = "IMPORT_DQ_BLOCKED"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dq_enabled() -> bool:
    raw = str(os.getenv("NR2_IMPORT_DQ") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


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


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _section_rows(bundle: dict[str, Any], source: str, key: str) -> list[dict[str, Any]]:
    try:
        from apex_backend import _section_rows as _sr

        rows = _sr(bundle, source, key) or []
        return [r for r in rows if isinstance(r, dict)]
    except Exception:
        block_src = bundle.get(source) if isinstance(bundle.get(source), dict) else {}
        block = block_src.get(key) if isinstance(block_src.get(key), dict) else {}
        rows = block.get("rows") if isinstance(block.get("rows"), list) else []
        return [r for r in rows if isinstance(r, dict)]


def _period_future(period: str, *, today: date | None = None) -> bool:
    """True when YYYY-MM is more than one month ahead of today."""
    m = re.fullmatch(r"(\d{4})-(\d{2})", str(period or "").strip())
    if not m:
        return False
    y, mo = int(m.group(1)), int(m.group(2))
    if mo < 1 or mo > 12:
        return True
    ref = today or datetime.now(timezone.utc).date()
    # allow current month and next month (export lag / early close)
    horizon_y, horizon_m = ref.year, ref.month + 1
    if horizon_m > 12:
        horizon_m = 1
        horizon_y += 1
    return (y, mo) > (horizon_y, horizon_m)


def validate_bundle_dq(
    bundle: dict[str, Any] | None,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """
    Run DQ rules. Returns ok=False when any critical violation is found.
    Does not mutate data.
    """
    b = bundle if isinstance(bundle, dict) else {}
    violations: list[dict[str, Any]] = []
    ref = today or datetime.now(timezone.utc).date()

    # no_negative_production / collections (dashboard)
    for idx, row in enumerate(_section_rows(b, "softdent", "dashboard")[:200]):
        prod = _parse_money(row.get("production") or row.get("Production"))
        if prod is not None and prod < 0:
            violations.append(
                {
                    "rule": "no_negative_production",
                    "path": f"softdent.dashboard[{idx}]",
                    "severity": "critical",
                }
            )
        if not row.get("collectionsPending"):
            coll = _parse_money(row.get("collections") or row.get("Collections"))
            if coll is not None and coll < 0:
                violations.append(
                    {
                        "rule": "no_negative_collections",
                        "path": f"softdent.dashboard[{idx}]",
                        "severity": "critical",
                    }
                )
        period = str(row.get("period") or row.get("Period") or "")
        if period and _period_future(period, today=ref):
            violations.append(
                {
                    "rule": "no_future_dates",
                    "path": f"softdent.dashboard[{idx}].period",
                    "severity": "critical",
                }
            )

    # procedure amounts / dates
    for idx, row in enumerate(_section_rows(b, "softdent", "procedures")[:500]):
        amt = _parse_money(row.get("Amount") or row.get("production_amount") or row.get("Production"))
        if amt is not None and amt < 0:
            violations.append(
                {
                    "rule": "no_negative_production",
                    "path": f"softdent.procedures[{idx}]",
                    "severity": "critical",
                }
            )
        for key in ("service_date", "ServiceDate", "posted_date", "PostedDate", "Date"):
            d = _parse_date(row.get(key))
            if d is not None and d > ref:
                violations.append(
                    {
                        "rule": "no_future_dates",
                        "path": f"softdent.procedures[{idx}].{key}",
                        "severity": "critical",
                    }
                )
                break
        # valid_claim_id — only when field is present (format check; no SoftDent master index)
        if "claim_id" in row or "ClaimId" in row or "ClaimID" in row:
            cid = row.get("claim_id") or row.get("ClaimId") or row.get("ClaimID")
            if cid is None or str(cid).strip() in {"", "NULL", "null", "None"}:
                violations.append(
                    {
                        "rule": "valid_claim_id",
                        "path": f"softdent.procedures[{idx}].claim_id",
                        "severity": "critical",
                    }
                )
        # patient id format when present (not a live SoftDent FK — empty/NULL only)
        if "patient_id" in row or "PatientId" in row or "PatientID" in row:
            pid = row.get("patient_id") or row.get("PatientId") or row.get("PatientID")
            if pid is None or str(pid).strip() in {"", "NULL", "null", "None"}:
                violations.append(
                    {
                        "rule": "foreign_key_patient",
                        "path": f"softdent.procedures[{idx}].patient_id",
                        "severity": "critical",
                        "note": "Format gate only — no SoftDent write-back / no master PHI index.",
                    }
                )

    # aging balances
    for idx, row in enumerate(_section_rows(b, "softdent", "ar")[:200]):
        bal = _parse_money(row.get("Balance") or row.get("Amount") or row.get("Outstanding"))
        if bal is not None and bal < 0:
            violations.append(
                {
                    "rule": "no_negative_aging",
                    "path": f"softdent.ar[{idx}]",
                    "severity": "critical",
                }
            )

    critical = [v for v in violations if v.get("severity") == "critical"]
    return {
        "ok": len(critical) == 0,
        "phase": "W1",
        "enabled": dq_enabled(),
        "gapCode": None if not critical else GAP_DQ_BLOCKED,
        "violationCount": len(violations),
        "criticalCount": len(critical),
        "violations": violations[:50],
        "rules": [
            "no_negative_production",
            "no_negative_collections",
            "no_future_dates",
            "valid_claim_id",
            "foreign_key_patient",
            "no_negative_aging",
        ],
        "honesty": "reject_only_no_imputation",
        "softDentWriteBack": False,
        "checkedAt": _utc_now(),
    }


def dq_status() -> dict[str, Any]:
    return {
        "ok": True,
        "phase": "W1",
        "enabled": dq_enabled(),
        "flag": "NR2_IMPORT_DQ",
        "gapCode": GAP_DQ_BLOCKED,
        "hint": "Set NR2_IMPORT_DQ=0 to bypass DQ gates (not recommended).",
        "refreshedAt": _utc_now(),
    }


def dq_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    if not dq_enabled():
        return {
            "id": "import-dq-status",
            "type": "status",
            "label": "Import DQ (W1)",
            "size": "full",
            "status": "empty",
            "message": "DQ disabled",
            "hint": "Set NR2_IMPORT_DQ=1 (default on).",
        }
    result = validate_bundle_dq(bundle or {})
    if result.get("ok"):
        return {
            "id": "import-dq-status",
            "type": "status",
            "label": "Import DQ (W1)",
            "size": "full",
            "status": "ok",
            "message": "Bundle DQ clean (or empty — empty ≠ $0)",
            "hint": "Reject-only gates before unified merge.",
        }
    return {
        "id": "import-dq-status",
        "type": "status",
        "label": "Import DQ (W1)",
        "size": "full",
        "status": "warn",
        "gapCode": GAP_DQ_BLOCKED,
        "message": f"{result.get('criticalCount')} critical DQ violation(s)",
        "hint": "Fix export or quarantine — no auto-correct / no SoftDent write-back.",
        "violationCount": result.get("violationCount"),
    }
