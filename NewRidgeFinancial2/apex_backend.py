"""
NR2-Apex backend — widget feeds wrapping existing NR2 data layer.

All APEX_PAGES have dedicated builders fed by financial_reports + import_loader.
Never invent dollar amounts — missing fields become honest empty KPIs.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

APEX_PAGES = (
    "financial",
    "taxes",
    "softdent",
    "quickbooks",
    "ar",
    "claims",
    "content",
    "narratives",
    "documents",
    "library",
    "office-manager",
    "hal",
)

BUILD_ID = "hal-10629"


def _apex_blank_all_widgets() -> bool:
    """Blank every Apex page stage (no page widgets).

    Default ON — page widgets and their CSS were removed for redesign.
    Set NR2_APEX_BLANK_WIDGETS=0 to restore builder payloads (tests/CI).
    """
    raw = os.getenv("NR2_APEX_BLANK_WIDGETS")
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}

HAL_STATUS_SUGGESTION = (
    "Dictate findings: … · morning financial brief · which widgets empty on all pages? · SoftDent sync"
)

# In-memory print packet store (session-local; browser print is primary)
_PRINT_PACKETS: dict[str, dict[str, Any]] = {}
_NARRATIVE_PACKETS: dict[str, dict[str, Any]] = {}
_WORKPAPER_PACKETS: dict[str, dict[str, Any]] = {}
_TICKER_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_TICKER_CACHE_TTL_SEC = 10.0
_WIDGETS_CACHE: dict[str, dict[str, Any]] = {}
_WIDGETS_CACHE_TTL_SEC = 15.0
_WIDGETS_FILL_FAILURES = 0  # Moonshot cache coherence — fill-thread crash counter
_LAST_SYNC_ERROR: str = ""
_LAST_SYNC_AT: str = ""
_REPORTS_BUNDLE_CACHE: dict[str, Any] = {"at": 0.0, "reports": None, "bundle": None, "errors": None}
# Moonshot import-cache KPIs: align TTL with widgets (was 20s → thundering herd)
_REPORTS_BUNDLE_CACHE_TTL_SEC = 15.0
_REPORTS_BUNDLE_CACHE_LOCK = threading.Lock()
_BUNDLE_LOAD_LOCK = threading.Lock()
_BUNDLE_LOAD_EVENT: threading.Event | None = None
# Moonshot crash/perf SHOULD: Sync back-pressure
_SYNC_SEMAPHORE = threading.Semaphore(1)
# Moonshot import-cache KPIs MUST: per-page fill progress (not a global singleton)
_FILL_PROGRESS: dict[str, dict[str, Any]] = {}
_FILL_PROGRESS_LOCK = threading.Lock()


def _update_fill_progress(pid: str, pct: int) -> None:
    """Thread-safe per-page fill progress (Moonshot import-cache KPIs)."""
    key = str(pid or "").strip() or "_"
    with _FILL_PROGRESS_LOCK:
        _FILL_PROGRESS[key] = {"pct": max(0, min(100, int(pct))), "ts": time.time()}


def _get_fill_progress(pid: str) -> dict[str, Any]:
    key = str(pid or "").strip() or "_"
    with _FILL_PROGRESS_LOCK:
        hit = _FILL_PROGRESS.get(key)
        return dict(hit) if isinstance(hit, dict) else {"pct": 0, "ts": 0.0}


def _prune_fill_progress(max_age_sec: float = 300.0) -> None:
    cutoff = time.time() - max_age_sec
    with _FILL_PROGRESS_LOCK:
        stale = [k for k, v in _FILL_PROGRESS.items() if float(v.get("ts") or 0.0) < cutoff]
        for k in stale:
            _FILL_PROGRESS.pop(k, None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).replace("$", "").replace(",", "").strip()
    if not raw or raw in {"—", "-", "N/A", "n/a", "null"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raw = str(value).replace(",", "").strip()
    if not raw:
        return None
    match = re.search(r"-?\d+", raw)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _section(bundle: dict[str, Any], system: str, key: str) -> dict[str, Any]:
    root = bundle.get(system) if isinstance(bundle.get(system), dict) else {}
    section = root.get(key) if isinstance(root, dict) else None
    return section if isinstance(section, dict) else {}


def _section_rows(bundle: dict[str, Any], system: str, key: str) -> list[dict[str, Any]]:
    section = _section(bundle, system, key)
    rows = section.get("rows")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    data = section.get("data")
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return []


def _dashboard_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    dash = sd.get("dashboard") if isinstance(sd.get("dashboard"), dict) else {}
    rows = dash.get("rows")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    if isinstance(dash.get("data"), list):
        return [r for r in dash["data"] if isinstance(r, dict)]
    return []


def _latest_period_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None

    def sort_key(row: dict[str, Any]) -> str:
        return str(row.get("period") or row.get("year_month") or row.get("month") or row.get("Period") or "")

    ordered = sorted(rows, key=sort_key)
    return ordered[-1] if ordered else None


def _spark_from_rows(rows: list[dict[str, Any]], field: str) -> list[float]:
    vals: list[float] = []
    for row in rows[-7:]:
        n = _parse_money(row.get(field))
        if n is not None:
            vals.append(n)
    return vals


def _empty_kpi(widget_id: str, label: str, *, hint: str) -> dict[str, Any]:
    """Honest empty KPI — collapse/omit by density contract (never $0 pad)."""
    return {
        "id": widget_id,
        "type": "kpi",
        "label": label,
        "value": None,
        "status": "empty",
        "emptyMessage": "No data",
        "display": "—",
        "hint": hint,
        "collapseWhenEmpty": True,
        "omitWhenEmpty": True,
        "emptyIsNotZero": True,
        "honestyDef": "HAL-10591",
        "size": "s",
    }


def _money_kpi(
    widget_id: str,
    label: str,
    value: float | None,
    *,
    hint: str,
    delta_label: str | None = None,
    sparkline: list[float] | None = None,
) -> dict[str, Any]:
    if value is None:
        return _empty_kpi(widget_id, label, hint=hint)
    out: dict[str, Any] = {
        "id": widget_id,
        "type": "kpi",
        "label": label,
        "value": float(value),
        "unit": "money",
        "display": f"${float(value):,.2f}",
        "hint": hint,
        "emptyIsNotZero": True,
        "honestyDef": "HAL-10591",
    }
    if delta_label:
        out["deltaLabel"] = delta_label
    if sparkline:
        out["sparkline"] = sparkline
    return out


def _count_kpi(
    widget_id: str,
    label: str,
    value: int | float | None,
    *,
    hint: str,
    delta_label: str | None = None,
) -> dict[str, Any]:
    if value is None:
        return _empty_kpi(widget_id, label, hint=hint)
    out: dict[str, Any] = {
        "id": widget_id,
        "type": "kpi",
        "label": label,
        "value": int(value) if float(value).is_integer() else float(value),
        "unit": "count",
        "hint": hint,
    }
    if delta_label:
        out["deltaLabel"] = delta_label
    return out


def _status_widget(
    widget_id: str,
    label: str,
    *,
    message: str,
    hint: str,
    status: str = "ok",
) -> dict[str, Any]:
    return {
        "id": widget_id,
        "type": "status",
        "label": label,
        "status": status,
        "message": message,
        "hint": hint,
    }


def _empty_chart(widget_id: str, label: str, *, hint: str, chart_type: str = "bar") -> dict[str, Any]:
    return {
        "id": widget_id,
        "type": "chart",
        "chartType": chart_type,
        "label": label,
        "series": [],
        "status": "empty",
        "emptyMessage": "No chart data",
        "hint": hint,
    }


def _visual_boost_financial(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Origin/Copilot-inspired density instruments — import-backed only."""
    out: list[dict[str, Any]] = []
    rows = _dashboard_rows(bundle)
    coll_spark = _spark_from_rows(rows, "collections")
    prod_spark = _spark_from_rows(rows, "production")

    # Morning brief — status from import health + HAL suggestion text (no invented $)
    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    connected = summary.get("connected")
    total = summary.get("total")
    missing = summary.get("missing")
    brief = "Imports ready."
    if isinstance(connected, int) and isinstance(total, int) and total > 0:
        brief = f"Imports {connected}/{total}"
        if isinstance(missing, int) and missing:
            brief += f" · {missing} missing"
    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    if ar.get("followUpHint"):
        brief += f" · {ar['followUpHint']}"
    out.append(
        _status_widget(
            "morning-brief",
            "Morning Brief",
            message=brief,
            hint="At-a-glance from SoftDent/QB import diagnostics — not a bank forecast.",
            status="ok" if isinstance(connected, int) else "empty",
        )
    )

    # Collections pulse — historical average of imported periods only
    if coll_spark and len(coll_spark) >= 2:
        avg = sum(coll_spark) / len(coll_spark)
        out.append(
            {
                "id": "liquidity-pulse",
                "type": "pulse",
                "label": "Collections Pulse",
                "size": "l",
                "value": float(avg),
                "unit": "money",
                "deltaLabel": f"avg of {len(coll_spark)} imported periods",
                "segments": [{"label": f"P{i+1}", "value": float(v)} for i, v in enumerate(coll_spark[-8:])],
                "hint": "Historical SoftDent collections average — not projected bank cash.",
                "status": "ok",
            }
        )
    elif prod_spark and len(prod_spark) >= 2:
        avg = sum(prod_spark) / len(prod_spark)
        out.append(
            {
                "id": "liquidity-pulse",
                "type": "pulse",
                "label": "Production Pulse",
                "size": "l",
                "value": float(avg),
                "unit": "money",
                "deltaLabel": f"avg of {len(prod_spark)} imported periods",
                "segments": [{"label": f"P{i+1}", "value": float(v)} for i, v in enumerate(prod_spark[-8:])],
                "hint": "Historical SoftDent production average — collections pending/missing.",
                "status": "ok",
            }
        )
    else:
        out.append(
            {
                "id": "liquidity-pulse",
                "type": "pulse",
                "label": "Collections Pulse",
                "size": "l",
                "status": "empty",
                "emptyMessage": "No pulse data",
                "segments": [],
                "hint": "Need ≥2 SoftDent dashboard periods for historical pulse.",
            }
        )
    return out


def _visual_boost_ar(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    buckets = reports.get("arAgingBuckets") if isinstance(reports.get("arAgingBuckets"), list) else []
    ar_total = ar.get("totalOutstanding")
    ninety = ar.get("ninetyPlusOutstanding")
    if not isinstance(ninety, (int, float)):
        for b in buckets:
            if not isinstance(b, dict):
                continue
            label = str(b.get("bucket") or "").lower()
            if "90" in label or "90+" in label:
                amt = b.get("amount")
                if isinstance(amt, (int, float)):
                    ninety = float(amt)
                    break

    if isinstance(ar_total, (int, float)):
        priority = float(ninety) if isinstance(ninety, (int, float)) else None
        under_90 = float(ar_total) - priority if priority is not None else None
        segments = []
        for b in buckets:
            if not isinstance(b, dict):
                continue
            amt = b.get("amount")
            if isinstance(amt, (int, float)) and amt >= 0:
                segments.append({"label": str(b.get("bucket") or "bucket"), "value": float(amt)})
        out.append(
            {
                "id": "collectible-remainder",
                "type": "remainder",
                "label": "Collectible Focus",
                "size": "l",
                "gross": float(ar_total),
                "priorityVintage": priority,
                "underNinety": under_90,
                "unit": "money",
                "segments": segments,
                "hint": "Gross A/R and 90+ from SoftDent import only — no invented denials/overhead.",
                "status": "ok",
            }
        )
    else:
        out.append(
            {
                "id": "collectible-remainder",
                "type": "remainder",
                "label": "Collectible Focus",
                "size": "l",
                "status": "empty",
                "emptyMessage": "No A/R totals",
                "hint": "Import SoftDent A/R aging to populate collectible focus.",
            }
        )

    # Heatmap rows from SoftDent A/R export (top balances)
    ar_rows = _section_rows(bundle, "softdent", "ar")
    grid: list[dict[str, Any]] = []
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in ar_rows:
        bal = _parse_money(row.get("Balance") or row.get("Outstanding") or row.get("Amount") or row.get("Total"))
        if bal is None:
            continue
        age = _parse_int(row.get("Age") or row.get("Days") or row.get("AgingDays") or row.get("ageDays"))
        name = str(
            row.get("Patient")
            or row.get("Name")
            or row.get("Account")
            or row.get("Guarantor")
            or row.get("Id")
            or "row"
        )[:40]
        bucket = "unknown"
        risk = "low"
        if age is not None:
            if age >= 90:
                bucket, risk = "90+", "high"
            elif age >= 61:
                bucket, risk = "61-90", "high"
            elif age >= 31:
                bucket, risk = "31-60", "medium"
            else:
                bucket, risk = "0-30", "low"
        else:
            bucket = str(row.get("Bucket") or row.get("Aging") or row.get("AgeBucket") or "unknown")
            if "90" in bucket:
                risk = "high"
            elif "60" in bucket or "61" in bucket:
                risk = "high"
            elif "30" in bucket or "31" in bucket:
                risk = "medium"
        scored.append((float(bal), {"label": name, "balance": float(bal), "ageBucket": bucket, "risk": risk}))
    scored.sort(key=lambda x: x[0], reverse=True)
    grid = [item for _, item in scored[:8]]
    out.append(
        {
            "id": "ar-heatmap-grid",
            "type": "heatmap",
            "label": "A/R Heatmap",
            "size": "xl",
            "grid": grid,
            "status": "ok" if grid else "empty",
            "emptyMessage": "No A/R rows",
            "hint": "Top balances from SoftDent A/R import — risk from age bucket only.",
        }
    )
    return out


def _visual_boost_claims(bundle: dict[str, Any], reports: dict[str, Any]) -> list[dict[str, Any]]:
    summary = _claims_summary_from_bundle(bundle)
    ct = reports.get("claimTracking") if isinstance(reports.get("claimTracking"), dict) else {}
    by_status = summary.get("byStatus") if isinstance(summary.get("byStatus"), dict) else {}
    stages: list[dict[str, Any]] = []
    if by_status:
        # Group statuses into funnel buckets without inventing counts
        buckets = {"open": 0, "submitted": 0, "pending": 0, "denied": 0, "paid": 0, "other": 0}
        for status, count in by_status.items():
            n = int(count) if isinstance(count, int) else 0
            s = str(status).lower()
            if re.search(r"denied|reject", s):
                buckets["denied"] += n
            elif re.search(r"paid|complete|closed", s):
                buckets["paid"] += n
            elif re.search(r"submit", s):
                buckets["submitted"] += n
            elif re.search(r"pending|hold|review|process", s):
                buckets["pending"] += n
            elif re.search(r"open", s):
                buckets["open"] += n
            else:
                buckets["other"] += n
        for key in ("open", "submitted", "pending", "denied", "paid", "other"):
            if buckets[key]:
                stages.append({"stage": key, "count": buckets[key]})
    elif summary.get("available"):
        if isinstance(summary.get("openCount"), int):
            stages.append({"stage": "open", "count": summary["openCount"]})
        if isinstance(summary.get("deniedCount"), int):
            stages.append({"stage": "denied", "count": summary["deniedCount"]})
        if isinstance(summary.get("totalClaims"), int):
            stages.append({"stage": "total", "count": summary["totalClaims"]})
    elif isinstance(ct.get("totalClaims"), int):
        stages.append({"stage": "total", "count": int(ct["totalClaims"])})
        if isinstance(ct.get("deniedCount"), int):
            stages.append({"stage": "denied", "count": int(ct["deniedCount"])})

    return [
        {
            "id": "claims-velocity-funnel",
            "type": "funnel",
            "label": "Claims Velocity",
            "size": "l",
            "stages": stages,
            "status": "ok" if stages else "empty",
            "emptyMessage": "No claims stages",
            "hint": "Status funnel from SoftDent ClaimStatus import — not invented.",
        }
    ]


def _visual_boost_taxes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    quarterly = plan.get("quarterlyEstimates") if isinstance(plan.get("quarterlyEstimates"), list) else []
    items: list[dict[str, Any]] = []
    for q in quarterly[:4]:
        if not isinstance(q, dict):
            continue
        due = str(q.get("due") or q.get("dueDate") or q.get("label") or "").strip()
        fed = _parse_money(q.get("federal"))
        ks = _parse_money(q.get("kansas"))
        total = None
        if fed is not None and ks is not None:
            total = fed + ks
        elif fed is not None:
            total = fed
        elif ks is not None:
            total = ks
        items.append(
            {
                "label": due or "Quarter",
                "due": due or None,
                "amount": total,
                "federal": fed,
                "kansas": ks,
            }
        )

    days_remaining = None
    next_due = None
    next_amount = None
    today = datetime.now(timezone.utc).date()
    for item in items:
        due_raw = item.get("due") or ""
        # Try ISO or common US date fragments
        parsed = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                parsed = datetime.strptime(str(due_raw)[:10], fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            continue
        delta = (parsed - today).days
        if delta >= 0 and (days_remaining is None or delta < days_remaining):
            days_remaining = delta
            next_due = parsed.isoformat()
            next_amount = item.get("amount")

    return [
        {
            "id": "obligation-countdown",
            "type": "countdown",
            "label": "Tax Obligation Horizon",
            "size": "l",
            "items": items,
            "nextDue": next_due,
            "daysRemaining": days_remaining,
            "nextAmount": next_amount,
            "unit": "money",
            "status": "ok" if items else "empty",
            "emptyMessage": "No quarterly estimates",
            "hint": "From tax_engine quarterly lines on QB book income — planning only, CPA review required.",
        }
    ]


def _category_leaf(name: str) -> str:
    """Prefer the rightmost human label from QB hierarchical Category paths."""
    text = str(name or "").strip()
    if not text:
        return ""
    # Paths look like: "… · Taxes:… · Federal:… · Payroll Expenses"
    parts = [p.strip() for p in re.split(r"\s*[·•|]\s*", text) if p.strip()]
    if not parts:
        return text
    leaf = parts[-1]
    # Drop "Taxes:123" style prefixes inside a segment
    if ":" in leaf:
        after = leaf.split(":")[-1].strip()
        if after and not after.replace(".", "", 1).isdigit():
            leaf = after
    return leaf or text


def _keyword_hit(text: str, key: str) -> bool:
    """Substring match with word-ish boundaries for short keys (avoid lab⊂labor)."""
    k = (key or "").lower().strip()
    t = (text or "").lower()
    if not k or not t:
        return False
    if len(k) <= 3:
        return re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", t) is not None
    return k in t


def _suggest_expense_category(memo: str) -> tuple[str, str]:
    """Local keyword categorize — no invented dollars, no external AI required."""
    leaf = _category_leaf(memo)
    # Match leaf first, then full path (leaf wins for precision)
    texts = [leaf.lower(), (memo or "").lower()]
    rules = (
        (("payroll tax", "payroll expenses", "payroll", "wage", "salary", "adp", "gusto", "paychex", "officer"), "Payroll", "keyword"),
        (("contract labor", "nprofessonal", "nprofessional", "professional fee", "prof fee"), "Professional Fees", "keyword"),
        (("rent", "lease", "landlord", "facility"), "Rent / Facility", "keyword"),
        (("laboratory", "lab fees", "dental lab", "glidwell", "dds lab"), "Lab Fees", "keyword"),
        (("dental", "supply", "supplies", "henry schein", "patterson", "benco", "dental supply"), "Dental Supplies", "keyword"),
        (("insur", "malpractice", "liability premium"), "Insurance", "keyword"),
        (("utilit", "electric", "gas bill", "water", "internet", "phone", "website"), "Utilities", "keyword"),
        (("software", "subscription", "saas", "microsoft", "adobe", "computer"), "Software / Subscriptions", "keyword"),
        (("marketing", "ads", "google ads", "facebook", "advertis"), "Marketing", "keyword"),
        (("state corp", "corp tax", "federal tax", "income tax"), "Taxes", "keyword"),
        (("cpa", "bookkeep", "tax prep", "legal"), "Professional Fees", "keyword"),
        (("loan", "interest", "bank fee", "merchant", "finance"), "Bank / Finance", "keyword"),
        (("depreci", "amort"), "Depreciation", "keyword"),
        (("travel", "mileage", "hotel", "airfare"), "Travel", "keyword"),
        (("repair", "maintenance", "janitor", "clean"), "Repairs / Maintenance", "keyword"),
        (("office", "postage", "shipping", "print"), "Office Expense", "keyword"),
        (("lab",), "Lab Fees", "keyword"),  # short key last; boundary-safe
    )
    for text in texts:
        for keys, cat, how in rules:
            if any(_keyword_hit(text, k) for k in keys):
                return cat, how
    return "Uncategorized", "none"


def build_categorize_assist(bundle: dict[str, Any]) -> dict[str, Any]:
    """Preview local category suggestions from QB expense category / memo imports."""
    cat_rows = _section_rows(bundle, "quickbooks", "expenseCategories")
    txn_rows = _section_rows(bundle, "quickbooks", "expenses") or _section_rows(
        bundle, "quickbooks", "transactions"
    )
    suggestions: list[dict[str, Any]] = []

    # Primary: expenseCategories (Category + Amount + Scope) — common NR2 import shape
    for row in cat_rows:
        name = str(row.get("Category") or row.get("Account") or row.get("Name") or "").strip()
        if not name:
            continue
        leaf = _category_leaf(name)
        suggested, method = _suggest_expense_category(name)
        # If keyword matched a cleaner label, prefer it; else keep imported leaf as confirmed
        if method == "none":
            suggested = leaf or name
            method = "import-label"
        amt = _parse_money(row.get("Amount") or row.get("amount") or row.get("Total"))
        scope = str(row.get("Scope") or "").strip()
        display = leaf or name
        if scope:
            display = f"{display} · {scope}"
        suggestions.append(
            {
                "memo": display[:90],
                "existing": (leaf or name)[:80],
                "suggested": suggested,
                "method": method,
                "amount": amt,
            }
        )
        if len(suggestions) >= 8:
            break

    # Secondary: expense/transaction memos when present (Period totals alone are skipped)
    if len(suggestions) < 8:
        for row in txn_rows:
            memo = str(
                row.get("Memo")
                or row.get("Description")
                or row.get("Name")
                or row.get("Payee")
                or ""
            ).strip()
            # Skip period-total rollups (no memo — only Period/TotalExpense)
            if not memo and ("Period" in row and ("TotalExpense" in row or "TotalIncome" in row)):
                continue
            if not memo:
                continue
            existing = str(row.get("Category") or row.get("Account") or "").strip()
            suggested, method = _suggest_expense_category(memo)
            generic = not existing or existing.lower() in {
                "uncategorized",
                "expense",
                "expenses",
                "other",
                "ask my accountant",
            }
            if not generic and method == "none":
                continue
            amt = _parse_money(row.get("Amount") or row.get("amount") or row.get("Total"))
            suggestions.append(
                {
                    "memo": memo[:80],
                    "existing": existing or "—",
                    "suggested": suggested,
                    "method": method,
                    "amount": amt,
                }
            )
            if len(suggestions) >= 8:
                break

    hint = "Keyword suggestions from QuickBooks import — local only, not posted to QB."
    if not suggestions and txn_rows and not cat_rows:
        hint = "QB expenses import has period totals only — no category/memo lines to suggest."
    elif not suggestions:
        hint = "Import QuickBooks expense categories (or memo lines) to populate categorize assist."

    return {
        "id": "hal-categorize-assist",
        "type": "categorize",
        "label": "Local Categorize Assist",
        "size": "xl",
        "suggestions": suggestions,
        "status": "ok" if suggestions else "empty",
        "emptyMessage": "No expense categories/memos to suggest",
        "hint": hint,
    }


def _visual_boost_office_calculator(bundle: dict[str, Any]) -> dict[str, Any]:
    # Fee schedule sample for local calculator defaults (no external POST)
    fees = _section_rows(bundle, "softdent", "feeSchedule") or _section_rows(bundle, "softdent", "fees")
    samples: list[dict[str, Any]] = []
    for row in fees[:6]:
        code = str(row.get("Code") or row.get("ADACode") or row.get("Procedure") or "").strip()
        fee = _parse_money(row.get("Fee") or row.get("Amount") or row.get("Price"))
        if code and fee is not None:
            samples.append({"code": code, "fee": float(fee)})
    return {
        "id": "patient-responsibility-calc",
        "type": "calculator",
        "label": "Patient Responsibility Estimator",
        "size": "xl",
        "feeSamples": samples,
        "status": "ok",
        "hint": "Local calculator only — uses imported fee samples when present; never posts PHI off-box.",
    }


def build_provider_horizontal_bars(bundle: dict[str, Any]) -> dict[str, Any]:
    """Top providers by SoftDent procedure Production — honest empty if no breakdown."""
    rows = _section_rows(bundle, "softdent", "procedures")
    totals: dict[str, float] = {}
    for row in rows:
        prov = str(row.get("Provider") or row.get("provider") or row.get("Doctor") or "").strip()
        if not prov:
            continue
        amt = _parse_money(row.get("Production") or row.get("Amount") or row.get("Fee") or row.get("Total"))
        if amt is None:
            continue
        totals[prov] = totals.get(prov, 0.0) + float(amt)
    bars = [
        {"label": k[:40], "value": v}
        for k, v in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:8]
    ]
    thin = len(bars) <= 1
    if not bars:
        return {
            "id": "provider-hbar",
            "type": "horizontal-bar",
            "label": "Provider Production",
            "size": "l",
            "bars": [],
            "status": "empty",
            "emptyMessage": "No provider breakdown available",
            "hint": "Import SoftDent procedures with Provider + Production to populate.",
        }
    return {
        "id": "provider-hbar",
        "type": "horizontal-bar",
        "label": "Provider Production",
        "size": "l",
        "bars": bars,
        "status": "ok",
        "hint": (
            "Aggregated SoftDent procedure Production by Provider."
            + (" Thin breakdown (few providers in import)." if thin else "")
        ),
    }


def build_expense_horizontal_bars(bundle: dict[str, Any]) -> dict[str, Any]:
    """Top QB expenseCategories as horizontal bars."""
    rows = _section_rows(bundle, "quickbooks", "expenseCategories")
    bars: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("Category") or row.get("Account") or row.get("Name") or "").strip()
        if not name:
            continue
        leaf = _category_leaf(name)
        amt = _parse_money(row.get("Amount") or row.get("amount") or row.get("Total"))
        if amt is None:
            continue
        bars.append({"label": (leaf or name)[:40], "value": float(amt)})
    bars = sorted(bars, key=lambda b: b["value"], reverse=True)[:8]
    if not bars:
        return {
            "id": "qb-expense-hbar",
            "type": "horizontal-bar",
            "label": "Expense Categories",
            "size": "l",
            "bars": [],
            "status": "empty",
            "emptyMessage": "No expense categories",
            "hint": "Import QuickBooks expenseCategories to populate.",
        }
    return {
        "id": "qb-expense-hbar",
        "type": "horizontal-bar",
        "label": "Expense Categories",
        "size": "l",
        "bars": bars,
        "status": "ok",
        "hint": "From QuickBooks expenseCategories import — amounts not invented.",
    }


def build_payer_donut(bundle: dict[str, Any]) -> dict[str, Any]:
    """Payer mix: multi-carrier from claims, else Insurance vs Patient from dashboard."""
    claim_rows = _section_rows(bundle, "softdent", "claims") or _section_rows(
        bundle, "softdent", "claimStatus"
    )
    by_payer: dict[str, float] = {}
    money_seen = False
    for row in claim_rows:
        payer = str(row.get("Payer") or row.get("Carrier") or row.get("Insurance") or "").strip()
        if not payer:
            continue
        amt = None
        for key in ("Amount", "Billed", "Charge", "Paid", "Balance"):
            amt = _parse_money(row.get(key))
            if amt is not None:
                money_seen = True
                break
        if amt is not None:
            by_payer[payer] = by_payer.get(payer, 0.0) + float(amt)
        else:
            by_payer[payer] = by_payer.get(payer, 0.0) + 1.0

    slices: list[dict[str, Any]] = []
    unit = "money"
    if len(by_payer) >= 2:
        for k, v in sorted(by_payer.items(), key=lambda kv: kv[1], reverse=True)[:8]:
            slices.append({"label": k[:32], "value": float(v)})
        if not money_seen:
            unit = "count"
    else:
        latest = _latest_period_row(_dashboard_rows(bundle))
        if latest:
            pending = bool(latest.get("collectionsPending"))
            ins_raw = latest.get("insurance")
            if ins_raw is None:
                ins_raw = latest.get("Insurance")
            pat_raw = latest.get("patient")
            if pat_raw is None:
                pat_raw = latest.get("Patient")
            ins = _parse_money(ins_raw)
            pat = _parse_money(pat_raw)
            # Honest empty: both zero while collections pending / unreported → no real split
            # Also: insurance=0 with all collections in patient is SoftDent dump, not a real mix
            if pending and (ins or 0) == 0 and (pat or 0) == 0:
                ins = None
                pat = None
            elif ins == 0.0 and pat == 0.0 and "collections" not in latest:
                ins = None
                pat = None
            elif (ins or 0) <= 0 and (pat or 0) > 0:
                ins = None
                pat = None
            if ins is not None and pat is not None and float(ins) > 0 and float(pat) > 0:
                slices.append({"label": "Insurance", "value": float(ins)})
                slices.append({"label": "Patient", "value": float(pat)})
            unit = "money"

    if len(slices) < 1:
        return {
            "id": "payer-donut",
            "type": "donut",
            "label": "Payer Mix",
            "size": "l",
            "slices": [],
            "status": "empty",
            "emptyMessage": "No payer classification",
            "hint": "Need SoftDent claims with Payer, or a real insurance/patient split (both sides > 0). Register Ins Plan $0 / all-patient dumps stay empty.",
        }
    return {
        "id": "payer-donut",
        "type": "donut",
        "label": "Payer Mix" if len(by_payer) >= 2 else "Insurance vs Patient",
        "size": "l",
        "slices": slices,
        "unit": unit,
        "status": "ok",
        "hint": (
            "From SoftDent claims by Payer."
            if len(by_payer) >= 2
            else "From SoftDent dashboard insurance/patient fields — not carrier-level."
        ),
    }


def build_ins_patient_split(bundle: dict[str, Any]) -> dict[str, Any]:
    """Stacked bar: Insurance vs Patient from dashboard (import-backed only)."""
    latest = _latest_period_row(_dashboard_rows(bundle))
    segs: list[dict[str, Any]] = []
    pending = False
    if latest:
        pending = bool(latest.get("collectionsPending"))
        ins_raw = latest.get("insurance")
        if ins_raw is None:
            ins_raw = latest.get("Insurance")
        pat_raw = latest.get("patient")
        if pat_raw is None:
            pat_raw = latest.get("Patient")
        ins = _parse_money(ins_raw)
        pat = _parse_money(pat_raw)
        # Do not display $0/$0 or $0/all-patient as a real split
        if pending and (ins or 0) == 0 and (pat or 0) == 0:
            ins = None
            pat = None
        elif ins == 0.0 and pat == 0.0 and "collections" not in latest:
            ins = None
            pat = None
        elif (ins or 0) <= 0 and (pat or 0) > 0:
            ins = None
            pat = None
        if ins is not None and pat is not None and float(ins) > 0 and float(pat) > 0:
            segs.append({"label": "Insurance", "value": float(ins)})
            segs.append({"label": "Patient", "value": float(pat)})
    if not segs:
        gap_code = None
        try:
            from apex_softdent_hardening_pack import assess_collections_gap

            gap_code = assess_collections_gap(bundle).get("gapCode")
        except Exception:
            gap_code = None
        return {
            "id": "ins-patient-split",
            "type": "stacked-bar",
            "label": "Insurance vs Patient",
            "size": "l",
            "segments": [],
            "status": "empty",
            "emptyMessage": "Collections pending — no split" if pending else "No real insurance/patient split",
            "hint": (
                "SoftDent latest period has collectionsPending — insurance/patient stay empty until collections export reports a real split."
                if pending
                else "Need both insurance > 0 and patient > 0 (Register Ins Plan $0 / all-patient dumps are not a mix)."
            ),
            "gapCode": gap_code,
            "def": "DEF-001" if pending or gap_code not in (None, "OK") else None,
        }
    return {
        "id": "ins-patient-split",
        "type": "stacked-bar",
        "label": "Insurance vs Patient",
        "size": "l",
        "segments": segs,
        "status": "ok",
        "hint": "Composition from SoftDent dashboard — not invented.",
    }


def build_collection_bullet(bundle: dict[str, Any]) -> dict[str, Any]:
    """Collection efficiency = collections / production when both reported (no invented target)."""
    rows = _dashboard_rows(bundle)
    chosen = None
    for row in reversed(rows):  # prefer newer periods that have both
        if not isinstance(row, dict):
            continue
        prod = _parse_money(row.get("production"))
        if prod is None or prod <= 0:
            continue
        if row.get("collectionsReported") is False or row.get("collectionsPending") is True:
            continue
        if "collections" not in row:
            continue
        coll = _parse_money(row.get("collections"))
        if coll is None:
            continue
        chosen = (row, prod, coll)
        break
    if not chosen:
        return {
            "id": "collection-bullet",
            "type": "bullet",
            "label": "Collection Efficiency",
            "size": "s",
            "status": "empty",
            "emptyMessage": "Collections pending",
            "hint": "Ratio appears when both production and collections are reported for a period.",
        }
    row, prod, coll = chosen
    ratio = float(coll) / float(prod) * 100.0
    return {
        "id": "collection-bullet",
        "type": "bullet",
        "label": "Collection Efficiency",
        "size": "s",
        "value": round(ratio, 1),
        "unit": "percent",
        "ranges": [
            {"max": 85, "tone": "warn"},
            {"max": 95, "tone": "mid"},
            {"max": 110, "tone": "ok"},
        ],
        "target": None,
        "status": "ok",
        "hint": f"Collections ÷ production for {row.get('period') or row.get('year_month') or 'period'} — scale bands are visual only.",
    }


def build_ar_waterfall(reports: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """A/R aging bucket waterfall — buckets only (no invented adjustments/gross)."""
    buckets = reports.get("arAgingBuckets") if isinstance(reports.get("arAgingBuckets"), list) else []
    steps: list[dict[str, Any]] = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        amt = b.get("amount")
        if isinstance(amt, (int, float)):
            steps.append(
                {
                    "label": str(b.get("bucket") or ""),
                    "value": float(amt),
                    "kind": "positive",
                }
            )
    if not steps:
        ar_rows = _section_rows(bundle, "softdent", "ar")
        for row in ar_rows:
            label = str(row.get("Bucket") or row.get("Aging") or row.get("AgeBucket") or "").strip()
            amt = _parse_money(row.get("Balance") or row.get("Outstanding") or row.get("Amount"))
            if label and amt is not None:
                steps.append({"label": label, "value": float(amt), "kind": "positive"})
    if not steps:
        return {
            "id": "ar-waterfall",
            "type": "waterfall",
            "label": "A/R Aging Flow",
            "size": "xl",
            "steps": [],
            "status": "empty",
            "emptyMessage": "No aging buckets",
            "hint": "Import SoftDent A/R aging. Adjustments walk omitted (not in import).",
        }
    total = sum(s["value"] for s in steps)
    steps.append({"label": "Total A/R", "value": float(total), "kind": "total"})
    return {
        "id": "ar-waterfall",
        "type": "waterfall",
        "label": "A/R Aging Flow",
        "size": "xl",
        "steps": steps,
        "status": "ok",
        "hint": "Bucket balances from SoftDent A/R — not Gross→Adjustments (those fields absent).",
    }


def build_period_scrubber(bundle: dict[str, Any], *, page: str = "financial") -> dict[str, Any]:
    """Timeline of imported SoftDent dashboard periods (display + select hint)."""
    rows = _dashboard_rows(bundle)
    periods: list[str] = []
    for row in rows:
        p = str(row.get("period") or row.get("year_month") or row.get("Period") or "").strip()
        if p and p not in periods:
            periods.append(p)
    latest = _latest_period_row(rows)
    active = str((latest or {}).get("period") or (latest or {}).get("year_month") or "")
    if page == "taxes":
        # Prefer tax quarter labels when tax plan has quarterly lines
        try:
            from tax_engine import build_tax_plan_from_bundle

            plan = build_tax_plan_from_bundle(bundle) or {}
            qlines = plan.get("quarterlyEstimates") or plan.get("quarters") or []
            q_periods: list[str] = []
            if isinstance(qlines, list):
                for q in qlines:
                    if isinstance(q, dict):
                        lab = str(q.get("label") or q.get("quarter") or q.get("Period") or "").strip()
                        if lab and lab not in q_periods:
                            q_periods.append(lab)
            if q_periods:
                periods = q_periods
                active = q_periods[0]
        except Exception:
            pass
    if not periods:
        return {
            "id": f"{page}-period-scrubber",
            "type": "scrubber",
            "label": "Period Horizon",
            "size": "full",
            "periods": [],
            "active": "",
            "status": "empty",
            "emptyMessage": "No periods",
            "hint": "Import SoftDent dashboard periods (or tax quarters) to scrub the timeline.",
        }
    return {
        "id": f"{page}-period-scrubber",
        "type": "scrubber",
        "label": "Period Horizon",
        "size": "full",
        "periods": periods,
        "active": active,
        "status": "ok",
        "hint": "Imported periods only — selection highlights active period label (no invented dates).",
    }


def _apply_threshold_alerts(
    widgets: list[dict[str, Any]], reports: dict[str, Any], *, claims_summary: dict[str, Any] | None = None
) -> None:
    """Mark widgets with alert=True when import-backed thresholds are exceeded."""
    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    ninety_pct = ar.get("ninetyPlusPct")
    ar_alert = isinstance(ninety_pct, (int, float)) and float(ninety_pct) > 20.0
    denial_alert = False
    if claims_summary and claims_summary.get("available"):
        total = claims_summary.get("totalClaims")
        denied = claims_summary.get("deniedCount")
        if isinstance(total, int) and total > 0 and isinstance(denied, int):
            denial_alert = (denied / total) * 100.0 > 15.0
    for w in widgets:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("id") or "")
        if ar_alert and wid in {"ar-outstanding", "ar-90-plus-pct", "collectible-remainder", "ar-waterfall"}:
            w["alert"] = True
            w["alertReason"] = f"90+ share {float(ninety_pct):.1f}% exceeds 20% threshold"
        if denial_alert and wid in {
            "claims-denied",
            "claims-total",
            "claims-velocity-funnel",
            "claims-aging-count",
            "claims-aging-30",
            "claims-aging-60",
            "claims-aging-90",
        }:
            w["alert"] = True
            w["alertReason"] = "Denial rate exceeds 15% of imported claims"


