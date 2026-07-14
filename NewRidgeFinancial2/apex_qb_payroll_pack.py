"""
Phase S0 — QuickBooks payroll detail + AP aging (AI PM SHOULD wave).

Ingests into additive nr2_unified.db. Redacts SSN before storage.
Missing payroll ≠ $0 — surfaces payroll_pending honesty.
Does not SoftDent write-back. Does not invent dollars.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

GAP_OK = "OK"
GAP_PAYROLL_PENDING = "PAYROLL_PENDING"
GAP_AP_PENDING = "AP_PENDING"
GAP_PAYROLL_AND_AP_PENDING = "PAYROLL_AND_AP_PENDING"

FIX_HINT_PAYROLL = (
    "Drop QuickBooks Payroll Detail CSV/Excel into the QB import inbox "
    "(quickbooks_payroll*.csv), then Sync. Empty ≠ $0."
)
FIX_HINT_AP = (
    "Drop QuickBooks Unpaid Bills / AP aging export "
    "(quickbooks_ap*.csv / unpaid_bills*.csv), then Sync. Empty ≠ $0."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def redact_phi(text: str) -> str:
    return SSN_RE.sub("[REDACTED]", str(text or ""))


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


def _period_key(row: dict[str, Any], default: str = "") -> str:
    return str(
        row.get("period") or row.get("year_month") or row.get("Period") or row.get("PayPeriod") or default
    ).strip()[:32]


def _section_rows(bundle: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(bundle, dict):
        return []
    try:
        from apex_backend import _section_rows as sr

        rows = sr(bundle, "quickbooks", key) or []
        return [r for r in rows if isinstance(r, dict)]
    except Exception:
        qb = bundle.get("quickbooks") if isinstance(bundle.get("quickbooks"), dict) else {}
        block = qb.get(key) if isinstance(qb.get(key), dict) else {}
        rows = block.get("rows") if isinstance(block.get("rows"), list) else []
        return [r for r in rows if isinstance(r, dict)]


def assess_payroll_ap_gap(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Honesty status for payroll/AP imports — never invents $."""
    payroll_rows = _section_rows(bundle, "payroll")
    ap_rows = _section_rows(bundle, "ap")
    has_payroll = bool(payroll_rows)
    has_ap = bool(ap_rows)

    empty_payroll = False
    empty_ap = False
    try:
        from apex_qb_export_inbox_pack import batch_empty_status

        empty = batch_empty_status()
        empty_payroll = bool((empty.get("payroll") or {}).get("batchEmpty"))
        empty_ap = bool((empty.get("ap") or {}).get("batchEmpty"))
    except Exception:
        pass

    # Header-only empty batch counts as "present" for optional gap (still empty ≠ $0).
    payroll_present = has_payroll or empty_payroll
    ap_present = has_ap or empty_ap

    if payroll_present and ap_present:
        gap = GAP_OK
    elif not payroll_present and not ap_present:
        gap = GAP_PAYROLL_AND_AP_PENDING
    elif not payroll_present:
        gap = GAP_PAYROLL_PENDING
    else:
        gap = GAP_AP_PENDING

    issues: list[str] = []
    if not payroll_present:
        issues.append("Payroll detail export not in import bundle.")
    elif empty_payroll and not has_payroll:
        issues.append("Payroll export present but empty period (empty ≠ $0).")
    if not ap_present:
        issues.append("AP / unpaid bills export not in import bundle.")
    elif empty_ap and not has_ap:
        issues.append("AP export present but empty period (empty ≠ $0).")

    return {
        "ok": True,
        "gapCode": gap,
        "healthy": gap == GAP_OK,
        "payrollPending": not payroll_present,
        "apPending": not ap_present,
        "payrollEmptyBatch": empty_payroll and not has_payroll,
        "apEmptyBatch": empty_ap and not has_ap,
        "payrollRowCount": len(payroll_rows),
        "apRowCount": len(ap_rows),
        "fixHint": None
        if gap == GAP_OK
        else (FIX_HINT_PAYROLL if not payroll_present else FIX_HINT_AP),
        "issues": issues,
        "honesty": "empty_not_zero" if (gap != GAP_OK or empty_payroll or empty_ap) else "reported",
        "checkedAt": _utc_now(),
    }


