from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4


IMPORT_CACHE_MANAGER = "Import cache"
MetricValue = str | int | float | bool | None


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.replace(",", "").replace("$", "").strip()
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def _coerce_int(value: object) -> int | None:
    number = _coerce_float(value)
    if number is None:
        return None
    return int(round(number))


def _scalar_metric(value: object) -> MetricValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def _first_profit_loss_row(summary: Mapping[str, Any]) -> dict[str, Any]:
    rows = summary.get("quickBooksProfitLossSummary")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0]
    return {}


def _current_month_production(summary: Mapping[str, Any]) -> dict[str, Any]:
    current = _as_dict(summary.get("currentMonthProduction"))
    if current:
        return current
    monthly = summary.get("monthlyKpis")
    if isinstance(monthly, list) and monthly and isinstance(monthly[-1], dict):
        return monthly[-1]
    return {}


def _latest_daily_kpi(summary: Mapping[str, Any]) -> dict[str, Any]:
    return _as_dict(summary.get("latestDailyKpi"))


def _latest_ar(summary: Mapping[str, Any]) -> dict[str, Any]:
    payload = _as_dict(summary.get("latestAr"))
    if not payload or payload.get("available") is False:
        return {}
    return payload


def _claims_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    return _as_dict(summary.get("claimsSummary"))


def _quickbooks_status(summary: Mapping[str, Any]) -> dict[str, Any]:
    return _as_dict(summary.get("quickBooksStatus"))


def _softdent_review_status(summary: Mapping[str, Any]) -> str:
    source_review = _as_dict(summary.get("sourceReview"))
    softdent = _as_dict(source_review.get("softDent"))
    status = str(softdent.get("status") or "").strip().lower()
    daily = _latest_daily_kpi(summary)
    month = _current_month_production(summary)
    latest_ar = _latest_ar(summary)
    has_ops_data = any(
        _coerce_float(value) is not None
        for value in (
            daily.get("production"),
            daily.get("collections"),
            month.get("gross_production"),
            month.get("collections"),
            latest_ar.get("total_ar"),
            latest_ar.get("patient_ar"),
        )
    )
    if status in {"ready", "available"} and has_ops_data:
        return "SUCCESS"
    if status in {"warning", "limited", "stale"} or has_ops_data:
        return "DEGRADED"
    return "FAILED"


def _quickbooks_review_status(summary: Mapping[str, Any]) -> str:
    qb_status = _quickbooks_status(summary)
    status = str(qb_status.get("status") or "").strip().lower()
    profit_loss = _first_profit_loss_row(summary)
    has_finance_data = any(
        _coerce_float(profit_loss.get(key)) is not None for key in ("income_total", "expense_total", "net_income")
    )
    if status in {"ready", "ok"} and not qb_status.get("lastError") and has_finance_data:
        return "SUCCESS"
    if status in {"warning", "limited"} or qb_status.get("lastError") or has_finance_data:
        return "DEGRADED"
    row_counts = _as_dict(qb_status.get("rowCounts"))
    if any(_coerce_int(row_counts.get(key)) for key in ("revenue", "expenses", "ar")):
        return "DEGRADED"
    return "FAILED"


def _claims_review_status(summary: Mapping[str, Any]) -> str:
    claims = _claims_summary(summary)
    if claims.get("available"):
        return "SUCCESS"
    if _coerce_float(_latest_ar(summary).get("total_ar")) is not None:
        return "DEGRADED"
    return "FAILED"


def _publish_job_status(widgets: Mapping[str, Any]) -> str:
    statuses = [str(_as_dict(widget).get("status") or "").strip().upper() for widget in widgets.values()]
    if statuses and all(status == "SUCCESS" for status in statuses):
        return "SUCCESS"
    if any(status == "SUCCESS" for status in statuses):
        return "DEGRADED"
    return "FAILED"


def _merge_widget_status(*statuses: str) -> str:
    normalized = [status for status in statuses if status]
    if not normalized:
        return "FAILED"
    if all(status == "SUCCESS" for status in normalized):
        return "SUCCESS"
    if any(status == "SUCCESS" for status in normalized):
        return "DEGRADED"
    return "FAILED"


def _collection_rate(summary: Mapping[str, Any], *, production: float | None, collections: float | None) -> float | None:
    month = _current_month_production(summary)
    explicit = _coerce_float(month.get("collection_rate"))
    if explicit is not None:
        return round(explicit, 2)
    if production and production > 0 and collections is not None:
        return round((collections / production) * 100, 2)
    return None


