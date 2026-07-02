"""Financial report summaries derived from NR2 import cache (read-only)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from import_loader import load_import_bundle
from softdent_practice_exports import read_practice_export_datasets, sync_practice_exports


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_money(value: Any) -> float:
    raw = str(value or "").replace("$", "").replace(",", "").strip()
    if not raw or raw in {"—", "-", "N/A"}:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _parse_days(value: Any) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    match = re.search(r"(\d+)", raw)
    return int(match.group(1)) if match else None


def _claim_tracking_summary(claims_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(claims_rows)
    by_status: dict[str, int] = {}
    denied = 0
    aging_30 = 0
    for row in claims_rows:
        status = str(row.get("Status") or row.get("status") or "Unknown").strip() or "Unknown"
        by_status[status] = by_status.get(status, 0) + 1
        if re.search(r"denied|reject", status, re.I):
            denied += 1
        days = _parse_days(row.get("Age") or row.get("Days") or row.get("AgingDays") or row.get("ageDays"))
        if days is not None and days >= 30 and re.search(r"denied|pending|hold|review", status, re.I):
            aging_30 += 1
    return {
        "totalClaims": total,
        "byStatus": by_status,
        "deniedCount": denied,
        "deniedAgingPast30Days": aging_30,
        "followUpHint": (
            "Review denied claims past 30 days for resubmit or appeal."
            if aging_30 or denied
            else "No denied claims flagged from import."
        ),
    }


def _ar_aging_summary(ar_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_outstanding = 0.0
    ninety_plus = 0.0
    for row in ar_rows:
        amount = _parse_money(row.get("Balance") or row.get("Outstanding") or row.get("Amount") or row.get("Total"))
        total_outstanding += amount
        bucket = str(row.get("Aging") or row.get("Bucket") or row.get("AgeBucket") or "")
        days = _parse_days(row.get("Days") or row.get("AgeDays"))
        if re.search(r"90\+|91\+|120", bucket) or (days is not None and days >= 90):
            ninety_plus += amount
    pct = round((ninety_plus / total_outstanding) * 100, 1) if total_outstanding > 0 else 0.0
    return {
        "totalOutstanding": round(total_outstanding, 2),
        "ninetyPlusOutstanding": round(ninety_plus, 2),
        "ninetyPlusPct": pct,
        "followUpHint": (
            "Prioritize 90+ day balances and insurance follow-up."
            if pct >= 15 or ninety_plus > 0
            else "A/R aging within normal review range for imported snapshot."
        ),
    }


def build_financial_reports(*, sync_exports: bool = False) -> dict[str, Any]:
    if sync_exports:
        sync_practice_exports()

    bundle = load_import_bundle(sync=False, deep=False)
    sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    claims_rows = (sd.get("claims") or {}).get("rows") if isinstance(sd.get("claims"), dict) else []
    ar_rows = (sd.get("ar") or {}).get("rows") if isinstance(sd.get("ar"), dict) else []
    claims_rows = claims_rows if isinstance(claims_rows, list) else []
    ar_rows = ar_rows if isinstance(ar_rows, list) else []

    practice = read_practice_export_datasets()
    treatment_rows = (practice.get("treatmentPlans") or {}).get("rows") if practice.get("treatmentPlans") else []
    case_rows = (practice.get("caseAcceptance") or {}).get("rows") if practice.get("caseAcceptance") else []

    return {
        "generatedAt": _utc_now(),
        "claimTracking": _claim_tracking_summary(claims_rows),
        "arAging": _ar_aging_summary(ar_rows),
        "treatmentPlans": {
            "rowCount": len(treatment_rows) if isinstance(treatment_rows, list) else 0,
            "rows": (treatment_rows or [])[:24],
            "available": bool(treatment_rows),
        },
        "caseAcceptance": {
            "rowCount": len(case_rows) if isinstance(case_rows, list) else 0,
            "rows": (case_rows or [])[:24],
            "available": bool(case_rows),
        },
        "collectionsNote": (
            "Compare production to collections in SoftDent dashboard; lead with aging/A/R and insurance when collections trail."
        ),
    }


def format_financial_reports_text(reports: dict[str, Any]) -> str:
    ct = reports.get("claimTracking") or {}
    ar = reports.get("arAging") or {}
    tp = reports.get("treatmentPlans") or {}
    ca = reports.get("caseAcceptance") or {}
    lines = [
        "Financial reports (import snapshot):",
        f"- Claims: {ct.get('totalClaims', 0)} total; {ct.get('deniedCount', 0)} denied; "
        f"{ct.get('deniedAgingPast30Days', 0)} denied aging 30+ days.",
        f"- A/R: ${ar.get('totalOutstanding', 0):,.2f} outstanding; 90+ day share {ar.get('ninetyPlusPct', 0)}%.",
        f"- Treatment plans: {'loaded' if tp.get('available') else 'missing'} ({tp.get('rowCount', 0)} rows).",
        f"- Case acceptance: {'loaded' if ca.get('available') else 'missing'} ({ca.get('rowCount', 0)} rows).",
        "",
        str(ct.get("followUpHint") or ""),
        str(ar.get("followUpHint") or ""),
    ]
    return "\n".join(line for line in lines if line)