def normalize_payroll_row(row: dict[str, Any], *, period_default: str = "current") -> dict[str, Any] | None:
    employee = redact_phi(
        str(row.get("Employee") or row.get("employee") or row.get("Name") or row.get("name") or "").strip()
    )[:120]
    if not employee:
        return None
    gross = _parse_money(row.get("Wages") or row.get("Gross") or row.get("gross_wages") or row.get("Amount"))
    ee_tax = _parse_money(
        row.get("employee_taxes")
        or row.get("EmployeeTaxes")
        or (
            (_parse_money(row.get("MedicareEE")) or 0)
            + (_parse_money(row.get("SS_EE")) or 0)
            + (_parse_money(row.get("FederalWH")) or 0)
            + (_parse_money(row.get("StateWH")) or 0)
        )
    )
    er_tax = _parse_money(
        row.get("employer_taxes")
        or row.get("EmployerTaxes")
        or ((_parse_money(row.get("MedicareER")) or 0) + (_parse_money(row.get("SS_ER")) or 0))
    )
    net = _parse_money(row.get("NetPay") or row.get("net_pay") or row.get("Net"))
    if gross is None and net is None:
        return None
    return {
        "period": _period_key(row, period_default) or period_default,
        "employee": employee,
        "gross_wages": gross,
        "employee_taxes": ee_tax,
        "employer_taxes": er_tax,
        "net_pay": net,
    }


def normalize_ap_row(row: dict[str, Any], *, period_default: str = "current") -> dict[str, Any] | None:
    vendor = redact_phi(
        str(row.get("Vendor") or row.get("vendor") or row.get("Name") or row.get("Payee") or "").strip()
    )[:120]
    amount = _parse_money(
        row.get("AmountDue") or row.get("amount_due") or row.get("OpenBalance") or row.get("Amount") or row.get("Balance")
    )
    if not vendor or amount is None:
        return None
    due = str(row.get("DueDate") or row.get("due_date") or row.get("Due") or "")[:32] or None
    bill = str(row.get("BillDate") or row.get("bill_date") or row.get("Date") or "")[:32] or None
    bucket = str(row.get("Bucket") or row.get("AgingBucket") or row.get("aging_bucket") or "").strip()[:32]
    if not bucket:
        bucket = _aging_bucket_from_due(due)
    return {
        "period": _period_key(row, period_default) or period_default,
        "vendor": vendor,
        "bill_date": bill,
        "due_date": due,
        "amount_due": amount,
        "aging_bucket": bucket or "Current",
    }