def build_import_freshness(bundle: dict[str, Any]) -> dict[str, Any]:
    """Sync-verify banner: SoftDent/QB import health from diagnostics — no invented $."""
    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    connected = summary.get("connected")
    total = summary.get("total")
    missing = summary.get("missing")
    stale = summary.get("stale")
    loaded = str(bundle.get("loadedAt") or "").strip()
    mode = str(bundle.get("importMode") or "")
    if isinstance(connected, int) and isinstance(total, int) and total > 0:
        if (missing or 0) == 0 and (stale or 0) == 0:
            msg = f"Imports fresh · {connected}/{total}"
            status = "ok"
            hint = f"SoftDent + QuickBooks diagnostics OK · loadedAt {loaded or '—'} · mode {mode or '—'}"
        elif (missing or 0) == 0:
            msg = f"Imports partial · {connected}/{total}"
            status = "ok"
            hint = f"{stale or 0} stale dataset(s) · re-sync SoftDent/QB exports · loadedAt {loaded or '—'}"
        else:
            msg = f"Import gaps · {missing} missing"
            status = "empty"
            hint = f"{connected}/{total} connected · sync SoftDent/QuickBooks · loadedAt {loaded or '—'}"
    else:
        msg = "Imports unknown"
        status = "empty"
        hint = "Run Apex Sync (or Sync-HAL-Imports.ps1) to verify SoftDent + QuickBooks."
    return {
        "id": "import-freshness",
        "type": "status",
        "label": "Import Sync Verify",
        "size": "full",
        "message": msg,
        "status": status,
        "hint": hint,
        "loadedAt": loaded,
        "importMode": mode,
    }


def build_ebitda_waterfall(bundle: dict[str, Any]) -> dict[str, Any]:
    """EBITDA management walk from tax_engine.compute_ebitda_walk."""
    try:
        from tax_engine import compute_ebitda_walk

        walk = compute_ebitda_walk(bundle) or {}
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "ebitda-waterfall",
            "type": "waterfall",
            "label": "EBITDA (Management)",
            "size": "xl",
            "steps": [],
            "status": "empty",
            "emptyMessage": "EBITDA unavailable",
            "hint": f"tax_engine EBITDA walk failed: {exc}",
        }
    steps = walk.get("steps") if isinstance(walk.get("steps"), list) else []
    missing = walk.get("missing") if isinstance(walk.get("missing"), list) else []
    if not steps:
        return {
            "id": "ebitda-waterfall",
            "type": "waterfall",
            "label": "EBITDA (Management)",
            "size": "xl",
            "steps": [],
            "status": "empty",
            "emptyMessage": "No QB net income for EBITDA",
            "hint": "Import QuickBooks P&L. Missing: " + (", ".join(missing) if missing else "book income"),
        }
    from apex_cpa_pack import _cite_for_line, cite_key_for_line

    cited = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        row = dict(s)
        lab = str(row.get("label") or "")
        row["citation"] = _cite_for_line(lab)
        row["citeKey"] = cite_key_for_line(lab)
        cited.append(row)
    return {
        "id": "ebitda-waterfall",
        "type": "waterfall",
        "label": "EBITDA (Book)",
        "size": "xl",
        "steps": cited,
        "value": walk.get("ebitda"),
        "status": "ok",
        "showCitations": True,
        "hint": str(walk.get("disclaimer") or "Management calc from QB — not GAAP.")
        + (f" Missing: {', '.join(missing)}." if missing else "")
        + " Click citations for QB category rows.",
    }


def build_ebitda_scrubber(bundle: dict[str, Any]) -> dict[str, Any]:
    """Interactive Book🔒 vs Planning✏️ EBITDA scrubber — planning inputs never post to QB."""
    try:
        from tax_engine import compute_ebitda_walk

        walk = compute_ebitda_walk(bundle) or {}
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "ebitda-scrubber",
            "type": "ebitda-scrubber",
            "label": "EBITDA Scrubber (CPA Planning)",
            "size": "full",
            "status": "empty",
            "emptyMessage": "Scrubber unavailable",
            "hint": str(exc),
        }
    if not walk.get("available"):
        return {
            "id": "ebitda-scrubber",
            "type": "ebitda-scrubber",
            "label": "EBITDA Scrubber (CPA Planning)",
            "size": "full",
            "status": "empty",
            "emptyMessage": "Need QB net income",
            "hint": "Import QuickBooks P&L to unlock Book vs Planning scrubber.",
            "scrubber": walk.get("scrubber") or {},
        }
    filing_locked = False
    try:
        from apex_cpa_pack import get_filing_state

        filing_locked = bool(get_filing_state().get("locked"))
    except Exception:
        filing_locked = False
    return {
        "id": "ebitda-scrubber",
        "type": "ebitda-scrubber",
        "label": "EBITDA Scrubber (CPA Planning)",
        "size": "full",
        "status": "ok",
        "bookNetIncome": walk.get("bookNetIncome"),
        "bookEbitda": walk.get("ebitda"),
        "planningEbitda": walk.get("planningEbitda"),
        "bookSteps": walk.get("steps") or [],
        "planningSteps": walk.get("planningSteps") or [],
        "scrubber": walk.get("scrubber") or {},
        "periodLabel": walk.get("periodLabel") or "",
        "locked": filing_locked,
        "disclaimer": "PLANNING ONLY — NOT BOOKED TO QUICKBOOKS. CPA review required.",
        "hint": str(walk.get("disclaimer") or "")
        + (
            " FILING LOCKED — sliders read-only."
            if filing_locked
            else " Sliders adjust planning column only; Book stays locked to imports."
        ),
    }


def _tax_line_citation(label: str) -> str:
    try:
        from apex_cpa_pack import _cite_for_line

        return _cite_for_line(label)
    except Exception:
        return "Import-backed / planning note"


def _tax_line_cite_key(label: str) -> str:
    try:
        from apex_cpa_pack import cite_key_for_line

        return cite_key_for_line(label)
    except Exception:
        return "other"


def build_scenario_manager_widget() -> dict[str, Any]:
    try:
        from apex_cpa_pack import list_scenarios

        scenarios = list_scenarios()
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "cpa-scenarios",
            "type": "scenario-manager",
            "label": "Tax / EBITDA Scenarios",
            "size": "xl",
            "status": "empty",
            "scenarios": [],
            "emptyMessage": "Scenario store unavailable",
            "hint": str(exc),
        }
    return {
        "id": "cpa-scenarios",
        "type": "scenario-manager",
        "label": "Tax / EBITDA Scenarios",
        "size": "xl",
        "status": "ok" if scenarios else "empty",
        "scenarios": scenarios,
        "emptyMessage": "No saved scenarios yet",
        "hint": "Save from EBITDA scrubber — NR2 local store only, never posted to QuickBooks.",
    }


def build_filing_workflow_widget() -> dict[str, Any]:
    try:
        from apex_cpa_pack import get_filing_state

        filing = get_filing_state()
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "cpa-filing",
            "type": "filing-workflow",
            "label": "Filing Workflow",
            "size": "full",
            "status": "empty",
            "emptyMessage": "Filing store unavailable",
            "hint": str(exc),
        }
    returns = []
    try:
        returns = list_tax_returns()
    except Exception:
        returns = []
    return {
        "id": "cpa-filing",
        "type": "filing-workflow",
        "label": "Filing Workflow",
        "size": "full",
        "status": "ok",
        **filing,
        "taxReturns": returns,
        "hint": "DRAFT → CPA_REVIEW → CLIENT_APPROVED → FILED → LOCKED. FILED requires a library PDF (pick or upload).",
    }


