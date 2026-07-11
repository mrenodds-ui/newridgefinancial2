"""
Phase T2 — QuickBooks net profit → nr2_unified (Moonshot REAUDIT2).

Prefer P&L summary rows; else derive from income/expense/payroll when present.
Gap: NET_PROFIT_PENDING when insufficient (never invent $).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

GAP_OK = "OK"
GAP_NET_PROFIT_PENDING = "NET_PROFIT_PENDING"

FIX_HINT = (
    "Drop QuickBooks P&L summary (quickbooks_profit_and_loss*.csv) or ensure "
    "revenue + expenses (+ payroll) imports exist, then Sync. Empty ≠ $0."
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


def _period_key(row: dict[str, Any], default: str = "current") -> str:
    return str(row.get("period") or row.get("year_month") or row.get("Period") or default).strip()[:32] or default


def _qb_rows(bundle: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(bundle, dict):
        return []
    try:
        from apex_backend import _section_rows

        rows = _section_rows(bundle, "quickbooks", key) or []
        return [r for r in rows if isinstance(r, dict)]
    except Exception:
        qb = bundle.get("quickbooks") if isinstance(bundle.get("quickbooks"), dict) else {}
        block = qb.get(key) if isinstance(qb.get(key), dict) else {}
        rows = block.get("rows") if isinstance(block.get("rows"), list) else []
        return [r for r in rows if isinstance(r, dict)]


def assess_net_profit_gap(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    pl = _qb_rows(bundle, "profitAndLoss")
    rev = _qb_rows(bundle, "revenue")
    exp = _qb_rows(bundle, "expenseCategories") or _qb_rows(bundle, "expenses")
    pay = _qb_rows(bundle, "payroll")
    has = bool(pl) or (bool(rev) and bool(exp))
    return {
        "ok": True,
        "gapCode": GAP_OK if has else GAP_NET_PROFIT_PENDING,
        "healthy": bool(has),
        "netProfitPending": not has,
        "plRowCount": len(pl),
        "hasRevenue": bool(rev),
        "hasExpenses": bool(exp),
        "hasPayroll": bool(pay),
        "fixHint": None if has else FIX_HINT,
        "honesty": "empty_not_zero" if not has else "reported",
        "checkedAt": _utc_now(),
    }


def ingest_net_profit_into_conn(
    conn: Any,
    bundle: dict[str, Any] | None,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    stamp = now or _utc_now()
    gap = assess_net_profit_gap(bundle)
    if gap.get("netProfitPending"):
        return {"ok": True, "netProfitRows": 0, "gapCode": GAP_NET_PROFIT_PENDING, "netProfitPending": True}

    pl = _qb_rows(bundle, "profitAndLoss")
    n = 0
    if pl:
        for row in pl[:36]:
            period = _period_key(row)
            income = _parse_money(
                row.get("total_income")
                or row.get("TotalIncome")
                or row.get("Income")
                or row.get("Revenue")
                or row.get("Total Revenue")
            )
            expenses = _parse_money(
                row.get("total_expenses")
                or row.get("TotalExpenses")
                or row.get("Expenses")
                or row.get("Total Expense")
            )
            payroll = _parse_money(row.get("total_payroll") or row.get("Payroll") or row.get("PayrollExpenses"))
            net = _parse_money(
                row.get("net_profit")
                or row.get("NetIncome")
                or row.get("Net Profit")
                or row.get("NetIncome")
            )
            if net is None and income is not None:
                net = float(income) - float(expenses or 0) - float(payroll or 0)
            if income is None and expenses is None and net is None:
                continue
            conn.execute(
                """
                INSERT INTO qb_net_profit (
                    period, total_income, total_expenses, total_payroll, net_profit, source_file, source, ingested_at
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(period) DO UPDATE SET
                    total_income=excluded.total_income,
                    total_expenses=excluded.total_expenses,
                    total_payroll=excluded.total_payroll,
                    net_profit=excluded.net_profit,
                    source=excluded.source,
                    ingested_at=excluded.ingested_at
                """,
                (period, income, expenses, payroll, net, None, "import_bundle", stamp),
            )
            n += 1
    else:
        # Derive from revenue + expense categories (+ optional payroll)
        rev = _qb_rows(bundle, "revenue")
        exp = _qb_rows(bundle, "expenseCategories") or _qb_rows(bundle, "expenses")
        pay = _qb_rows(bundle, "payroll")
        period = "current"
        if rev:
            period = _period_key(rev[0], period)
        elif exp:
            period = _period_key(exp[0], period)
        income = 0.0
        for row in rev:
            income += _parse_money(row.get("Amount") or row.get("Revenue") or row.get("Total")) or 0.0
        expenses = 0.0
        for row in exp:
            expenses += _parse_money(row.get("Amount") or row.get("amount") or row.get("Total")) or 0.0
        payroll = 0.0
        for row in pay:
            payroll += _parse_money(row.get("Wages") or row.get("gross_wages") or row.get("Amount")) or 0.0
            payroll += _parse_money(row.get("employer_taxes") or row.get("MedicareER") or 0) or 0.0
        net = income - expenses - payroll
        conn.execute(
            """
            INSERT INTO qb_net_profit (
                period, total_income, total_expenses, total_payroll, net_profit, source_file, source, ingested_at
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(period) DO UPDATE SET
                total_income=excluded.total_income,
                total_expenses=excluded.total_expenses,
                total_payroll=excluded.total_payroll,
                net_profit=excluded.net_profit,
                source=excluded.source,
                ingested_at=excluded.ingested_at
            """,
            (period, income, expenses, payroll if pay else None, net, None, "derived_bundle", stamp),
        )
        n = 1

    return {
        "ok": True,
        "netProfitRows": n,
        "gapCode": GAP_OK,
        "netProfitPending": False,
    }


def net_profit_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    gap = assess_net_profit_gap(bundle)
    if gap.get("netProfitPending"):
        return {
            "id": "qb-net-profit-gap",
            "type": "status",
            "label": "Net Profit (T2)",
            "size": "full",
            "status": "empty",
            "gapCode": GAP_NET_PROFIT_PENDING,
            "message": "Net profit pending",
            "emptyMessage": "No P&L / revenue+expense basis — empty ≠ $0.",
            "hint": FIX_HINT,
        }
    return {
        "id": "qb-net-profit-gap",
        "type": "status",
        "label": "Net Profit (T2)",
        "size": "full",
        "status": "ok",
        "gapCode": GAP_OK,
        "message": "Net profit source available for unified ingest",
        "hint": "Stored in qb_net_profit on Sync (P&L or derived).",
    }