def _aging_bucket_from_due(due: str | None) -> str:
    if not due:
        return "Current"
    try:
        # Accept YYYY-MM-DD
        due_dt = datetime.strptime(due[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - due_dt).days
        if days <= 0:
            return "Current"
        if days <= 30:
            return "1-30"
        if days <= 60:
            return "31-60"
        if days <= 90:
            return "61-90"
        return "90+"
    except ValueError:
        return "Current"


def ingest_payroll_ap_into_conn(
    conn: Any,
    bundle: dict[str, Any] | None,
    *,
    period_qb: str = "current",
    now: str | None = None,
) -> dict[str, Any]:
    """Write payroll + AP rows into an open unified DB connection."""
    stamp = now or _utc_now()
    payroll_n = 0
    ap_n = 0
    payroll_rows = _section_rows(bundle, "payroll")
    ap_rows = _section_rows(bundle, "ap")

    if payroll_rows:
        conn.execute(
            "DELETE FROM qb_payroll_rows WHERE period = ? AND source = ?",
            (period_qb, "import_bundle"),
        )
        for row in payroll_rows[:500]:
            norm = normalize_payroll_row(row, period_default=period_qb)
            if not norm:
                continue
            # Prefer explicit period on row; else sync period slice
            period = norm["period"] if norm["period"] != "current" else period_qb
            conn.execute(
                """
                INSERT INTO qb_payroll_rows (
                    period, employee, gross_wages, employee_taxes, employer_taxes, net_pay, source, imported_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    period,
                    norm["employee"],
                    norm["gross_wages"],
                    norm["employee_taxes"],
                    norm["employer_taxes"],
                    norm["net_pay"],
                    "import_bundle",
                    stamp,
                ),
            )
            payroll_n += 1

    if ap_rows:
        conn.execute(
            "DELETE FROM qb_ap_rows WHERE period = ? AND source = ?",
            (period_qb, "import_bundle"),
        )
        for row in ap_rows[:500]:
            norm = normalize_ap_row(row, period_default=period_qb)
            if not norm:
                continue
            period = norm["period"] if norm["period"] != "current" else period_qb
            conn.execute(
                """
                INSERT INTO qb_ap_rows (
                    period, vendor, bill_date, due_date, amount_due, aging_bucket, source, imported_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    period,
                    norm["vendor"],
                    norm["bill_date"],
                    norm["due_date"],
                    norm["amount_due"],
                    norm["aging_bucket"],
                    "import_bundle",
                    stamp,
                ),
            )
            ap_n += 1

    gap = assess_payroll_ap_gap(bundle)
    return {
        "ok": True,
        "payrollRows": payroll_n,
        "apRows": ap_n,
        "gapCode": gap.get("gapCode"),
        "payrollPending": gap.get("payrollPending"),
        "apPending": gap.get("apPending"),
    }


def payroll_ap_widgets(bundle: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    gap = assess_payroll_ap_gap(bundle)
    out: list[dict[str, Any]] = []

    if gap.get("payrollPending"):
        out.append(
            {
                "id": "qb-payroll-gap",
                "type": "status",
                "label": "Payroll Import (S0)",
                "size": "full",
                "status": "empty",
                "gapCode": GAP_PAYROLL_PENDING,
                "message": "Payroll detail pending",
                "emptyMessage": "No QuickBooks payroll export in bundle — empty ≠ $0.",
                "hint": FIX_HINT_PAYROLL,
            }
        )
    else:
        n = int(gap.get("payrollRowCount") or 0)
        out.append(
            {
                "id": "qb-payroll-gap",
                "type": "status",
                "label": "Payroll Import (S0)",
                "size": "full",
                "status": "ok",
                "gapCode": GAP_OK,
                "message": f"{n} payroll row(s) imported (SSN redacted)",
                "hint": "Mirrored into nr2_unified.db qb_payroll_rows on Sync.",
            }
        )

    if gap.get("apPending"):
        out.append(
            {
                "id": "qb-ap-aging",
                "type": "status",
                "label": "AP Aging (S0)",
                "size": "full",
                "status": "empty",
                "gapCode": GAP_AP_PENDING,
                "message": "AP / unpaid bills pending",
                "emptyMessage": "No QuickBooks AP export in bundle — empty ≠ $0.",
                "hint": FIX_HINT_AP,
            }
        )
    else:
        rows = _section_rows(bundle, "ap")
        buckets: dict[str, float] = {}
        for r in rows:
            norm = normalize_ap_row(r)
            if not norm:
                continue
            b = norm["aging_bucket"]
            buckets[b] = buckets.get(b, 0.0) + float(norm["amount_due"] or 0)
        bits = ", ".join(f"{k}=${v:,.0f}" for k, v in sorted(buckets.items()))
        out.append(
            {
                "id": "qb-ap-aging",
                "type": "status",
                "label": "AP Aging (S0)",
                "size": "full",
                "status": "ok",
                "gapCode": GAP_OK,
                "message": bits or f"{len(rows)} AP row(s)",
                "hint": "Mirrored into nr2_unified.db qb_ap_rows on Sync.",
                "buckets": buckets,
            }
        )
    return out


def format_payroll_ap_reply(gap: dict[str, Any] | None = None) -> str:
    g = gap or {}
    code = g.get("gapCode") or GAP_PAYROLL_AND_AP_PENDING
    lines = [f"QB payroll/AP status: `{code}` (honesty: empty ≠ $0)."]
    for issue in g.get("issues") or []:
        lines.append(f"- {issue}")
    if g.get("fixHint"):
        lines.append(str(g["fixHint"]))
    return "\n".join(lines)