def build_workpaper_widget(plan: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    del bundle
    return {
        "id": "cpa-workpaper",
        "type": "workpaper",
        "label": "CPA Workpaper Export",
        "size": "l",
        "status": "ok" if plan.get("hasBookData") else "empty",
        "emptyMessage": "Need QB book income",
        "exportUrl": "/api/apex/workpapers/generate",
        "hint": "Printable workpaper with book-to-tax + EBITDA citations. Planning only — CPA review required.",
    }


def build_variance_alert_widget(bundle: dict[str, Any]) -> dict[str, Any]:
    try:
        from apex_cpa_pack import detect_import_variances

        alerts = detect_import_variances(bundle)
    except Exception:
        alerts = []
    if not alerts:
        return {
            "id": "import-variance",
            "type": "status",
            "label": "Import Variance Watch",
            "size": "l",
            "message": "No >=10% period swings",
            "status": "ok",
            "hint": "Compares last two SoftDent dashboard periods when both report production/collections.",
        }
    msg = " · ".join(str(a.get("message") or "") for a in alerts[:3])
    return {
        "id": "import-variance",
        "type": "status",
        "label": "Import Variance Watch",
        "size": "l",
        "message": msg[:120],
        "status": "ok",
        "alert": True,
        "alertReason": msg,
        "alerts": alerts,
        "hint": "Import-backed period deltas only — not forecasts.",
    }


def _tax_returns_root():
    try:
        from document_sync import NR2_DATA_DIR

        root = NR2_DATA_DIR / "document_library" / "tax_returns"
    except Exception:
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "app_data" / "nr2" / "document_library" / "tax_returns"
    root.mkdir(parents=True, exist_ok=True)
    return root


def list_tax_returns() -> list[dict[str, Any]]:
    """List local prior tax return PDFs under document_library/tax_returns."""
    root = _tax_returns_root()
    out: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.upper() == "README.TXT":
            continue
        if path.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        parts = rel.split("/")
        year = parts[0] if parts and parts[0].isdigit() else ""
        jurisdiction = parts[1] if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
        out.append(
            {
                "name": path.name,
                "relPath": rel,
                "year": year,
                "jurisdiction": jurisdiction,
                "sizeBytes": path.stat().st_size,
            }
        )
    return out


def build_tax_library_widget() -> dict[str, Any]:
    files = list_tax_returns()
    return {
        "id": "tax-returns-library",
        "type": "tax-library",
        "label": "Tax Returns Library",
        "size": "xl",
        "files": files,
        "status": "ok" if files else "empty",
        "emptyMessage": "No tax returns on file",
        "hint": "Upload prior 1120S / K-120S PDFs for EBITDA context. Local only — not committed to git.",
    }


def resolve_tax_return_file(rel_path: str):
    """Safe resolve under tax_returns root (no path traversal)."""
    root = _tax_returns_root().resolve()
    rel = str(rel_path or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if not target.is_file():
        return None
    return target


def save_tax_return_upload(*, year: str, jurisdiction: str, filename: str, data: bytes) -> dict[str, Any]:
    year_s = re.sub(r"[^0-9]", "", str(year or ""))[:4]
    jur = re.sub(r"[^a-zA-Z\-]", "", str(jurisdiction or "federal").lower()) or "federal"
    if jur not in {"federal", "kansas", "ks", "other"}:
        jur = "federal"
    if jur == "ks":
        jur = "kansas"
    if not year_s or len(year_s) != 4:
        year_s = str(datetime.now(timezone.utc).year)
    safe_name = re.sub(r"[^a-zA-Z0-9._\-]", "_", Path(filename or "return.pdf").name)
    if not safe_name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff")):
        safe_name += ".pdf"
    dest_dir = _tax_returns_root() / year_s / jur
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_name
    dest.write_bytes(data)
    return {"ok": True, "relPath": f"{year_s}/{jur}/{safe_name}", "bytes": len(data)}


def _load_reports_and_bundle(*, _waited: bool = False) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Load import bundle + financial reports with single-flight coalescing.

    Moonshot import-cache KPIs MUST: at most one concurrent loader across pages.
    """
    global _BUNDLE_LOAD_EVENT
    import copy

    now = time.monotonic()
    with _REPORTS_BUNDLE_CACHE_LOCK:
        cached_at = float(_REPORTS_BUNDLE_CACHE.get("at") or 0.0)
        if (
            _REPORTS_BUNDLE_CACHE.get("reports") is not None
            and _REPORTS_BUNDLE_CACHE.get("bundle") is not None
            and (now - cached_at) < _REPORTS_BUNDLE_CACHE_TTL_SEC
        ):
            return (
                copy.deepcopy(_REPORTS_BUNDLE_CACHE["reports"]),
                copy.deepcopy(_REPORTS_BUNDLE_CACHE["bundle"]),
                list(_REPORTS_BUNDLE_CACHE.get("errors") or []),
            )

    wait_required = False
    i_am_loader = False
    event: threading.Event | None = None
    with _BUNDLE_LOAD_LOCK:
        now = time.monotonic()
        with _REPORTS_BUNDLE_CACHE_LOCK:
            cached_at = float(_REPORTS_BUNDLE_CACHE.get("at") or 0.0)
            if (
                _REPORTS_BUNDLE_CACHE.get("reports") is not None
                and _REPORTS_BUNDLE_CACHE.get("bundle") is not None
                and (now - cached_at) < _REPORTS_BUNDLE_CACHE_TTL_SEC
            ):
                return (
                    copy.deepcopy(_REPORTS_BUNDLE_CACHE["reports"]),
                    copy.deepcopy(_REPORTS_BUNDLE_CACHE["bundle"]),
                    list(_REPORTS_BUNDLE_CACHE.get("errors") or []),
                )
        if _BUNDLE_LOAD_EVENT is not None:
            event = _BUNDLE_LOAD_EVENT
            wait_required = True
        else:
            _BUNDLE_LOAD_EVENT = threading.Event()
            event = _BUNDLE_LOAD_EVENT
            i_am_loader = True

    if wait_required and event is not None:
        event.wait(timeout=30.0)
        now = time.monotonic()
        with _REPORTS_BUNDLE_CACHE_LOCK:
            cached_at = float(_REPORTS_BUNDLE_CACHE.get("at") or 0.0)
            if (
                _REPORTS_BUNDLE_CACHE.get("reports") is not None
                and _REPORTS_BUNDLE_CACHE.get("bundle") is not None
                and (now - cached_at) < _REPORTS_BUNDLE_CACHE_TTL_SEC
            ):
                return (
                    copy.deepcopy(_REPORTS_BUNDLE_CACHE["reports"]),
                    copy.deepcopy(_REPORTS_BUNDLE_CACHE["bundle"]),
                    list(_REPORTS_BUNDLE_CACHE.get("errors") or []),
                )
        if not _waited:
            return _load_reports_and_bundle(_waited=True)
        # Timed out / empty after wait: take ownership for one recovery load.
        with _BUNDLE_LOAD_LOCK:
            if _BUNDLE_LOAD_EVENT is None:
                _BUNDLE_LOAD_EVENT = threading.Event()
                event = _BUNDLE_LOAD_EVENT
                i_am_loader = True
            else:
                # Another recovery loader won; wait once more then read cache.
                event = _BUNDLE_LOAD_EVENT
                event.wait(timeout=30.0)
                with _REPORTS_BUNDLE_CACHE_LOCK:
                    return (
                        copy.deepcopy(_REPORTS_BUNDLE_CACHE.get("reports") or {}),
                        copy.deepcopy(_REPORTS_BUNDLE_CACHE.get("bundle") or {}),
                        list(_REPORTS_BUNDLE_CACHE.get("errors") or []),
                    )

    reports: dict[str, Any] = {}
    bundle: dict[str, Any] = {}
    errors: list[str] = []
    try:
        try:
            from import_loader import load_import_bundle

            bundle = load_import_bundle(sync=False, deep=False)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"import_loader: {exc}")
            bundle = {}

        try:
            from financial_reports import build_financial_reports

            # Reuse the same bundle — avoid a second cold import scan on every page.
            reports = build_financial_reports(sync_exports=False, bundle=bundle or None)
        except Exception as exc:  # noqa: BLE001 — surface honest empty state
            errors.append(f"financial_reports: {exc}")
            reports = {}

        with _REPORTS_BUNDLE_CACHE_LOCK:
            _REPORTS_BUNDLE_CACHE["at"] = time.monotonic()
            _REPORTS_BUNDLE_CACHE["reports"] = copy.deepcopy(reports)
            _REPORTS_BUNDLE_CACHE["bundle"] = copy.deepcopy(bundle)
            _REPORTS_BUNDLE_CACHE["errors"] = list(errors)
        return copy.deepcopy(reports), copy.deepcopy(bundle), list(errors)
    finally:
        if i_am_loader:
            with _BUNDLE_LOAD_LOCK:
                if _BUNDLE_LOAD_EVENT is not None:
                    _BUNDLE_LOAD_EVENT.set()
                    _BUNDLE_LOAD_EVENT = None


def _load_local_json(key: str) -> dict[str, Any] | None:
    try:
        from document_sync import NR2_DATA_DIR
        from local_store import LocalStore

        raw = LocalStore(NR2_DATA_DIR).get(key)
        if not raw:
            return None
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _claim_status(row: dict[str, Any]) -> str:
    return str(
        row.get("ClaimStatus")
        or row.get("Status")
        or row.get("status")
        or row.get("claimStatus")
        or "Unknown"
    ).strip() or "Unknown"


def _claims_summary_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    rows = _section_rows(bundle, "softdent", "claims")
    if not rows:
        rows = _section_rows(bundle, "softdent", "claimStatus")
    total = len(rows)
    by_status: dict[str, int] = {}
    denied = 0
    open_count = 0
    aging_30 = 0
    for row in rows:
        status = _claim_status(row)
        by_status[status] = by_status.get(status, 0) + 1
        if re.search(r"denied|reject", status, re.I):
            denied += 1
        if re.search(r"open|pending|review|hold|submitted|in.?process", status, re.I):
            open_count += 1
        days = _parse_int(row.get("Age") or row.get("Days") or row.get("AgingDays") or row.get("ageDays"))
        if days is not None and days >= 30:
            aging_30 += 1
    aging_payload: dict[str, Any] = {}
    try:
        from apex_claims_narratives_pack import build_aging_buckets

        aging_payload = build_aging_buckets(rows)
        counts = aging_payload.get("counts") if isinstance(aging_payload.get("counts"), dict) else {}
        # Prefer bucketed 30+ count when Age/DOS available
        bucketed_30_plus = int(counts.get("30") or 0) + int(counts.get("60") or 0) + int(counts.get("90") or 0)
        if bucketed_30_plus or aging_payload.get("available"):
            aging_30 = bucketed_30_plus if rows else aging_30
    except Exception:
        aging_payload = {}
    return {
        "totalClaims": total if rows else None,
        "openCount": open_count if rows else None,
        "deniedCount": denied if rows else None,
        "agingPast30": aging_30 if rows else None,
        "agingBuckets": aging_payload.get("buckets") if aging_payload else None,
        "agingCounts": aging_payload.get("counts") if aging_payload else None,
        "agingMeta": {
            "missingAgeField": bool(aging_payload.get("missingAgeField")),
            "missingAgeCount": aging_payload.get("missingAgeCount"),
            "lastImport": aging_payload.get("lastImport"),
        }
        if aging_payload
        else None,
        "byStatus": by_status,
        "available": bool(rows),
        "followUpHint": (
            "Review open/denied claims past 30 days for resubmit or appeal."
            if (aging_30 or denied)
            else "No denied claims flagged from import."
            if rows
            else "Import SoftDent claims to populate this page."
        ),
    }


def _qb_pick(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        n = _parse_money(row.get(key))
        if n is not None:
            return n
    return None


def _financial_widgets_from_reports(
    reports: dict[str, Any],
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Financial Executive Console (hal-10430) — Moonshot Option A primary design.

    Packed top-down: command → vitals → chart row (trend/provider/A/R/revenue) →
    KPI row → notes → EBITDA. Empty large instruments collapse to strips.
    """
    widgets: list[dict[str, Any]] = []
    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}

    def _ar_aging_widget() -> dict[str, Any]:
        buckets = (
            reports.get("arAgingBuckets")
            if isinstance(reports.get("arAgingBuckets"), list)
            else []
        )
        series = []
        for b in buckets:
            if not isinstance(b, dict):
                continue
            amt = b.get("amount")
            if isinstance(amt, (int, float)):
                series.append({"label": str(b.get("bucket") or ""), "value": float(amt)})
        if series and any(s["value"] for s in series):
            return {
                "id": "ar-aging-chart",
                "type": "chart",
                "chartType": "bar",
                "label": "A/R Aging",
                "size": "m",
                "series": series,
                "hint": "Buckets from SoftDent A/R import via financial_reports.",
            }
        empty_ar = _empty_chart(
            "ar-aging-chart",
            "A/R Aging",
            hint="Import SoftDent A/R aging to populate this chart.",
        )
        empty_ar["size"] = "strip"
        empty_ar["collapseWhenEmpty"] = True
        empty_ar["compact"] = True
        return empty_ar

    try:
        from apex_financial_console_pack import (
            build_dual_axis_trend,
            build_ebitda_station,
            build_financial_command_strip,
            build_financial_vital_signs,
            build_revenue_composition,
            collapse_empty_large,
        )

        # Level 1 — Command strip (import + period + morning brief)
        widgets.append(build_financial_command_strip(bundle, reports))
        # Level 2 — Vital signs (prod / collections / A/R / efficiency)
        vitals = build_financial_vital_signs(reports, bundle)
        ninety_pct = ar.get("ninetyPlusPct")
        if isinstance(ninety_pct, (int, float)) and float(ninety_pct) > 20.0:
            vitals["alert"] = True
            vitals["alertReason"] = f"90+ share {float(ninety_pct):.1f}% exceeds 20%"
        widgets.append(vitals)
        # Moonshot MUST: Collections Radial-Gauge alongside existing vitals
        try:
            from apex_better_backend_widgets_pack import build_collections_radial_gauge

            coll_gauge = build_collections_radial_gauge(bundle, reports)
            if coll_gauge:
                widgets.append(coll_gauge)
        except Exception:
            pass
        # Level 3 — Chart row: dual-trend + provider + A/R (all size m for tight pack)
        widgets.append(build_dual_axis_trend(bundle))
        provider = build_provider_horizontal_bars(bundle)
        if provider.get("status") == "empty":
            provider = collapse_empty_large(provider)
        else:
            provider["size"] = "m"
        widgets.append(provider)
        widgets.append(_ar_aging_widget())
        # Level 4 — Revenue composition (m when populated so it packs with charts)
        revenue = build_revenue_composition(bundle)
        if revenue.get("status") == "ok" and revenue.get("size") == "l":
            revenue["size"] = "m"
        widgets.append(revenue)
        # DEF-001 — surface Collections gap strip on Financial when revenue is empty
        if revenue.get("status") == "empty":
            try:
                from apex_softdent_hardening_pack import collections_gap_widget

                gap_w = collections_gap_widget(bundle)
                if gap_w.get("status") == "empty":
                    widgets.insert(0, gap_w)
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001
        # Fallback: legacy mosaic if console pack fails
        widgets.append(
            _status_widget(
                "financial-console-fallback",
                "Financial console",
                message="Using legacy layout",
                hint=f"Console pack unavailable: {exc}",
                status="empty",
            )
        )
        widgets.insert(0, build_import_freshness(bundle))
        widgets[0]["size"] = "strip"
        widgets[0]["compact"] = True
        widgets.insert(1, build_period_scrubber(bundle, page="financial"))
        widgets[1]["size"] = "strip"
        widgets.extend(_visual_boost_financial(reports, bundle))
        widgets.append(_ar_aging_widget())

    # Level 5 — Secondary ops packed into ONE micro-strip (≤4 pills; KPI density)
    ct = reports.get("claimTracking") if isinstance(reports.get("claimTracking"), dict) else {}
    total_claims = ct.get("totalClaims")
    denied = ct.get("deniedCount")
    tp = reports.get("treatmentPlans") if isinstance(reports.get("treatmentPlans"), dict) else {}
    ca = reports.get("caseAcceptance") if isinstance(reports.get("caseAcceptance"), dict) else {}
    try:
        from apex_compact_pages_pack import build_kpi_micro_strip

        widgets.append(
            build_kpi_micro_strip(
                "financial-ops-strip",
                "Ops Snapshot",
                [
                    {
                        "id": "claims-total",
                        "label": "Claims",
                        "value": total_claims if isinstance(total_claims, int) else None,
                        "format": "count",
                        "empty": not isinstance(total_claims, int),
                        "sub": f"Denied {ct.get('deniedCount', 0)}"
                        if isinstance(total_claims, int)
                        else "",
                    },
                    {
                        "id": "claims-denied",
                        "label": "Denied",
                        "value": denied if isinstance(denied, int) else None,
                        "format": "count",
                        "empty": not isinstance(denied, int),
                        "sub": f"Aging 30+ {ct.get('deniedAgingPast30Days', 0)}"
                        if isinstance(denied, int)
                        else "",
                    },
                    {
                        "id": "treatment-plans",
                        "label": "Tx Plans",
                        "value": tp.get("rowCount") if tp.get("available") else None,
                        "format": "count",
                        "empty": not tp.get("available"),
                    },
                    {
                        "id": "case-acceptance",
                        "label": "Case Acc.",
                        "value": ca.get("rowCount") if ca.get("available") else None,
                        "format": "count",
                        "empty": not ca.get("available"),
                    },
                ],
                hint="Packed ops KPIs · import-backed only · empty stays empty.",
                nav_hash="financial/workpapers",
            )
        )
    except Exception:
        # Fallback: at most one claims KPI (density budget)
        if isinstance(total_claims, int):
            claims_kpi = _count_kpi(
                "claims-total",
                "Claims (import)",
                total_claims,
                hint=str(ct.get("followUpHint") or "From SoftDent claims import."),
                delta_label=f"Denied {ct.get('deniedCount', 0)}",
            )
            claims_kpi["size"] = "s"
            widgets.append(claims_kpi)

    note = reports.get("collectionsNote")
    if note:
        widgets.append(
            {
                **_status_widget(
                    "collections-note",
                    "Collections note",
                    message="Guidance",
                    hint=str(note),
                ),
                "size": "strip",
                "compact": True,
            }
        )

    # Level 6 — EBITDA Command Station + variance bar (FIN-004)
    try:
        from apex_financial_console_pack import build_ebitda_station, collapse_empty_large

        station = build_ebitda_station(bundle)
        if station.get("status") == "empty":
            station = collapse_empty_large(station)
        widgets.append(station)
    except Exception:
        widgets.append(build_ebitda_waterfall(bundle))
        widgets.append(build_ebitda_scrubber(bundle))
    try:
        from apex_bar_trend_page_org_pack import build_ebitda_variance_bar
        from apex_financial_console_pack import collapse_empty_large

        variance = build_ebitda_variance_bar(bundle)
        if variance.get("status") == "empty":
            variance = collapse_empty_large(variance)
        widgets.append(variance)
    except Exception:
        pass

    try:
        from apex_missing_widgets_pack import append_financial_missing

        append_financial_missing(widgets, bundle)
    except Exception:
        pass
    try:
        from apex_unified_db_pack import unified_db_widget

        widgets.append(unified_db_widget(bundle))
    except Exception:
        pass
    try:
        from apex_qb_payroll_pack import payroll_ap_widgets

        widgets.extend(payroll_ap_widgets(bundle))
    except Exception:
        pass
    try:
        from apex_softdent_production_pack import production_widgets
        from apex_softdent_aging_schedule_pack import aging_schedule_widgets
        from apex_qb_net_profit_pack import net_profit_widget
        from apex_unified_db_pack import production_vs_payroll_widget

        widgets.extend(production_widgets(bundle))
        widgets.extend(aging_schedule_widgets(bundle))
        widgets.append(net_profit_widget(bundle))
        widgets.append(production_vs_payroll_widget(bundle))
    except Exception:
        pass
    try:
        from apex_softdent_extended_pack import extended_metrics_widgets

        widgets.extend(extended_metrics_widgets(bundle))
    except Exception:
        pass
    try:
        from apex_deep_audit_pack import deep_audit_widget

        widgets.append(deep_audit_widget(bundle))
    except Exception:
        pass
    # 32B program fixes — import-cache / bridge errors / SoftDent×QB recon / Gold ticket OPS
    try:
        from apex_32b_program_fixes_pack import (
            bridge_errors_widget,
            gold_ticket_hint_widget,
            import_cache_kpi_widget,
            import_cache_telemetry,
            reconciliation_surface_widget,
        )

        tele = import_cache_telemetry(
            widgets_cache=_WIDGETS_CACHE,
            fill_progress=_FILL_PROGRESS,
            fill_failures=_WIDGETS_FILL_FAILURES,
            ttl_sec=_WIDGETS_CACHE_TTL_SEC,
        )
        widgets.insert(0, import_cache_kpi_widget(tele))
        widgets.insert(1, bridge_errors_widget(
            bundle=bundle,
            fill_failures=_WIDGETS_FILL_FAILURES,
            last_sync_error=_LAST_SYNC_ERROR or None,
        ))
        widgets.insert(2, reconciliation_surface_widget(bundle))
        widgets.insert(3, gold_ticket_hint_widget())
    except Exception:
        try:
            from apex_reconciliation_pack import reconciliation_widget

            widgets.append(reconciliation_widget(bundle))
        except Exception:
            pass
    try:
        from apex_import_quarantine_pack import quarantine_widget

        widgets.append(quarantine_widget(bundle))
    except Exception:
        pass
    try:
        from apex_import_dq_pack import dq_widget
        from apex_import_scheduler_pack import import_cron_widget

        widgets.append(dq_widget(bundle))
        widgets.append(import_cron_widget(bundle))
    except Exception:
        pass
    try:
        from apex_dashboard_layout_pack import layout_widget

        widgets.append(layout_widget(bundle))
    except Exception:
        pass
    try:
        from apex_ai_telemetry_pack import telemetry_widget

        widgets.append(telemetry_widget(bundle))
    except Exception:
        pass
    try:
        from apex_sync_status_pack import freshness_widget

        widgets.append(freshness_widget(bundle))
    except Exception:
        pass

    _apply_threshold_alerts(widgets, reports)
    # Moonshot NICE: A/R aging Pareto on financial
    try:
        from apex_better_backend_widgets_pack import build_ar_aging_pareto

        widgets.append(build_ar_aging_pareto(bundle, reports))
    except Exception:
        pass
    return widgets


def _taxes_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Taxes cockpit (hal-10610): micro-strip + bridge; planning table/calendar on #taxes/planning."""
    del reports  # reserved for future tax fields on financial_reports
    widgets: list[dict[str, Any]] = []
    plan: dict[str, Any] = {}
    try:
        from tax_engine import build_tax_plan_from_bundle

        plan = build_tax_plan_from_bundle(bundle) or {}
    except Exception as exc:  # noqa: BLE001
        widgets.append(
            _status_widget(
                "tax-engine-error",
                "Tax engine",
                message="Unavailable",
                hint=f"tax_engine could not load: {exc}",
                status="empty",
            )
        )
        plan = {}

    has_book = bool(plan.get("hasBookData"))
    period = str(plan.get("periodLabel") or "")
    book_net = _parse_money(plan.get("bookNetIncome")) if has_book else None
    owner_tax = _parse_money(plan.get("totalOwnerTaxEstimate")) if has_book else None
    k1 = _parse_money(plan.get("k1Ordinary")) if has_book else None
    q_est = None
    if has_book:
        q_rows = plan.get("quarterlyEstimates") if isinstance(plan.get("quarterlyEstimates"), list) else []
        if q_rows and isinstance(q_rows[0], dict):
            fed = _parse_money(q_rows[0].get("federal"))
            ks = _parse_money(q_rows[0].get("kansas"))
            if fed is not None or ks is not None:
                q_est = float(fed or 0) + float(ks or 0)

    widgets.insert(0, build_period_scrubber(bundle, page="taxes"))

    # Single Tax Year Status chip (nav to planning — KPIs live in micro-strip)
    if has_book and book_net is not None:
        status_msg = "Book connected"
        if period:
            status_msg = f"{period} · {status_msg}"
        widgets.append(
            {
                **_status_widget(
                    "tax-year-status",
                    "Tax Year Status",
                    message=status_msg,
                    hint="QB P&L book income linked · planning estimates on #taxes/planning (CPA review).",
                    status="ok",
                ),
                "size": "strip",
                "compact": True,
                "navHash": "taxes/planning",
                "kpiBudgetExempt": True,
            }
        )
    elif has_book:
        widgets.append(
            {
                **_status_widget(
                    "tax-year-status",
                    "Tax Year Status",
                    message="Book linked · net income field missing",
                    hint="P&L present but book net not parsed — open #taxes/planning.",
                    status="empty",
                ),
                "size": "strip",
                "compact": True,
                "navHash": "taxes/planning",
            }
        )
    else:
        widgets.append(
            {
                **_status_widget(
                    "tax-year-status",
                    "Tax Year Status",
                    message="Book not connected",
                    hint="Import QuickBooks P&L — tax KPIs stay empty (not $0). Planning on #taxes/planning.",
                    status="empty",
                ),
                "size": "strip",
                "compact": True,
                "navHash": "taxes/planning",
            }
        )

    # hal-10610: ≤4 book-backed pills above fold (omit empty — never $0 pad)
    try:
        from apex_compact_pages_pack import build_kpi_micro_strip

        widgets.append(
            build_kpi_micro_strip(
                "tax-core-strip",
                "Tax core",
                [
                    {
                        "id": "tax-book-net-pill",
                        "label": "Net income",
                        "value": book_net,
                        "format": "money",
                        "empty": book_net is None,
                        "sub": period or "",
                    },
                    {
                        "id": "tax-est-owner-pill",
                        "label": "Est. tax",
                        "value": owner_tax,
                        "format": "money",
                        "tone": "warning",
                        "empty": owner_tax is None,
                        "sub": "CPA review",
                    },
                    {
                        "id": "tax-k1-pill",
                        "label": "K-1",
                        "value": k1,
                        "format": "money",
                        "empty": k1 is None,
                    },
                    {
                        "id": "tax-quarterly-pill",
                        "label": "Quarterly",
                        "value": q_est,
                        "format": "money",
                        "tone": "warning",
                        "empty": q_est is None,
                        "sub": "Q1 est." if q_est is not None else "",
                    },
                ],
                hint="Tax core strip · empty stays empty · full planning on #taxes/planning.",
                nav_hash="taxes/planning",
            )
        )
    except Exception:
        pass

    widgets.append(
        {
            **_status_widget(
                "tax-open-planning",
                "Tax Planning",
                message="Open planning · table · calendar",
                hint="Owner tax / K-1 / quarterly / data-table / calendar · #taxes/planning · CPA review.",
            ),
            "size": "strip",
            "compact": True,
            "navHash": "taxes/planning",
            "halAction": "open_taxes_planning",
            "halActionLabel": "Open Planning",
        }
    )

    if plan.get("disclaimer"):
        widgets.append(
            {
                **_status_widget(
                    "tax-disclaimer",
                    "TAX PLANNING — CPA REVIEW",
                    message="PLANNING ESTIMATES ONLY — NOT FOR FILING",
                    hint=str(plan.get("disclaimer")),
                ),
                "size": "strip",
                "compact": True,
            }
        )

    # Book-to-tax bridge chart only on main (not individual planning KPIs)
    if has_book:
        bridge = plan.get("bridgeLines") if isinstance(plan.get("bridgeLines"), list) else []
        bridge_steps = []
        for line in bridge:
            if not isinstance(line, dict):
                continue
            amt = _parse_money(line.get("amount"))
            if amt is None:
                continue
            kind = str(line.get("kind") or "positive")
            if kind in {"less", "negative"}:
                kind = "negative"
            elif kind in {"result", "total", "book"}:
                kind = "total" if kind != "book" else "start"
            else:
                kind = "positive"
            bridge_steps.append(
                {
                    "label": str(line.get("line") or "")[:40],
                    "value": float(amt),
                    "kind": kind,
                    "citation": _tax_line_citation(str(line.get("line") or "")),
                    "citeKey": _tax_line_cite_key(str(line.get("line") or "")),
                }
            )
        if bridge_steps:
            widgets.append(
                {
                    "id": "tax-bridge-waterfall",
                    "type": "waterfall",
                    "label": "Book-to-Tax Bridge (planning)",
                    "size": "m",
                    "maxHeight": 320,
                    "compact": True,
                    "steps": bridge_steps,
                    "status": "ok",
                    "hint": "Planning bridge from tax_engine — citations are import sources, not invented dollars.",
                    "showCitations": True,
                }
            )

    try:
        from apex_cpa_pack import build_c0_import_guidance

        widgets.append(build_c0_import_guidance(bundle))
    except Exception:
        pass

    try:
        from apex_bar_trend_page_org_pack import build_ebitda_variance_bar
        from apex_financial_console_pack import collapse_empty_large

        variance = build_ebitda_variance_bar(bundle)
        if variance.get("status") == "empty":
            variance = collapse_empty_large(variance)
        widgets.append(variance)
    except Exception:
        pass

    # Planning data-table + calendar moved to #taxes/planning (hal-10610 compact remap)
    return widgets


def _softdent_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets: list[dict[str, Any]] = []
    rows = _dashboard_rows(bundle)
    latest = _latest_period_row(rows)
    period = str((latest or {}).get("period") or (latest or {}).get("year_month") or "")

    prod = _parse_money((latest or {}).get("production")) if latest else None

    coll = None
    coll_gap: dict[str, Any] = {}
    if latest:
        if latest.get("collectionsReported") is False or latest.get("collectionsPending") is True:
            coll = None
        elif "collections" in latest:
            coll = _parse_money(latest.get("collections"))
    try:
        from apex_softdent_hardening_pack import assess_collections_gap

        coll_gap = assess_collections_gap(bundle)
    except Exception:
        coll_gap = {}

    np_rows = _section_rows(bundle, "softdent", "newPatients")
    np_latest = _latest_period_row(np_rows)
    np_count = None
    if np_latest:
        np_count = _parse_int(np_latest.get("Count") or np_latest.get("count") or np_latest.get("NewPatients"))

    op = _section(bundle, "softdent", "operatory")
    chairs = op.get("operatoryChairs") if isinstance(op.get("operatoryChairs"), list) else []
    slot_count = 0
    for chair in chairs:
        if isinstance(chair, dict) and isinstance(chair.get("slots"), list):
            slot_count += len(chair["slots"])

    def _as_ops_strip(w: dict[str, Any] | None) -> dict[str, Any] | None:
        """Demote Gold/ERA/audit status widgets to strip height (hal-10610)."""
        if not isinstance(w, dict):
            return w
        out = dict(w)
        size = str(out.get("size") or "")
        if size in {"full", "xl", "l", "large", ""} or out.get("type") in {"status", "alert"}:
            out["size"] = "strip"
            out["compact"] = True
            out["maxHeight"] = int(out.get("maxHeight") or 120)
        return out

    try:
        from apex_compact_pages_pack import build_kpi_micro_strip

        coll_sub = period or ""
        if coll is None and coll_gap:
            coll_sub = str(coll_gap.get("hint") or "Pending — sync Daysheet")[:40]
        widgets.append(
            build_kpi_micro_strip(
                "sd-vitals-strip",
                "SoftDent Vitals",
                [
                    {
                        "id": "sd-production",
                        "label": "Production",
                        "value": prod,
                        "format": "money",
                        "tone": "success",
                        "empty": prod is None,
                        "sub": period or "",
                    },
                    {
                        "id": "sd-collections",
                        "label": "Collections",
                        "value": coll,
                        "format": "money",
                        "tone": "warning" if coll is None else "success",
                        "empty": coll is None,
                        "pending": coll is None,
                        "sub": coll_sub,
                    },
                    {
                        "id": "sd-new-patients",
                        "label": "New Patients",
                        "value": np_count,
                        "format": "count",
                        "empty": np_count is None,
                    },
                    {
                        "id": "sd-operatory-chairs",
                        "label": "Chairs",
                        "value": len(chairs) if chairs else None,
                        "format": "count",
                        "empty": not chairs,
                        "sub": f"{slot_count} slots" if chairs else "",
                    },
                ],
                hint="SoftDent dashboard vitals · empty stays empty · detail on charts below.",
            )
        )
    except Exception:
        widgets.append(
            _money_kpi(
                "sd-production",
                "Production",
                prod,
                hint="SoftDent dashboard import." if prod is not None else "SoftDent dashboard production not loaded.",
                delta_label=period or None,
            )
        )

    # Collections efficiency gauge (reuse Financial primitive — no new chart type)
    try:
        from apex_better_backend_widgets_pack import build_collections_radial_gauge

        coll_gauge = build_collections_radial_gauge(bundle, {})
        if coll_gauge:
            coll_gauge = dict(coll_gauge)
            coll_gauge["size"] = "m"
            coll_gauge["maxHeight"] = 240
            coll_gauge["compact"] = True
            widgets.append(coll_gauge)
    except Exception:
        pass

    # Operatory detail is in vitals Chairs pill — skip redundant status when chairs loaded
    if not chairs:
        widgets.append(
            {
                **_status_widget(
                    "sd-operatory-status",
                    "Operatory / daysheet",
                    message="No schedule",
                    hint="Need operatoryChairs[] in SoftDent operatory import (not a row table).",
                    status="empty",
                ),
                "size": "strip",
                "compact": True,
            }
        )

    prod_vals = _spark_from_rows(rows, "production")
    if len(prod_vals) >= 2:
        widgets.append(
            {
                "id": "sd-prod-trend",
                "type": "chart",
                "chartType": "line",
                "label": "Production Trend",
                "values": prod_vals,
                "hint": "SoftDent dashboard periods.",
            }
        )
    else:
        widgets.append(
            _empty_chart(
                "sd-prod-trend",
                "Production Trend",
                hint="Need at least two SoftDent dashboard periods for a trend chart.",
                chart_type="line",
            )
        )

    try:
        from apex_bar_trend_page_org_pack import (
            build_import_health_timeline,
            build_operatory_util_chart,
            build_stale_import_alert_chip,
        )
        from apex_financial_console_pack import collapse_empty_large

        widgets.insert(0, build_stale_import_alert_chip(bundle))
        timeline = build_import_health_timeline(bundle)
        if timeline.get("status") == "empty":
            timeline = collapse_empty_large(timeline)
        widgets.append(timeline)
        util = build_operatory_util_chart(bundle)
        if util.get("status") == "empty":
            util = collapse_empty_large(util)
        widgets.append(util)
    except Exception:
        pass

    widgets.append(build_provider_horizontal_bars(bundle))
    try:
        from apex_softdent_hardening_pack import collections_gap_widget

        widgets.insert(0, collections_gap_widget(bundle))
    except Exception:
        pass
    try:
        from softdent_outstanding_claims_bridge import outstanding_claims_bridge_widget

        w = _as_ops_strip(outstanding_claims_bridge_widget())
        if w:
            widgets.insert(1, w)
    except Exception:
        pass
    try:
        from softdent_insco_ada_probabilistic import insco_ada_estimate_widget

        w = _as_ops_strip(insco_ada_estimate_widget())
        if w:
            widgets.insert(2, w)
    except Exception:
        pass
    try:
        from softdent_insco_ada_catalog_matrix import insco_ada_catalog_widget

        w = _as_ops_strip(insco_ada_catalog_widget())
        if w:
            widgets.insert(3, w)
    except Exception:
        pass
    try:
        from softdent_treatment_planning import treatment_plan_estimate_widget

        w = _as_ops_strip(treatment_plan_estimate_widget())
        if w:
            widgets.insert(4, w)
    except Exception:
        pass
    try:
        from softdent_gold_payment_pipeline import gold_payment_pipeline_widget

        w = _as_ops_strip(gold_payment_pipeline_widget())
        if w:
            widgets.insert(5, w)
    except Exception:
        pass
    try:
        from softdent_gold_csv_drop_ops import gold_csv_drop_ops_widget

        w = _as_ops_strip(gold_csv_drop_ops_widget())
        if w:
            widgets.insert(6, w)
    except Exception:
        pass
    try:
        from softdent_gold_drop_facilitation_hal10606 import gold_drop_facilitation_widget

        w = _as_ops_strip(gold_drop_facilitation_widget())
        if w:
            widgets.insert(7, w)
    except Exception:
        pass
    try:
        from softdent_pwimages_eligibility_hal10607 import pwimages_eligibility_widget

        w = _as_ops_strip(pwimages_eligibility_widget())
        if w:
            widgets.insert(8, w)
    except Exception:
        pass
    try:
        from softdent_gold_era_settlement_hal10608 import gold_era_settlement_widget

        w = _as_ops_strip(gold_era_settlement_widget())
        if w:
            widgets.insert(9, w)
    except Exception:
        pass
    try:
        from softdent_print_preview_audit import print_preview_audit_widget

        w = _as_ops_strip(print_preview_audit_widget())
        if w:
            widgets.insert(10, w)
    except Exception:
        pass
    try:
        from ui_honesty_policy import ui_honesty_widget

        w = _as_ops_strip(ui_honesty_widget())
        if w:
            widgets.insert(11, w)
    except Exception:
        pass
    try:
        from softdent_visual_ledger_recon import visual_ledger_recon_widget

        w = _as_ops_strip(visual_ledger_recon_widget())
        if w:
            widgets.insert(12, w)
    except Exception:
        pass
    try:
        from apex_softdent_production_pack import production_widgets
        from apex_softdent_aging_schedule_pack import aging_schedule_widgets
        from apex_financial_console_pack import collapse_empty_large

        for w in production_widgets(bundle):
            widgets.append(collapse_empty_large(w) if isinstance(w, dict) else w)
        for w in aging_schedule_widgets(bundle):
            widgets.append(collapse_empty_large(w) if isinstance(w, dict) else w)
    except Exception:
        pass
    try:
        from apex_softdent_extended_pack import extended_metrics_widgets
        from apex_financial_console_pack import collapse_empty_large

        for w in extended_metrics_widgets(bundle):
            widgets.append(collapse_empty_large(w) if isinstance(w, dict) else w)
    except Exception:
        pass
    try:
        from apex_era835_pack import era835_widget

        widgets.append(era835_widget(bundle))
    except Exception:
        pass

    # Moonshot SHOULD: SoftDent patient dossier (empty placeholder)
    try:
        from apex_better_backend_widgets_pack import build_softdent_patient_dossier

        dossier = build_softdent_patient_dossier(bundle)
        if isinstance(dossier, dict):
            dossier = dict(dossier)
            dossier["maxHeight"] = int(dossier.get("maxHeight") or 240)
            dossier["compact"] = True
        widgets.append(dossier)
    except Exception:
        pass
    # Moonshot NEXT: TXN ledger surface (read-only JSONL / sd_account_transactions)
    try:
        from apex_better_backend_widgets_pack import (
            build_account_tx_ledger_coverage_chip,
            build_transaction_ledger_table,
        )

        widgets.append(build_account_tx_ledger_coverage_chip(bundle, page="softdent"))
        ledger = build_transaction_ledger_table(bundle, page="softdent", limit=5)
        if isinstance(ledger, dict):
            ledger = dict(ledger)
            ledger["rowCap"] = 5
            ledger["maxHeight"] = 320
            ledger["compact"] = True
        widgets.append(ledger)
    except Exception:
        pass

    return widgets


def _quickbooks_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets: list[dict[str, Any]] = []
    pl_rows = _section_rows(bundle, "quickbooks", "profitAndLoss")
    rev_rows = _section_rows(bundle, "quickbooks", "revenue")
    exp_rows = _section_rows(bundle, "quickbooks", "expenses")
    cat_rows = _section_rows(bundle, "quickbooks", "expenseCategories")

    latest_pl = _latest_period_row(pl_rows)
    latest_rev = _latest_period_row(rev_rows)
    latest_exp = _latest_period_row(exp_rows)

    net = _qb_pick(latest_pl, ("NetIncome", "net_income", "Net Income")) if latest_pl else None
    revenue = None
    if latest_pl:
        revenue = _qb_pick(latest_pl, ("TotalIncome", "Income", "Revenue", "Total Revenue"))
    if revenue is None and latest_rev:
        revenue = _qb_pick(latest_rev, ("TotalIncome", "Income", "Revenue", "Amount"))
    expenses = None
    if latest_pl:
        expenses = _qb_pick(latest_pl, ("TotalExpense", "Expenses", "Expense", "Total Expenses"))
    if expenses is None and latest_exp:
        expenses = _qb_pick(latest_exp, ("TotalExpense", "Expenses", "Expense", "Amount"))

    period = ""
    for row in (latest_pl, latest_rev, latest_exp):
        if row:
            period = str(row.get("Period") or row.get("period") or "")
            if period:
                break

    if not pl_rows and not rev_rows and not exp_rows:
        try:
            from apex_compact_pages_pack import build_kpi_micro_strip

            widgets.append(
                build_kpi_micro_strip(
                    "qb-vitals-strip",
                    "QuickBooks Vitals",
                    [
                        {"id": "qb-net-income", "label": "Net Income", "value": None, "format": "money", "empty": True},
                        {"id": "qb-revenue", "label": "Revenue", "value": None, "format": "money", "empty": True},
                        {"id": "qb-expenses", "label": "Expenses", "value": None, "format": "money", "empty": True},
                        {
                            "id": "qb-categories",
                            "label": "Categories",
                            "value": None,
                            "format": "count",
                            "empty": True,
                        },
                    ],
                    hint="QuickBooks not imported — empty stays empty (not $0).",
                )
            )
        except Exception:
            widgets.append(
                _empty_kpi("qb-net-income", "Net Income", hint="QuickBooks not imported — P&L / revenue missing.")
            )
        widgets.append(
            {
                **_status_widget(
                    "qb-pl-summary",
                    "P&L Summary",
                    message="Not imported",
                    hint="Drop QuickBooks exports into the document inbox and sync.",
                    status="empty",
                ),
                "size": "strip",
                "compact": True,
            }
        )
        widgets.append(
            _empty_chart(
                "qb-expense-breakdown",
                "Expense Breakdown",
                hint="Expense category rows appear after QuickBooks category import.",
            )
        )
        try:
            from apex_financial_console_pack import collapse_empty_large

            widgets.append(collapse_empty_large(build_expense_horizontal_bars(bundle)))
        except Exception:
            widgets.append(build_expense_horizontal_bars(bundle))
        widgets.append(build_categorize_assist(bundle))
        try:
            from apex_missing_widgets_pack import append_quickbooks_missing

            append_quickbooks_missing(widgets, bundle)
        except Exception:
            pass
        try:
            from apex_qb_payroll_pack import payroll_ap_widgets

            widgets.extend(payroll_ap_widgets(bundle))
        except Exception:
            pass
        try:
            from apex_qb_net_profit_pack import net_profit_widget

            widgets.append(net_profit_widget(bundle))
        except Exception:
            pass
        return widgets

    try:
        from apex_compact_pages_pack import build_kpi_micro_strip

        widgets.append(
            build_kpi_micro_strip(
                "qb-vitals-strip",
                "QuickBooks Vitals",
                [
                    {
                        "id": "qb-net-income",
                        "label": "Net Income",
                        "value": net,
                        "format": "money",
                        "empty": net is None,
                        "sub": period or "",
                    },
                    {
                        "id": "qb-revenue",
                        "label": "Revenue",
                        "value": revenue,
                        "format": "money",
                        "empty": revenue is None,
                        "sub": period or "",
                    },
                    {
                        "id": "qb-expenses",
                        "label": "Expenses",
                        "value": expenses,
                        "format": "money",
                        "empty": expenses is None,
                        "sub": period or "",
                    },
                    {
                        "id": "qb-categories",
                        "label": "Categories",
                        "value": len(cat_rows) if cat_rows else None,
                        "format": "count",
                        "empty": not cat_rows,
                    },
                ],
                hint="QuickBooks P&L vitals · import-backed only.",
            )
        )
    except Exception:
        widgets.append(
            _money_kpi(
                "qb-net-income",
                "Net Income",
                net,
                hint="QuickBooks P&L import." if net is not None else "Net income field missing on P&L row.",
                delta_label=period or None,
            )
        )

    summary_bits = []
    if period:
        summary_bits.append(period)
    if net is not None:
        summary_bits.append(f"Net ${net:,.0f}")
    widgets.append(
        {
            **_status_widget(
                "qb-pl-summary",
                "P&L Summary",
                message=" · ".join(summary_bits) if summary_bits else "Loaded",
                hint="Read-only QuickBooks import snapshot — not a live ledger.",
            ),
            "size": "strip",
            "compact": True,
        }
    )

    series = []
    for row in cat_rows:
        label = str(row.get("Category") or row.get("category") or "").strip()
        # Prefer short trailing segment when OCR/redaction prefixes are long
        if len(label) > 48:
            parts = [p.strip() for p in re.split(r"[·:>\|]", label) if p.strip()]
            label = parts[-1] if parts else label[:48]
        amt = _parse_money(row.get("Amount") or row.get("amount"))
        if label and amt is not None:
            series.append({"label": label[:32], "value": float(amt)})
    series = series[:8]
    if series and any(s["value"] for s in series):
        widgets.append(
            {
                "id": "qb-expense-breakdown",
                "type": "chart",
                "chartType": "bar",
                "label": "Expense Breakdown",
                "series": series,
                "hint": "Top categories from QuickBooks expenseCategories import.",
            }
        )
    else:
        widgets.append(
            _empty_chart(
                "qb-expense-breakdown",
                "Expense Breakdown",
                hint="Expense category rows not available in QuickBooks import.",
            )
        )

    widgets.append(build_expense_horizontal_bars(bundle))
    try:
        from apex_financial_console_pack import collapse_empty_large

        # Phase 6 polish: empty expense hbar collapses to strip chip
        for i, w in enumerate(widgets):
            if isinstance(w, dict) and w.get("id") == "qb-expense-hbar" and w.get("status") == "empty":
                widgets[i] = collapse_empty_large(w)
                break
            if isinstance(w, dict) and w.get("id") == "qb-expense-hbar":
                w["size"] = "m"
                break
    except Exception:
        pass
    widgets.append(build_categorize_assist(bundle))
    try:
        from apex_missing_widgets_pack import append_quickbooks_missing

        append_quickbooks_missing(widgets, bundle)
    except Exception:
        pass
    try:
        from apex_qb_payroll_pack import payroll_ap_widgets

        widgets.extend(payroll_ap_widgets(bundle))
    except Exception:
        pass
    try:
        from apex_qb_net_profit_pack import net_profit_widget

        widgets.append(net_profit_widget(bundle))
    except Exception:
        pass
    return widgets


def _ar_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    widgets: list[dict[str, Any]] = []
    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    buckets = reports.get("arAgingBuckets") if isinstance(reports.get("arAgingBuckets"), list) else []
    ar_rows = _section_rows(bundle, "softdent", "ar")

    ar_total = ar.get("totalOutstanding")
    if not isinstance(ar_total, (int, float)) and ar_rows:
        # Fallback: sum SoftDent A/R rows directly when reports summary missing
        total = 0.0
        any_amt = False
        for row in ar_rows:
            amt = _parse_money(row.get("Balance") or row.get("Outstanding") or row.get("Amount") or row.get("Total"))
            if amt is not None:
                total += amt
                any_amt = True
        ar_total = total if any_amt else None

    ninety_pct = ar.get("ninetyPlusPct")

    series: list[dict[str, Any]] = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        amt = b.get("amount")
        if isinstance(amt, (int, float)):
            series.append({"label": str(b.get("bucket") or ""), "value": float(amt)})
    if not series and ar_rows:
        for row in ar_rows:
            label = str(row.get("Bucket") or row.get("Aging") or row.get("AgeBucket") or "").strip()
            amt = _parse_money(row.get("Balance") or row.get("Outstanding") or row.get("Amount"))
            if label and amt is not None:
                series.append({"label": label, "value": float(amt)})

    lag: dict[str, Any] = {}
    try:
        from nr2_analytics import collection_lag

        lag = collection_lag(bundle=bundle) or {}
    except Exception:
        lag = {}

    try:
        from apex_compact_pages_pack import build_kpi_micro_strip

        ninety_val = float(ninety_pct) if isinstance(ninety_pct, (int, float)) else None
        lag_val = float(lag["avgLagDays"]) if lag.get("hasData") and lag.get("avgLagDays") is not None else None
        widgets.append(
            build_kpi_micro_strip(
                "ar-vitals-strip",
                "A/R Vitals",
                [
                    {
                        "id": "ar-outstanding",
                        "label": "Outstanding",
                        "value": float(ar_total) if isinstance(ar_total, (int, float)) else None,
                        "format": "money",
                        "empty": not isinstance(ar_total, (int, float)),
                    },
                    {
                        "id": "ar-90-plus-pct",
                        "label": "90+ %",
                        "value": ninety_val,
                        "format": "pct",
                        "empty": ninety_val is None,
                        "tone": "danger" if ninety_val is not None and ninety_val > 20 else "",
                        "sub": f"${float(ar.get('ninetyPlusOutstanding') or 0):,.0f}"
                        if ninety_val is not None
                        else "",
                    },
                    {
                        "id": "ar-collection-lag",
                        "label": "Coll. Lag",
                        "value": lag_val,
                        "format": "count",
                        "empty": lag_val is None,
                        "sub": "days" if lag_val is not None else "",
                    },
                    {
                        "id": "ar-bucket-count",
                        "label": "Buckets",
                        "value": len(series) if series else None,
                        "format": "count",
                        "empty": not series,
                    },
                ],
                hint="A/R vitals from SoftDent aging · empty stays empty.",
                nav_hash="ar/collections",
            )
        )
    except Exception:
        widgets.append(
            _money_kpi(
                "ar-outstanding",
                "A/R Outstanding",
                float(ar_total) if isinstance(ar_total, (int, float)) else None,
                hint=str(ar.get("followUpHint") or "From SoftDent A/R import.")
                if isinstance(ar_total, (int, float))
                else "A/R aging import not available.",
            )
        )

    if series and any(s["value"] for s in series):
        widgets.append(
            {
                "id": "ar-aging-chart",
                "type": "chart",
                "chartType": "bar",
                "label": "A/R Aging Buckets",
                "series": series,
                "hint": "Buckets from SoftDent A/R import.",
            }
        )
    else:
        widgets.append(
            _empty_chart(
                "ar-aging-chart",
                "A/R Aging Buckets",
                hint="Import SoftDent A/R aging to populate this chart.",
            )
        )

    widgets.append(
        {
            **_status_widget(
                "ar-follow-up",
                "A/R Follow-up",
                message="Guidance",
                hint=str(ar.get("followUpHint") or "Prioritize 90+ balances when aging import is present."),
                status="ok" if isinstance(ar_total, (int, float)) else "empty",
            ),
            "size": "strip",
            "compact": True,
        }
    )

    widgets[0:0] = _visual_boost_ar(reports, bundle)
    widgets.append(build_ar_waterfall(reports, bundle))
    widgets.append(build_ar_aging_outlook(reports, bundle))
    try:
        from apex_bar_trend_page_org_pack import build_ar_forecast_trend_blocked

        # Phase 5: honest blocked dual-axis stub (no illustrative decay dollars)
        widgets.append(build_ar_forecast_trend_blocked(reports, bundle))
    except Exception:
        pass
    widgets.append(build_collection_bullet(bundle))
    # Moonshot MUST: Collections Radial-Gauge on A/R page too
    try:
        from apex_better_backend_widgets_pack import build_collections_radial_gauge

        coll_gauge_ar = build_collections_radial_gauge(bundle, reports)
        if coll_gauge_ar:
            widgets.append(coll_gauge_ar)
    except Exception:
        pass
    try:
        from apex_missing_widgets_pack import append_ar_missing

        append_ar_missing(widgets, bundle)
    except Exception:
        pass
    # Moonshot SHOULD: A/R main page collection task list
    try:
        from apex_better_backend_widgets_pack import build_ar_main_collection_task_list

        widgets.append(build_ar_main_collection_task_list(bundle))
    except Exception:
        pass
    # Moonshot NICE: A/R aging Pareto
    try:
        from apex_better_backend_widgets_pack import build_ar_aging_pareto

        widgets.append(build_ar_aging_pareto(bundle, reports))
    except Exception:
        pass
    _apply_threshold_alerts(widgets, reports)
    return widgets


def build_ar_aging_outlook(reports: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """Illustrative A/R bucket trend when ≥2 SoftDent snapshots exist — never invents dollars."""
    buckets = reports.get("arAgingBuckets") if isinstance(reports.get("arAgingBuckets"), list) else []
    current = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        amt = b.get("amount")
        if isinstance(amt, (int, float)):
            current.append({"label": str(b.get("bucket") or ""), "value": float(amt)})
    # Look for historical SoftDent A/R period rows (rare)
    ar_hist: list[dict[str, Any]] = []
    softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    for key in ("arHistory", "arSnapshots", "ar"):
        sec = softdent.get(key)
        if isinstance(sec, dict):
            rows = sec.get("history") if isinstance(sec.get("history"), list) else None
            if rows is None:
                rows = sec.get("snapshots") if isinstance(sec.get("snapshots"), list) else None
            if isinstance(rows, list):
                ar_hist = [r for r in rows if isinstance(r, dict)]
                break
    projection = None
    status = "partial" if current else "empty"
    hint = "Need ≥2 SoftDent A/R snapshots for trend/projection — showing current buckets only. Not a cash forecast."
    if len(ar_hist) >= 2 and current:
        # Simple linear delta on matching bucket labels between last two snapshots
        prior = ar_hist[-2]
        latest = ar_hist[-1]
        prior_map = {}
        latest_map = {}
        for src, dest in ((prior, prior_map), (latest, latest_map)):
            buck = src.get("buckets") if isinstance(src.get("buckets"), list) else []
            for b in buck:
                if isinstance(b, dict) and isinstance(b.get("amount"), (int, float)):
                    dest[str(b.get("bucket") or "")] = float(b["amount"])
        if prior_map and latest_map:
            projection = []
            for item in current:
                lab = item["label"]
                a = prior_map.get(lab)
                b = latest_map.get(lab, item["value"])
                if a is None:
                    projection.append({"label": lab, "value": max(0.0, float(item["value"]))})
                    continue
                delta = float(b) - float(a)
                projection.append({"label": lab, "value": max(0.0, float(b) + delta)})
            status = "ok"
            hint = "Illustrative next-period trend from last two SoftDent A/R snapshots — not a cash forecast."
    if not current:
        return {
            "id": "ar-aging-outlook",
            "type": "stacked-bar",
            "label": "A/R Aging Outlook",
            "size": "l",
            "segments": [],
            "status": "empty",
            "emptyMessage": "No A/R buckets",
            "hint": "Import SoftDent A/R aging to populate outlook.",
            "projection": None,
        }
    return {
        "id": "ar-aging-outlook",
        "type": "stacked-bar",
        "label": "A/R Aging Outlook",
        "size": "l",
        "segments": projection or current,
        "status": status,
        "projection": projection,
        "current": current,
        "hint": hint,
    }


def _claims_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    widgets: list[dict[str, Any]] = []
    summary = _claims_summary_from_bundle(bundle)
    ct = reports.get("claimTracking") if isinstance(reports.get("claimTracking"), dict) else {}

    # Prefer ClaimStatus-aware summary; fall back to financial_reports totals
    total = summary.get("totalClaims")
    if total is None and isinstance(ct.get("totalClaims"), int):
        total = ct.get("totalClaims")
        summary["available"] = True
        summary["deniedCount"] = ct.get("deniedCount")
        summary["agingPast30"] = ct.get("deniedAgingPast30Days")
        summary["followUpHint"] = ct.get("followUpHint") or summary.get("followUpHint")
        summary["totalClaims"] = total

    # Professional layout (hal-10420): Executive RCM Console primary design
    # Import strip → KPI strip → aging+critical → table/kanban workbench → risk+ERA
    try:
        from apex_claims_narratives_pack import (
            apply_aging_threshold_alerts,
            build_status_columns,
            claims_aging_exposure_widget,
            claims_critical_actions_widget,
            claims_era_gauge_widget,
            claims_executive_strip_widget,
            claims_risk_analytics_widget,
            kanban_widget,
        )
        from apex_program_improve_pack import (
            apply_era_to_kanban_columns,
            attachment_counts,
            import_health_widget,
        )

        claim_rows = _section_rows(bundle, "softdent", "claims") or _section_rows(
            bundle, "softdent", "claimStatus"
        )
        kanban_payload = build_status_columns(claim_rows if isinstance(claim_rows, list) else [])
        cols = kanban_payload.get("columns") if isinstance(kanban_payload.get("columns"), dict) else {}
        kanban_payload["columns"] = apply_era_to_kanban_columns(cols)
        kanban_payload["counts"] = {
            k: len(v) if isinstance(v, list) else 0 for k, v in (kanban_payload.get("columns") or {}).items()
        }
        att_counts = attachment_counts()
        for _col, cards in (kanban_payload.get("columns") or {}).items():
            if not isinstance(cards, list):
                continue
            for card in cards:
                if not isinstance(card, dict):
                    continue
                cid = str(card.get("claimId") or "")
                n = int(att_counts.get(cid) or 0)
                if n and not card.get("attachments"):
                    card["attachments"] = {"current": n, "required": None}
                elif n and isinstance(card.get("attachments"), dict):
                    card["attachments"]["current"] = max(int(card["attachments"].get("current") or 0), n)

        kmeta = kanban_payload.get("meta") if isinstance(kanban_payload.get("meta"), dict) else {}
        buckets = summary.get("agingBuckets") if isinstance(summary.get("agingBuckets"), dict) else {}
        aging_meta = summary.get("agingMeta") if isinstance(summary.get("agingMeta"), dict) else {}
        missing_age = bool(aging_meta.get("missingAgeField"))

        health = import_health_widget(bundle)
        health["size"] = "strip"
        health["label"] = "Import Health"
        health["compact"] = True
        widgets.append(health)
        widgets.append(claims_executive_strip_widget(summary, kmeta))
        try:
            from apex_bar_trend_page_org_pack import (
                build_claims_aging_mini_trend,
                build_claims_status_bar,
            )

            widgets.append(
                build_claims_status_bar(summary, kanban_payload.get("counts") if isinstance(kanban_payload, dict) else None)
            )
            widgets.append(
                build_claims_aging_mini_trend(
                    summary.get("agingCounts") if isinstance(summary.get("agingCounts"), dict) else {}
                )
            )
        except Exception:
            pass
        widgets.append(
            claims_aging_exposure_widget(
                {"buckets": buckets or {}, "counts": summary.get("agingCounts") or {}},
                missing_age=missing_age,
            )
        )
        # Demote xl aging matrix for zero-scroll (hal-10610); full detail on #claims/kanban
        for _w in widgets:
            if isinstance(_w, dict) and _w.get("id") == "claims-aging-exposure":
                _w["size"] = "m"
                _w["maxHeight"] = 320
                _w["compact"] = True
                break
        # Moonshot zero-scroll: pipeline + Top 5 on main; full workbench → #claims/kanban
        # Skip claims_critical_actions when top-critical list is present (duplicate height).
        try:
            from apex_compact_pages_pack import (
                claims_pipeline_summary_widget,
                claims_top_critical_widget,
            )

            rows: list[Any] = []
            if isinstance(kanban_payload, dict):
                cols = kanban_payload.get("columns") if isinstance(kanban_payload.get("columns"), dict) else {}
                for key in ("denied", "pendingReview", "pending", "submitted", "eraMatched"):
                    for card in cols.get(key) if isinstance(cols.get(key), list) else []:
                        if isinstance(card, dict):
                            rows.append(card)
                if not rows:
                    for card in kanban_payload.get("rows") if isinstance(kanban_payload.get("rows"), list) else []:
                        if isinstance(card, dict):
                            rows.append(card)
            widgets.append(
                claims_top_critical_widget(
                    rows,
                    available=bool(kanban_payload.get("available")),
                )
            )
            widgets.append(
                claims_pipeline_summary_widget(
                    kanban_payload.get("counts") if isinstance(kanban_payload, dict) else None,
                    available=bool(kanban_payload.get("available")),
                )
            )
            widgets.append(
                {
                    "id": "claims-open-kanban",
                    "type": "status",
                    "label": "Claims Workbench",
                    "size": "strip",
                    "compact": True,
                    "maxHeight": 120,
                    "status": "ok",
                    "message": "Open full Kanban / table workbench",
                    "hint": "Hash #claims/kanban — zero-scroll (pipeline + Top 5 above).",
                    "navHash": "claims/kanban",
                }
            )
        except Exception:
            widgets.append(claims_critical_actions_widget(kanban_payload))
            widgets.append(kanban_widget(kanban_payload))
        widgets.append(
            claims_risk_analytics_widget(kmeta, available=bool(kanban_payload.get("available")))
        )
        era_g = claims_era_gauge_widget(kmeta, available=bool(kanban_payload.get("available")))
        if isinstance(era_g, dict):
            era_g = dict(era_g)
            era_g["size"] = "m"
            era_g["maxHeight"] = 240
            era_g["compact"] = True
        widgets.append(era_g)
        apply_aging_threshold_alerts(
            widgets,
            {"counts": summary.get("agingCounts") or {}},
        )
    except Exception:
        # Fallback: legacy KPI mosaic if pack import fails
        widgets.append(
            _count_kpi(
                "claims-total",
                "Total Claims",
                total,
                hint="SoftDent claims import." if total is not None else "Claims import not available.",
            )
        )
        widgets.append(
            _count_kpi(
                "claims-open",
                "Open / Pending Claims",
                summary.get("openCount") if summary.get("available") else None,
                hint="Statuses matching open/pending/review from SoftDent ClaimStatus."
                if summary.get("available")
                else "Import SoftDent claims to count open items.",
            )
        )
        widgets.append(
            _count_kpi(
                "claims-denied",
                "Denied Claims",
                summary.get("deniedCount") if summary.get("available") else None,
                hint="Denied/rejected ClaimStatus counts — not invented."
                if summary.get("available")
                else "Claims import not available.",
            )
        )

    # Below-fold analytics (not part of primary above-fold console)
    widgets.append(build_ins_patient_split(bundle))
    try:
        from apex_missing_widgets_pack import append_claims_missing

        append_claims_missing(widgets, bundle)
    except Exception:
        pass
    try:
        from apex_hal_said_improve_pack import append_claims_hal_said

        append_claims_hal_said(widgets)
    except Exception:
        pass
    # Moonshot NICE: Claim status timeline lanes
    try:
        from apex_better_backend_widgets_pack import build_claim_status_lanes

        widgets.append(build_claim_status_lanes(bundle))
    except Exception:
        pass
    _apply_threshold_alerts(widgets, reports, claims_summary=summary)
    return widgets


def _narratives_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets: list[dict[str, Any]] = []
    state = _load_local_json("nr2:v2:narratives") or {}
    drafts = state.get("drafts") if isinstance(state.get("drafts"), list) else []
    draft_text = str(state.get("draftText") or "").strip()
    clinical = _section_rows(bundle, "softdent", "clinicalNotes")

    draft_count = len(drafts)
    if draft_count == 0 and draft_text:
        draft_count = 1

    if draft_count:
        widgets.append(
            _count_kpi(
                "narr-drafts",
                "Narrative Drafts",
                draft_count,
                hint="Local narrative workflow store (nr2:v2:narratives).",
            )
        )
    else:
        widgets.append(
            _empty_kpi(
                "narr-drafts",
                "Narrative Drafts",
                hint="No saved narrative drafts — use SoftDent clinical notes to seed drafts.",
            )
        )

    widgets.append(
        _count_kpi(
            "narr-clinical-notes",
            "Clinical Notes (import)",
            len(clinical) if clinical else None,
            hint="SoftDent clinicalNotes import — source material for narratives."
            if clinical
            else "Import SoftDent clinical notes to support narrative drafting.",
        )
    )

    lib_count = None
    try:
        from hal_narrative_library import build_generic_draft_library

        lib_count = len(build_generic_draft_library())
    except Exception:
        lib_count = None
    widgets.append(
        _count_kpi(
            "narr-template-library",
            "Template Library",
            lib_count,
            hint="Generic insurance narrative templates available locally."
            if lib_count is not None
            else "Narrative template library unavailable.",
        )
    )

    composer = state.get("composer") if isinstance(state.get("composer"), dict) else {}
    if drafts or draft_text:
        focus = str(composer.get("focus") or "Medical Necessity")
        widgets.append(
            _status_widget(
                "narr-workflow",
                "Narrative Workflow",
                message="Draft in progress" if draft_text or drafts else "Idle",
                hint=f"Composer focus: {focus}. Review before any outbound use.",
            )
        )
    else:
        widgets.append(
            _status_widget(
                "narr-workflow",
                "Narrative Workflow",
                message="Empty",
                hint="No drafts yet — start from SoftDent clinical notes or the template library.",
                status="empty",
            )
        )

    # Moonshot SHOULD: Narratives AI insight (rule-backed variance)
    try:
        from apex_better_backend_widgets_pack import build_narratives_ai_insight

        widgets.append(build_narratives_ai_insight(bundle))
    except Exception:
        pass

    return widgets


def _documents_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets: list[dict[str, Any]] = []
    state = _load_local_json("nr2:v2:documents") or {}
    queue = state.get("queue") if isinstance(state.get("queue"), list) else []
    previews = state.get("previewById") if isinstance(state.get("previewById"), dict) else {}

    if queue:
        by_status: dict[str, int] = {}
        for doc in queue:
            if not isinstance(doc, dict):
                continue
            st = str(doc.get("status") or doc.get("Status") or "queued").strip() or "queued"
            by_status[st] = by_status.get(st, 0) + 1
        widgets.append(
            _count_kpi(
                "docs-queue",
                "Intake Queue",
                len(queue),
                hint="Document intake queue from local document sync store.",
                delta_label=", ".join(f"{k}:{v}" for k, v in sorted(by_status.items())[:3]) or None,
            )
        )
        widgets.append(
            _count_kpi(
                "docs-previews",
                "Previews Cached",
                len(previews) if previews else 0,
                hint="previewById entries paired with intake queue documents.",
            )
        )
        widgets.append(
            _status_widget(
                "docs-intake-status",
                "Document Intake",
                message="Queue active",
                hint=f"{len(queue)} document(s) awaiting review / posting.",
            )
        )
    else:
        # Try integration_health count as secondary signal
        count = None
        try:
            from integration_health import _document_queue_count

            info = _document_queue_count(None)
            if isinstance(info, dict) and info.get("ok"):
                count = int(info.get("count") or 0)
        except Exception:
            count = None
        if count:
            widgets.append(
                _count_kpi(
                    "docs-queue",
                    "Intake Queue",
                    count,
                    hint="Document intake count from integration health.",
                )
            )
        else:
            widgets.append(
                _empty_kpi(
                    "docs-queue",
                    "Intake Queue",
                    hint="Document intake queue empty — sync accounting documents to populate.",
                )
            )
        widgets.append(
            _empty_kpi(
                "docs-previews",
                "Previews Cached",
                hint="No document previews in local store.",
            )
        )
        widgets.append(
            _status_widget(
                "docs-intake-status",
                "Document Intake",
                message="Empty",
                hint="Run document sync / OCR intake to fill the queue.",
                status="empty",
            )
        )

    widgets.append(build_tax_library_widget())
    # Moonshot NICE: Claim status lanes on documents workflow view
    try:
        from apex_better_backend_widgets_pack import build_claim_status_lanes

        widgets.append(build_claim_status_lanes(bundle))
    except Exception:
        pass
    return widgets


def _library_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports, bundle
    widgets: list[dict[str, Any]] = []
    # Moonshot fix-all: seed library index from document queue when storage empty
    try:
        from hal_post_pull_setup import seed_document_library

        seed_document_library(force=False)
    except Exception:
        pass
    state = _load_local_json("nr2:v2:library") or {}
    docs = state.get("docs") if isinstance(state.get("docs"), list) else []
    detail = state.get("detailById") if isinstance(state.get("detailById"), dict) else {}
    results = state.get("results")
    doc_count = len(docs)
    if isinstance(results, int) and results > doc_count:
        doc_count = results

    # Previews may live on documents store
    doc_state = _load_local_json("nr2:v2:documents") or {}
    previews = doc_state.get("previewById") if isinstance(doc_state.get("previewById"), dict) else {}

    if doc_count:
        widgets.append(
            _count_kpi(
                "lib-docs",
                "Library Documents",
                doc_count,
                hint="Indexed document library (nr2:v2:library).",
            )
        )
    else:
        widgets.append(
            _empty_kpi(
                "lib-docs",
                "Library Documents",
                hint="Document library empty — promote intake docs or seed library after sync.",
            )
        )

    preview_count = len(detail) or len(previews)
    if preview_count:
        widgets.append(
            _count_kpi(
                "lib-previews",
                "Preview Records",
                preview_count,
                hint="Library detailById and/or document preview cache.",
            )
        )
    else:
        widgets.append(
            _empty_kpi(
                "lib-previews",
                "Preview Records",
                hint="No library preview metadata available yet.",
            )
        )

    storage = state.get("storage") if isinstance(state.get("storage"), dict) else {}
    if storage:
        widgets.append(
            _status_widget(
                "lib-storage",
                "Library Storage",
                message=f"Indexed {storage.get('indexed', doc_count)}",
                hint=f"Source: {storage.get('source') or 'local'} · refreshed {storage.get('refreshedAt') or '—'}.",
            )
        )
    else:
        widgets.append(
            _status_widget(
                "lib-storage",
                "Library Storage",
                message="Not indexed",
                hint="Library index builds from document intake after post-pull setup.",
                status="empty",
            )
        )
        widgets[-1]["gapCode"] = "LIBRARY_NOT_INDEXED"

    return widgets


def _office_manager_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    widgets: list[dict[str, Any]] = []
    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}

    connected = summary.get("connected")
    partial = summary.get("partial")
    missing = summary.get("missing")
    stale = summary.get("stale")
    total = summary.get("total")

    try:
        from apex_compact_pages_pack import build_kpi_micro_strip

        widgets.append(
            build_kpi_micro_strip(
                "om-vitals-strip",
                "Import Vitals",
                [
                    {
                        "id": "om-connected",
                        "label": "Connected",
                        "value": connected if isinstance(connected, int) else None,
                        "format": "count",
                        "empty": not isinstance(connected, int),
                        "sub": f"of {total}" if isinstance(total, int) else "",
                    },
                    {
                        "id": "om-partial",
                        "label": "Partial",
                        "value": partial if isinstance(partial, int) else None,
                        "format": "count",
                        "empty": not isinstance(partial, int),
                    },
                    {
                        "id": "om-missing",
                        "label": "Missing",
                        "value": missing if isinstance(missing, int) else None,
                        "format": "count",
                        "empty": not isinstance(missing, int),
                    },
                    {
                        "id": "om-stale",
                        "label": "Stale",
                        "value": stale if isinstance(stale, int) else None,
                        "format": "count",
                        "empty": not isinstance(stale, int),
                    },
                ],
                hint="Import diagnostics vitals · empty stays empty.",
                nav_hash="office-manager/tasks",
            )
        )
    except Exception:
        if isinstance(connected, int):
            widgets.append(
                _count_kpi(
                    "om-connected",
                    "Imports Connected",
                    connected,
                    hint="Import diagnostics: datasets with connected status.",
                    delta_label=f"of {total}" if isinstance(total, int) else None,
                )
            )
        else:
            widgets.append(
                _empty_kpi(
                    "om-connected",
                    "Imports Connected",
                    hint="Import diagnostics unavailable — refresh imports.",
                )
            )

    # Readiness posture
    if isinstance(connected, int) and isinstance(total, int) and total > 0:
        if missing == 0 and partial == 0 and stale == 0:
            posture = "Ready"
            posture_hint = f"All {total} diagnosed datasets connected."
            posture_status = "ok"
        elif missing == 0:
            posture = "Partial"
            posture_hint = f"{connected}/{total} connected; review partial/stale datasets."
            posture_status = "ok"
        else:
            posture = "Gaps"
            posture_hint = f"{missing} missing dataset(s) — sync SoftDent/QuickBooks exports."
            posture_status = "empty"
    else:
        posture = "Unknown"
        posture_hint = "Run import sync to evaluate readiness."
        posture_status = "empty"

    widgets.append(
        {
            **_status_widget(
                "om-readiness",
                "Import Readiness",
                message=posture,
                hint=posture_hint,
                status=posture_status,
            ),
            "size": "strip",
            "compact": True,
        }
    )

    # Top priorities from diagnostic gaps
    priorities: list[str] = []
    datasets = diag.get("datasets") if isinstance(diag.get("datasets"), list) else []
    for item in datasets:
        if not isinstance(item, dict):
            continue
        st = str(item.get("status") or "")
        if st in {"missing", "partial", "stale"}:
            name = str(item.get("key") or item.get("dataset") or item.get("name") or "dataset")
            detail = str(item.get("detail") or item.get("message") or st)
            priorities.append(f"{name}: {detail}")
        if len(priorities) >= 3:
            break

    # Secondary priorities from financial follow-ups
    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    ct = reports.get("claimTracking") if isinstance(reports.get("claimTracking"), dict) else {}
    if ar.get("followUpHint") and len(priorities) < 3:
        priorities.append(str(ar["followUpHint"]))
    if ct.get("followUpHint") and len(priorities) < 3:
        priorities.append(str(ct["followUpHint"]))

    if priorities:
        widgets.append(
            _status_widget(
                "om-priorities",
                "Top Priorities",
                message=f"{len(priorities)} item(s)",
                hint=" · ".join(priorities),
            )
        )
    else:
        widgets.append(
            _status_widget(
                "om-priorities",
                "Top Priorities",
                message="Clear",
                hint="No import gaps or follow-up hints flagged from current snapshot.",
                status="ok" if isinstance(connected, int) else "empty",
            )
        )

    mode = str(bundle.get("importMode") or "")
    widgets.append(
        _status_widget(
            "om-import-mode",
            "Import Mode",
            message=mode or "unknown",
            hint=f"Bundle loadedAt {bundle.get('loadedAt') or '—'} · build {BUILD_ID}.",
        )
    )

    widgets.append(_visual_boost_office_calculator(bundle))
    widgets.append(build_payer_donut(bundle))
    widgets.append(build_ins_patient_split(bundle))
    widgets.insert(0, build_import_freshness(bundle))
    try:
        from apex_bar_trend_page_org_pack import build_operatory_util_chart
        from apex_financial_console_pack import collapse_empty_large
        from apex_program_improve_pack import build_daily_huddle_widget, import_health_widget

        widgets.insert(0, import_health_widget(bundle))
        widgets.insert(0, build_daily_huddle_widget(reports, bundle))
        util = build_operatory_util_chart(bundle)
        if util.get("status") == "empty":
            util = collapse_empty_large(util)
        else:
            util["size"] = "s"
        widgets.insert(1, util)
        widgets.insert(
            2,
            {
                "id": "om-open-operatory",
                "type": "status",
                "label": "Operatory",
                "size": "strip",
                "compact": True,
                "status": "ok",
                "message": "Open operatory detail",
                "hint": "Hash #office-manager/operatory",
                "navHash": "office-manager/operatory",
            },
        )
    except Exception:
        pass
    try:
        from apex_hal_said_improve_pack import append_office_manager_hal_said

        append_office_manager_hal_said(widgets)
    except Exception:
        pass
    try:
        from apex_missing_widgets_pack import append_office_manager_missing

        append_office_manager_missing(widgets, bundle)
    except Exception:
        pass
    # Moonshot MUST: System Health Status-Matrix
    try:
        from apex_better_backend_widgets_pack import build_system_health_status_matrix

        health_matrix = build_system_health_status_matrix(bundle)
        if health_matrix:
            widgets.append(health_matrix)
    except Exception:
        pass
    # Moonshot NEXT: TXN ledger surface on Office Manager
    try:
        from apex_better_backend_widgets_pack import (
            build_account_tx_ledger_coverage_chip,
            build_transaction_ledger_table,
        )

        widgets.append(build_account_tx_ledger_coverage_chip(bundle, page="office-manager"))
        widgets.append(build_transaction_ledger_table(bundle, page="office-manager", limit=25))
    except Exception:
        pass
    return widgets


def _hal_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """HAL medium spine (hal-10624): trust pair → insight + chat rail."""
    del reports  # HAL spine is import/insight oriented
    widgets: list[dict[str, Any]] = []

    # A rail: Ask HAL (client mounts into sticky right rail)
    widgets.append(
        {
            "id": "hal-ask",
            "type": "hal-chat",
            "label": "Ask HAL",
            "size": "l",
            "status": "ok",
            "hint": "Dictate findings · prioritize work · run grounded tools.",
            "chrome": "hal-medium",
        }
    )

    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    connected = summary.get("connected")
    total = summary.get("total")
    missing = summary.get("missing")

    # Trust pair (Import Health | Program Posture)
    if isinstance(connected, int) and isinstance(total, int) and total > 0:
        health = _count_kpi(
            "hal-import-health",
            "Import Health",
            connected,
            hint=f"{connected}/{total} datasets connected"
            + (f"; {missing} missing" if missing else "")
            + ".",
            delta_label=f"{round(100.0 * connected / total, 0):.0f}%",
        )
        health["badge"] = "connected" if not missing else "partial"
    else:
        health = _empty_kpi(
            "hal-import-health",
            "Import Health",
            hint="Import diagnostics not available.",
        )
        health["badge"] = "standby"
    health["chrome"] = "hal-medium"
    health["layoutRole"] = "trust"
    health["size"] = "m"
    widgets.append(health)

    if isinstance(connected, int) and isinstance(total, int) and total > 0 and missing == 0:
        posture_msg = "Operational"
        posture_hint = "Imports connected — HAL answers stay grounded to live imports."
        posture_status = "ok"
        posture_badge = "ok"
    elif isinstance(connected, int):
        posture_msg = "Degraded"
        posture_hint = "Some imports missing/partial — answers stay grounded to available data."
        posture_status = "ok"
        posture_badge = "warn"
    else:
        posture_msg = "Standby"
        posture_hint = "Awaiting import diagnostics."
        posture_status = "empty"
        posture_badge = "standby"

    posture = _status_widget(
        "hal-program-posture",
        "Program Posture",
        message=posture_msg,
        hint=posture_hint,
        status=posture_status,
    )
    posture["chrome"] = "hal-medium"
    posture["layoutRole"] = "trust"
    posture["badge"] = posture_badge
    posture["size"] = "m"
    widgets.append(posture)

    # AI insight
    try:
        from apex_structured_insight_pack import ai_insight_widget

        insight = ai_insight_widget()
        if isinstance(insight, dict):
            insight["chrome"] = "hal-medium"
            insight["layoutRole"] = "insight"
            widgets.append(insight)
    except Exception:
        pass

    return widgets


def _content_hub_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """hal-10618/10621 — Documents + Narratives + Library summaries on one Content page."""
    widgets: list[dict[str, Any]] = []
    try:
        from apex_compact_pages_pack import build_kpi_micro_strip

        widgets.append(
            build_kpi_micro_strip(
                "content-hub-strip",
                "Content Hub",
                [
                    {"id": "hub-docs", "label": "Documents", "value": "Open", "empty": False},
                    {"id": "hub-narr", "label": "Narratives", "value": "Open", "empty": False},
                    {"id": "hub-lib", "label": "Library", "value": "Open", "empty": False},
                    {"id": "hub-ops", "label": "Ops", "value": "Open", "empty": False},
                ],
                hint="Unified Content Hub · subpages for Documents / Narratives / Library.",
                nav_hash="content/documents",
            )
        )
    except Exception:
        pass
    for builder in (_documents_widgets, _narratives_widgets, _library_widgets):
        try:
            for w in builder(reports, bundle) or []:
                if isinstance(w, dict):
                    widgets.append(w)
        except Exception:
            pass
    return widgets


_PAGE_BUILDERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], list[dict[str, Any]]]] = {
    "financial": _financial_widgets_from_reports,
    "taxes": _taxes_widgets,
    "softdent": _softdent_widgets,
    "quickbooks": _quickbooks_widgets,
    "ar": _ar_widgets,
    "claims": _claims_widgets,
    "content": _content_hub_widgets,
    "narratives": _narratives_widgets,
    "documents": _documents_widgets,
    "library": _library_widgets,
    "office-manager": _office_manager_widgets,
    "hal": _hal_widgets,
}