def _posting_queue_pending_count() -> int | None:
    try:
        from app.hal.orchestrator import get_accounting_posting_queue_summary

        metrics = get_accounting_posting_queue_summary()
        if not isinstance(metrics, dict):
            return None
        return _coerce_int(metrics.get("pending_review_count"))
    except Exception:
        return None


def build_widget_feed_from_financial_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    profit_loss = _first_profit_loss_row(summary)
    month = _current_month_production(summary)
    daily = _latest_daily_kpi(summary)
    latest_ar = _latest_ar(summary)
    claims = _claims_summary(summary)

    production_total = _coerce_float(daily.get("production") or month.get("gross_production"))
    collections_total = _coerce_float(daily.get("collections") or month.get("collections"))
    monthly_revenue = _coerce_float(profit_loss.get("income_total"))
    monthly_net_income = _coerce_float(profit_loss.get("net_income"))
    expense_total = _coerce_float(profit_loss.get("expense_total"))
    collection_rate = _collection_rate(summary, production=production_total, collections=collections_total)

    qb_status = _quickbooks_review_status(summary)
    softdent_status = _softdent_review_status(summary)
    claims_status = _claims_review_status(summary)

    posting_queue_pending = _posting_queue_pending_count()
    softdent_metrics = _as_dict(_as_dict(summary.get("sourceReview")).get("softDent")).get("metrics")
    provider_count = _coerce_int(_as_dict(softdent_metrics).get("providerCount")) or 1

    widgets = {
        "practice_financial_overview": {
            "title": "Practice Financial Overview",
            "status": _merge_widget_status(qb_status, softdent_status),
            "summary": "Practice revenue from QuickBooks and production/collections from SoftDent import cache. Dental A/R is not sourced from QuickBooks.",
            "metrics": {
                "monthly_revenue": _scalar_metric(monthly_revenue),
                "monthly_net_income": _scalar_metric(monthly_net_income),
                "production_total": _scalar_metric(production_total),
                "collections_total": _scalar_metric(collections_total),
                "collection_rate": _scalar_metric(collection_rate),
            },
        },
        "accounts_payable_automation": {
            "title": "Accounts Payable Automation",
            "status": qb_status,
            "summary": "QuickBooks expense totals and posting-queue workflow counts from the import cache.",
            "metrics": {
                "open_bills_total": None,
                "expense_total": _scalar_metric(expense_total),
                "posting_queue_pending_count": _scalar_metric(posting_queue_pending),
            },
        },
        "smart_claims_and_receivables": {
            "title": "Smart Claims & Receivables",
            "status": claims_status,
            "summary": "SoftDent claims and receivables totals derived from imported practice operations data.",
            "metrics": {
                "outstanding_claim_count": _scalar_metric(_coerce_int(claims.get("true_outstanding_claims_count"))),
                "outstanding_claim_amount": _scalar_metric(_coerce_float(claims.get("true_outstanding_claims_amount"))),
                "unsubmitted_claim_count": _scalar_metric(_coerce_int(claims.get("unsubmitted_claims_count"))),
                "accounts_receivable_total": _scalar_metric(_coerce_float(latest_ar.get("total_ar"))),
            },
        },
        "care_delivery_performance": {
            "title": "Care Delivery Performance",
            "status": softdent_status,
            "summary": "Practice-wide SoftDent operational balances from the import cache.",
            "metrics": {
                "provider_count": _scalar_metric(provider_count),
                "patient_count": None,
                "patient_balance_total": _scalar_metric(_coerce_float(latest_ar.get("patient_ar"))),
            },
        },
    }

    generated_at = str(summary.get("generatedAt") or summary.get("lastRefreshed") or "").strip() or None
    publish_status = _publish_job_status(widgets)

    return {
        "manager": IMPORT_CACHE_MANAGER,
        "run_id": uuid4().hex,
        "generated_at": generated_at,
        "widgets": widgets,
        "sources": {
            "quickbooks": {
                "last_status": qb_status,
                "origin": "imports",
            },
            "softdent": {
                "last_status": softdent_status,
                "origin": "imports",
            },
        },
        "jobs": {
            "import_cache_refresh": {"status": publish_status},
            "widget_publish": {"status": publish_status},
        },
    }


def refresh_import_driven_widget_feed() -> dict[str, Any]:
    from app.routes import _build_financial_summary_payload

    from .widget_feed import record_widget_feed

    summary = _build_financial_summary_payload()
    payload = build_widget_feed_from_financial_summary(summary)
    return record_widget_feed(payload)


__all__ = [
    "IMPORT_CACHE_MANAGER",
    "build_widget_feed_from_financial_summary",
    "refresh_import_driven_widget_feed",
]
