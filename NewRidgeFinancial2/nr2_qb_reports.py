"""QuickBooks extended report surface — import cache + SDK probe (hal-10071)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_loader import load_import_bundle, quickbooks_import_dir
from quickbooks_monthly_sync import _normalize_monthly_rows, _rows_from_probe_monthly

REPORT_TYPES = (
    "balance_sheet",
    "cash_flow",
    "net_income",
    "revenue_by_service",
    "ap_aging",
    "ar_aging",
    "credit_cards",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _probe_summary_path() -> Path | None:
    dest = quickbooks_import_dir()
    for relative in (
        "quickbooks_diagnostics/quickbooks_sdk_report_probe_summary.json",
        "quickbooks_sdk_report_probe_summary.json",
    ):
        candidate = dest / relative
        if candidate.is_file():
            return candidate
    return None


def load_probe_summary() -> dict[str, Any]:
    path = _probe_summary_path()
    if not path:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _cache_path() -> Path:
    return quickbooks_import_dir() / "qb_report_cache.json"


def load_report_cache() -> dict[str, Any]:
    path = _cache_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_report_cache(reports: dict[str, Any]) -> Path:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updatedAt": _utc_now(), "reports": reports}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _bundle_qb(bundle: dict[str, Any] | None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    qb = bundle.get("quickbooks") if isinstance(bundle, dict) else {}
    return qb if isinstance(qb, dict) else {}


def _monthly_pl_rows(bundle: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    qb = _bundle_qb(bundle)
    rows: list[dict[str, Any]] = []
    for key in ("profitAndLoss", "revenue"):
        chunk = qb.get(key)
        if isinstance(chunk, dict):
            rows.extend(chunk.get("rows") or [])
        elif isinstance(chunk, list):
            rows.extend(chunk)
    probe_rows = _rows_from_probe_monthly(load_probe_summary())
    if probe_rows:
        rows = probe_rows
    return _normalize_monthly_rows(rows)


def _cached_report(report_type: str) -> dict[str, Any] | None:
    cache = load_report_cache()
    reports = cache.get("reports") if isinstance(cache.get("reports"), dict) else {}
    payload = reports.get(report_type)
    return payload if isinstance(payload, dict) else None


def balance_sheet_summary(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    cached = _cached_report("balance_sheet")
    if cached:
        return cached
    probe = load_probe_summary()
    qb = _bundle_qb(bundle)
    ar_rows = (qb.get("ar") or {}).get("rows") if isinstance(qb.get("ar"), dict) else qb.get("ar")
    ar_total = 0.0
    if isinstance(ar_rows, list):
        for row in ar_rows:
            if isinstance(row, dict):
                ar_total += _parse_money(row.get("Balance") or row.get("balance") or row.get("Amount"))
    if ar_total <= 0:
        ar_total = _parse_money(probe.get("accounts_receivable"))
    income = _parse_money(probe.get("total_income"))
    expenses = _parse_money(probe.get("total_expenses"))
    cash_proxy = max(0.0, income - expenses) if income and expenses else 0.0
    assets = []
    if ar_total > 0:
        assets.append({"label": "Accounts Receivable", "amount": round(ar_total, 2)})
    if cash_proxy > 0:
        assets.append({"label": "Cash & Deposits (proxy)", "amount": round(cash_proxy, 2)})
    equity = round(income - expenses, 2) if income or expenses else None
    return {
        "hasData": bool(assets or equity is not None),
        "period": probe.get("period"),
        "assets": assets,
        "liabilities": [],
        "equity": equity,
        "source": "probe+import",
    }


def cash_flow_trend(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    cached = _cached_report("cash_flow")
    if cached:
        return cached
    monthly = _monthly_pl_rows(bundle)[-12:]
    labels = [row["Period"] for row in monthly]
    inflows = [row["TotalIncome"] for row in monthly]
    outflows = [row["TotalExpense"] for row in monthly]
    net = [round(row["NetIncome"] or (row["TotalIncome"] - row["TotalExpense"]), 2) for row in monthly]
    return {
        "hasData": bool(labels),
        "labels": labels,
        "inflows": inflows,
        "outflows": outflows,
        "net": net,
        "source": "monthly-pl",
    }


def net_income_summary(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    cached = _cached_report("net_income")
    if cached:
        return cached
    monthly = _monthly_pl_rows(bundle)
    probe = load_probe_summary()
    ytd_net = sum(_parse_money(row.get("NetIncome")) for row in monthly)
    if ytd_net == 0 and probe:
        ytd_net = _parse_money(probe.get("total_income")) - _parse_money(probe.get("total_expenses"))
    latest = monthly[-1] if monthly else None
    return {
        "hasData": bool(monthly or probe),
        "ytdNetIncome": round(ytd_net, 2) if ytd_net else None,
        "latestMonth": latest.get("Period") if latest else probe.get("period"),
        "latestNetIncome": latest.get("NetIncome") if latest else (
            round(_parse_money(probe.get("total_income")) - _parse_money(probe.get("total_expenses")), 2)
            if probe else None
        ),
        "monthCount": len(monthly),
        "source": "monthly-pl",
    }


def revenue_by_service(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    cached = _cached_report("revenue_by_service")
    if cached:
        return cached
    qb = _bundle_qb(bundle)
    slices: list[dict[str, Any]] = []
    categories = qb.get("expenseCategories")
    if isinstance(categories, dict):
        for row in categories.get("slices") or []:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or row.get("Category") or "Category")
            amount = _parse_money(row.get("amount") or row.get("Amount") or row.get("pct"))
            if amount > 0:
                slices.append({"label": label, "amount": amount})
    probe = load_probe_summary()
    for row in probe.get("top_expense_categories") or []:
        if not isinstance(row, dict):
            continue
        slices.append(
            {
                "label": str(row.get("category") or "Service"),
                "amount": _parse_money(row.get("amount")),
            }
        )
    income = _parse_money(probe.get("total_income"))
    if not slices and income > 0:
        slices = [{"label": "Clinical Production (proxy)", "amount": income}]
    total = sum(item["amount"] for item in slices)
    if total > 0:
        for item in slices:
            item["pct"] = round((item["amount"] / total) * 100, 1)
    return {"hasData": bool(slices), "slices": slices[:8], "total": round(total, 2), "source": "categories+probe"}


def ap_aging(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    cached = _cached_report("ap_aging")
    if cached:
        return cached
    qb = _bundle_qb(bundle)
    rows = []
    for key in ("ap", "accountsPayable"):
        chunk = qb.get(key)
        if isinstance(chunk, dict):
            rows = chunk.get("rows") or []
            break
    buckets = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        buckets.append(
            {
                "bucket": str(row.get("Bucket") or row.get("bucket") or "Current"),
                "balance": _parse_money(row.get("Balance") or row.get("balance") or row.get("Amount")),
            }
        )
    return {"hasData": bool(buckets), "buckets": buckets, "source": "import"}


def ar_aging(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    cached = _cached_report("ar_aging")
    if cached:
        return cached
    probe = load_probe_summary()
    buckets = []
    for row in probe.get("ar_aging") or []:
        if isinstance(row, dict):
            buckets.append(
                {
                    "bucket": str(row.get("bucket") or row.get("Bucket") or ""),
                    "balance": _parse_money(row.get("balance") or row.get("Balance")),
                }
            )
    if not buckets:
        qb = _bundle_qb(bundle)
        ar_rows = (qb.get("ar") or {}).get("rows") if isinstance(qb.get("ar"), dict) else qb.get("ar")
        if isinstance(ar_rows, list):
            for row in ar_rows:
                if isinstance(row, dict):
                    buckets.append(
                        {
                            "bucket": str(row.get("Bucket") or row.get("bucket") or ""),
                            "balance": _parse_money(row.get("Balance") or row.get("balance")),
                        }
                    )
    total = round(sum(item["balance"] for item in buckets), 2)
    return {"hasData": bool(buckets), "buckets": buckets, "total": total, "source": "probe+import"}


def credit_card_balances(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    cached = _cached_report("credit_cards")
    if cached:
        return cached
    qb = _bundle_qb(bundle)
    cards: list[dict[str, Any]] = []
    categories = qb.get("expenseCategories")
    if isinstance(categories, dict):
        for row in categories.get("slices") or []:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "")
            if "card" in label.lower() or "credit" in label.lower():
                cards.append({"label": label, "balance": _parse_money(row.get("amount") or row.get("Amount"))})
    return {"hasData": bool(cards), "cards": cards, "source": "expense-categories"}


def sync_extended_qb_reports(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    reports = {
        "balance_sheet": balance_sheet_summary(bundle=bundle),
        "cash_flow": cash_flow_trend(bundle=bundle),
        "net_income": net_income_summary(bundle=bundle),
        "revenue_by_service": revenue_by_service(bundle=bundle),
        "ap_aging": ap_aging(bundle=bundle),
        "ar_aging": ar_aging(bundle=bundle),
        "credit_cards": credit_card_balances(bundle=bundle),
    }
    path = write_report_cache(reports)
    populated = sum(1 for payload in reports.values() if isinstance(payload, dict) and payload.get("hasData"))
    return {"ok": populated > 0, "written": str(path), "populated": populated, "reports": reports}


def get_balance_sheet(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    return balance_sheet_summary(bundle=bundle)


def get_cash_flow_trend(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    return cash_flow_trend(bundle=bundle)


def get_ap_aging(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    return ap_aging(bundle=bundle)


def get_ar_aging(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    return ar_aging(bundle=bundle)


def get_credit_card_balances(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    return credit_card_balances(bundle=bundle)


def get_revenue_by_service(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    return revenue_by_service(bundle=bundle)


def get_net_income_summary(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    return net_income_summary(bundle=bundle)