def build_apex_widgets(
    page_id: str,
    *,
    sub: str | None = None,
    claim_id: str | None = None,
    patient_id: str | None = None,
    _fill: bool = False,
) -> dict[str, Any]:
    import copy
    import sys
    import threading
    import time

    pid = re.sub(r"[^a-z0-9\-]", "", str(page_id or "").strip().lower())
    sub_key = re.sub(r"[^a-z0-9\-]", "", str(sub or "").strip().lower()) or None
    cid = str(claim_id or "").strip() or None
    pid_patient = str(patient_id or "").strip() or None
    if _apex_blank_all_widgets():
        # Strip every page/subpage stage — no warming stubs, no widgets.
        page_label = pid if not sub_key else f"{pid}/{sub_key}"
        return {
            "page": page_label if pid in APEX_PAGES else (pid or "unknown"),
            "parent": pid if sub_key and pid in APEX_PAGES else None,
            "sub": sub_key,
            "claimId": cid,
            "patientId": pid_patient,
            "refreshedAt": _utc_now(),
            "buildId": BUILD_ID,
            "warming": False,
            "widgets": [],
            "mosaicLayout": None,
            "sourceNote": "blank-stage — all widgets removed",
            "blankWidgets": True,
        }
    if pid not in APEX_PAGES:
        return {
            "page": pid or "unknown",
            "sub": sub_key,
            "refreshedAt": _utc_now(),
            "buildId": BUILD_ID,
            "widgets": [
                {
                    "id": "unknown-page",
                    "type": "status",
                    "status": "empty",
                    "label": "Unknown page",
                    "message": "Unknown page id",
                    "hint": f"Valid pages: {', '.join(APEX_PAGES)}",
                }
            ],
            "sourceNote": "invalid page",
        }

    cache_key = pid if not sub_key else f"{pid}:{sub_key}:{cid or ''}:{pid_patient or ''}"
    if not sub_key and pid_patient:
        cache_key = f"{pid}:::{pid_patient}"
    # Local-DB / attachment-backed subpages must not serve stale payloads.
    skip_cache = sub_key in {
        "collections",
        "huddle",
        "batch",
        "claim-docs",
        "payers",
        "era",
        "forecast",
        "periods",
        "calendar",
        "planning",
        "ops",
        "tasks",
        "attachments",
        "history",
        "audit",
        "templates",
        "system-logs",
        "tax-docs",
    } or bool(pid_patient)
    now = time.monotonic()
    if not skip_cache:
        hit = _WIDGETS_CACHE.get(cache_key)
        if hit and (now - float(hit.get("at") or 0.0)) < _WIDGETS_CACHE_TTL_SEC:
            cached = hit.get("payload")
            if isinstance(cached, dict):
                return copy.deepcopy(cached)

    # Moonshot Expert SE Phase 3 REC-007: stub fast-path on cold/expired miss; background fill.
    stub_on = str(os.getenv("NR2_WIDGETS_STUB_FASTPATH") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    warming_key = f"{cache_key}:warming"
    if not skip_cache and not _fill and stub_on:
        # Stale-while-revalidate: if TTL expired but we still have a real payload, keep serving
        # it while a background fill runs. Returning warming:true here remounted HAL chat and
        # triggered client hard-reloads mid-conversation.
        stale_hit = _WIDGETS_CACHE.get(cache_key)
        stale_payload = stale_hit.get("payload") if isinstance(stale_hit, dict) else None
        if isinstance(stale_payload, dict) and not stale_payload.get("warming"):
            if warming_key not in _WIDGETS_CACHE:

                def _refill_stale_widgets() -> None:
                    try:
                        build_apex_widgets(
                            pid, sub=sub_key, claim_id=cid, patient_id=pid_patient, _fill=True
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(f"Widget stale refill failed for {cache_key}: {exc}", file=sys.stderr)
                    finally:
                        _WIDGETS_CACHE.pop(warming_key, None)

                _WIDGETS_CACHE[warming_key] = {"at": now}
                threading.Thread(
                    target=_refill_stale_widgets, daemon=True, name=f"nr2-widgets-stale-{cache_key}"
                ).start()
            out = copy.deepcopy(stale_payload)
            out["staleWhileRevalidate"] = True
            return out

        # Moonshot import-cache KPIs: per-page progress + retryAfter (empty mosaic ≠ crash)
        progress = _get_fill_progress(pid)
        fill_pct = int(progress.get("pct") or 0)
        if fill_pct <= 0:
            # Queued / about to fill — never leave all tabs at silent 0 forever
            _update_fill_progress(pid, 5)
            fill_pct = 5
        retry_after = max(1, min(5, (100 - fill_pct) // 25 + 1)) if fill_pct < 100 else 1
        stub = {
            "page": pid,
            "sub": sub_key,
            "refreshedAt": _utc_now(),
            "buildId": BUILD_ID,
            "warming": True,
            "fillProgress": fill_pct,
            "fillPage": pid,
            "retryAfter": retry_after,
            "widgets": [
                {
                    "id": "warming-bridge",
                    "type": "status",
                    "status": "empty",
                    "label": "Loading bridge instruments…",
                    "message": f"Warming import cache · {fill_pct}% (empty ≠ $0).",
                    "fillProgress": fill_pct,
                    "fillPage": pid,
                    "showFillProgress": True,
                    "hint": "Direct-first pipeline assembling SoftDent/QuickBooks.",
                }
            ],
            "sourceNote": "stub-fastpath",
            "cachedForSec": 0,
        }
        already = _WIDGETS_CACHE.get(warming_key)
        if not already:

            def _fill_widgets_cache() -> None:
                global _WIDGETS_FILL_FAILURES
                _update_fill_progress(pid, 5)
                try:
                    _update_fill_progress(pid, 40)
                    build_apex_widgets(
                        pid, sub=sub_key, claim_id=cid, patient_id=pid_patient, _fill=True
                    )
                    _update_fill_progress(pid, 100)
                except Exception as exc:  # noqa: BLE001
                    import traceback

                    _WIDGETS_FILL_FAILURES += 1
                    traceback.print_exc()
                    print(
                        f"Widget cache fill failed for {cache_key}: {exc} "
                        f"(failures={_WIDGETS_FILL_FAILURES})",
                        file=sys.stderr,
                    )
                    # Fail-open: surface error payload so client exits infinite warming stub
                    fail_payload = {
                        "page": pid if not sub_key else f"{pid}/{sub_key}",
                        "parent": pid,
                        "sub": sub_key,
                        "claimId": cid,
                        "refreshedAt": _utc_now(),
                        "buildId": BUILD_ID,
                        "warming": False,
                        "fillFailed": True,
                        "widgets": [
                            {
                                "id": "warming-fill-failed",
                                "type": "status",
                                "status": "empty",
                                "label": "Bridge cache fill failed",
                                "message": "Retry Sync imports if this persists — empty ≠ $0.",
                                "hint": f"{type(exc).__name__}: {str(exc)[:160]}",
                                "size": "strip",
                                "compact": True,
                            }
                        ],
                        "sourceNote": "stub-fill-failed",
                        "errors": [str(exc)[:200]],
                        "cachedForSec": 5,
                    }
                    _WIDGETS_CACHE[cache_key] = {
                        "at": time.monotonic(),
                        "payload": copy.deepcopy(fail_payload),
                    }
                finally:
                    _WIDGETS_CACHE.pop(warming_key, None)
                    _update_fill_progress(pid, 100)
                    _prune_fill_progress()

            _WIDGETS_CACHE[warming_key] = {"at": now}
            threading.Thread(
                target=_fill_widgets_cache, daemon=True, name=f"nr2-widgets-warm-{cache_key}"
            ).start()
        # Moonshot: prevent CDN/browser from caching warming stubs (buildId skew)
        try:
            from bottle import response

            response.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            response.set_header("Pragma", "no-cache")
            response.set_header("Expires", "0")
            response.set_header("X-NR2-Build-Id", BUILD_ID)
            response.set_header("Retry-After", str(retry_after))
        except Exception:
            pass
        return stub

    reports, bundle, errors = _load_reports_and_bundle()
    # Moonshot fix-all: hydrate selectedPatient when patient_id query is present
    if pid_patient and isinstance(bundle, dict):
        try:
            from patient_dossier import build_patient_dossier

            dossier = build_patient_dossier(pid_patient)
            if isinstance(dossier, dict):
                bundle = dict(bundle)
                bundle["selectedPatient"] = dossier
                bundle["selectedPatientId"] = pid_patient
        except Exception:
            pass
    if sub_key:
        try:
            from apex_subpages_pack import resolve_subpage_builder

            sub_builder = resolve_subpage_builder(pid, sub_key)
        except Exception:
            sub_builder = None
        if sub_builder is None:
            widgets = [
                {
                    "id": "unknown-subpage",
                    "type": "status",
                    "status": "empty",
                    "label": "Unknown subpage",
                    "message": f"No subpage '{sub_key}' under {pid}",
                    "hint": "Supported: financial/workpapers|providers|periods, claims/detail|batch|era, ar/collections|forecast, office-manager/huddle, documents/claim-docs, library/payers.",
                }
            ]
            source_note = f"{pid}/{sub_key}: unknown subpage"
        elif pid == "financial" and sub_key == "workpapers":
            widgets = sub_builder(
                reports,
                bundle,
                workpaper_widget=build_workpaper_widget,
                variance_widget=build_variance_alert_widget,
            )
            source_note = f"{pid}/{sub_key}: subpage pack + CPA workpaper"
        elif pid == "claims" and sub_key == "detail":
            widgets = sub_builder(reports, bundle, claim_id=cid)
            source_note = f"{pid}/{sub_key}: claim detail (id={cid or 'none'})"
        elif pid == "documents" and sub_key == "claim-docs":
            widgets = sub_builder(reports, bundle, claim_id=cid)
            source_note = f"{pid}/{sub_key}: claim docs (id={cid or 'none'})"
        elif pid == "claims" and sub_key == "attachments":
            widgets = sub_builder(reports, bundle, claim_id=cid)
            source_note = f"{pid}/{sub_key}: claim attachments (id={cid or 'none'})"
        elif pid == "taxes" and sub_key == "workpapers":
            widgets = sub_builder(
                reports,
                bundle,
                workpaper_widget=build_workpaper_widget,
                variance_widget=build_variance_alert_widget,
            )
            source_note = f"{pid}/{sub_key}: tax workpapers"
        else:
            widgets = sub_builder(reports, bundle)
            source_note = f"{pid}/{sub_key}: subpage pack"
    else:
        builder = _PAGE_BUILDERS[pid]
        widgets = builder(reports, bundle)
        source_note = f"{pid}: financial_reports + import_loader"

    if errors:
        source_note += f" (partial: {'; '.join(errors)})"

    # Phase U3 — reorder widgets by dashboard layout schema (parent page only)
    if not sub_key:
        try:
            from apex_dashboard_layout_pack import order_widget_specs

            widgets = order_widget_specs(widgets, page=pid)
            source_note += " +U3 layout"
        except Exception:
            pass

    # Free stage (hal-10623): no omit/partition/KPI-density/zero-scroll packing.
    # Builders emit the full widget list; client stacks them with natural height.
    cleaned: list[Any] = []
    for w in widgets if isinstance(widgets, list) else []:
        if not isinstance(w, dict):
            cleaned.append(w)
            continue
        item = dict(w)
        for key in ("band", "tileClass", "mosaicBand", "maxHeight", "zeroScroll"):
            item.pop(key, None)
        cleaned.append(item)
    widgets = cleaned
    source_note += " +free-stack-10623"

    page_label = f"{pid}/{sub_key}" if sub_key else pid
    payload = {
        "page": page_label,
        "parent": pid,
        "sub": sub_key,
        "claimId": cid,
        "refreshedAt": reports.get("generatedAt") or bundle.get("loadedAt") or _utc_now(),
        "buildId": BUILD_ID,
        "widgets": widgets,
        "mosaicLayout": None,
        "sourceNote": source_note,
        "errors": errors or None,
        "widgetCensus": summarize_widget_census(widgets),
        "cachedForSec": 0 if skip_cache else _WIDGETS_CACHE_TTL_SEC,
    }
    if not skip_cache:
        _WIDGETS_CACHE[cache_key] = {"at": time.monotonic(), "payload": copy.deepcopy(payload)}
    return payload


def _widget_has_data(w: dict[str, Any]) -> bool:
    """True when the instrument is showing import-backed content (not empty/awaiting)."""
    if not isinstance(w, dict):
        return False
    status = str(w.get("status") or "").lower()
    if status in {"empty", "awaiting-migration"}:
        return False
    wtype = str(w.get("type") or "")
    if wtype == "claim-shelf":
        tiles = w.get("tiles") if isinstance(w.get("tiles"), list) else []
        return bool(tiles)
    if wtype == "claims-kanban":
        columns = w.get("columns") if isinstance(w.get("columns"), dict) else {}
        return any(isinstance(v, list) and v for v in columns.values())
    if wtype == "claims-header-stats":
        stats = w.get("stats") if isinstance(w.get("stats"), list) else []
        return any(isinstance(s, dict) and s.get("value") is not None for s in stats)
    if wtype == "claims-risk-bars":
        bars = w.get("bars") if isinstance(w.get("bars"), list) else []
        return any(isinstance(b, dict) and int(b.get("value") or 0) > 0 for b in bars)
    if wtype in {"claims-executive-strip", "executive-strip"}:
        pills = w.get("pills") if isinstance(w.get("pills"), list) else []
        return any(isinstance(p, dict) and p.get("value") is not None and not p.get("empty") for p in pills)
    if wtype == "financial-command-strip":
        return bool(w.get("importMessage") or w.get("briefMessage") or w.get("periods"))
    if wtype == "revenue-composition":
        return bool(w.get("segments") or w.get("slices"))
    if wtype == "dual-axis-trend":
        return bool(w.get("production") or w.get("collections"))
    if wtype == "ebitda-station":
        return bool(w.get("steps"))
    if wtype == "kpi":
        return w.get("value") is not None and w.get("value") != ""
    if wtype in {"chart", "bar", "line"}:
        series = w.get("series") if isinstance(w.get("series"), list) else []
        values = w.get("values") if isinstance(w.get("values"), list) else []
        return bool(series or values)
    if wtype == "funnel":
        return bool(w.get("stages"))
    if wtype in {"donut", "stacked-bar", "horizontal-bar"}:
        return bool(w.get("slices") or w.get("bars") or w.get("segments"))
    if wtype == "waterfall":
        return bool(w.get("steps"))
    if wtype == "status":
        return status in {"ok", "warn"} or bool(w.get("message"))
    # Default: non-empty status counts as showing
    return status != "empty"


COLLECTIONS_PENDING_FIX = (
    "Fix: SoftDent data not in the DB for this Collections KPI — Sign On and use SoftDent UI "
    "to export daysheet / Register for a Period / Collections, then Sync imports "
    "(or ask HAL to refresh SoftDent period). Collections stay empty until reported — not $0."
)


def census_has_collections_pending(census: dict[str, Any] | None) -> bool:
    """True when Collections KPI is empty because SoftDent period is pending/missing."""
    if not isinstance(census, dict):
        return False
    empties = census.get("emptyWidgets") if isinstance(census.get("emptyWidgets"), list) else []
    for row in empties:
        if not isinstance(row, dict):
            continue
        wid = str(row.get("id") or "").strip().lower()
        label = str(row.get("label") or "").strip().lower()
        hint = str(row.get("hint") or "").strip().lower()
        if wid in {"hal-mosaic-coll", "sd-collections"} or label == "collections":
            if "pending" in hint or "missing" in hint:
                return True
    return False


def append_collections_pending_board_actions(actions: list[dict[str, Any]]) -> None:
    """Guide staff to SoftDent Collections KPI — honesty: never invent $."""
    actions.append(
        {
            "type": "set_status_banner",
            "message": "Collections pending: import SoftDent daysheet / Register for a Period, then Sync.",
            "hint": "Not $0 — production exists without reported collections for the latest period.",
            "tone": "warn",
        }
    )
    if not any(a.get("type") == "navigate" and a.get("page") == "softdent" for a in actions):
        actions.append({"type": "navigate", "page": "softdent"})
    actions.append({"type": "focus_widget", "widgetId": "sd-collections"})
    actions.append({"type": "highlight_widget", "widgetId": "sd-collections", "ms": 4500})


def summarize_widget_census(widgets: list[dict[str, Any]]) -> dict[str, Any]:
    populated: list[dict[str, str]] = []
    empty: list[dict[str, str]] = []
    for w in widgets:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("id") or "")
        wtype = str(w.get("type") or "").strip().lower()
        # Skip chat surfaces by type or id prefix (hal-ask is type=hal-chat).
        if not wid or wid.startswith("hal-chat") or wtype in {"hal-chat", "chat"}:
            continue
        label = str(w.get("label") or wid)
        hint = str(w.get("hint") or w.get("emptyMessage") or "")
        row = {"id": wid, "label": label, "hint": hint[:160]}
        if _widget_has_data(w):
            populated.append(row)
        else:
            empty.append(row)
    return {
        "total": len(populated) + len(empty),
        "withData": len(populated),
        "empty": len(empty),
        "populatedIds": [r["id"] for r in populated],
        "emptyIds": [r["id"] for r in empty],
        "emptyWidgets": empty[:12],
        "populatedWidgets": populated[:12],
    }


def build_page_widget_census(page_id: str) -> dict[str, Any]:
    payload = build_apex_widgets(page_id)
    census = payload.get("widgetCensus") if isinstance(payload.get("widgetCensus"), dict) else {}
    return {
        "ok": True,
        "page": payload.get("page"),
        "refreshedAt": payload.get("refreshedAt"),
        "sourceNote": payload.get("sourceNote"),
        "census": census,
        "buildId": BUILD_ID,
    }


def build_all_pages_widget_census() -> dict[str, Any]:
    """Census every Apex page — HAL program-wide widget data awareness."""
    pages: list[dict[str, Any]] = []
    total_with = 0
    total_empty = 0
    total_widgets = 0
    empty_highlights: list[str] = []
    for pid in APEX_PAGES:
        try:
            row = build_page_widget_census(pid)
        except Exception as exc:  # noqa: BLE001
            pages.append({"page": pid, "ok": False, "error": str(exc)})
            continue
        census = row.get("census") if isinstance(row.get("census"), dict) else {}
        with_data = int(census.get("withData") or 0)
        empty_n = int(census.get("empty") or 0)
        total = int(census.get("total") or (with_data + empty_n))
        total_with += with_data
        total_empty += empty_n
        total_widgets += total
        empties = census.get("emptyWidgets") if isinstance(census.get("emptyWidgets"), list) else []
        for e in empties[:3]:
            if isinstance(e, dict):
                empty_highlights.append(f"{pid}/{e.get('label') or e.get('id')}")
        pages.append(
            {
                "page": pid,
                "ok": True,
                "withData": with_data,
                "empty": empty_n,
                "total": total,
                "emptyIds": census.get("emptyIds") or [],
                "populatedIds": census.get("populatedIds") or [],
            }
        )
    return {
        "ok": True,
        "scope": "all-pages",
        "pages": pages,
        "totals": {
            "pages": len(APEX_PAGES),
            "widgets": total_widgets,
            "withData": total_with,
            "empty": total_empty,
        },
        "emptyHighlights": empty_highlights[:20],
        "pageList": list(APEX_PAGES),
        "buildId": BUILD_ID,
        "refreshedAt": _utc_now(),
    }


def format_all_pages_census_reply(payload: dict[str, Any]) -> str:
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    lines = [
        f"All Apex pages ({totals.get('pages') or len(APEX_PAGES)}): "
        f"{totals.get('withData', 0)}/{totals.get('widgets', 0)} widgets showing data; "
        f"{totals.get('empty', 0)} empty."
    ]
    page_bits = []
    for row in payload.get("pages") or []:
        if not isinstance(row, dict) or not row.get("ok"):
            continue
        empty_n = int(row.get("empty") or 0)
        if empty_n:
            page_bits.append(f"{row.get('page')}: {row.get('withData')}/{row.get('total')} ok · {empty_n} empty")
    if page_bits:
        lines.append("Pages with gaps: " + " · ".join(page_bits[:8]))
    highlights = payload.get("emptyHighlights") if isinstance(payload.get("emptyHighlights"), list) else []
    if highlights:
        lines.append("Examples empty: " + " · ".join(str(h) for h in highlights[:10]))
    lines.append(
        "Pages I know: " + ", ".join(APEX_PAGES) + ". Ask about a page (e.g. which widgets are empty on taxes) or Sync imports."
    )
    return " ".join(lines)


def format_page_inventory_reply(page_id: str) -> str:
    """List widgets on a page with data/empty status — HAL page map."""
    row = build_page_widget_census(page_id)
    census = row.get("census") if isinstance(row.get("census"), dict) else {}
    pid = str(row.get("page") or page_id)
    populated = census.get("populatedWidgets") if isinstance(census.get("populatedWidgets"), list) else []
    empties = census.get("emptyWidgets") if isinstance(census.get("emptyWidgets"), list) else []
    lines = [
        f"Page `{pid}` inventory: {census.get('withData', 0)} with data, {census.get('empty', 0)} empty "
        f"(of {census.get('total', 0)})."
    ]
    if populated:
        lines.append("Showing: " + ", ".join(str(p.get("label") or p.get("id")) for p in populated[:10] if isinstance(p, dict)))
    if empties:
        lines.append(
            "Empty: "
            + " · ".join(
                f"{e.get('label') or e.get('id')}" + (f" ({str(e.get('hint') or '')[:60]})" if e.get("hint") else "")
                for e in empties[:8]
                if isinstance(e, dict)
            )
        )
    return " ".join(lines)


def build_export_playbook() -> dict[str, Any]:
    """When/how to obtain SoftDent + QuickBooks exports for NR2 — HAL guidance only."""
    return {
        "when": [
            "After SoftDent day-close / daysheet is final (production + collections).",
            "After posting QuickBooks entries for the period you want on Taxes/EBITDA.",
            "When widgets show empty/stale, or HAL reports missing Age/Days on claims.",
            "At least daily for SoftDent operational pages; weekly (or after books close) for QuickBooks P&L.",
        ],
        "howSoftDent": [
            "TEACHING: Desktop SoftDent report pull — Launch CS SoftDent Software.lnk (-sus) → Sign On "
            "COMPUTE/computer → Reports → <report> → Output Options → click Excel then Enter "
            "(or Print Preview then Enter) — NEVER Printer. Setup dates / doctor 999 → OK. "
            r"Save Excel into C:\SoftDentReportExports (temp SDWIN*.csv → SaveCopyAs). "
            "Preview: last page for totals. Then NR2 SoftDent → Sync. "
            "Ask HAL: how do I pull SoftDent reports? (policy softdent-report-pull).",
            "Phase-1 menus: Accounting→Registers/Period; Practice Management→Collection Reports→Summary; "
            "Accounting→Trans for a Period (Format 1 for line txs); Accounting→Daysheet; "
            "Accounting→Account Aging. Automation: "
            "python scripts\\run_softdent_money_widget_pull.py --reports register,daysheet,aging,collections",
            "Preferred for ops detail when DB has rows: Direct-First / ODBC lane (Sensei DataSync or SoftDent ODBC).",
            "Doctrine: SoftDent data that cannot be reached by the database requires SoftDent Sign On "
            "(SOFTDENT_SIGNON_* env vars) + SoftDent UI report export — no invented dollars, no SoftDent write-back.",
            "SoftDent GUI Sign On: SOFTDENT_SIGNON_USER / SOFTDENT_SIGNON_PASSWORD "
            r"(aliases SOFTDENT_GUI_USER / SOFTDENT_GUI_PASSWORD; also C:\New folder\.env). "
            "HAL never prints the password.",
            "File path: SoftDent Excel/CSV into C:\\SoftDentReportExports then Sync into "
            "app_data/nr2/document_inbox/softdent/ (or configured SoftDent import dir).",
            "Claims aging shelves need ClaimId, PatientName, ServiceDate, and Age/Days (or DOS so age can be computed).",
            "Then tell HAL: Sync imports and populate the widgets — or click Apex Sync.",
        ],
        "howQuickBooks": [
            "Export Profit & Loss and expense/category detail (CSV or IIF) for the S-corp books period.",
            "Place files in app_data/nr2/document_inbox/quickbooks/ (or configured QB import dir).",
            "Taxes/EBITDA need QB net income + expense categories (depreciation/interest when present).",
            "Then Sync imports — HAL never invents QB dollars into Book KPIs.",
        ],
        "halCommands": [
            "Sync imports and populate the widgets",
            "Verify SoftDent and QuickBooks import status",
            "Which widgets are empty on this page?",
            "How do I get SoftDent exports?",
            "How do I pull SoftDent reports?",
            "Teach me SoftDent Output Options Excel",
            "How do I get SoftDent data not in the database?",
            "How do I get QuickBooks exports?",
            "How does SoftDent Sign On work?",
            "Where is the SoftDent Sign On password?",
        ],
        "honesty": (
            "Prefer SoftDent DB/ODBC when available. "
            "Data that cannot be reached by the database requires Sign On + SoftDent UI export only. "
            "SoftDent Sign On user/password live in env vars (SOFTDENT_SIGNON_*); "
            "HAL/refresh may use them for GUI Sign On assist only. "
            "HAL never invents dollars and never writes SoftDent clinical/financial data."
        ),
    }


def format_census_reply(page: str, census: dict[str, Any]) -> str:
    with_data = int(census.get("withData") or 0)
    empty_n = int(census.get("empty") or 0)
    total = int(census.get("total") or (with_data + empty_n))
    lines = [f"Page `{page}`: {with_data}/{total} widgets showing import-backed data; {empty_n} empty."]
    empties = census.get("emptyWidgets") if isinstance(census.get("emptyWidgets"), list) else []
    if empties:
        bits = []
        for row in empties[:8]:
            if not isinstance(row, dict):
                continue
            label = row.get("label") or row.get("id")
            hint = str(row.get("hint") or "").strip()
            bits.append(f"{label}" + (f" — {hint}" if hint else ""))
        lines.append("Empty: " + " · ".join(bits))
        if census_has_collections_pending(census):
            lines.append(COLLECTIONS_PENDING_FIX)
        else:
            lines.append(
                "Fix: place SoftDent/QB exports in the inbox (or refresh ODBC), then Sync imports. "
                "Ask: how do I get SoftDent/QuickBooks exports?"
            )
    else:
        lines.append("All listed instruments on this page currently show data from the import cache.")
    return " ".join(lines)


def format_learn_priorities_reply(*, empty_highlights: list[str] | None = None) -> str:
    """Staff-assistant answer: what to teach HAL (not a generic 'no preferences' disclaimer)."""
    lines = [
        "Operational learning priorities for New Ridge (not hobbies) — two lanes:",
        "A) STAFF MEMORY (Remember this: … → learned_memories.jsonl; no PHI/secrets): "
        "payer-specific denial reason codes and appeal narratives (Sun Life composites, MetLife downgrades, etc.); "
        "carrier workflow quirks (prior-auth steps, DentaQuest/Medicaid forms, surface notation); "
        "clearinghouse/SoftDent error → rejection mappings; internal billing exceptions "
        "(write-off thresholds, discount agreements, payment-plan rules); concise appeal templates that worked.",
        "B) IMPORT DATA (not memory — dollars stay in analytics): SoftDent Insurance Payment Analysis CSV → "
        r"C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv (+ optional procedure_codes_YYYYMMDD.csv), "
        "then Sync so HAL can answer InsCo × ADA paid-after-write-off estimates for treatment planning "
        "(e.g. How much will Delta Dental typically pay for D0274?).",
        "Governed layer: docs/hal_knowledge/memories.jsonl (maintainer-approved). "
        "Worksheet: docs/hal_knowledge/NEW_RIDGE_OPERATING_RULES_WORKSHEET.md + scripts/seed_practice_learned_memories.py.",
        "Ask: Treatment planning data status · which widgets are empty on all pages?",
    ]
    try:
        from softdent_treatment_planning import treatment_planning_status

        st = treatment_planning_status()
        lines.append(
            f"Live tx-planning ingest: {st.get('paymentLines', 0)} payment lines, "
            f"{st.get('estimatesWithMinSample', 0)} InsCo×ADA estimates with n>=10 "
            f"(of {st.get('estimates', 0)} total)."
        )
    except Exception:  # noqa: BLE001
        pass
    if empty_highlights:
        lines.append("Current empty widget examples: " + " · ".join(str(h) for h in empty_highlights[:8]) + ".")
    return " ".join(lines)


def format_export_playbook_reply(topic: str = "both") -> str:
    book = build_export_playbook()
    parts = [
        "WHEN: " + " ".join(str(x) for x in book["when"][:3]),
    ]
    t = (topic or "both").lower()
    if t in {"softdent", "both", "sd"}:
        parts.append("SOFTDENT: " + " ".join(str(x) for x in book["howSoftDent"]))
    if t in {"quickbooks", "qb", "both"}:
        parts.append("QUICKBOOKS: " + " ".join(str(x) for x in book["howQuickBooks"]))
    parts.append(str(book["honesty"]))
    parts.append("Commands: " + " · ".join(str(x) for x in book["halCommands"][:4]))
    return " ".join(parts)


def refresh_softdent_period_imports() -> dict[str, Any]:
    """Promote SoftDentReportExports period files → analytics DB → dashboard (no invented $)."""
    import subprocess
    import sys
    from pathlib import Path as _Path

    result: dict[str, Any] = {
        "ok": False,
        "buildId": BUILD_ID,
        "startedAt": _utc_now(),
        "steps": [],
    }
    # 0) SoftDent GUI Sign On credentials status + optional UI assist (no password in payload)
    try:
        from softdent_signon import ensure_softdent_signed_on, softdent_signon_status

        sign_status = softdent_signon_status()
        sign_assist = ensure_softdent_signed_on(timeout_s=20.0, force_change_login=False)
        result["steps"].append(
            {
                "step": "softdent_signon",
                "ok": bool(sign_status.get("ok")),
                "user": sign_status.get("user"),
                "passwordConfigured": bool(sign_status.get("passwordConfigured")),
                "signedOn": bool(sign_assist.get("signedOn")),
                "assistOk": bool(sign_assist.get("ok")),
                "assistSteps": sign_assist.get("steps"),
                "error": sign_assist.get("error") or sign_status.get("hint"),
            }
        )
        result["softdentSignOn"] = {
            "user": sign_status.get("user"),
            "passwordConfigured": bool(sign_status.get("passwordConfigured")),
            "signedOn": bool(sign_assist.get("signedOn")),
        }
    except Exception as exc:  # noqa: BLE001
        result["steps"].append({"step": "softdent_signon", "ok": False, "error": str(exc)})

    # 1) Period export automation (promote Register/Trans if present)
    auto_ps1 = _Path(r"C:\New folder\ops\softdent\automation\run_softdent_export_automation.ps1")
    auto_py = _Path(r"C:\New folder\ops\softdent\periods\softdent_period_export_automation.py")
    try:
        if auto_ps1.is_file():
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(auto_ps1),
                ],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            result["steps"].append(
                {
                    "step": "period_automation_ps1",
                    "ok": proc.returncode == 0,
                    "exitCode": proc.returncode,
                    "tail": (proc.stdout or proc.stderr or "")[-500:],
                }
            )
        elif auto_py.is_file():
            proc = subprocess.run(
                [sys.executable, str(auto_py)],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            result["steps"].append(
                {
                    "step": "period_automation_py",
                    "ok": proc.returncode == 0,
                    "exitCode": proc.returncode,
                    "tail": (proc.stdout or proc.stderr or "")[-500:],
                }
            )
        else:
            result["steps"].append({"step": "period_automation", "ok": False, "error": "automation script not found"})
    except Exception as exc:  # noqa: BLE001
        result["steps"].append({"step": "period_automation", "ok": False, "error": str(exc)})

    # 2) DEF-001 inbox period stub ingest + dashboard sync (force when unprocessed exports present)
    force_reimport = False
    try:
        from apex_softdent_hardening_pack import scan_collections_export_inbox

        pre_inbox = scan_collections_export_inbox()
        force_reimport = bool(pre_inbox.get("matchCount"))
        result["steps"].append(
            {
                "step": "inbox_preflight",
                "ok": True,
                "matchCount": pre_inbox.get("matchCount"),
                "forceReimport": force_reimport,
                "matches": (pre_inbox.get("matches") or [])[:6],
            }
        )
        result["exportInbox"] = pre_inbox
    except Exception as exc:  # noqa: BLE001
        result["steps"].append({"step": "inbox_preflight", "ok": False, "error": str(exc)})

    try:
        from softdent_dashboard_period_sync import ingest_daysheet_to_period, sync_dashboard_period_rows

        ingest = ingest_daysheet_to_period(force_reimport=force_reimport)
        result["steps"].append(
            {
                "step": "inbox_period_ingest",
                "ok": bool(ingest.get("ok")),
                "detail": {
                    "created": ingest.get("created"),
                    "updated": ingest.get("updated"),
                    "summaries": ingest.get("summaries"),
                    "forceReimport": force_reimport,
                },
            }
        )
        dash = sync_dashboard_period_rows(force_reimport=force_reimport)
        result["steps"].append(
            {
                "step": "dashboard_period_sync",
                "ok": bool(dash.get("ok")),
                "detail": {
                    "periods": dash.get("periods"),
                    "rowCount": dash.get("rowCount"),
                    "mergeLog": dash.get("mergeLog"),
                    "forceReimport": force_reimport,
                    "inboxIngest": dash.get("inboxIngest"),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        result["steps"].append({"step": "dashboard_period_sync", "ok": False, "error": str(exc)})

    # 3) Practice exports (operatory date filter)
    try:
        from softdent_practice_exports import sync_practice_exports

        op = sync_practice_exports()
        result["steps"].append({"step": "practice_exports", "ok": bool(op.get("ok")), "written": op.get("written")})
    except Exception as exc:  # noqa: BLE001
        result["steps"].append({"step": "practice_exports", "ok": False, "error": str(exc)})

    # 4) DEF-001 — scan SoftDent export inbox for Collections/Daysheet files (presence only)
    try:
        from apex_softdent_hardening_pack import scan_collections_export_inbox

        inbox = scan_collections_export_inbox()
        result["steps"].append(
            {
                "step": "collections_export_inbox",
                "ok": True,
                "matchCount": inbox.get("matchCount"),
                "hasCollectionsLikeFile": inbox.get("hasCollectionsLikeFile"),
                "hasDaysheetLikeFile": inbox.get("hasDaysheetLikeFile"),
                "matches": (inbox.get("matches") or [])[:6],
                "hint": inbox.get("hint"),
            }
        )
        result["exportInbox"] = inbox
    except Exception as exc:  # noqa: BLE001
        result["steps"].append({"step": "collections_export_inbox", "ok": False, "error": str(exc)})

    # 5) Status snapshot
    try:
        status_path = _Path(r"C:\SoftDentFinancialExports\softdent_period_export_automation_status.json")
        if status_path.is_file():
            result["periodStatus"] = json.loads(status_path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass

    result["ok"] = any(bool(s.get("ok")) for s in result["steps"])
    result["completedAt"] = _utc_now()
    inbox = result.get("exportInbox") if isinstance(result.get("exportInbox"), dict) else {}
    try:
        from apex_softdent_hardening_pack import assess_collections_gap, FORMAT_HINT

        _reports, bundle, _err = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        result["collectionsGap"] = {
            "gapCode": gap.get("gapCode"),
            "collectionsGapCode": gap.get("collectionsGapCode"),
            "period": gap.get("period"),
            "healthy": gap.get("healthy"),
            "coversOpenMonth": (gap.get("exportInbox") or {}).get("coversOpenMonth"),
            "classifiedPeriods": (gap.get("exportInbox") or {}).get("classifiedPeriods"),
        }
        if gap.get("collectionsFormatRequired") or gap.get("gapCode") == "COLLECTIONS_FORMAT_REQUIRED":
            result["nextStep"] = FORMAT_HINT
        elif gap.get("collectionsPending"):
            result["nextStep"] = (
                f"DEF-001: period {gap.get('period') or 'open'} still collectionsPending. "
                "SoftDent → Reports → Accounting → Register for a Period (open month start → today) "
                r"or Collections/Daysheet with Ins/Patient split → C:\SoftDentReportExports → Sync. "
                "DaySheet presence alone is not enough. Empty ≠ $0."
            )
        elif inbox.get("matchCount"):
            result["nextStep"] = (
                "Matching Collections/Daysheet/Register file(s) found in export inbox. "
                "If revenue-composition is still empty, Sync imports again or re-run Refresh SoftDent period. "
                "Honesty: empty ≠ $0 — do not invent insurance/patient dollars."
            )
        else:
            result["nextStep"] = (
                "DEF-001: SoftDent → Reports → Accounting → Collections or Daysheet "
                "(or Register for a Period for the open month) → export CSV to "
                r"C:\SoftDentReportExports, then Sync / Refresh SoftDent period. "
                "Empty revenue-composition is not $0."
            )
    except Exception:
        if inbox.get("matchCount"):
            result["nextStep"] = (
                "Matching Collections/Daysheet/Register file(s) found in export inbox. "
                "If revenue-composition is still empty, Sync imports again or re-run Refresh SoftDent period. "
                "Honesty: empty ≠ $0 — do not invent insurance/patient dollars."
            )
        else:
            result["nextStep"] = (
                "DEF-001: SoftDent → Reports → Accounting → Collections or Daysheet "
                "(or Register for a Period for the open month) → export CSV to "
                r"C:\SoftDentReportExports, then Sync / Refresh SoftDent period. "
                "Empty revenue-composition is not $0."
            )
    return result


def _build_hal_status_payload() -> dict[str, Any]:
    """HAL operational state + grounded suggestion (no invented dollars).

    Moonshot Expert SE Phase 1: always report system/HAL availability separately from
    import freshness. When imports are degraded, label is
    ``HAL Ready · Import Degraded`` — never a false Standby from the import gate.
    """
    suggestion = HAL_STATUS_SUGGESTION
    status = "ready"
    status_label = "HAL Ready"
    confidence = None
    extras: dict[str, Any] = {}
    readiness: dict[str, Any] | None = None
    try:
        from import_diagnostics import assess_import_readiness

        readiness = assess_import_readiness(sync_state=None)
    except Exception as exc:  # noqa: BLE001
        readiness = {"ok": False, "level": "unknown", "error": str(exc)}

    import_level = str((readiness or {}).get("level") or "unknown")
    import_degraded = import_level not in ("fresh",)

    try:
        reports, bundle, errors = _load_reports_and_bundle()
        diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
        summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
        missing = summary.get("missing")
        connected = summary.get("connected")
        total = summary.get("total")

        claims = _claims_summary_from_bundle(bundle)
        ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
        ct = reports.get("claimTracking") if isinstance(reports.get("claimTracking"), dict) else {}

        candidates: list[tuple[str, float]] = []
        if isinstance(missing, int) and missing > 0:
            candidates.append(
                (f"Review {missing} missing import dataset(s) before trusting empty KPIs.", 0.9)
            )
        denied = claims.get("deniedCount")
        if isinstance(denied, int) and denied > 0:
            candidates.append((f"Review {denied} denied claim(s) for resubmit or appeal.", 0.88))
        open_claims = claims.get("openCount")
        aging = claims.get("agingPast30")
        if isinstance(aging, int) and aging > 0:
            candidates.append((f"{aging} claim(s) aging past 30 days — prioritize follow-up.", 0.86))
        elif isinstance(open_claims, int) and open_claims > 0:
            candidates.append((f"{open_claims} open claim(s) on SoftDent import — check status.", 0.8))
        if ar.get("followUpHint"):
            candidates.append((str(ar["followUpHint"]), 0.82))
        if ct.get("followUpHint"):
            candidates.append((str(ct["followUpHint"]), 0.8))
        if not candidates and isinstance(connected, int) and isinstance(total, int) and total > 0:
            candidates.append(
                (f"Imports healthy ({connected}/{total}). Ask HAL about production or A/R.", 0.7)
            )

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            suggestion, confidence = candidates[0]

        extras = {
            "importConnected": connected,
            "importTotal": total,
            "importMissing": missing,
            "claimsOpen": open_claims if isinstance(open_claims, int) else None,
            "claimsDenied": denied if isinstance(denied, int) else None,
        }
        if errors:
            extras["loadNotes"] = errors[:3]
    except Exception as exc:  # noqa: BLE001
        extras["error"] = str(exc)
        suggestion = HAL_STATUS_SUGGESTION

    # System/HAL availability vs import honesty (Moonshot REC-001 / path B+C).
    if import_degraded:
        status = "degraded"
        status_label = "HAL Ready · Import Degraded"
        if not suggestion or suggestion == HAL_STATUS_SUGGESTION:
            suggestion = (
                "HAL is online. Import data is not fresh — refresh SoftDent/QuickBooks "
                "before trusting financial KPIs or posting."
            )
    else:
        status = "ready"
        status_label = "HAL Ready"

    # Compact readiness for UI (no PHI / no invented dollars).
    readiness_public: dict[str, Any] | None = None
    if isinstance(readiness, dict):
        readiness_public = {
            "ok": bool(readiness.get("ok")),
            "level": import_level,
            "codes": readiness.get("codes"),
            "error": readiness.get("error"),
            "completeness": readiness.get("completeness"),
            "summary": readiness.get("summary"),
        }

    softdent_signon: dict[str, Any] | None = None
    try:
        from softdent_signon import softdent_signon_status

        st = softdent_signon_status()
        softdent_signon = {
            "ok": bool(st.get("ok")),
            "user": st.get("user"),
            "passwordConfigured": bool(st.get("passwordConfigured")),
            "envUserKey": st.get("envUserKey"),
            "envPasswordKey": st.get("envPasswordKey"),
            "knowledge": st.get("knowledge"),
            "dataAccessDoctrine": st.get("dataAccessDoctrine"),
            "masterReports": st.get("masterReports"),
        }
    except Exception:
        softdent_signon = None

    return {
        "status": status,
        "statusLabel": status_label,
        "suggestion": suggestion,
        "confidence": confidence,
        "buildId": BUILD_ID,
        "refreshedAt": _utc_now(),
        "metrics": extras or None,
        "readiness": readiness_public,
        "importDegraded": import_degraded,
        "orchestrator": _orchestrator_status_safe(),
        "softdentSignOn": softdent_signon,
    }


def _orchestrator_status_safe() -> dict[str, Any]:
    try:
        from apex_orchestrator_pack import orchestrator_status

        return orchestrator_status()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "enabled": False, "error": str(exc), "phase": "I0"}


def _print_packet_html(page: str, widget_ids: list[Any], job_id: str) -> str:
    ids = ", ".join(str(w) for w in widget_ids) if widget_ids else "(all visible)"
    safe_page = str(page or "view")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>NR2 Apex Print — {safe_page}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 24px; color: #111; }}
  h1 {{ font-size: 18px; margin: 0 0 8px; }}
  .meta {{ color: #555; font-size: 12px; margin-bottom: 16px; }}
  .note {{ border: 1px solid #ccc; padding: 12px; border-radius: 4px; font-size: 13px; }}
  @media print {{ button {{ display: none; }} }}
</style></head><body>
  <h1>NewRidgeFinancial 2.0 — Apex print packet</h1>
  <div class="meta">Job {job_id} · Page: {safe_page} · Widgets: {ids} · Build {BUILD_ID}</div>
  <div class="note">Use the browser Print dialog for the live Apex view (File → Print or Ctrl+P).
  This packet records the print request for audit. Dollar amounts are only those already shown on screen — never invented.</div>
  <p><button type="button" onclick="window.print()">Print</button>
  <button type="button" onclick="window.close()">Close</button></p>
  <script>window.addEventListener('load', function() {{ setTimeout(function() {{ window.print(); }}, 250); }});</script>
</body></html>"""


def apex_print_job(packet_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    job_id = f"prt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
    page = body.get("page")
    widgets = body.get("widgets") or []
    html = _print_packet_html(str(page or ""), widgets if isinstance(widgets, list) else [], job_id)
    _PRINT_PACKETS[job_id] = {
        "html": html,
        "createdAt": _utc_now(),
        "page": page,
        "widgets": widgets,
        "packetType": str(packet_type or "view"),
    }
    # Bound memory
    if len(_PRINT_PACKETS) > 40:
        for old in list(_PRINT_PACKETS.keys())[:20]:
            _PRINT_PACKETS.pop(old, None)
    return {
        "ok": True,
        "jobId": job_id,
        "status": "ready",
        "packetType": str(packet_type or "view"),
        "page": page,
        "widgets": widgets,
        "format": body.get("format") or "browser",
        "estimatedReady": "immediate",
        "url": f"/api/apex/print/packet/{job_id}",
        "note": "Open url for print packet, or use window.print on the live Apex view.",
        "createdAt": _utc_now(),
    }


def parse_voice_report_command(query: str) -> dict[str, Any] | None:
    """
    Parse voice commands for reports (Moonshot HAL voice+report consult).
    Returns: {"tool": "clock_out_shift"|"readiness_diagnostics"|"daily_ops_briefing", "speak": True}
    """
    q = str(query or "").strip().lower()
    if not q:
        return None
    # Avoid collision with existing parsers
    if re.search(r"\b(salary|ebitda|depreciat|scrubber|narrat|dictat)\b", q):
        return None

    if re.search(r"\b(handoff|shift report|end of shift|clock out)\b", q):
        return {"tool": "clock_out_shift", "speak": True, "intent": "handoff"}
    if re.search(r"\b(readiness|system check|health check|smoke test)\b", q):
        return {"tool": "readiness_diagnostics", "speak": True, "intent": "readiness"}
    if re.search(r"\b(briefing|morning brief|daily ops|status update)\b", q):
        return {"tool": "daily_ops_briefing", "speak": True, "intent": "briefing"}
    return None


def resolve_hal_board_actions(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Deterministic HAL → board control.
    Safe actions only: sync imports, refresh mosaic, navigate, focus/highlight widgets,
    surface import-backed hints. NEVER invents or writes dollar amounts into KPIs.
    """
    body = payload if isinstance(payload, dict) else {}
    query = str(body.get("query") or body.get("text") or "").strip()
    page = re.sub(r"[^a-z0-9\-]", "", str(body.get("page") or "financial").lower())
    q = query.lower()
    actions: list[dict[str, Any]] = []
    notes: list[str] = []
    handled = False
    ctx = body.get("context") if isinstance(body.get("context"), dict) else {}
    ctx_widget = str(ctx.get("widgetId") or ctx.get("id") or "").strip()

    # --- Ask-HAL on a specific widget (consult §4) — focus/highlight only, then chat may continue ---
    if ctx_widget and re.search(r"\b(explain this widget|explain (the )?widget|what is this widget)\b", q):
        actions.append({"type": "focus_widget", "widgetId": ctx_widget})
        actions.append({"type": "highlight_widget", "widgetId": ctx_widget, "ms": 4000})
        denial_codes = ctx.get("denialCodes") if isinstance(ctx.get("denialCodes"), list) else []
        patient_hash = ctx.get("patientHash") if isinstance(ctx.get("patientHash"), list) else []
        if denial_codes:
            notes.append(
                "Denial codes in view (import-backed): "
                + ", ".join(str(c) for c in denial_codes[:8])
                + ". Summarize top denial impact only from these codes — never invent dollars."
            )
        elif patient_hash:
            notes.append(
                "Anonymized patient hashes in view: "
                + ", ".join(str(h) for h in patient_hash[:8])
                + ". Refer by hash/initials only — no PHI expansion."
            )
        else:
            notes.append(f"Focusing widget `{ctx_widget}` for explanation (import-backed display only).")
        handled = True

    # Advisory / ethics questions must reach chat — do not hijack on topic keywords
    # like "categorize", "import health", or "ebitda" embedded in a longer ask.
    advisory_chat = bool(
        re.search(
            r"\b("
            r"prioritize|ranked|action list|what should (i|we|front desk|staff)|"
            r"how (do|should|can) (i|we)|why (is|are|do|does)|explain|"
            r"compare|draft|outline|advise|recommend|give (me )?(a )?(ranked|priority)|"
            r"if i ask|invent|fabricate|make up|look better|what (exact|do you) do|"
            r"refuse|should you|would you"
            r")\b",
            q,
        )
    ) or (len(q.split()) >= 12 and "?" in query)
    explicit_board = bool(
        re.search(
            r"\b("
            r"focus|highlight|point (me )?to|look at|open widget|"
            r"show me (the )?(widget|scrubber|board|kanban|table|categorize|ebitda)|"
            r"open (the )?(categorize|ebitda|claims workbench|import health|program posture|ai insight)|"
            r"go to|switch to|take me to|navigate"
            r")\b",
            q,
        )
    )
    allow_topic_focus = explicit_board or not advisory_chat

    # --- Ethics: never invent dollars / write-offs (deterministic refusal) ---
    if re.search(
        r"\b(invent|fabricate|fake|make up)\b.{0,80}\b(write-?off|\$|dollar|ebitda|revenue|collections|kpi)\b",
        q,
    ) or re.search(
        r"\b(write-?off|ebitda).{0,60}\b(invent|fake|fabricate|look better|make .{0,20} better)\b",
        q,
    ):
        notes.append(
            "I will not invent write-offs or dollar amounts to make EBITDA (or any KPI) look better. "
            "Books stay import-backed; staff posts real adjustments in SoftDent/QuickBooks with approval."
        )
        handled = True

    # --- Sync / populate from imports ---
    if re.search(
        r"\b(sync|refresh imports|reload imports|pull (softdent|quickbooks|qb)|update (the )?board|populate (the )?(widgets|board)|refill widgets)\b",
        q,
    ):
        actions.append({"type": "sync_imports", "fullSync": True})
        actions.append({"type": "refresh_page"})
        notes.append("Syncing SoftDent/QuickBooks imports and refreshing the mosaic from import data.")
        handled = True

    # --- SoftDent period Register/Daysheet promote (after operator drops files) ---
    if re.search(
        r"\b(refresh softdent period|refresh period imports|promote (softdent )?register|import (july )?register|softdent period refresh)\b",
        q,
    ):
        actions.append({"type": "refresh_softdent_period"})
        actions.append({"type": "refresh_page"})
        actions.append({"type": "navigate", "page": "taxes"})
        actions.append({"type": "focus_widget", "widgetId": "c0-import-guidance"})
        notes.append(
            "Refreshing SoftDent period imports from C:\\SoftDentReportExports (Register/Daysheet promote). "
            "If the open month is still pending production/collections, export Register for a Period once. "
            "Do not re-export Register hoping Ins Plan Collections > 0 when SoftDent already printed $0 — "
            "use ERA-835 for insurance detail."
        )
        handled = True

    # --- Refresh widgets only (no file sync) ---
    if re.search(r"\b(refresh (the )?(widgets|page|mosaic|board)|reload (the )?(page|widgets))\b", q) and not any(
        a.get("type") == "sync_imports" for a in actions
    ):
        actions.append({"type": "refresh_page"})
        notes.append("Refreshing widgets from the current import cache (no new file sync).")
        handled = True

    # --- Phase 3: targeted refresh_widget (consult optional enhancement) ---
    if re.search(r"\b(refresh (this |the )?(widget|instrument)|reload (this |the )?widget)\b", q):
        wid = ctx_widget or ""
        if not wid:
            # try focus_rules match for named widget in same utterance
            for pat, rule_wid, _pg in (
                (r"\bexpense treemap\b", "expense-treemap", None),
                (r"\bdenial pareto\b", "denial-pareto", None),
                (r"\bunapplied\b", "unapplied-credit-float", None),
                (r"\brecall gauge\b", "recall-gauge", None),
                (r"\bcash (flow )?bridge\b", "cash-flow-bridge", None),
            ):
                if re.search(pat, q):
                    wid = rule_wid
                    break
        if wid:
            actions.append({"type": "refresh_widget", "widgetId": wid})
            notes.append(f"Refreshing widget `{wid}` from import cache.")
            handled = True

    # --- Navigate to a page ---
    page_map = {
        "financial": r"\b(financial|finance|dashboard)\b",
        "taxes": r"\b(tax|taxes|kansas|federal tax|s-?corp tax)\b",
        "softdent": r"\bsoftdent\b",
        "quickbooks": r"\b(quickbooks|quick books|\bqb\b)\b",
        "ar": r"\b(a/?r|accounts receivable|aging)\b",
        "claims": r"\bclaims?\b",
        "narratives": r"\bnarratives?\b",
        "documents": r"\b(documents?|tax returns? library)\b",
        "library": r"\blibrary\b",
        "office-manager": r"\b(office.?mgr|office.?manager)\b",
        "hal": r"\b(hal page|open hal)\b",
    }
    nav_target = None
    # Prefer explicit "go to / open / show <page>"
    if re.search(r"\b(go to|open|show|switch to|take me to)\b", q):
        # QB AP aging must not route to SoftDent A/R (bare "aging" trap)
        if re.search(r"\b(ap aging|accounts payable|unpaid bills|qb[- ]?ap)\b", q):
            nav_target = "quickbooks"
            if nav_target != page:
                actions.append({"type": "navigate", "page": nav_target})
                notes.append(f"Opening the {nav_target} page.")
                page = nav_target
            actions.append({"type": "focus_widget", "widgetId": "qb-ap-aging"})
            actions.append({"type": "highlight_widget", "widgetId": "qb-ap-aging", "ms": 4500})
            notes.append("Focusing widget `qb-ap-aging` (import-backed display only).")
            handled = True
        else:
            for pid, pat in page_map.items():
                if re.search(pat, q):
                    nav_target = pid
                    break
            if nav_target and nav_target != page:
                actions.append({"type": "navigate", "page": nav_target})
                notes.append(f"Opening the {nav_target} page.")
                handled = True
                page = nav_target

    # --- Focus / highlight specific instruments ---
    focus_rules = (
        (r"\bebitda scrubber|ebitda slider|planning ebitda\b", "ebitda-scrubber", "taxes"),
        (r"\bebitda station|ebitda command\b", "ebitda-station", "financial"),
        (r"\bebitda\b", "ebitda-station", "financial"),
        (r"\b(provider production|production by provider)\b", "provider-hbar", "financial"),
        (r"\b(payer mix|insurance vs patient|revenue composition)\b", "revenue-composition", "financial"),
        (r"\b(collection efficiency|collections? ratio)\b", "financial-vital-signs", "financial"),
        (r"\b(a/?r (aging )?flow|aging waterfall|collectible)\b", "ar-waterfall", "ar"),
        (r"\b(categorize|categoris|expense categor)\b", "hal-categorize-assist", "quickbooks"),
        (r"\b(tax (returns? )?library|upload (tax )?return)\b", "tax-returns-library", "documents"),
        (r"\b(book.?to.?tax|tax bridge)\b", "tax-bridge-waterfall", "taxes"),
        (r"\b(import (sync )?verify|import status|import readiness|financial command)\b", "financial-command-strip", "financial"),
        (r"\b(morning (financial )?brief|financial brief)\b", "financial-command-strip", "financial"),
        (r"\b(vital signs|financial vitals)\b", "financial-vital-signs", "financial"),
        (r"\b(liquidity|collections pulse|production pulse|dual.?axis|production (and|&) collections)\b", "financial-dual-trend", "financial"),
        (r"\bfederal tax\b", "tax-federal-est", "taxes"),
        (r"\bkansas tax\b", "tax-kansas-est", "taxes"),
        (r"\b(scenario manager|saved scenarios|tax scenarios)\b", "cpa-scenarios", "taxes"),
        (r"\b(filing workflow|filing state|tax filing)\b", "cpa-filing", "taxes"),
        (r"\b(workpaper|cpa workpaper)\b", "cpa-workpaper", "taxes"),
        (r"\b(import variance|variance watch|period swing)\b", "import-variance", "taxes"),
        (r"\b(c0|import remediation|import guidance)\b", "c0-import-guidance", "taxes"),
        (r"\b(a/?r outlook|aging outlook|predictive a/?r|ar forecast)\b", "ar-aging-outlook", "ar"),
        (r"\b(30[- ]?day claims?|claims? (aged )?30)\b", "claims-aging-30", "claims"),
        (r"\b(60[- ]?day claims?|claims? (aged )?60)\b", "claims-aging-60", "claims"),
        (r"\b(90[- ]?day claims?|claims? (aged )?90|aging over 90)\b", "claims-aging-90", "claims"),
        (r"\b(claims? aging|aging (tiles|shelves|claims|exposure|matrix))\b", "claims-aging-exposure", "claims"),
        (r"\b(claims? (workbench|kanban|table)|kanban board|status (board|columns))\b", "claims-kanban-board", "claims"),
        (r"\b(critical actions?|action queue)\b", "claims-critical-actions", "claims"),
        (r"\b(executive strip|claims? (kpi|command) strip)\b", "claims-executive-strip", "claims"),
        (r"\b(aging risk|risk (bars|analytics))\b", "claims-risk-analytics", "claims"),
        (r"\b(pipeline stats|claims? (header )?stats|pending dollars)\b", "claims-header-stats", "claims"),
        # HAL spine tiles (prefer over legacy monitors when talking on/about HAL)
        (r"\b(hal )?import health|health (tile|card|kpi)\b", "hal-import-health", "hal"),
        (r"\b(program posture|hal posture|operational posture)\b", "hal-program-posture", "hal"),
        (r"\b(import health|health monitor|stale imports?)\b", "import-health-monitor", None),
        (r"\b(daily huddle|morning huddle|morning briefing)\b", "om-daily-huddle", "office-manager"),
        (r"\b(ebitda trend|ebitda chart)\b", "ebitda-station", "financial"),
        (r"\b(ebitda variance|net income variance)\b", "ebitda-variance-bar", "financial"),
        (r"\b(claims status (bar|distribution|chart)|status distribution)\b", "claims-status-bar", "claims"),
        (r"\b(claims (aging )?trend|90\+ aging trend)\b", "claims-aging-mini-trend", "claims"),
        (r"\b(import health timeline|import timeline)\b", "import-health-timeline", "softdent"),
        # Prefer W-09 board for board/schedule/status; keep trend for util/slot/load charts
        (r"\b(operatory (slot|load)|chair (load|slots)|operatory util(ization)? (trend|chart))\b", "operatory-util-trend", "office-manager"),
        (r"\b(ar forecast|a/?r forecast|era velocity)\b", "ar-forecast-trend", "ar"),
        (r"\b(expense (hbar|bars|categories)|qb expense)\b", "qb-expense-hbar", "quickbooks"),
        (r"\b(a/?r forecast|aging forecast)\b", "ar-aging-forecast", "ar"),
        (r"\b(claim attachments?|attachment bridge)\b", "claim-attachments-bridge", "documents"),
        # W-01..W-10 Missing Widgets (Moonshot CODING_HAL consult 2026-07-11) + Phase 3 phrase polish
        (r"\bexpense treemap|spending (map|tree|concentration)|where (is|does) (the )?money go|expense concentration\b", "expense-treemap", "financial"),
        (r"\bprocedure profitability|procedure scatter|dental code profit|which procedures (lose|make) money|profitable procedures?\b", "procedure-profitability-scatter", "financial"),
        (r"\bdenial pareto|denial (reason )?chart|claim denials by impact|top denial (codes|reasons)|pareto (of )?denials?\b", "denial-pareto", "claims"),
        (r"\btreatment (plan )?conversion|case acceptance|treatment pipeline|presented to accepted|conversion funnel\b", "treatment-conversion-pipeline", "financial"),
        (r"\bpre[- ]?auth (aging|lanes|board)|preauthorization status|pending preauths|pre-auth timeline|pre auth aging\b", "preauth-aging-lanes", "claims"),
        (r"\bunapplied (credit|payment)s?|credit float|floating money|unallocated payments|unapplied float\b", "unapplied-credit-float", "ar"),
        (r"\bcash (flow )?bridge|liquidity bridge|cash projection|30[- ]?day cash|projected cash\b", "cash-flow-bridge", "financial"),
        (r"\b(insurance )?verification matrix|eligibility matrix|verify (patients|benefits)|insurance check|elig(ibility)? matrix\b", "verification-matrix", "claims"),
        (r"\boperatory (util|board|schedule|status)|chair (util|schedule|board)|room (board|schedule)|op schedule|op board\b", "operatory-util-board", "office-manager"),
        (r"\brecall gauge|recall (status|tracker|compliance)|hygiene (recall|due)|recall (percent|rate|board)\b", "recall-gauge", "office-manager"),
        # HAL-said improve-fix (2026-07-11)
        (r"\beob (posting )?backlog|unposted eob|era backlog\b", "eob-posting-backlog", "office-manager"),
        (r"\b(clinical )?sign-?off|dr\.?\s*reno (sign|review)|pending clinical review\b", "clinical-signoff-queue", "narratives"),
        (r"\bpayer (change )?alerts?|carrier (update|change) alerts?\b", "payer-change-alerts", "office-manager"),
        (r"\bpolicy (change|changelog|updates?)\b", "policy-changelog", "office-manager"),
        (r"\bpayer contacts?|carrier (phones?|contacts?)|eligibility phones?\b", "payer-contact-admin", "office-manager"),
        (r"\b(teach hal|structured remember|remember (form|structured))\b", "hal-structured-remember", "hal"),
        (r"\b(ai insight|structured insight|insight (card|widget))\b", "hal-ai-insight", "hal"),
        (r"\b(collections gap|def-?001|daysheet gap|why .{0,20}collections)\b", "softdent-collections-gap", "softdent"),
        (r"\b(unified (db|database|snapshot)|nr2_unified|practice health snapshot)\b", "unified-db-snapshot", "financial"),
        (r"\b(payroll (gap|import|detail)|qb payroll|show payroll)\b", "qb-payroll-gap", "quickbooks"),
        (r"\b(ap aging|accounts payable|unpaid bills|show ap)\b", "qb-ap-aging", "quickbooks"),
        (r"\b(production (gap|import)|softdent production)\b", "softdent-production-gap", "softdent"),
        (r"\b(case acceptance|acceptance rate)\b", "softdent-case-acceptance-gap", "softdent"),
        (r"\b(patient aging|aging summary|aging buckets)\b", "softdent-aging-gap", "softdent"),
        (r"\b(scheduling (gap|metrics)|fill rate|broken appointments)\b", "softdent-scheduling-gap", "softdent"),
        (r"\b(net profit|qb net profit)\b", "qb-net-profit-gap", "quickbooks"),
        (r"\b(production vs payroll|payroll.?to.?production)\b", "production-vs-payroll", "financial"),
        (r"\b(deep audit|monthly (practice )?health audit|quarter forecast)\b", "deep-audit-status", "financial"),
        (r"\b(era\s*835|remittance|era ingest)\b", "era835-ingest-gap", "softdent"),
        (r"\b(reconcil|variance alert|production vs payroll variance)\b", "reconciliation-status", "financial"),
        (r"\b(import quarantine|quarantined import|poisoned (file|export))\b", "import-quarantine-panel", "financial"),
        (r"\b(dashboard layout|mosaic layout|widget order)\b", "dashboard-layout-status", "financial"),
        (r"\b(ai lane health|lane telemetry|model latency)\b", "ai-lane-health", "financial"),
        (r"\b(data freshness|sync status|import age)\b", "data-freshness-status", "financial"),
    )
    if (not handled) and allow_topic_focus and (
        re.search(r"\b(focus|highlight|show me|point (me )?to|look at|open widget)\b", q)
        or any(re.search(pat, q) for pat, _wid, _pg in focus_rules)
    ):
        for pat, wid, pg in focus_rules:
            if re.search(pat, q):
                if pg and pg != page and not any(a.get("type") == "navigate" for a in actions):
                    actions.append({"type": "navigate", "page": pg})
                    page = pg
                actions.append({"type": "focus_widget", "widgetId": wid})
                actions.append({"type": "highlight_widget", "widgetId": wid, "ms": 4000})
                notes.append(f"Focusing widget `{wid}` (import-backed display only).")
                handled = True
                break

    # --- Voice → planning scrubber inputs (local planning only; never invents into Book KPIs) ---
    try:
        from apex_cpa_pack import parse_voice_slider_command

        voice_inputs = parse_voice_slider_command(query)
    except Exception:
        voice_inputs = None
    if voice_inputs:
        if page != "taxes" and not any(a.get("type") == "navigate" for a in actions):
            actions.append({"type": "navigate", "page": "taxes"})
            page = "taxes"
        actions.append({"type": "focus_widget", "widgetId": "ebitda-scrubber"})
        actions.append({"type": "set_inputs", "widgetId": "ebitda-scrubber", "inputs": voice_inputs})
        notes.append(
            "Applied planning scrubber inputs from your command (Planning column only — not booked to QuickBooks)."
        )
        handled = True

    # --- Voice → narrative composer (dictate/append into section; never invents clinical facts) ---
    if not handled:
        try:
            from apex_claims_narratives_pack import parse_voice_narrative_command

            voice_narr = parse_voice_narrative_command(query)
        except Exception:
            voice_narr = None
        if voice_narr:
            if page != "narratives" and not any(a.get("type") == "navigate" for a in actions):
                actions.append({"type": "navigate", "page": "narratives"})
                page = "narratives"
            actions.append(
                {
                    "type": "narrative_append",
                    "section": voice_narr.get("section") or "notes",
                    "text": voice_narr.get("text") or "",
                    "mode": voice_narr.get("mode") or "append",
                }
            )
            notes.append(
                f"Voice-to-narrative: {voice_narr.get('mode')} into `{voice_narr.get('section')}` "
                "(your spoken/typed words only — HAL does not invent clinical findings)."
            )
            handled = True

    # --- Voice → report tools (handoff / readiness / daily ops briefing) ---
    if not handled:
        # Operator-approved proceed: enabled unless NR2_CONFIG.voiceReportsEnabled === false (client),
        # or env NR2_VOICE_REPORTS=0.
        voice_reports_on = os.environ.get("NR2_VOICE_REPORTS", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        if voice_reports_on:
            voice_report = parse_voice_report_command(query)
            if voice_report:
                actions.append(
                    {
                        "type": "run_tool",
                        "tool": voice_report["tool"],
                        "speak": voice_report.get("speak", True),
                    }
                )
                notes.append(f"Voice report request: {voice_report['intent']}")
                handled = True

    # --- Save scenario by voice ---
    save_m = re.search(r"\bsave scenario\s+(.+)$", q)
    if save_m:
        name = save_m.group(1).strip(" .\"'")[:64]
        if page != "taxes" and not any(a.get("type") == "navigate" for a in actions):
            actions.append({"type": "navigate", "page": "taxes"})
            page = "taxes"
        actions.append({"type": "focus_widget", "widgetId": "ebitda-scrubber"})
        actions.append({"type": "save_scenario", "widgetId": "ebitda-scrubber", "name": name})
        notes.append(f'Save planning scenario "{name}" from current scrubber (NR2 store only).')
        handled = True

    # --- Import variance alerts (import-backed period deltas) ---
    if re.search(r"\b(variance|period swing|import alert|what changed)\b", q) and not handled:
        _reports, bundle, _err = _load_reports_and_bundle()
        try:
            from apex_cpa_pack import detect_import_variances

            alerts = detect_import_variances(bundle)
        except Exception:
            alerts = []
        msg = (
            " · ".join(str(a.get("message") or "") for a in alerts[:3])
            if alerts
            else "No >=10% SoftDent period swings between the last two dashboard rows."
        )
        actions.append(
            {
                "type": "set_status_banner",
                "message": msg[:120],
                "hint": "Import-backed period deltas only.",
                "tone": "warn" if alerts else "ok",
            }
        )
        if not any(a.get("type") == "navigate" for a in actions):
            actions.append({"type": "navigate", "page": "taxes"})
        actions.append({"type": "focus_widget", "widgetId": "import-variance"})
        notes.append(msg)
        handled = True

    # --- Import-backed status hint (non-dollar) ---
    if re.search(r"\b(import status|import readiness|are imports|sync status|verify (softdent|quickbooks|imports))\b", q):
        _reports, bundle, _err = _load_reports_and_bundle()
        fresh = build_import_freshness(bundle)
        actions.append(
            {
                "type": "set_status_banner",
                "message": fresh.get("message") or "Imports unknown",
                "hint": fresh.get("hint") or "",
                "tone": "ok" if fresh.get("status") == "ok" else "warn",
            }
        )
        if not any(a.get("type") == "navigate" for a in actions):
            # Stay on HAL when staff is chatting — do not yank the mosaic to Financial.
            if page != "hal":
                actions.append({"type": "navigate", "page": "financial"})
                actions.append({"type": "focus_widget", "widgetId": "financial-command-strip"})
        notes.append(str(fresh.get("message") or "Import diagnostics loaded from cache."))
        notes.append(str(fresh.get("hint") or ""))
        handled = True

    # --- Surface categorize suggestions (already computed from imports; not inventing $) ---
    if allow_topic_focus and re.search(r"\b(categorize|suggest categor|expense categor|remap categor)\b", q):
        _reports, bundle, _err = _load_reports_and_bundle()
        cat = build_categorize_assist(bundle)
        n = len(cat.get("suggestions") or [])
        actions.append({"type": "navigate", "page": "quickbooks"})
        actions.append({"type": "focus_widget", "widgetId": "hal-categorize-assist"})
        actions.append(
            {
                "type": "set_status_banner",
                "message": f"Categorize assist: {n} suggestion(s)" if n else "No categorize suggestions",
                "hint": cat.get("hint") or "",
                "tone": "ok" if n else "warn",
            }
        )
        notes.append(
            f"Opened categorize assist with {n} import-backed suggestion(s). HAL does not post to QuickBooks."
        )
        handled = True

    # --- Claims aging / claim tile focus (import-backed only) ---
    claim_m = re.search(r"\b(?:find|focus|highlight|open)\s+claim\s+([A-Za-z0-9\-_.]+)", query, re.I)
    if claim_m:
        cid = claim_m.group(1).strip()
        if page != "claims" and not any(a.get("type") == "navigate" for a in actions):
            actions.append({"type": "navigate", "page": "claims"})
            page = "claims"
        actions.append({"type": "focus_claim_tile", "claimId": cid})
        if re.search(r"\bopen\b", q):
            actions.append({"type": "open_claim_detail", "claimId": cid})
        notes.append(f"Focusing claim tile `{cid}` from SoftDent import (no invented fields).")
        handled = True

    if re.search(r"\b(claims? import status|aging tiles? status)\b", q):
        _reports, bundle, _err = _load_reports_and_bundle()
        summary = _claims_summary_from_bundle(bundle)
        counts = summary.get("agingCounts") if isinstance(summary.get("agingCounts"), dict) else {}
        meta = summary.get("agingMeta") if isinstance(summary.get("agingMeta"), dict) else {}
        msg = (
            f"Claims import: {summary.get('totalClaims') or 0} rows · "
            f"30:{counts.get('30', 0)} 60:{counts.get('60', 0)} 90:{counts.get('90', 0)}"
        )
        hint = (
            "Age/Days or ServiceDate missing on many rows — aging shelves may be empty."
            if meta.get("missingAgeField")
            else "Aging shelves from SoftDent import."
        )
        actions.append(
            {
                "type": "set_status_banner",
                "message": msg[:120],
                "hint": hint,
                "tone": "warn" if meta.get("missingAgeField") else "ok",
            }
        )
        if not any(a.get("type") == "navigate" for a in actions):
            actions.append({"type": "navigate", "page": "claims"})
        notes.append(msg)
        handled = True

    if re.search(r"\b(draft narrative|insurance narrative|appeal letter)\b", q):
        if page != "narratives" and not any(a.get("type") == "navigate" for a in actions):
            actions.append({"type": "navigate", "page": "narratives"})
            page = "narratives"
        notes.append(
            "Open Narratives, lock clinical notes + claim + payer context, then generate an insurance draft with consent."
        )
        handled = True

    # --- Widget data census (current page, named page, or all pages) ---
    # Runtime mosaic census — not governed memory. Memory holds payer/policy hints only;
    # widget inventory/health always comes from build_*_widget_census.
    wants_all_pages = bool(
        re.search(
            r"\b("
            r"all pages|every page|whole (app|program|bridge)|program.?wide|across (all )?pages|"
            r"(see|know|show|list|find|view|check|inspect)\s+(me\s+)?(all|every|the)\s+widgets?|"
            r"all (the )?widgets?|"
            r"every widget|"
            r"widgets? (across|in) (the )?(app|program|bridge|office)"
            r")\b",
            q,
        )
    )
    page_in_query = None
    for pid in APEX_PAGES:
        if re.search(rf"\b(on|for|about)\s+(the\s+)?{re.escape(pid)}\b", q) or re.search(
            rf"\b{re.escape(pid)}\s+page\b", q
        ):
            page_in_query = pid
            break
    if page_in_query is None:
        for pat, pid in (
            (r"\b(tax|taxes)\s+page\b|\bon taxes\b", "taxes"),
            (r"\b(a/?r|accounts receivable)\s+page\b|\bon a/?r\b", "ar"),
            (r"\b(qb|quickbooks)\s+page\b|\bon quickbooks\b", "quickbooks"),
            (r"\boffice\s*(mgr|manager)\b", "office-manager"),
        ):
            if re.search(pat, q):
                page_in_query = pid
                break
    wants_inventory = bool(
        re.search(
            r"\b("
            r"(what|which|list|show|see|know)\s+(all\s+)?(the\s+)?widgets?\b|"
            r"widget(s)?\s+(on|for|list|inventory|map|catalog)\b|"
            r"widgets on\b|"
            r"can you see (all |the )?widgets?"
            r")\b",
            q,
        )
    )
    wants_census = bool(
        re.search(
            r"\b("
            r"which widgets (are )?(empty|populated|showing|have data)|"
            r"do(es)? (the )?widgets? (show|have|display) data|"
            r"widget (health|census|status|data)|"
            r"are (all |the )?widgets? (empty|healthy|populated|showing)|"
            r"empty widgets|"
            r"what('s| is) (empty|missing) on (this|the|all)\s*(page|pages)?"
            r")\b",
            q,
        )
    )
    if (not handled) and (wants_all_pages or wants_census or wants_inventory):
        if wants_all_pages or (wants_census and re.search(r"\ball\b", q) and not page_in_query):
            all_payload = build_all_pages_widget_census()
            reply_txt = format_all_pages_census_reply(all_payload)
            totals = all_payload.get("totals") if isinstance(all_payload.get("totals"), dict) else {}
            empty_n = int(totals.get("empty") or 0)
            actions.append(
                {
                    "type": "set_status_banner",
                    "message": f"All pages: {totals.get('withData', 0)}/{totals.get('widgets', 0)} with data"
                    + (f" · {empty_n} empty" if empty_n else ""),
                    "hint": "Program-wide import-backed census.",
                    "tone": "warn" if empty_n else "ok",
                }
            )
            notes.append(reply_txt)
            handled = True
        else:
            target = page_in_query or page
            if page_in_query and page_in_query != page and not any(a.get("type") == "navigate" for a in actions):
                actions.append({"type": "navigate", "page": page_in_query})
                page = page_in_query
            if wants_inventory and not wants_census:
                reply_txt = format_page_inventory_reply(target)
                actions.append(
                    {
                        "type": "set_status_banner",
                        "message": f"Widget inventory · {target}",
                        "hint": "Import-backed page map.",
                        "tone": "ok",
                    }
                )
            else:
                census_payload = build_page_widget_census(target)
                census = census_payload.get("census") if isinstance(census_payload.get("census"), dict) else {}
                reply_txt = format_census_reply(str(census_payload.get("page") or target), census)
                empty_n = int(census.get("empty") or 0)
                actions.append(
                    {
                        "type": "set_status_banner",
                        "message": f"{target}: {census.get('withData', 0)}/{census.get('total', 0)} with data"
                        + (f" · {empty_n} empty" if empty_n else ""),
                        "hint": "Import-backed census — HAL does not invent values.",
                        "tone": "warn" if empty_n else "ok",
                    }
                )
                empty_ids = census.get("emptyIds") if isinstance(census.get("emptyIds"), list) else []
                if empty_ids:
                    actions.append({"type": "focus_widget", "widgetId": str(empty_ids[0])})
                    actions.append({"type": "highlight_widget", "widgetId": str(empty_ids[0]), "ms": 4000})
            notes.append(reply_txt)
            handled = True

    # --- DEF-001 / Phase I2: why collections empty / revenue composition empty ---
    if (not handled) and re.search(
        r"\b("
        r"why .{0,40}collections|collections (empty|pending|missing|gap)|def-?001|"
        r"daysheet (gap|missing|empty)|"
        r"why .{0,40}revenue.?composition|revenue.?composition (empty|pending|missing)|"
        r"payer mix (empty|missing)|insurance.?patient (empty|pending|missing)"
        r")\b",
        q,
    ):
        try:
            from apex_softdent_hardening_pack import assess_collections_gap, format_collections_gap_reply

            _reports, bundle, _err = _load_reports_and_bundle()
            gap = assess_collections_gap(bundle)
            notes.append(format_collections_gap_reply(gap))
            if not gap.get("healthy"):
                append_collections_pending_board_actions(actions)
            if gap.get("healthy"):
                actions.append(
                    {
                        "type": "set_status_banner",
                        "message": f"Collections reported · {gap.get('period') or 'latest'}",
                        "hint": "gapCode=OK",
                        "tone": "ok",
                    }
                )
            if page not in ("softdent", "financial") and not any(a.get("type") == "navigate" for a in actions):
                actions.append({"type": "navigate", "page": "financial"})
            actions.append({"type": "focus_widget", "widgetId": "revenue-composition"})
            actions.append({"type": "highlight_widget", "widgetId": "revenue-composition", "ms": 4500})
            actions.append({"type": "focus_widget", "widgetId": "softdent-collections-gap"})
            actions.append({"type": "highlight_widget", "widgetId": "softdent-collections-gap", "ms": 4500})
            handled = True
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Collections gap check failed: {exc}")
            handled = True

    # --- S0: QB payroll / AP honesty ---
    if (not handled) and re.search(
        r"\b(payroll (gap|pending|import)|why .{0,20}payroll|ap aging|accounts payable|unpaid bills)\b",
        q,
    ):
        try:
            from apex_qb_payroll_pack import assess_payroll_ap_gap, format_payroll_ap_reply

            _reports, bundle, _err = _load_reports_and_bundle()
            gap = assess_payroll_ap_gap(bundle)
            notes.append(format_payroll_ap_reply(gap))
            if page != "quickbooks" and not any(a.get("type") == "navigate" for a in actions):
                actions.append({"type": "navigate", "page": "quickbooks"})
            wid = "qb-payroll-gap" if gap.get("payrollPending") else "qb-ap-aging"
            if re.search(r"\b(ap|payable|unpaid)\b", q):
                wid = "qb-ap-aging"
            actions.append({"type": "focus_widget", "widgetId": wid})
            actions.append({"type": "highlight_widget", "widgetId": wid, "ms": 4500})
            handled = True
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Payroll/AP gap check failed: {exc}")
            handled = True

    # --- HAL-said: assign SoftDent denials → Steve (NR2 tasks only) ---
    if (not handled) and re.search(
        r"\b(assign (open )?denials?( to steve)?|denials? (to|for) steve|steve.?s? denial(s| queue)?)\b",
        q,
    ):
        try:
            from apex_hal_said_improve_pack import assign_softdent_denials_to_steve

            _reports, bundle, _err = _load_reports_and_bundle()
            rows = _section_rows(bundle, "softdent", "claims") or _section_rows(
                bundle, "softdent", "claimStatus"
            )
            result = assign_softdent_denials_to_steve(rows if isinstance(rows, list) else [])
            n = int(result.get("created") or 0)
            notes.append(
                f"Assigned {n} denial follow-up task(s) to Steve (NR2-local office_tasks; no SoftDent write-back). "
                f"Skipped duplicates: {result.get('skipped', 0)}."
            )
            actions.append(
                {
                    "type": "set_status_banner",
                    "message": f"Steve denial tasks · {n} created",
                    "hint": "NR2-local assignee only.",
                    "tone": "ok" if n else "warn",
                }
            )
            if page != "office-manager" and not any(a.get("type") == "navigate" for a in actions):
                actions.append({"type": "navigate", "page": "office-manager"})
            actions.append({"type": "focus_widget", "widgetId": "om-daily-huddle"})
            handled = True
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Could not assign denials: {exc}")
            handled = True

    # --- HAL-said: request clinical sign-off ---
    if (not handled) and re.search(
        r"\b(request (dr\.?\s*)?reno sign-?off|clinical sign-?off for claim|sign-?off (this )?narrative)\b",
        q,
    ):
        try:
            from apex_hal_said_improve_pack import submit_clinical_signoff

            m = re.search(r"claim\s+([A-Za-z0-9\-]+)", q, re.I)
            cid = m.group(1) if m else ""
            result = submit_clinical_signoff({"claimId": cid, "note": "Requested via HAL"})
            if result.get("ok"):
                notes.append(
                    f"Queued clinical sign-off for Dr. Reno (claim `{cid or 'n/a'}`). "
                    "HAL does not submit to payer."
                )
                actions.append({"type": "navigate", "page": "narratives"})
                actions.append({"type": "focus_widget", "widgetId": "clinical-signoff-queue"})
            else:
                notes.append(result.get("error") or "Sign-off request failed — include a claim id.")
            handled = True
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Sign-off request error: {exc}")
            handled = True

    # --- What should HAL learn / teach me (staff memory priorities) ---
    wants_learn = bool(
        re.search(
            r"\b("
            r"what (would|do|should) you (like|want|prefer|prioritize) to learn|"
            r"what (would|do|should) (you|hal) prioritize|"
            r"prioritize learning|"
            r"learning priorit|"
            r"key areas .{0,40}learn|"
            r"what should (i|we) (teach|tell|remember|save)|"
            r"what (can|should) (you|hal) learn|"
            r"what .{0,30}(governed|learned) memor|"
            r"teach (you|hal)|"
            r"based on .{0,40}governed memor"
            r")\b",
            q,
        )
    )
    if (not handled) and wants_learn:
        highlights: list[str] = []
        try:
            all_payload = build_all_pages_widget_census()
            raw = all_payload.get("emptyHighlights") if isinstance(all_payload, dict) else None
            if isinstance(raw, list):
                highlights = [str(h) for h in raw[:8]]
        except Exception:  # noqa: BLE001
            highlights = []
        notes.append(format_learn_priorities_reply(empty_highlights=highlights or None))
        actions.append(
            {
                "type": "set_status_banner",
                "message": "Learning priorities · Remember this: …",
                "hint": "Staff learned_memories + governed memories.jsonl — no PHI.",
                "tone": "ok",
            }
        )
        handled = True

    # --- InsCo x ADA probabilistic ledger estimates (HAL-10582/83) — exact default ---
    # Prefer ledger probabilistic when gold payment-lines are empty (hal-10400).
    if not handled:
        try:
            from softdent_insco_ada_probabilistic import (
                format_probabilistic_estimate_reply,
                format_probabilistic_status_reply,
                log_inferred_view_audit,
                lookup_probabilistic_estimate,
                parse_probabilistic_estimate_query,
                probabilistic_report_status,
            )

            parsed_p = parse_probabilistic_estimate_query(query)
            if parsed_p and parsed_p.get("kind") == "status":
                st = probabilistic_report_status()
                notes.append(format_probabilistic_status_reply(st))
                actions.append(
                    {
                        "type": "set_status_banner",
                        "message": (
                            f"InsCo x ADA ledger · published={st.get('publishedCells') or 0} · "
                            f"high={st.get('highCredibilityCells') or 0}"
                        ),
                        "hint": "Exact usable+ only by default; inferred needs opt-in. empty != $0.",
                        "tone": "ok" if int(st.get("publishedCells") or 0) else "warn",
                    }
                )
                handled = True
            elif parsed_p and parsed_p.get("kind") == "lookup":
                include_inf = bool(parsed_p.get("includeInferred"))
                est = lookup_probabilistic_estimate(
                    payer=str(parsed_p.get("payer") or ""),
                    ada_code=str(parsed_p.get("adaCode") or ""),
                    include_inferred=include_inf,
                )
                if include_inf:
                    log_inferred_view_audit(
                        payer=str(parsed_p.get("payer") or ""),
                        ada=str(parsed_p.get("adaCode") or ""),
                        source="hal-board-action",
                    )
                notes.append(
                    format_probabilistic_estimate_reply(
                        est,
                        payer=str(parsed_p.get("payer") or ""),
                        ada=str(parsed_p.get("adaCode") or ""),
                        include_inferred=include_inf,
                    )
                )
                tone = "ok"
                if not est:
                    tone = "warn"
                elif str(est.get("tier")) == "inferred":
                    tone = "danger"
                elif str(est.get("credibility")) == "usable":
                    tone = "warn"
                actions.append(
                    {
                        "type": "set_status_banner",
                        "message": (
                            f"InsCo x ADA · {parsed_p.get('payer')} x {parsed_p.get('adaCode')} · "
                            f"{(est or {}).get('credibility') or 'insufficient'}"
                        ),
                        "hint": (
                            "Inferred opt-in — proportional split warning."
                            if include_inf
                            else "Exact usable+ only (ledger estimate, not contractual)."
                        ),
                        "tone": tone,
                    }
                )
                handled = True
        except Exception as exc:  # noqa: BLE001
            notes.append(f"InsCo x ADA probabilistic lookup unavailable: {exc}")

    # --- Treatment planning estimate (InsCo x ADA from payment-line aggregates / gold path) ---
    if not handled:
        try:
            from softdent_treatment_planning import (
                format_treatment_estimate_reply,
                lookup_treatment_estimate,
                parse_treatment_estimate_query,
                treatment_planning_status,
            )

            parsed = parse_treatment_estimate_query(query)
            if parsed:
                est = lookup_treatment_estimate(payer=parsed["payer"], ada_code=parsed["adaCode"])
                chip = est.get("chip") if isinstance(est.get("chip"), dict) else {}
                reply_txt = format_treatment_estimate_reply(est)
                notes.append(reply_txt)
                tone = str(chip.get("tone") or ("ok" if est.get("sufficient") else "warn"))
                src = str(est.get("source") or chip.get("source") or "")
                actions.append(
                    {
                        "type": "set_status_banner",
                        "message": (
                            f"Tx plan [{chip.get('label') or chip.get('badge') or 'estimate'}] · "
                            f"{parsed['payer']} x {parsed['adaCode']}"
                        ),
                        "hint": (
                            f"{chip.get('display') or ''} · source={src or 'unknown'} · "
                            "not a benefits guarantee · empty != $0"
                        ).strip(" ·"),
                        "tone": tone,
                    }
                )
                handled = True
            elif re.search(
                r"\b(treatment plan(ning)? (data|status|ready|estimates?)|insurance payment (analysis|lines)|"
                r"ada (payer|payment) (data|estimates?))\b",
                q,
            ):
                st = treatment_planning_status()
                notes.append(
                    f"Treatment-planning data: {st.get('paymentLines', 0)} payment lines, "
                    f"{st.get('procedureCodes', 0)} procedure crosswalk rows, "
                    f"{st.get('estimates', 0)} gold InsCo x ADA estimates "
                    f"({st.get('estimatesWithMinSample', 0)} with n>=10); "
                    f"ledger spine exact usable={st.get('ledgerSpineExactUsable') or 0} "
                    f"(fallback={st.get('fallbackSource') or 'none'}). "
                    f"{st.get('hint') or ''}"
                )
                actions.append(
                    {
                        "type": "set_status_banner",
                        "message": (
                            f"Tx planning: gold {st.get('estimatesWithMinSample', 0)} · "
                            f"spine exact {st.get('ledgerSpineExactUsable') or 0}"
                        ),
                        "hint": st.get("hint") or "",
                        "tone": (
                            "ok"
                            if int(st.get("estimatesWithMinSample") or 0)
                            or int(st.get("ledgerSpineExactUsable") or 0)
                            else "warn"
                        ),
                    }
                )
                handled = True
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Treatment-planning lookup unavailable: {exc}")

    # --- SoftDent / QuickBooks export playbook (when + how) ---
    export_sd = bool(
        re.search(r"\b(how|when).{0,40}\b(softdent|soft dent)\b.{0,40}\b(export|sync|import|grab|pull|get)\b", q)
        or re.search(r"\b(softdent|soft dent).{0,30}\b(export|csv|odbc|inbox)\b", q)
        or re.search(r"\bhow (do i |to )?(get|grab|pull|export).{0,20}softdent\b", q)
        or re.search(
            r"\b(softdent|soft dent).{0,50}(cannot be reached|not in (the )?(database|db|odbc)|sign on and use|ui export)\b",
            q,
        )
    )
    export_qb = bool(
        re.search(r"\b(how|when).{0,40}\b(quickbooks|\bqb\b)\b.{0,40}\b(export|sync|import|grab|pull|get)\b", q)
        or re.search(r"\b(quickbooks|\bqb\b).{0,30}\b(export|csv|iif|inbox|p&l|profit)\b", q)
        or re.search(r"\bhow (do i |to )?(get|grab|pull|export).{0,20}(quickbooks|\bqb\b)\b", q)
    )
    export_both = bool(
        re.search(r"\b(how|when).{0,40}\b(export|sync|import|grab).{0,40}\b(softdent|quickbooks|imports)\b", q)
        or re.search(r"\b(where|how).{0,20}\b(put|place|drop).{0,20}\b(exports?|csv|files)\b", q)
        or re.search(r"\b(export playbook|import playbook|how (do i )?sync)\b", q)
    )
    if (not handled) and (export_sd or export_qb or export_both):
        topic = "both"
        if export_sd and not export_qb and not export_both:
            topic = "softdent"
        elif export_qb and not export_sd and not export_both:
            topic = "quickbooks"
        play = format_export_playbook_reply(topic)
        actions.append(
            {
                "type": "set_status_banner",
                "message": "Export playbook: SoftDent + QuickBooks → inbox → Sync",
                "hint": (
                    "DB/ODBC first; else Sign On + SoftDent UI export. "
                    "SOFTDENT_SIGNON_* env vars; HAL never prints the password."
                ),
                "tone": "ok",
            }
        )
        if re.search(r"\b(sync|refill|populate|now)\b", q):
            actions.append({"type": "sync_imports", "fullSync": True})
            actions.append({"type": "refresh_page"})
            notes.append("Starting Sync after explaining the export path.")
        notes.append(play)
        handled = True

    reply = " ".join(n for n in notes if n).strip()
    if not handled:
        reply = (
            "I can sync imports, refresh the mosaic, open a page, focus instruments "
            "(EBITDA scrubber, claims 30/60/90 shelves, scenarios, filing, workpaper, variance), "
            "report which widgets are empty vs showing data, explain when/how to grab SoftDent and QuickBooks exports, "
            "focus a claim by ID, or set planning scrubber inputs by voice. "
            "Voice reports: handoff report, readiness check, morning briefing / daily ops. "
            "I never invent dollar amounts or claim facts — values come from SoftDent/QuickBooks imports only."
        )

    return {
        "ok": True,
        "handled": handled,
        "query": query,
        "page": page,
        "reply": reply,
        "actions": actions,
        "buildId": BUILD_ID,
        "honesty": "Board actions never invent financial dollar amounts.",
        "exportPlaybook": build_export_playbook() if handled and (export_sd or export_qb or export_both) else None,
    }


def apex_sync_trigger(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Trigger import refresh using existing NR2 sync path when available.

    Moonshot crash/perf SHOULD: serialize Sync with a non-blocking semaphore.
    Concurrent calls return ok=False / status=sync_locked (HTTP 423 via route).
    """
    global _LAST_SYNC_ERROR, _LAST_SYNC_AT
    body = payload if isinstance(payload, dict) else {}
    acquired = _SYNC_SEMAPHORE.acquire(blocking=False)
    if not acquired:
        return {
            "ok": False,
            "error": "Sync already in progress",
            "status": "sync_locked",
            "retryAfter": 30,
            "buildId": BUILD_ID,
            "page": body.get("page"),
        }
    try:
        sync_page = str(body.get("page") or "financial")
        _update_fill_progress(sync_page, 5)
        started = _utc_now()
        try:
            from apex_32b_program_fixes_pack import ensure_reconciliation_env, record_program_mutation

            ensure_reconciliation_env()
            record_program_mutation(
                "sync",
                actor=str(body.get("actor") or "Staff"),
                detail={"page": sync_page, "fullSync": bool(body.get("fullSync", True))},
                path="/api/apex/sync/trigger",
                hal_involved=bool(body.get("halInvolved")),
            )
        except Exception:
            pass
        result: dict[str, Any] = {
            "ok": True,
            "startedAt": started,
            "status": "syncing",
            "sources": ["softdent", "quickbooks"],
            "page": body.get("page"),
            "buildId": BUILD_ID,
            "fillProgress": 5,
        }
        # Optional document inbox sync (SoftDent/QB file merge) before reload
        try:
            from document_sync import NR2_DATA_DIR, sync_accounting_documents
            from local_store import LocalStore

            store = LocalStore(NR2_DATA_DIR)
            doc_sync = sync_accounting_documents(store)
            result["documentSync"] = {
                "ok": True,
                "imported": doc_sync.get("imported") if isinstance(doc_sync, dict) else None,
                "updated": doc_sync.get("updated") if isinstance(doc_sync, dict) else None,
                "warnings": (doc_sync.get("warnings") if isinstance(doc_sync, dict) else None) or [],
            }
        except Exception as exc:  # noqa: BLE001
            result["documentSync"] = {"ok": False, "error": str(exc)}
        try:
            from import_loader import load_import_bundle

            sync = bool(body.get("fullSync", True))
            _update_fill_progress(sync_page, 40)
            result["fillProgress"] = 40
            bundle = load_import_bundle(sync=sync, deep=False)
            # Fresh imports must not serve stale page payloads.
            _WIDGETS_CACHE.clear()
            with _REPORTS_BUNDLE_CACHE_LOCK:
                _REPORTS_BUNDLE_CACHE["at"] = 0.0
                _REPORTS_BUNDLE_CACHE["reports"] = None
                _REPORTS_BUNDLE_CACHE["bundle"] = None
                _REPORTS_BUNDLE_CACHE["errors"] = None
            _TICKER_CACHE["at"] = 0.0
            _TICKER_CACHE["payload"] = None
            try:
                from apex_reconciliation_pack import invalidate_explain_cache

                result["explainCache"] = invalidate_explain_cache(reason="import")
            except Exception as exc:  # noqa: BLE001
                result["explainCache"] = {"ok": False, "error": str(exc)}
            result["status"] = "ok"
            result["completedAt"] = _utc_now()
            result["importMode"] = bundle.get("importMode")
            result["loadedAt"] = bundle.get("loadedAt")
            diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
            summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
            result["diagnostics"] = {
                "connected": summary.get("connected"),
                "total": summary.get("total"),
                "missing": summary.get("missing"),
                "stale": summary.get("stale"),
            }
            result["freshness"] = build_import_freshness(bundle)
            scrub = (bundle.get("filterSummary") if isinstance(bundle, dict) else None) or {}
            if scrub:
                result["filterSummary"] = scrub
            # Phase I3 — mirror import bundle into additive unified SQLite
            try:
                from apex_unified_db_pack import ingest_from_bundle

                result["unifiedIngest"] = ingest_from_bundle(bundle)
            except Exception as exc:  # noqa: BLE001
                result["unifiedIngest"] = {"ok": False, "error": str(exc)}
            _LAST_SYNC_ERROR = ""
            _LAST_SYNC_AT = str(result.get("completedAt") or started)
        except Exception as exc:  # noqa: BLE001
            result["ok"] = False
            result["status"] = "error"
            result["error"] = str(exc)
            result["completedAt"] = _utc_now()
            _LAST_SYNC_ERROR = str(exc)[:240]
            _LAST_SYNC_AT = str(result.get("completedAt") or started)
        _update_fill_progress(sync_page, 100)
        result["fillProgress"] = 100
        result["lastSyncError"] = _LAST_SYNC_ERROR or None
        return result
    finally:
        _SYNC_SEMAPHORE.release()


def build_apex_ticker(*, force: bool = False) -> dict[str, Any]:
    """Scrolling ticker items — grounded to imports; never invent dollar amounts."""
    import time

    now = time.time()
    cached = _TICKER_CACHE.get("payload")
    cached_at = float(_TICKER_CACHE.get("at") or 0.0)
    if (not force) and cached is not None and (now - cached_at) < _TICKER_CACHE_TTL_SEC:
        return cached

    items: list[dict[str, Any]] = []
    try:
        reports, bundle, errors = _load_reports_and_bundle()
        hal = _build_hal_status_payload()
        diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
        summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
        connected = summary.get("connected")
        total = summary.get("total")
        missing = summary.get("missing")

        items.append(
            {
                "type": "system",
                "text": f"BRIDGE {BUILD_ID} · SYNC {_utc_now()[11:16]}Z",
            }
        )
        if isinstance(connected, int) and isinstance(total, int) and total > 0:
            items.append(
                {
                    "type": "metric",
                    "label": "IMPORTS",
                    "value": f"{connected}/{total}",
                    "unit": "datasets",
                    "status": "ok" if missing == 0 else "partial",
                    "text": f"IMPORTS {connected}/{total}"
                    + (f" · {missing} missing" if isinstance(missing, int) and missing else ""),
                }
            )
        if isinstance(missing, int) and missing > 0:
            items.append(
                {
                    "type": "alert",
                    "severity": "amber",
                    "text": f"ALERT: {missing} import dataset(s) missing",
                }
            )

        claims = _claims_summary_from_bundle(bundle)
        open_c = claims.get("openCount")
        denied = claims.get("deniedCount")
        aging = claims.get("agingPast30")
        if claims.get("available"):
            parts = []
            if isinstance(open_c, int):
                parts.append(f"open {open_c}")
            if isinstance(denied, int) and denied:
                parts.append(f"denied {denied}")
            if isinstance(aging, int) and aging:
                parts.append(f"30+ {aging}")
            items.append(
                {
                    "type": "metric",
                    "label": "CLAIMS",
                    "value": None,
                    "text": "CLAIMS " + (" · ".join(parts) if parts else "imported"),
                }
            )
            if isinstance(aging, int) and aging > 0:
                items.append(
                    {
                        "type": "alert",
                        "severity": "amber",
                        "text": f"ALERT: {aging} claim(s) aging past 30 days",
                    }
                )

        ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
        if ar.get("followUpHint"):
            items.append({"type": "alert", "severity": "amber", "text": f"A/R: {ar['followUpHint']}"})
        elif "totalOutstanding" in ar:
            total_ar = ar.get("totalOutstanding")
            if isinstance(total_ar, (int, float)):
                items.append(
                    {
                        "type": "metric",
                        "label": "A/R OUTSTANDING",
                        "value": f"${total_ar:,.0f}",
                        "unit": "USD",
                        "text": f"A/R OUTSTANDING ${total_ar:,.0f}",
                    }
                )
            else:
                items.append(
                    {
                        "type": "metric",
                        "label": "A/R OUTSTANDING",
                        "value": None,
                        "text": "A/R OUTSTANDING: —",
                    }
                )

        suggestion = str(hal.get("suggestion") or "").strip()
        if suggestion:
            items.append({"type": "hal", "text": f"HAL: {suggestion}"})

        mode = str(bundle.get("importMode") or "")
        loaded = str(bundle.get("loadedAt") or "")
        if mode or loaded:
            items.append(
                {
                    "type": "system",
                    "text": f"IMPORT MODE {mode or '—'} · loaded {loaded or '—'}",
                }
            )
        if errors:
            items.append({"type": "alert", "severity": "amber", "text": f"LOAD NOTE: {errors[0][:80]}"})
    except Exception as exc:  # noqa: BLE001
        items = [
            {"type": "system", "text": f"BRIDGE {BUILD_ID}"},
            {"type": "alert", "severity": "amber", "text": f"TICKER ERROR: {exc}"},
        ]

    if not items:
        items = [{"type": "system", "text": "TELEMETRY STANDBY"}]

    payload = {
        "items": items,
        "timestamp": _utc_now(),
        "buildId": BUILD_ID,
        "cachedForSec": _TICKER_CACHE_TTL_SEC,
    }
    _TICKER_CACHE["at"] = now
    _TICKER_CACHE["payload"] = payload
    return payload


def build_narrative_structure() -> dict[str, Any]:
    reports, bundle, errors = _load_reports_and_bundle()
    del reports
    notes_rows = _section_rows(bundle, "softdent", "clinicalNotes")
    claim_rows = _section_rows(bundle, "softdent", "claims") or _section_rows(bundle, "softdent", "claimStatus")
    hint = "SoftDent clinical notes import available for narrative source material."
    if not notes_rows:
        hint = "Clinical notes import empty — compose manually or import SoftDent notes."
    else:
        hint = f"{len(notes_rows)} clinical note row(s) available from SoftDent import (not auto-filled)."
    if errors:
        hint += f" · {errors[0][:60]}"

    clinical = []
    claims = []
    payers = []
    payer_templates = []
    try:
        from apex_claims_narratives_pack import (
            clinical_note_summaries,
            insurance_payers_from_claims,
            list_payer_appeal_templates,
            normalize_claim_row,
        )

        clinical = clinical_note_summaries(notes_rows)
        for row in claim_rows[:120]:
            tile = normalize_claim_row(row)
            if tile:
                claims.append(tile)
        payers = insurance_payers_from_claims(claim_rows)
        payer_templates = [
            {
                "id": t.get("id"),
                "displayName": t.get("displayName"),
                "payerKey": t.get("payerKey"),
                "operatorMaintained": bool(t.get("operatorMaintained")),
            }
            for t in list_payer_appeal_templates()
        ]
    except Exception:
        pass

    return {
        "sections": [
            {"id": "intro", "title": "Introduction", "order": 0, "content": ""},
            {"id": "findings", "title": "Findings", "order": 1, "content": ""},
            {"id": "treatment", "title": "Treatment Plan", "order": 2, "content": ""},
            {"id": "notes", "title": "Clinical Notes", "order": 3, "content": ""},
            {"id": "followup", "title": "Follow-up", "order": 4, "content": ""},
            {"id": "insurance", "title": "Insurance Narrative", "order": 5, "content": ""},
        ],
        "contextHint": hint,
        "sourceNote": hint,
        "clinicalNoteRows": len(notes_rows),
        "sources": {
            "clinicalNotes": clinical,
            "claims": claims,
            "insurance": payers,
            "lastImport": str(bundle.get("loadedAt") or ""),
            "payerTemplates": payer_templates,
        },
        "buildId": BUILD_ID,
        "refreshedAt": _utc_now(),
    }


def apex_claims_aging_payload() -> dict[str, Any]:
    _reports, bundle, errors = _load_reports_and_bundle()
    rows = _section_rows(bundle, "softdent", "claims") or _section_rows(bundle, "softdent", "claimStatus")
    from apex_claims_narratives_pack import build_aging_buckets

    aging = build_aging_buckets(rows)
    return {
        "ok": True,
        "buckets": aging.get("buckets") or {"30": [], "60": [], "90": []},
        "meta": {
            "lastImport": str(bundle.get("loadedAt") or aging.get("lastImport") or ""),
            "totalClaims": aging.get("totalClaims") or 0,
            "missingAgeField": bool(aging.get("missingAgeField")),
            "missingAgeCount": aging.get("missingAgeCount") or 0,
            "counts": aging.get("counts") or {},
        },
        "errors": errors[:3] if errors else [],
        "buildId": BUILD_ID,
        "refreshedAt": _utc_now(),
    }


def apex_claims_kanban_payload() -> dict[str, Any]:
    _reports, bundle, errors = _load_reports_and_bundle()
    rows = _section_rows(bundle, "softdent", "claims") or _section_rows(bundle, "softdent", "claimStatus")
    from apex_claims_narratives_pack import build_status_columns

    payload = build_status_columns(rows if isinstance(rows, list) else [])
    return {
        "ok": True,
        "columns": payload.get("columns") or {},
        "counts": payload.get("counts") or {},
        "meta": payload.get("meta") or {},
        "totalClaims": payload.get("totalClaims") or 0,
        "available": bool(payload.get("available")),
        "errors": errors[:3] if errors else [],
        "buildId": BUILD_ID,
        "refreshedAt": _utc_now(),
    }


def apex_claim_detail(claim_id: str) -> dict[str, Any]:
    _reports, bundle, _errors = _load_reports_and_bundle()
    rows = _section_rows(bundle, "softdent", "claims") or _section_rows(bundle, "softdent", "claimStatus")
    from apex_claims_narratives_pack import find_claim_by_id

    claim = find_claim_by_id(rows, claim_id)
    if not claim:
        return {"ok": False, "error": "Claim not found in SoftDent import.", "claimId": claim_id, "buildId": BUILD_ID}
    return {"ok": True, **claim, "buildId": BUILD_ID}


def narrative_lock_context(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from apex_claims_narratives_pack import save_narrative_context

    result = save_narrative_context(payload if isinstance(payload, dict) else {})
    result["buildId"] = BUILD_ID
    return result


def narrative_insurance_generate(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    from apex_claims_narratives_pack import (
        clinical_note_summaries,
        generate_insurance_narrative,
        get_narrative_context,
        normalize_claim_row,
    )

    _reports, bundle, _errors = _load_reports_and_bundle()
    notes_rows = _section_rows(bundle, "softdent", "clinicalNotes")
    claim_rows = _section_rows(bundle, "softdent", "claims") or _section_rows(bundle, "softdent", "claimStatus")

    ctx = None
    context_id = str(body.get("contextId") or "").strip()
    if context_id:
        ctx = get_narrative_context(context_id)

    claim_id = str(body.get("claimId") or (ctx or {}).get("claimId") or "").strip()
    note_ids = body.get("clinicalNoteIds") if isinstance(body.get("clinicalNoteIds"), list) else None
    if note_ids is None and ctx:
        note_ids = ctx.get("clinicalNoteIds") if isinstance(ctx.get("clinicalNoteIds"), list) else []
    note_ids = [str(x) for x in (note_ids or []) if str(x).strip()]
    payer_id = str(body.get("payerId") or body.get("payerName") or (ctx or {}).get("payerId") or "").strip()

    claim = None
    if claim_id:
        for row in claim_rows:
            tile = normalize_claim_row(row)
            if tile and tile.get("claimId") == claim_id:
                claim = tile
                break

    all_notes = clinical_note_summaries(notes_rows, limit=200)
    if note_ids:
        idset = set(note_ids)
        notes = [n for n in all_notes if n.get("noteId") in idset]
    else:
        notes = []

    payer_name = payer_id
    if payer_id and claim and claim.get("payer") and str(claim.get("payer")).strip().lower() == payer_id.lower():
        payer_name = str(claim.get("payer"))
    elif payer_id:
        # Resolve display name from claims payers
        for row in claim_rows:
            tile = normalize_claim_row(row)
            if tile and tile.get("payer") and str(tile.get("payer")).strip().lower() == payer_id.lower():
                payer_name = str(tile.get("payer"))
                break

    result = generate_insurance_narrative(
        narrative_type=str(body.get("type") or body.get("narrativeType") or "appeal"),
        claim=claim,
        notes=notes,
        payer_name=payer_name or None,
        denial_reason=str(body.get("denialReason") or "") or None,
        attachments=body.get("attachments") if isinstance(body.get("attachments"), list) else None,
        operator_consent=bool(body.get("operatorConsent") or body.get("consent")),
        build_id=BUILD_ID,
        template_id=str(body.get("templateId") or body.get("payerTemplateId") or "").strip() or None,
    )
    result["buildId"] = BUILD_ID
    return result


def narrative_batch_generate(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """REC-008: generate appeal drafts for multiple claim IDs with shared context."""
    body = payload if isinstance(payload, dict) else {}
    from apex_program_improve_pack import (
        BATCH_NARRATIVE_MAX,
        batch_narrative_seed,
        record_claim_action,
        shared_batch_context,
    )

    consent = bool(body.get("operatorConsent") or body.get("consent"))
    if not consent:
        return {"ok": False, "error": "Operator consent required before batch narrative generation.", "buildId": BUILD_ID}

    raw_ids = body.get("claimIds") if isinstance(body.get("claimIds"), list) else []
    seed = batch_narrative_seed([str(x) for x in raw_ids])
    if not seed.get("ok"):
        return {**seed, "buildId": BUILD_ID}
    ids = list((seed.get("seed") or {}).get("claimIds") or [])
    shared = shared_batch_context(body)

    results: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    ok_count = 0
    for claim_id in ids:
        one = narrative_insurance_generate(
            {
                "claimId": claim_id,
                "type": shared["type"],
                "denialReason": shared.get("denialReason"),
                "payerId": shared.get("payerId"),
                "templateId": shared.get("templateId"),
                "clinicalNoteIds": shared.get("clinicalNoteIds") or [],
                "attachments": shared.get("attachments"),
                "operatorConsent": True,
            }
        )
        entry: dict[str, Any] = {
            "claimId": claim_id,
            "ok": bool(one.get("ok")),
            "error": one.get("error"),
            "draftText": one.get("draftText") if one.get("ok") else None,
            "sourcesCited": one.get("sourcesCited") if one.get("ok") else None,
        }
        results.append(entry)
        if one.get("ok"):
            ok_count += 1
            sections.append(
                {
                    "title": f"Appeal draft · {claim_id}",
                    "content": str(one.get("draftText") or ""),
                }
            )
            try:
                record_claim_action(
                    {
                        "action": "generate-narrative",
                        "claimId": claim_id,
                        "note": f"REC-008 batch ({shared['type']})",
                    }
                )
            except Exception:
                pass

    packet = None
    if sections:
        packet = narrative_print_packet({"sections": sections})

    return {
        "ok": ok_count > 0,
        "count": len(ids),
        "successCount": ok_count,
        "failCount": len(ids) - ok_count,
        "maxBatch": BATCH_NARRATIVE_MAX,
        "sharedContext": {k: v for k, v in shared.items() if k != "attachments" or v},
        "results": results,
        "packet": packet,
        "buildId": BUILD_ID,
        "hint": "Drafts require human review before payer submission. Empty clinical notes stay empty — not invented.",
    }


def narrative_generate(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    # Insurance narrative path when type is set
    if body.get("type") or body.get("narrativeType") or body.get("operatorConsent"):
        return narrative_insurance_generate(body)
    text = str(body.get("text") or "").strip()
    if not text:
        return {"ok": False, "suggestion": "", "status": "empty", "error": "No text provided."}
    # Local cleanup only — never invent clinical facts or dollar amounts.
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return {
        "ok": True,
        "suggestion": cleaned,
        "status": "local-cleanup",
        "confidence": None,
        "note": "Whitespace-normalized draft. Use insurance narrative generate with consent for payer letters.",
    }


def narrative_print_packet(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    import html as html_lib

    body = payload if isinstance(payload, dict) else {}
    sections = body.get("sections") if isinstance(body.get("sections"), list) else []
    job_id = f"narr_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
    parts: list[str] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = html_lib.escape(str(sec.get("title") or sec.get("id") or "Section"))
        content = html_lib.escape(str(sec.get("content") or "").strip() or "[empty]")
        parts.append(f"<h2>{title}</h2><pre>{content}</pre>")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>NR2 Narrative Packet</title>
<style>
  body {{ font-family: Georgia, serif; margin: 28px; color: #111; }}
  h1 {{ font-size: 18px; }} h2 {{ font-size: 14px; margin-top: 18px; }}
  pre {{ white-space: pre-wrap; font-family: inherit; font-size: 13px; }}
  .meta {{ color: #555; font-size: 12px; }}
  @media print {{ button {{ display: none; }} }}
</style></head><body>
  <h1>NewRidgeFinancial 2.0 — Narrative Packet</h1>
  <div class="meta">Job {job_id} · Build {BUILD_ID}</div>
  {''.join(parts) or '<p>[No sections]</p>'}
  <p><button type="button" onclick="window.print()">Print</button></p>
  <script>window.addEventListener('load', function() {{ setTimeout(function() {{ window.print(); }}, 250); }});</script>
</body></html>"""
    _NARRATIVE_PACKETS[job_id] = {"html": html, "createdAt": _utc_now()}
    if len(_NARRATIVE_PACKETS) > 30:
        for old in list(_NARRATIVE_PACKETS.keys())[:15]:
            _NARRATIVE_PACKETS.pop(old, None)
    return {
        "ok": True,
        "jobId": job_id,
        "status": "ready",
        "url": f"/api/apex/narratives/packet/{job_id}",
        "createdAt": _utc_now(),
    }


def register_apex_routes(app: Any, json_response_fn: Callable[..., Any]) -> None:
    """Register Apex Bottle routes on the existing NR2 app."""

    @app.get("/api/apex/widgets/<page_id>")
    def apex_widgets_api(page_id: str):
        try:
            from nr2_rbac import has_capability

            try:
                if not (has_capability("read_financial") or has_capability("read_all") or has_capability("read")):
                    pass
            except Exception:
                pass
            import bottle

            sub = bottle.request.query.get("sub") or None
            claim_id = bottle.request.query.get("id") or None
            patient_id = (
                bottle.request.query.get("patient_id")
                or bottle.request.query.get("patientId")
                or None
            )
            return json_response_fn(
                build_apex_widgets(
                    page_id, sub=sub, claim_id=claim_id, patient_id=patient_id
                )
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "widgets": []}, status=500)

    @app.post("/api/apex/print/<packet_type>")
    def apex_print_api(packet_type: str):
        try:
            import bottle

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            return json_response_fn(apex_print_job(packet_type, payload))
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/print/")
    def apex_print_api_root():
        return apex_print_api("view")

    @app.get("/api/apex/print/packet/<job_id>")
    def apex_print_packet(job_id: str):
        import bottle

        packet = _PRINT_PACKETS.get(str(job_id or ""))
        if not packet:
            bottle.response.status = 404
            bottle.response.content_type = "text/plain; charset=utf-8"
            return "Print packet not found or expired."
        bottle.response.content_type = "text/html; charset=utf-8"
        return packet.get("html") or ""

    @app.post("/api/apex/sync/trigger")
    def apex_sync_api():
        try:
            import bottle

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            result = apex_sync_trigger(payload)
            # Moonshot crash/perf SHOULD: HTTP 423 when Sync semaphore is held
            if isinstance(result, dict) and result.get("status") == "sync_locked":
                return json_response_fn(result, status=423)
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/sync/qb-payroll-ap-export")
    def apex_qb_payroll_ap_export_api():
        """Drop QB payroll/AP CSVs into document-inbox (optional gap). No invented dollars."""
        try:
            import bottle
            from apex_qb_export_inbox_pack import write_qb_payroll_ap_exports
            from apex_qb_payroll_pack import assess_payroll_ap_gap

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            try:
                payload = json.loads(raw or "{}")
            except Exception:
                payload = {}
            result = write_qb_payroll_ap_exports(
                payroll_rows=list(payload.get("payrollRows") or [])[:500],
                ap_rows=list(payload.get("apRows") or [])[:500],
                empty_payroll=bool(payload.get("emptyPayroll") or payload.get("empty_payroll")),
                empty_ap=bool(payload.get("emptyAp") or payload.get("empty_ap")),
                period=str(payload.get("period") or "") or None,
            )
            result["gap"] = assess_payroll_ap_gap()
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/hal/status")
    def apex_hal_status_api():
        try:
            return json_response_fn(_build_hal_status_payload())
        except Exception as exc:  # noqa: BLE001
            return json_response_fn(
                {
                    "status": "idle",
                    "statusLabel": "HAL Standby",
                    "suggestion": HAL_STATUS_SUGGESTION,
                    "confidence": None,
                    "buildId": BUILD_ID,
                    "refreshedAt": _utc_now(),
                    "error": str(exc),
                }
            )

    @app.post("/api/apex/hal/history-append")
    def apex_hal_history_append_api():
        """Persist one HAL chat turn for #hal/history (local store only)."""
        try:
            import bottle
            from apex_subpages_wave5_pack import append_hal_history_entry

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            role = str(payload.get("role") or "").strip()
            text = str(payload.get("text") or payload.get("query") or "").strip()
            entry_id = str(payload.get("id") or "").strip() or None
            result = append_hal_history_entry(role, text, entry_id=entry_id)
            status = 200 if result.get("ok") else 400
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/orchestrator")
    def apex_hal_orchestrator_status():
        try:
            from apex_orchestrator_pack import orchestrator_status

            payload = orchestrator_status()
            payload["buildId"] = BUILD_ID
            return json_response_fn(payload)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn(
                {"ok": False, "enabled": False, "error": str(exc), "buildId": BUILD_ID},
                status=500,
            )

    @app.post("/api/apex/hal/orchestrate")
    def apex_hal_orchestrate_api():
        """Phase I0 program-manager route: classify lane then (optional) evaluate_query."""
        try:
            import bottle
            from apex_orchestrator_pack import orchestrate, orchestrator_enabled

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            query = str(payload.get("query") or "").strip()
            classify_only = bool(payload.get("classifyOnly") or payload.get("classify_only"))
            if not query:
                return json_response_fn({"ok": False, "error": "query required", "buildId": BUILD_ID}, status=400)

            # classifyOnly always allowed (validation) even when flag off
            if not classify_only and not orchestrator_enabled():
                return json_response_fn(
                    {
                        "ok": False,
                        "error": "orchestrator_disabled",
                        "hint": "Set NR2_AI_ORCHESTRATOR=1",
                        "buildId": BUILD_ID,
                    },
                    status=503,
                )

            readiness = {"level": "unknown"}
            try:
                from import_diagnostics import assess_import_readiness

                readiness = assess_import_readiness(operation="dailyOps") or readiness
            except Exception:
                readiness = {"level": "unknown"}

            store = None
            try:
                from document_sync import NR2_DATA_DIR
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
            except Exception:
                store = None

            result = orchestrate(
                query,
                readiness=readiness if isinstance(readiness, dict) else {"level": "unknown"},
                context=payload.get("shiftContext")
                if isinstance(payload.get("shiftContext"), dict)
                else payload.get("context")
                if isinstance(payload.get("context"), dict)
                else {"page": payload.get("page")},
                system_prompt=str(payload.get("systemPrompt") or payload.get("system") or ""),
                messages=payload.get("messages") if isinstance(payload.get("messages"), list) else None,
                options=payload.get("options") if isinstance(payload.get("options"), dict) else None,
                store=store,
                classify_only=classify_only,
                force_enabled=True if classify_only else None,
                require_structured=bool(payload.get("requireStructured") or payload.get("require_structured")),
            )
            result["buildId"] = BUILD_ID
            status = 200 if result.get("ok") or classify_only else 400
            if result.get("error") == "orchestrator_disabled":
                status = 503
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/insight-validate")
    def apex_hal_insight_validate():
        try:
            import bottle
            from apex_structured_insight_pack import parse_and_validate_insight_text, validate_insight

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            if "text" in payload and not payload.get("insight"):
                result = parse_and_validate_insight_text(str(payload.get("text") or ""))
            else:
                insight = payload.get("insight") if isinstance(payload.get("insight"), dict) else payload
                result = validate_insight(insight if isinstance(insight, dict) else None)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/collections-gap")
    def apex_hal_collections_gap():
        try:
            from apex_softdent_hardening_pack import assess_collections_gap

            _reports, bundle, _err = _load_reports_and_bundle()
            result = assess_collections_gap(bundle)
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/softdent-report-pull")
    def apex_hal_softdent_report_pull():
        """HAL/program SoftDent desktop report-pull teaching playbook."""
        try:
            import bottle

            from softdent_report_pull import (
                format_softdent_report_pull_hal_reply,
                office_report_catalog,
                universal_report_pull_steps,
            )

            q = str(bottle.request.query.get("q") or "").strip()
            return json_response_fn(
                {
                    "ok": True,
                    "buildId": BUILD_ID,
                    "steps": universal_report_pull_steps(),
                    "catalog": office_report_catalog(),
                    "exportDir": r"C:\SoftDentReportExports",
                    "reply": format_softdent_report_pull_hal_reply(q),
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn(
                {"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500
            )

    @app.get("/api/apex/hal/softdent-kb")
    def apex_hal_softdent_kb():
        """HAL/program SoftDent full product knowledge base (Help TOC + report catalog)."""
        try:
            import bottle

            from softdent_product_kb import (
                format_softdent_product_kb_hal_reply,
                load_softdent_product_kb,
                lookup_help_topics,
                lookup_report,
                lookup_topic_bodies,
                product_kb_summary,
            )

            q = str(bottle.request.query.get("q") or "").strip()
            summary = product_kb_summary()
            kb = load_softdent_product_kb()
            pull_reply = None
            try:
                from softdent_report_pull import format_softdent_report_pull_hal_reply

                if q and re.search(r"\b(pull|export|run|output\s+options)\b", q.lower()):
                    pull_reply = format_softdent_report_pull_hal_reply(q)
            except Exception:
                pull_reply = None
            return json_response_fn(
                {
                    "ok": True,
                    "buildId": BUILD_ID,
                    "summary": summary,
                    "officeDoctrine": kb.get("officeDoctrine"),
                    "howSoftDentWorks": {
                        "summary": ((kb.get("howSoftDentWorks") or {}).get("summary")),
                        "lifecycle": ((kb.get("howSoftDentWorks") or {}).get("lifecycle")),
                        "coreArticleIds": list(
                            ((kb.get("howSoftDentWorks") or {}).get("coreHelpArticles") or {}).keys()
                        ),
                    },
                    "productModules": kb.get("productModules"),
                    "reportCategoryCounts": summary.get("categoryCounts"),
                    "endOfDayRecommended": (
                        (kb.get("reportCatalog") or {}).get("endOfDayRecommended")
                    ),
                    "reportPull": pull_reply,
                    "matches": {
                        "topicBodies": lookup_topic_bodies(q, limit=8) if q else [],
                        "reports": lookup_report(q, limit=12) if q else [],
                        "helpTopics": lookup_help_topics(q, limit=12) if q else [],
                    },
                    "reply": format_softdent_product_kb_hal_reply(q),
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn(
                {"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500
            )

    @app.get("/api/apex/hal/softdent-signon")
    def apex_hal_softdent_signon():
        """HAL/program SoftDent Sign On status — env keys only; never returns password."""
        try:
            from softdent_signon import format_softdent_signon_hal_reply, softdent_signon_status

            status = softdent_signon_status()
            master_verify = None
            try:
                from softdent_master_reports import format_master_reports_hal_reply, verify_master_reports

                master_verify = verify_master_reports(require_inbox_files=False)
                reply = (
                    format_softdent_signon_hal_reply(status)
                    + " "
                    + format_master_reports_hal_reply()
                )
            except Exception:
                reply = format_softdent_signon_hal_reply(status)
            return json_response_fn(
                {
                    "ok": True,
                    "buildId": BUILD_ID,
                    "softdentSignOn": {
                        "ok": bool(status.get("ok")),
                        "user": status.get("user"),
                        "passwordConfigured": bool(status.get("passwordConfigured")),
                        "envUserKey": status.get("envUserKey"),
                        "envPasswordKey": status.get("envPasswordKey"),
                        "knowledge": status.get("knowledge"),
                        "dataAccessDoctrine": status.get("dataAccessDoctrine"),
                        "masterReports": status.get("masterReports"),
                    },
                    "dataAccessDoctrine": status.get("dataAccessDoctrine"),
                    "masterVerify": {
                        "ok": bool((master_verify or {}).get("ok")),
                        "missingGuiPulls": (master_verify or {}).get("missingGuiPulls"),
                        "missingDb": (master_verify or {}).get("missingDb"),
                        "guiExportIds": (master_verify or {}).get("guiExportIds"),
                    }
                    if master_verify
                    else None,
                    "reply": reply,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/unified/snapshot")
    def apex_unified_snapshot():
        try:
            from apex_unified_db_pack import orchestrator_context_snapshot

            result = orchestrator_context_snapshot(limit=12)
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/should-wave")
    def apex_should_wave_status():
        try:
            from apex_orchestrator_polish_pack import should_wave_status

            result = should_wave_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/insight-latest")
    def apex_insight_latest():
        try:
            from apex_insight_sse_pack import insight_latest_payload

            result = insight_latest_payload()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/insight-stream")
    def apex_insight_stream():
        """Server-Sent Events for live AI insight widget updates."""
        import bottle
        from apex_insight_sse_pack import insight_sse_frames

        watch = 0.0
        try:
            watch = float(bottle.request.query.get("watch") or 0)
        except (TypeError, ValueError):
            watch = 0.0
        watch = max(0.0, min(watch, 30.0))
        bottle.response.content_type = "text/event-stream; charset=utf-8"
        bottle.response.set_header("Cache-Control", "no-cache")
        bottle.response.set_header("X-Accel-Buffering", "no")
        return insight_sse_frames(watch_seconds=watch)

    @app.get("/api/apex/hal/insight-sse-status")
    def apex_insight_sse_status():
        try:
            from apex_insight_sse_pack import sse_status

            result = sse_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/health-audit")
    def apex_health_audit():
        try:
            import bottle
            from apex_health_monitor_pack import run_scheduled_health_audit

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            classify_only = bool(payload.get("classifyOnly") or payload.get("classify_only"))
            result = run_scheduled_health_audit(classify_only=classify_only)
            result["buildId"] = BUILD_ID
            status = 200 if result.get("ok") or result.get("reason") == "orchestrator_disabled" else 400
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/deep-audit-status")
    def apex_deep_audit_status():
        """Phase U0 — deep audit / forecast status."""
        try:
            from apex_deep_audit_pack import deep_audit_status

            result = deep_audit_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/deep-audit")
    def apex_deep_audit():
        """Phase U0 — monthly practice health audit (30B / classify-only)."""
        try:
            import bottle
            from apex_deep_audit_pack import generate_monthly_audit

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            classify_only = bool(payload.get("classifyOnly") or payload.get("classify_only"))
            period = payload.get("period")
            result = generate_monthly_audit(
                period=str(period) if period else None,
                classify_only=classify_only,
            )
            result["buildId"] = BUILD_ID
            status = (
                200
                if result.get("ok")
                or result.get("reason") in {"orchestrator_disabled", "deep_audit_disabled"}
                else 400
            )
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/deep-forecast")
    def apex_deep_forecast():
        """Phase U0 — quarter forecast scaffold (null future $ until 30B)."""
        try:
            import bottle
            from apex_deep_audit_pack import forecast_next_quarter

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            classify_only = bool(payload.get("classifyOnly") or payload.get("classify_only"))
            period = payload.get("period")
            result = forecast_next_quarter(
                period=str(period) if period else None,
                classify_only=classify_only,
            )
            result["buildId"] = BUILD_ID
            status = (
                200
                if result.get("ok")
                or result.get("reason") in {"orchestrator_disabled", "deep_audit_disabled"}
                else 400
            )
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/cache-warm-status")
    def apex_hal_cache_warm_status():
        """REC-007 HAL model keep-alive / prompt-warm status (telemetry)."""
        try:
            from apex_hal_cache_warm_pack import warm_status

            result = warm_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/hal/cache-warm")
    def apex_hal_cache_warm_run():
        """Trigger HAL local model warm (optional CAS/payer lists). Background by default."""
        try:
            import bottle
            from apex_hal_cache_warm_pack import warm_hal_cache

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            try:
                payload = json.loads(raw or "{}")
            except Exception:
                payload = {}
            background = payload.get("background", True)
            result = warm_hal_cache(
                payer_labels=list(payload.get("payerLabels") or payload.get("payers") or [])[:6],
                cas_codes=list(payload.get("casCodes") or [])[:8],
                background=bool(background),
            )
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/hal/era835-status")
    def apex_era835_status():
        try:
            from apex_era835_pack import era835_status

            result = era835_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/era-inbox/status")
    def apex_era_inbox_status():
        """hal-10576 — ERA-835 drop-box status + mutation-auth contract (empty ≠ $0)."""
        try:
            from apex_era835_pack import era_inbox_status
            from nr2_browser_security import (
                era_inbox_mutation_contract,
                request_mutation_token_if_bound,
            )

            result = era_inbox_status(ensure_dirs=True)
            token = None
            try:
                token = request_mutation_token_if_bound()
            except Exception:
                token = None
            # Always expose CSRF contract; attach live token when request already bound.
            result.update(era_inbox_mutation_contract(mutation_token=token))
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/era-inbox/ingest")
    def apex_era_inbox_ingest():
        """hal-10576 — ingest ERA drop-box (requires X-NR2-Session-Token in browser; empty ≠ $0)."""
        try:
            from apex_era835_pack import ingest_era_inbox

            result = ingest_era_inbox(ensure_dirs=True)
            result["buildId"] = BUILD_ID
            result["softDentWriteBack"] = False
            result["writeBack"] = False
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/era-inbox/discover")
    def apex_era_inbox_discover_get():
        """hal-10576 — read-only remittance discovery across SoftDent/export roots."""
        try:
            from apex_era835_pack import discover_era_candidates

            result = discover_era_candidates()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/era-inbox/discover")
    def apex_era_inbox_discover_post():
        """hal-10576 — same discovery via CSRF session POST (UI Scan for ERA Files)."""
        try:
            from apex_era835_pack import discover_era_candidates

            result = discover_era_candidates()
            result["buildId"] = BUILD_ID
            result["writeBack"] = False
            result["softDentWriteBack"] = False
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/collections-export/health")
    def apex_collections_export_health():
        """hal-10576 — Collections/Register Excel-temp readability (empty ≠ $0; no write-back)."""
        try:
            from softdent_excel_temp import collections_export_health

            result = collections_export_health()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/era835-payments")
    def apex_era835_payments():
        try:
            from apex_era835_pack import list_era835_payments

            rows = list_era835_payments(limit=50)
            return json_response_fn(
                {"ok": True, "phase": "U1", "rows": rows, "buildId": BUILD_ID}
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/era835-ingest")
    def apex_era835_ingest():
        """Phase U1 — parse ERA 835 EDI/CSV into payer aggregates (no PHI)."""
        try:
            import bottle
            from apex_era835_pack import ingest_era835_to_unified

            upload = bottle.request.files.get("file") if bottle.request.files else None
            text = ""
            filename = None
            if upload is not None:
                filename = str(getattr(upload, "filename", None) or "era.835")
                text = upload.file.read().decode("utf-8", errors="replace")
            else:
                raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                try:
                    payload = json.loads(raw or "{}")
                except Exception:
                    payload = {"text": raw}
                text = str(payload.get("text") or payload.get("content") or "")
                filename = payload.get("filename")
            result = ingest_era835_to_unified(content=text, filename=filename)
            result["buildId"] = BUILD_ID
            status = (
                200
                if result.get("ok")
                or result.get("reason") == "era835_disabled"
                or result.get("gap") == "ERA835_PENDING"
                else 400
            )
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/reconciliation-status")
    def apex_reconciliation_status():
        try:
            from apex_reconciliation_pack import reconciliation_status

            result = reconciliation_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/extended-metrics-status")
    def apex_extended_metrics_status():
        """Phase W0 — SoftDent case acceptance / aging / scheduling views."""
        try:
            from apex_softdent_extended_pack import extended_metrics_status

            result = extended_metrics_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/reconciliation")
    def apex_reconciliation_run():
        """Phase U2 — SoftDent×QB variance scan (+ optional 30B explainer)."""
        try:
            import bottle
            from apex_reconciliation_pack import run_reconciliation

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            classify_only = bool(payload.get("classifyOnly") or payload.get("classify_only"))
            explain = payload.get("explain")
            if explain is None:
                explain = True
            period = payload.get("period")
            result = run_reconciliation(
                period=str(period) if period else None,
                classify_only=classify_only,
                explain=bool(explain),
            )
            result["buildId"] = BUILD_ID
            status = (
                200
                if result.get("ok") or result.get("reason") == "reconciliation_disabled"
                else 400
            )
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/import-quarantine-status")
    def apex_import_quarantine_status():
        try:
            from apex_import_quarantine_pack import quarantine_status

            result = quarantine_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/import-quarantine")
    def apex_import_quarantine_list():
        try:
            from apex_import_quarantine_pack import list_quarantine

            rows = list_quarantine(limit=50)
            return json_response_fn(
                {"ok": True, "phase": "U2b+W2", "rows": rows, "buildId": BUILD_ID}
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/import-quarantine-release")
    def apex_import_quarantine_release():
        try:
            import bottle
            from apex_import_quarantine_pack import release_quarantine

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            name = str(payload.get("name") or payload.get("file") or "")
            result = release_quarantine(name)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/import-quarantine-retry")
    def apex_import_quarantine_retry():
        """Phase W2 — release quarantined file and re-queue ingest."""
        try:
            import bottle
            from apex_import_quarantine_pack import retry_quarantine

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            name = str(payload.get("name") or payload.get("file") or "")
            result = retry_quarantine(name)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/import-quarantine-purge")
    def apex_import_quarantine_purge():
        """Phase W2 — permanently delete quarantined local copy (+ reason sidecar)."""
        try:
            import bottle
            from apex_import_quarantine_pack import purge_quarantine

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            name = str(payload.get("name") or payload.get("file") or "")
            result = purge_quarantine(name)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/dashboard-layout")
    def apex_dashboard_layout_get():
        try:
            import bottle
            from apex_dashboard_layout_pack import get_layout

            page = str(bottle.request.query.get("page") or "financial")
            result = get_layout(page)
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/dashboard-layout")
    def apex_dashboard_layout_save():
        try:
            import bottle
            from apex_dashboard_layout_pack import save_layout

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            page = payload.get("page")
            layout = payload.get("layout") if isinstance(payload.get("layout"), dict) else payload
            result = save_layout(layout, page=str(page) if page else None)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/dashboard-layout-reset")
    def apex_dashboard_layout_reset():
        try:
            import bottle
            from apex_dashboard_layout_pack import reset_layout

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            page = str(payload.get("page") or "financial")
            result = reset_layout(page)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/ai-lane-health")
    def apex_ai_lane_health():
        """Phase V0 — 8B/30B latency & error counters (no PHI)."""
        try:
            from apex_ai_telemetry_pack import lane_health, maybe_emit_telemetry_alert

            result = lane_health()
            if result.get("alertLanes"):
                result["alert"] = maybe_emit_telemetry_alert(result)
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/sync-status")
    def apex_sync_status():
        """Phase V0 — SoftDent/QB/ERA last-import freshness chips."""
        try:
            from apex_sync_status_pack import build_sync_status

            _reports, bundle, _err = _load_reports_and_bundle()
            result = build_sync_status(bundle=bundle)
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/import-watcher-status")
    def apex_import_watcher_status():
        """Phase T3 — import inbox poll/watcher status."""
        try:
            from apex_import_watcher_pack import watcher_status

            result = watcher_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/import-cron-status")
    def apex_import_cron_status():
        """Phase W1 — import cron + DQ status."""
        try:
            from apex_import_scheduler_pack import import_cron_status

            result = import_cron_status()
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/import-cron-run")
    def apex_import_cron_run():
        """Phase W1 — one-shot cron tick (honors NR2_IMPORT_CRON unless force)."""
        try:
            import bottle
            from apex_import_scheduler_pack import run_import_cron_once

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            force = bool(payload.get("force"))
            result = run_import_cron_once(force=force)
            result["buildId"] = BUILD_ID
            log = result.get("log") if isinstance(result.get("log"), dict) else result
            status = 200
            if isinstance(log, dict) and log.get("reason") == "import_cron_disabled":
                status = 400
            elif isinstance(log, dict) and int(log.get("exit") or 0) not in {0, 2}:
                status = 400
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/hal/import-dq-status")
    def apex_import_dq_status():
        """Phase W1 — DQ flag + optional live bundle check."""
        try:
            from apex_import_dq_pack import dq_status, validate_bundle_dq

            result = dq_status()
            _reports, bundle, _err = _load_reports_and_bundle()
            result["live"] = validate_bundle_dq(bundle if isinstance(bundle, dict) else {})
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/hal/import-poll")
    def apex_import_poll():
        """Phase T3 — one-shot import inbox poll (debounce + ingest)."""
        try:
            import bottle
            from apex_import_watcher_pack import poll_once

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            since = payload.get("sinceMtime")
            if since is None:
                since = payload.get("since_mtime")
            result = poll_once(since_mtime=float(since) if since is not None else None)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/unified/ingest")
    def apex_unified_ingest():
        try:
            from apex_unified_db_pack import ingest_from_bundle

            _reports, bundle, _err = _load_reports_and_bundle()
            result = ingest_from_bundle(bundle)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/ticker")
    def apex_ticker_api():
        try:
            return json_response_fn(build_apex_ticker())
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"items": [], "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/claims-aging")
    def apex_claims_aging_api():
        try:
            return json_response_fn(apex_claims_aging_payload())
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buckets": {}}, status=500)

    @app.get("/api/apex/widget-census/<page_id>")
    def apex_widget_census_api(page_id: str):
        try:
            if str(page_id or "").lower() in {"all", "*", "program"}:
                return json_response_fn(build_all_pages_widget_census())
            return json_response_fn(build_page_widget_census(page_id))
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/widget-census")
    def apex_widget_census_all_api():
        try:
            return json_response_fn(build_all_pages_widget_census())
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/treatment-planning/status")
    def apex_treatment_planning_status_api():
        try:
            from softdent_treatment_planning import treatment_planning_status

            return json_response_fn({"ok": True, **treatment_planning_status(), "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/treatment-planning/estimate")
    def apex_treatment_planning_estimate_api():
        try:
            import bottle

            from softdent_treatment_planning import (
                build_tp_estimate_chip,
                format_treatment_estimate_reply,
                log_tp_estimate_audit,
                lookup_treatment_estimate,
            )

            payer = str(bottle.request.query.get("payer") or "").strip()
            ada = str(bottle.request.query.get("ada") or bottle.request.query.get("adaCode") or "").strip()
            include_inferred = str(bottle.request.query.get("includeInferred") or "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            if include_inferred:
                # Opt-in inferred: use spine fallback path with include_inferred via direct call
                from softdent_treatment_planning import _ledger_spine_treatment_fallback
                from softdent_treatment_planning import resolve_analytics_db
                from pathlib import Path as _Path

                db = resolve_analytics_db()
                if db:
                    est = _ledger_spine_treatment_fallback(
                        payer=payer, ada_code=ada, db_path=_Path(db), include_inferred=True
                    )
                    est["chip"] = build_tp_estimate_chip(est)
                    est["def"] = "HAL-10587"
                else:
                    est = lookup_treatment_estimate(payer=payer, ada_code=ada)
            else:
                est = lookup_treatment_estimate(payer=payer, ada_code=ada)
            chip = est.get("chip") if isinstance(est.get("chip"), dict) else build_tp_estimate_chip(est)
            log_tp_estimate_audit(est, source="api")
            return json_response_fn(
                {
                    "ok": bool(est.get("ok")),
                    "result": est,
                    "chip": chip,
                    "reply": format_treatment_estimate_reply(est),
                    "honesty": "empty != $0; not a benefits guarantee",
                    "def": "HAL-10587",
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/gold-payment-pipeline/status")
    def apex_gold_payment_pipeline_status_api():
        try:
            from softdent_gold_payment_pipeline import (
                audit_gold_payment_pipeline,
                format_gold_pipeline_reply,
            )

            st = audit_gold_payment_pipeline()
            return json_response_fn(
                {
                    "ok": bool(st.get("ok")),
                    **st,
                    "reply": format_gold_pipeline_reply(st),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/gold-payment-pipeline/repair")
    def apex_gold_payment_pipeline_repair_api():
        try:
            from softdent_gold_payment_pipeline import run_gold_payment_pipeline_repair

            result = run_gold_payment_pipeline_repair()
            return json_response_fn({**result, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/gold-csv-drop-ops/status")
    def apex_gold_csv_drop_ops_status_api():
        try:
            from softdent_gold_csv_drop_ops import (
                checklist_post_ingest,
                format_gold_csv_drop_ops_reply,
                gold_csv_drop_playbook,
            )

            st = checklist_post_ingest()
            return json_response_fn(
                {
                    "ok": bool(st.get("ok")),
                    **st,
                    "playbook": gold_csv_drop_playbook(),
                    "reply": format_gold_csv_drop_ops_reply({"post": st}),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/gold-csv-drop-ops/run")
    def apex_gold_csv_drop_ops_run_api():
        try:
            from softdent_gold_csv_drop_ops import run_ops_10589_gold_csv_drop

            # Default: no GUI from HTTP (operator/desktop owns SoftDent focus)
            result = run_ops_10589_gold_csv_drop(attempt_gui_export=False)
            return json_response_fn({**result, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/gold-drop-facilitation/status")
    def apex_gold_drop_facilitation_status_api():
        try:
            from softdent_gold_drop_facilitation_hal10606 import (
                format_hal10606_reply,
                gold_drop_facilitation_playbook,
                settlement_matrix_gate,
                staff_briefing,
                verify_export_path_writable,
            )
            from softdent_gold_payment_pipeline import audit_gold_payment_pipeline

            audit = audit_gold_payment_pipeline()
            matrix = settlement_matrix_gate()
            path = verify_export_path_writable()
            if matrix.get("steps"):
                matrix["steps"][0] = {
                    "id": "export_path_writable",
                    "ok": bool(path.get("ok")),
                    "detail": path.get("path") if path.get("ok") else path.get("error"),
                }
                matrix["passCount"] = sum(1 for s in matrix["steps"] if s["ok"])
            payload = {
                "ok": True,
                "def": "HAL-10606",
                "audit": {
                    "gapCode": audit.get("gapCode"),
                    "paymentLines": audit.get("paymentLines"),
                    "newestPaymentCsv": audit.get("newestPaymentCsv"),
                },
                "exportPath": path,
                "matrixGate": matrix,
                "playbook": gold_drop_facilitation_playbook(),
                "staffBriefing": staff_briefing(),
                "reply": format_hal10606_reply(
                    {
                        "acceptance": {
                            "gapCode": audit.get("gapCode"),
                            "paymentLines": audit.get("paymentLines"),
                            "matrixCells": (matrix.get("matrix") or {}).get("matrixCells"),
                            "cellsNge10": (matrix.get("matrix") or {}).get("cellsNge10"),
                            "acceptanceGateMet": (matrix.get("matrix") or {}).get(
                                "acceptanceGateMet"
                            ),
                            "blockedReason": (
                                None
                                if audit.get("gapCode") == "GOLD_OK"
                                else "GOLD_CSV_MISSING — drop real line-item CSV; Print Preview ≠ gold"
                            ),
                        }
                    }
                ),
                "buildId": BUILD_ID,
            }
            return json_response_fn(payload)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/gold-drop-facilitation/run")
    def apex_gold_drop_facilitation_run_api():
        try:
            from softdent_gold_drop_facilitation_hal10606 import (
                run_ops_10606_gold_drop_facilitation,
            )

            result = run_ops_10606_gold_drop_facilitation(attempt_gui_export=False)
            return json_response_fn({**result, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/pwimages-eligibility/status")
    def apex_pwimages_eligibility_status_api():
        try:
            from softdent_pwimages_eligibility_hal10607 import (
                format_hal10607_reply,
                pwimages_eligibility_status,
            )

            st = pwimages_eligibility_status()
            return json_response_fn(
                {
                    **st,
                    "reply": format_hal10607_reply(st),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/pwimages-eligibility/run")
    def apex_pwimages_eligibility_run_api():
        try:
            from softdent_pwimages_eligibility_hal10607 import (
                format_hal10607_reply,
                run_hal10607_ingest,
            )

            result = run_hal10607_ingest()
            result["reply"] = format_hal10607_reply(result)
            return json_response_fn({**result, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/gold-era-settlement/status")
    def apex_gold_era_settlement_status_api():
        try:
            from softdent_gold_era_settlement_hal10608 import (
                format_hal10608_reply,
                gold_era_settlement_status,
            )

            st = gold_era_settlement_status()
            return json_response_fn(
                {
                    **st,
                    "reply": format_hal10608_reply(st),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/gold-era-settlement/run")
    def apex_gold_era_settlement_run_api():
        try:
            from softdent_gold_era_settlement_hal10608 import (
                format_hal10608_reply,
                run_ops_10608_gold_era_settlement,
            )

            result = run_ops_10608_gold_era_settlement()
            result["reply"] = format_hal10608_reply(result)
            return json_response_fn({**result, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/prodbyada/status")
    def apex_prodbyada_status_api():
        try:
            from softdent_prodbyada_xls_ingest import find_prodbyada_xls, format_prodbyada_reply

            path = find_prodbyada_xls()
            payload = {
                "ok": True,
                "def": "HAL-10609",
                "found": bool(path),
                "path": str(path) if path else None,
                "inventedGold": False,
                "writesPaymentLines": False,
                "honesty": (
                    "PRODBYADA.xls = SoftDent CODE rollups; NOT InsCo×ADA gold; "
                    "empty != $0"
                ),
            }
            payload["reply"] = (
                f"PRODBYADA: {'found ' + str(path) if path else 'missing'}. "
                "Not gold. empty != $0."
            )
            return json_response_fn({**payload, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/prodbyada/run")
    def apex_prodbyada_run_api():
        try:
            from softdent_prodbyada_xls_ingest import (
                format_prodbyada_reply,
                ingest_prodbyada_xls,
            )

            result = ingest_prodbyada_xls()
            result["reply"] = format_prodbyada_reply(result)
            return json_response_fn({**result, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/print-preview-audit/status")
    def apex_print_preview_audit_status_api():
        try:
            from softdent_print_preview_audit import (
                format_print_preview_audit_reply,
                list_print_preview_audits,
            )

            st = list_print_preview_audits()
            return json_response_fn(
                {
                    "ok": True,
                    **st,
                    "reply": format_print_preview_audit_reply(st),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/print-preview-audit/record")
    def apex_print_preview_audit_record_api():
        try:
            import bottle

            from softdent_print_preview_audit import append_print_preview_audit

            body = bottle.request.json if getattr(bottle.request, "json", None) else {}
            if not isinstance(body, dict):
                body = {}
            result = append_print_preview_audit(body)
            status = 400 if not result.get("ok") else 200
            return json_response_fn({**result, "buildId": BUILD_ID}, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/print-preview-audit/run")
    def apex_print_preview_audit_run_api():
        try:
            import bottle

            from softdent_print_preview_audit import run_ops_10590_print_preview_audit

            body = bottle.request.json if getattr(bottle.request, "json", None) else {}
            if not isinstance(body, dict):
                body = {}
            result = run_ops_10590_print_preview_audit(body or None)
            return json_response_fn({**result, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/ui-honesty/status")
    def apex_ui_honesty_status_api():
        try:
            from ui_honesty_policy import (
                audit_ui_honesty_surfaces,
                format_honesty_audit_reply,
            )

            result = audit_ui_honesty_surfaces()
            return json_response_fn(
                {
                    **result,
                    "reply": format_honesty_audit_reply(result),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/reconciliation/visual-ledger/status")
    def apex_visual_ledger_recon_status_api():
        try:
            import bottle

            from softdent_visual_ledger_recon import (
                format_visual_ledger_recon_reply,
                reconcile_visual_vs_ledger,
            )

            period = None
            try:
                period = bottle.request.query.get("period")  # type: ignore[attr-defined]
            except Exception:
                period = None
            result = reconcile_visual_vs_ledger(period=period or None)
            return json_response_fn(
                {
                    **result,
                    "reply": format_visual_ledger_recon_reply(result),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/apex/reconciliation/visual-ledger/run")
    def apex_visual_ledger_recon_run_api():
        try:
            import bottle

            from softdent_visual_ledger_recon import run_ops_10593_visual_ledger_recon

            body = bottle.request.json if getattr(bottle.request, "json", None) else {}
            if not isinstance(body, dict):
                body = {}
            result = run_ops_10593_visual_ledger_recon(period=body.get("period"))
            return json_response_fn({**result, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/reconciliation/visual-ledger/history")
    def apex_visual_ledger_recon_history_api():
        try:
            import bottle

            from softdent_visual_ledger_recon import list_recon_variance_history

            months = 3
            try:
                raw_m = bottle.request.query.get("months")  # type: ignore[attr-defined]
                if raw_m is not None and str(raw_m).strip() != "":
                    months = max(1, min(24, int(raw_m)))
            except Exception:
                months = 3
            result = list_recon_variance_history(months=months)
            # HAL-10595: rows include totalCents / *Cents; float totals deprecated
            return json_response_fn({**result, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/insco-ada-estimates/status")
    def apex_insco_ada_estimates_status_api():
        try:
            from softdent_insco_ada_probabilistic import (
                format_probabilistic_status_reply,
                probabilistic_report_status,
            )

            st = probabilistic_report_status()
            return json_response_fn(
                {
                    "ok": True,
                    **st,
                    "reply": format_probabilistic_status_reply(st),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/insco-ada-estimates/estimate")
    def apex_insco_ada_estimates_estimate_api():
        try:
            import bottle

            from softdent_insco_ada_probabilistic import (
                format_probabilistic_estimate_reply,
                log_inferred_view_audit,
                lookup_probabilistic_estimate,
            )

            payer = str(bottle.request.query.get("payer") or "").strip()
            ada = str(
                bottle.request.query.get("ada") or bottle.request.query.get("adaCode") or ""
            ).strip()
            include_inferred = str(bottle.request.query.get("includeInferred") or "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            est = lookup_probabilistic_estimate(
                payer=payer, ada_code=ada, include_inferred=include_inferred
            )
            if include_inferred:
                log_inferred_view_audit(payer=payer, ada=ada, source="api")
            if not est:
                return json_response_fn(
                    {
                        "ok": True,
                        "status": "insufficient_data",
                        "n": 0,
                        "estimate": None,
                        "includeInferred": include_inferred,
                        "reply": format_probabilistic_estimate_reply(
                            None, payer=payer, ada=ada, include_inferred=include_inferred
                        ),
                        "buildId": BUILD_ID,
                        "honesty": "empty != $0",
                    }
                )
            return json_response_fn(
                {
                    "ok": True,
                    "status": "ok",
                    "estimate": est,
                    "includeInferred": include_inferred,
                    "reply": format_probabilistic_estimate_reply(
                        est, payer=payer, ada=ada, include_inferred=include_inferred
                    ),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/insco-ada-pct-variance/status")
    def apex_insco_ada_pct_variance_status_api():
        try:
            from softdent_insco_ada_pct_variance import (
                format_pct_variance_status_reply,
                pct_variance_status,
            )

            st = pct_variance_status()
            return json_response_fn(
                {
                    "ok": bool(st.get("ok")),
                    **st,
                    "reply": format_pct_variance_status_reply(st),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/insco-ada-pct-variance/lookup")
    def apex_insco_ada_pct_variance_lookup_api():
        try:
            import bottle

            from softdent_insco_ada_pct_variance import (
                format_pct_variance_reply,
                lookup_pct_variance,
            )

            payer = str(bottle.request.query.get("payer") or "").strip()
            ada = str(
                bottle.request.query.get("ada") or bottle.request.query.get("adaCode") or ""
            ).strip()
            include_inferred = str(bottle.request.query.get("includeInferred") or "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            row = lookup_pct_variance(payer=payer, ada_code=ada, include_inferred=include_inferred)
            return json_response_fn(
                {
                    "ok": True,
                    "status": "ok" if row else "insufficient_data",
                    "result": row,
                    "includeInferred": include_inferred,
                    "reply": format_pct_variance_reply(row, payer=payer, ada=ada),
                    "buildId": BUILD_ID,
                    "honesty": "empty != $0; code 2/51 episode pairing; +/- 1 SD",
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/insco-ada-catalog/status")
    def apex_insco_ada_catalog_status_api():
        try:
            from softdent_insco_ada_catalog_matrix import (
                catalog_matrix_status,
                format_catalog_status_reply,
            )

            st = catalog_matrix_status()
            return json_response_fn(
                {
                    "ok": bool(st.get("ok")),
                    **st,
                    "reply": format_catalog_status_reply(st),
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/insco-ada-catalog")
    def apex_insco_ada_catalog_api():
        try:
            import bottle

            from softdent_insco_ada_catalog_matrix import (
                PACKAGE_BUILD_ID,
                DEF_ID as CATALOG_DEF,
                catalog_matrix_status,
                export_catalog_matrix_report,
                list_catalog_matrix_rows,
                list_ledger_cdt_universe,
                uncovered_ledger_cdts,
            )

            q = bottle.request.query
            include_insufficient = str(q.get("includeInsufficient") or "1").strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }
            include_inferred = str(q.get("includeInferred") or "1").strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }
            try:
                limit = int(q.get("limit") or 500)
            except (TypeError, ValueError):
                limit = 500
            try:
                offset = int(q.get("offset") or 0)
            except (TypeError, ValueError):
                offset = 0
            export_now = str(q.get("export") or "").strip().lower() in {"1", "true", "yes", "csv"}
            export_meta = {}
            if export_now:
                export_meta = export_catalog_matrix_report()
            st = catalog_matrix_status()
            rows = list_catalog_matrix_rows(
                include_insufficient=include_insufficient,
                include_inferred=include_inferred,
                credibility=str(q.get("credibility") or "").strip() or None,
                payer=str(q.get("payer") or "").strip() or None,
                ada=str(q.get("ada") or q.get("adaCode") or "").strip() or None,
                limit=limit,
                offset=offset,
            )
            w = None
            try:
                from softdent_insco_ada_catalog_matrix import insco_ada_catalog_widget

                w = insco_ada_catalog_widget()
            except Exception:
                w = {}
            return json_response_fn(
                {
                    "ok": True,
                    "def": CATALOG_DEF,
                    "packageBuildId": PACKAGE_BUILD_ID,
                    "count": len(rows),
                    "includeInsufficient": include_insufficient,
                    "includeInferred": include_inferred,
                    "cells": rows,
                    "totalCells": st.get("totalCells"),
                    "exactUsableCells": st.get("exactUsableCells"),
                    "insufficientCells": st.get("insufficientCells"),
                    "ledgerCdtUniverseCount": len(list_ledger_cdt_universe()),
                    "uncoveredCount": len(uncovered_ledger_cdts()),
                    "csvPath": (export_meta.get("csvPath") if export_meta else None)
                    or (w or {}).get("csvPath"),
                    "inboxCsvPath": (export_meta.get("inboxCsvPath") if export_meta else None)
                    or (w or {}).get("inboxCsvPath"),
                    "floatMoneyDeprecated": True,
                    "honesty": "empty != $0; insufficient cells are not invented zeros",
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/softdent/ledger")
    def apex_softdent_ledger_api():
        """Read-only TXN Excel JSONL ledger — empty≠$0; filters: account_num, patient_name, date_range."""
        try:
            import bottle

            from apex_better_backend_widgets_pack import build_transaction_ledger_table

            q = bottle.request.query
            account_num = str(q.get("account_num") or q.get("account") or "").strip() or None
            patient_name = str(q.get("patient_name") or q.get("patient") or "").strip() or None
            date_range = str(q.get("date_range") or q.get("period") or "").strip() or None
            try:
                limit = int(q.get("limit") or 40)
            except (TypeError, ValueError):
                limit = 40
            widget = build_transaction_ledger_table(
                {},
                page="softdent",
                account_num=account_num,
                patient_name=patient_name,
                date_range=date_range,
                limit=limit,
            )
            return json_response_fn(
                {
                    "ok": True,
                    "buildId": BUILD_ID,
                    "widget": widget,
                    "emptyState": bool(widget.get("emptyState") or widget.get("status") == "empty"),
                    "matchCount": widget.get("matchCount") or 0,
                    "filters": widget.get("filters") or {},
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/patient-dossier/<patient_id>")
    def apex_patient_dossier_api(patient_id: str):
        """HAL mega-dossier — SoftDent READ-ONLY, empty≠$0, RBAC read_patient_dossier."""
        try:
            import bottle
            from nr2_rbac import current_role, has_capability
            from patient_dossier import (
                build_patient_dossier,
                check_rate_limit,
                format_dossier_markdown,
                summarize_dossier_with_local_ai,
            )
            from hal_patient_audit import log_patient_query

            if not (
                has_capability("read_patient_dossier")
                or has_capability("read_all")
                or has_capability("*")
            ):
                return json_response_fn(
                    {
                        "ok": False,
                        "error": "Permission denied: patient dossier. Contact office manager.",
                        "capability": "read_patient_dossier",
                        "role": current_role(),
                        "buildId": BUILD_ID,
                    },
                    status=403,
                )

            session_id = str(
                bottle.request.headers.get("X-NR2-Session-Token")
                or bottle.request.query.get("session")
                or ""
            ).strip()
            allowed, retry_after = check_rate_limit(session_id or current_role())
            if not allowed:
                return json_response_fn(
                    {
                        "ok": False,
                        "error": "rate_limited",
                        "retryAfterSec": retry_after,
                        "buildId": BUILD_ID,
                    },
                    status=429,
                )

            practice = str(bottle.request.query.get("practiceId") or "").strip()
            do_summarize = str(bottle.request.query.get("summarize") or "").strip().lower() in (
                "1",
                "true",
                "yes",
            )
            member_id = str(bottle.request.query.get("memberId") or "").strip()
            payer_id = str(bottle.request.query.get("payerId") or "").strip()
            payer_name = str(bottle.request.query.get("payerName") or "").strip()
            provider_npi = str(bottle.request.query.get("providerNpi") or "").strip()
            fetch_eligibility = str(bottle.request.query.get("fetchEligibility") or "").strip().lower() in (
                "1",
                "true",
                "yes",
            )
            eligibility_overrides: dict[str, str] = {}
            if member_id:
                eligibility_overrides["memberId"] = member_id
            if payer_id:
                eligibility_overrides["payerId"] = payer_id
            if payer_name:
                eligibility_overrides["payerName"] = payer_name
            if provider_npi:
                eligibility_overrides["providerNpi"] = provider_npi
            dossier = build_patient_dossier(
                patient_id,
                practice_id=practice,
                eligibility_overrides=eligibility_overrides or None,
                force_eligibility_fetch=fetch_eligibility,
            )
            staff_id = str(bottle.request.headers.get("X-NR2-Staff-Id") or current_role() or "Staff")
            log_patient_query(staff_id, patient_id, "dossier_summary", session_id=session_id)
            if eligibility_overrides or fetch_eligibility:
                log_patient_query(staff_id, patient_id, "eligibility_query", session_id=session_id)

            payload: dict[str, Any] = {
                "ok": bool(dossier.get("ok", True)),
                "dossier": dossier,
                "summaryMarkdown": format_dossier_markdown(dossier),
                "buildId": BUILD_ID,
            }
            if do_summarize:
                ai = summarize_dossier_with_local_ai(dossier)
                payload["summary"] = ai.get("summary")
                payload["summarySource"] = ai.get("source")
                payload["summaryModel"] = ai.get("model")
                if ai.get("error"):
                    payload["summaryError"] = ai.get("error")
            return json_response_fn(payload)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/patient-dossier-mini/<patient_id>")
    def apex_patient_dossier_mini_api(patient_id: str):
        try:
            from nr2_rbac import current_role, has_capability
            from om_patient_dossier import get_patient_dossier_mini
            from hal_patient_audit import log_hal_patient_action
            from patient_dossier import patient_hash

            if not (
                has_capability("read_patient_dossier")
                or has_capability("read_all")
                or has_capability("*")
                or has_capability("read_schedule")
            ):
                return json_response_fn(
                    {"ok": False, "error": "capability_rejected", "role": current_role(), "buildId": BUILD_ID},
                    status=403,
                )
            mini = get_patient_dossier_mini(patient_id)
            log_hal_patient_action(
                user_id=current_role(),
                patient_hash=patient_hash(patient_id),
                action="query_summary",
                tools_used='["get_patient_dossier_mini"]',
            )
            mini["buildId"] = BUILD_ID
            return json_response_fn(mini)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.post("/api/audit/hal-patient-context")
    def apex_hal_patient_context_audit_api():
        try:
            import bottle
            from nr2_rbac import current_role
            from hal_patient_audit import log_hal_patient_action

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            ph = str(payload.get("patientHash") or payload.get("patient_hash") or "").strip()
            action = str(payload.get("action") or "set_context").strip()
            if not ph:
                return json_response_fn({"ok": False, "error": "patientHash required", "buildId": BUILD_ID}, status=400)
            log_hal_patient_action(
                user_id=str(payload.get("userId") or current_role()),
                patient_hash=ph,
                action=action,
                tools_used=str(payload.get("toolsUsed") or "[]"),
                ip=str(bottle.request.remote_addr or ""),
            )
            return json_response_fn({"ok": True, "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

    @app.get("/api/apex/export-playbook")
    def apex_export_playbook_api():
        try:
            return json_response_fn({"ok": True, "playbook": build_export_playbook(), "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/claims-aging/alerts")
    def apex_claims_aging_alerts_get():
        try:
            from apex_claims_narratives_pack import get_aging_alert_config

            return json_response_fn({"ok": True, "config": get_aging_alert_config(), "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/claims-aging/alerts")
    def apex_claims_aging_alerts_set():
        try:
            import bottle
            from apex_claims_narratives_pack import set_aging_alert_config

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            result = set_aging_alert_config(payload)
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/claims/actions")
    def apex_claim_actions_list():
        """Moonshot Expert SE Phase 3 REC-006 — list NR2-local claim card actions."""
        try:
            import bottle
            from apex_program_improve_pack import list_claim_actions

            cid = str(bottle.request.query.get("claimId") or "").strip() or None
            return json_response_fn(
                {"ok": True, "entries": list_claim_actions(cid), "buildId": BUILD_ID}
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "entries": []}, status=500)

    @app.post("/api/apex/claims/actions")
    def apex_claim_actions_post():
        """Moonshot Expert SE Phase 3 REC-006 — audit-log only (no SoftDent write-back)."""
        try:
            import bottle
            from apex_program_improve_pack import record_claim_action

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            result = record_claim_action(payload)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/claims/era-ingest")
    def apex_era_ingest_api():
        """Moonshot Expert SE Phase 3 REC-005 — ERA 835 upload → match → ERA Matched."""
        try:
            import bottle
            from apex_program_improve_pack import ingest_era_835

            upload = bottle.request.files.get("file") if bottle.request.files else None
            text = ""
            filename = None
            if upload is not None:
                filename = str(getattr(upload, "filename", None) or "era.835")
                text = upload.file.read().decode("utf-8", errors="replace")
            else:
                raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                try:
                    payload = json.loads(raw or "{}")
                except Exception:
                    payload = {"text": raw}
                text = str(payload.get("text") or payload.get("content") or "")
                filename = payload.get("filename")
            _reports, bundle, _err = _load_reports_and_bundle()
            rows = _section_rows(bundle, "softdent", "claims") or _section_rows(
                bundle, "softdent", "claimStatus"
            )
            result = ingest_era_835(text, rows if isinstance(rows, list) else [], filename=filename)
            result["buildId"] = BUILD_ID
            return json_response_fn(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/claims/era-summary")
    def apex_era_summary_api():
        """REC-005 depth — structured 835 remittance summary for HAL (no invented dollars)."""
        try:
            import bottle
            from era835_parser import parse_835_text, summarize_835_for_hal

            upload = bottle.request.files.get("file") if bottle.request.files else None
            text = ""
            if upload is not None:
                text = upload.file.read().decode("utf-8", errors="replace")
            else:
                raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                try:
                    payload = json.loads(raw or "{}")
                except Exception:
                    payload = {"text": raw}
                text = str(payload.get("text") or payload.get("content") or "")
            parsed = parse_835_text(text)
            summary = summarize_835_for_hal(parsed)
            summary["buildId"] = BUILD_ID
            summary["segmentCount"] = parsed.get("count")
            return json_response_fn(summary, status=200 if summary.get("ok") else 400)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/claims/<claim_id>")
    def apex_claim_detail_api(claim_id: str):
        try:
            return json_response_fn(apex_claim_detail(claim_id))
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/narratives/structure")
    def apex_narratives_structure_api():
        try:
            return json_response_fn(build_narrative_structure())
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "sections": []}, status=500)

    @app.post("/api/apex/narratives/context")
    def apex_narratives_context_api():
        try:
            import bottle

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            return json_response_fn(narrative_lock_context(payload))
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/hal/narrative-generate")
    def apex_hal_narrative_generate_api():
        try:
            import bottle

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            return json_response_fn(narrative_insurance_generate(payload))
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/narratives/audit")
    def apex_narratives_audit_api():
        try:
            import bottle
            from apex_claims_narratives_pack import list_narrative_audit

            limit = int(bottle.request.query.get("limit") or 40)
            return json_response_fn({"ok": True, "entries": list_narrative_audit(limit), "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "entries": []}, status=500)

    @app.get("/api/apex/narratives/payer-templates")
    def apex_payer_templates_list():
        try:
            from apex_claims_narratives_pack import list_payer_appeal_templates

            return json_response_fn(
                {"ok": True, "templates": list_payer_appeal_templates(), "buildId": BUILD_ID}
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "templates": []}, status=500)

    @app.post("/api/apex/narratives/payer-templates")
    def apex_payer_templates_save():
        try:
            import bottle
            from apex_claims_narratives_pack import save_payer_appeal_template

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            result = save_payer_appeal_template(payload)
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/narratives/generate")
    def apex_narratives_generate_api():
        try:
            import bottle

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            return json_response_fn(narrative_generate(payload))
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/narratives/batch-seed")
    def apex_narratives_batch_seed_api():
        try:
            import bottle
            from apex_program_improve_pack import batch_narrative_seed

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            ids = payload.get("claimIds") if isinstance(payload.get("claimIds"), list) else []
            result = batch_narrative_seed(ids, payer=str(payload.get("payer") or "") or None)
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/narratives/batch-generate")
    def apex_narratives_batch_generate_api():
        """REC-008: multi-claim appeal drafts + optional print packet."""
        try:
            import bottle

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            return json_response_fn(narrative_batch_generate(payload))
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/narratives/print-packet")
    def apex_narratives_print_api():
        try:
            import bottle

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            return json_response_fn(narrative_print_packet(payload))
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/narratives/packet/<job_id>")
    def apex_narratives_packet(job_id: str):
        import bottle

        packet = _NARRATIVE_PACKETS.get(str(job_id or ""))
        if not packet:
            bottle.response.status = 404
            bottle.response.content_type = "text/plain; charset=utf-8"
            return "Narrative packet not found or expired."
        bottle.response.content_type = "text/html; charset=utf-8"
        return packet.get("html") or ""

    @app.get("/api/apex/tax-returns")
    def apex_tax_returns_list():
        try:
            return json_response_fn(
                {
                    "ok": True,
                    "files": list_tax_returns(),
                    "buildId": BUILD_ID,
                    "rootHint": "app_data/nr2/document_library/tax_returns",
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "files": []}, status=500)

    @app.get("/api/apex/tax-returns/file")
    def apex_tax_returns_file():
        import bottle

        rel = str(bottle.request.query.get("path") or "").strip()
        target = resolve_tax_return_file(rel)
        if not target:
            bottle.response.status = 404
            bottle.response.content_type = "text/plain; charset=utf-8"
            return "Tax return not found."
        suffix = target.suffix.lower()
        ctype = "application/pdf" if suffix == ".pdf" else "application/octet-stream"
        bottle.response.content_type = ctype
        bottle.response.set_header("Content-Disposition", f'attachment; filename="{target.name}"')
        return target.read_bytes()

    @app.post("/api/apex/tax-returns/upload")
    def apex_tax_returns_upload():
        try:
            import bottle

            year = str(bottle.request.forms.get("year") or bottle.request.query.get("year") or "")
            jurisdiction = str(
                bottle.request.forms.get("jurisdiction") or bottle.request.query.get("jurisdiction") or "federal"
            )
            upload = bottle.request.files.get("file")
            if upload is None:
                return json_response_fn({"ok": False, "error": "file required"}, status=400)
            raw = upload.file.read() if hasattr(upload, "file") else upload.read()
            name = getattr(upload, "filename", None) or "return.pdf"
            saved = save_tax_return_upload(year=year, jurisdiction=jurisdiction, filename=str(name), data=raw)
            return json_response_fn(saved)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/tax/calculate-planning")
    def apex_tax_calculate_planning():
        try:
            import bottle
            from tax_engine import build_tax_plan

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            data = json.loads(raw or "{}")
            book = data.get("book_net_income")
            if book is None:
                # Fall back to live QB import
                _reports, bundle, _err = _load_reports_and_bundle()
                from tax_engine import build_tax_plan_from_bundle

                plan = build_tax_plan_from_bundle(bundle)
            else:
                plan = build_tax_plan(
                    book_net_income=book,
                    ebitda_add_backs=float(data.get("ebitda_add_backs") or 0),
                    modeled_officer_w2=data.get("modeled_officer_w2"),
                    tax_year=int(data.get("tax_year") or 2025),
                    period_label=str(data.get("period_label") or "manual"),
                )
            plan["disclaimer"] = "PLANNING ONLY — REQUIRES CPA REVIEW BEFORE FILING"
            plan["buildId"] = BUILD_ID
            return json_response_fn(plan)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/hal/board-actions")
    def apex_hal_board_actions_api():
        """Deterministic HAL board control — sync/focus/navigate only; never invents dollars."""
        try:
            import bottle

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(raw or "{}")
            return json_response_fn(resolve_hal_board_actions(payload))
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "handled": False, "error": str(exc), "actions": []}, status=500)

    @app.get("/api/apex/scenarios")
    def apex_scenarios_list():
        try:
            from apex_cpa_pack import list_scenarios

            return json_response_fn({"ok": True, "scenarios": list_scenarios(), "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "scenarios": []}, status=500)

    @app.post("/api/apex/scenarios/save")
    def apex_scenarios_save():
        try:
            import bottle
            from apex_cpa_pack import save_scenario

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            data = json.loads(raw or "{}")
            result = save_scenario(
                name=str(data.get("name") or "Scenario"),
                inputs=data.get("inputs") if isinstance(data.get("inputs"), dict) else {},
                book_net_income=data.get("bookNetIncome"),
                planning_ebitda=data.get("planningEbitda"),
                scenario_id=data.get("id"),
            )
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/scenarios/delete")
    def apex_scenarios_delete():
        try:
            import bottle
            from apex_cpa_pack import delete_scenario

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            data = json.loads(raw or "{}")
            result = delete_scenario(str(data.get("id") or ""))
            result["buildId"] = BUILD_ID
            status = 200 if result.get("ok") else 404
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/scenarios/compare")
    def apex_scenarios_compare():
        try:
            import bottle
            from apex_cpa_pack import compare_scenarios

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            data = json.loads(raw or "{}")
            ids = data.get("ids") if isinstance(data.get("ids"), list) else []
            result = compare_scenarios([str(i) for i in ids])
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/filing")
    def apex_filing_get():
        try:
            from apex_cpa_pack import get_filing_state

            return json_response_fn({"ok": True, **get_filing_state(), "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.post("/api/apex/filing/set")
    def apex_filing_set():
        try:
            import bottle
            from apex_cpa_pack import set_filing_state

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            data = json.loads(raw or "{}")
            result = set_filing_state(
                state=str(data.get("state") or ""),
                note=str(data.get("note") or ""),
                filed_rel_path=str(data.get("filedRelPath") or ""),
            )
            result["buildId"] = BUILD_ID
            status = 200 if result.get("ok") else 400
            return json_response_fn(result, status=status)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/audit")
    def apex_audit_list():
        try:
            import bottle
            from apex_cpa_pack import list_audit

            limit = int(bottle.request.query.get("limit") or 40)
            return json_response_fn({"ok": True, "entries": list_audit(limit), "buildId": BUILD_ID})
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "entries": []}, status=500)

    @app.post("/api/apex/workpapers/generate")
    def apex_workpapers_generate():
        try:
            import bottle
            from apex_cpa_pack import append_audit, build_workpaper_html, list_scenarios
            from tax_engine import build_tax_plan_from_bundle, compute_ebitda_walk

            raw = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            data = json.loads(raw or "{}")
            _reports, bundle, _err = _load_reports_and_bundle()
            plan = build_tax_plan_from_bundle(bundle) or {}
            walk = compute_ebitda_walk(bundle) or {}
            scenario = None
            sid = str(data.get("scenario_id") or data.get("scenarioId") or "").strip()
            if sid:
                for row in list_scenarios():
                    if row.get("id") == sid:
                        scenario = row
                        break
            html = build_workpaper_html(plan=plan, ebitda_walk=walk, scenario=scenario, build_id=BUILD_ID)
            job_id = f"wp_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
            _WORKPAPER_PACKETS[job_id] = {"html": html, "createdAt": _utc_now()}
            if len(_WORKPAPER_PACKETS) > 20:
                for old in list(_WORKPAPER_PACKETS.keys())[:10]:
                    _WORKPAPER_PACKETS.pop(old, None)
            append_audit("workpaper_generate", {"jobId": job_id, "scenarioId": sid or None})
            return json_response_fn(
                {
                    "ok": True,
                    "jobId": job_id,
                    "download_url": f"/api/apex/workpapers/packet/{job_id}",
                    "url": f"/api/apex/workpapers/packet/{job_id}",
                    "buildId": BUILD_ID,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc)}, status=500)

    @app.get("/api/apex/workpapers/packet/<job_id>")
    def apex_workpapers_packet(job_id: str):
        import bottle

        packet = _WORKPAPER_PACKETS.get(str(job_id or ""))
        if not packet:
            bottle.response.status = 404
            bottle.response.content_type = "text/plain; charset=utf-8"
            return "Workpaper not found or expired."
        bottle.response.content_type = "text/html; charset=utf-8"
        return packet.get("html") or ""

    @app.get("/api/apex/citations/qb")
    def apex_citations_qb():
        try:
            import bottle
            from apex_cpa_pack import list_qb_citation_rows

            key = str(bottle.request.query.get("key") or "").strip()
            _reports, bundle, _err = _load_reports_and_bundle()
            result = list_qb_citation_rows(bundle, key)
            result["buildId"] = BUILD_ID
            return json_response_fn(result)
        except Exception as exc:  # noqa: BLE001
            return json_response_fn(
                {"ok": False, "error": str(exc), "rows": [], "empty": True, "buildId": BUILD_ID},
                status=500,
            )

    @app.post("/api/apex/softdent/refresh-period")
    def apex_softdent_refresh_period():
        try:
            return json_response_fn(refresh_softdent_period_imports())
        except Exception as exc:  # noqa: BLE001
            return json_response_fn({"ok": False, "error": str(exc), "buildId": BUILD_ID}, status=500)

