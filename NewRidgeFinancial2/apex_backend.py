"""
NR2-Apex backend — widget feeds wrapping existing NR2 data layer.

All APEX_PAGES have dedicated builders fed by financial_reports + import_loader.
Never invent dollar amounts — missing fields become honest empty KPIs.
"""

from __future__ import annotations

import json
import random
import re
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
    "narratives",
    "documents",
    "library",
    "office-manager",
    "hal",
)

BUILD_ID = "hal-10484"

HAL_STATUS_SUGGESTION = (
    "Dictate findings: … · payer appeal templates · which widgets empty on all pages? · SoftDent sync"
)

# In-memory print packet store (session-local; browser print is primary)
_PRINT_PACKETS: dict[str, dict[str, Any]] = {}
_NARRATIVE_PACKETS: dict[str, dict[str, Any]] = {}
_WORKPAPER_PACKETS: dict[str, dict[str, Any]] = {}
_TICKER_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_TICKER_CACHE_TTL_SEC = 10.0


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
    return {
        "id": widget_id,
        "type": "kpi",
        "label": label,
        "value": None,
        "status": "empty",
        "emptyMessage": "No data",
        "hint": hint,
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
        "hint": hint,
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


def _load_reports_and_bundle() -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    reports: dict[str, Any] = {}
    bundle: dict[str, Any] = {}
    errors: list[str] = []

    try:
        from financial_reports import build_financial_reports

        reports = build_financial_reports(sync_exports=False)
    except Exception as exc:  # noqa: BLE001 — surface honest empty state
        errors.append(f"financial_reports: {exc}")
        reports = {}

    try:
        from import_loader import load_import_bundle

        bundle = load_import_bundle(sync=False, deep=False)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"import_loader: {exc}")
        bundle = {}

    return reports, bundle, errors


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
    widgets: list[dict[str, Any]] = []
    rows = _dashboard_rows(bundle)
    latest = _latest_period_row(rows)

    prod = _parse_money(latest.get("production")) if latest else None
    coll = None
    if latest:
        if latest.get("collectionsReported") is False or latest.get("collectionsPending") is True:
            coll = None
        elif "collections" in latest:
            coll = _parse_money(latest.get("collections"))

    if prod is not None:
        widgets.append(
            {
                "id": "prod-mtd",
                "type": "kpi",
                "label": "Production (latest period)",
                "value": prod,
                "unit": "money",
                "deltaLabel": str(latest.get("period") or latest.get("year_month") or ""),
                "sparkline": _spark_from_rows(rows, "production"),
                "hint": "From SoftDent dashboard import cache — not invented.",
            }
        )
    else:
        widgets.append(
            _empty_kpi(
                "prod-mtd",
                "Production (latest period)",
                hint="SoftDent dashboard production rows not loaded. Refresh imports.",
            )
        )

    if coll is not None:
        widgets.append(
            {
                "id": "collections-mtd",
                "type": "kpi",
                "label": "Collections (latest period)",
                "value": coll,
                "unit": "money",
                "deltaLabel": str(latest.get("period") or latest.get("year_month") or ""),
                "sparkline": _spark_from_rows(rows, "collections"),
                "hint": "From SoftDent dashboard import cache — not invented.",
            }
        )
    else:
        widgets.append(
            _empty_kpi(
                "collections-mtd",
                "Collections (latest period)",
                hint="Collections pending for latest SoftDent period — not reported as $0. Sync SoftDent collections/daysheet export.",
            )
        )

    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    ar_total = ar.get("totalOutstanding")
    if isinstance(ar_total, (int, float)):
        widgets.append(
            {
                "id": "ar-outstanding",
                "type": "kpi",
                "label": "A/R Outstanding",
                "value": float(ar_total),
                "unit": "money",
                "deltaLabel": f"90+ share {ar.get('ninetyPlusPct', 0)}%",
                "hint": str(ar.get("followUpHint") or "From SoftDent A/R import."),
            }
        )
    else:
        widgets.append(
            _empty_kpi(
                "ar-outstanding",
                "A/R Outstanding",
                hint="A/R aging import not available.",
            )
        )

    buckets = reports.get("arAgingBuckets") if isinstance(reports.get("arAgingBuckets"), list) else []
    series = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        amt = b.get("amount")
        if isinstance(amt, (int, float)):
            series.append({"label": str(b.get("bucket") or ""), "value": float(amt)})
    if series and any(s["value"] for s in series):
        widgets.append(
            {
                "id": "ar-aging-chart",
                "type": "chart",
                "chartType": "bar",
                "label": "A/R Aging",
                "series": series,
                "hint": "Buckets from SoftDent A/R import via financial_reports.",
            }
        )
    else:
        widgets.append(
            _empty_chart(
                "ar-aging-chart",
                "A/R Aging",
                hint="Import SoftDent A/R aging to populate this chart.",
            )
        )

    ct = reports.get("claimTracking") if isinstance(reports.get("claimTracking"), dict) else {}
    total_claims = ct.get("totalClaims")
    if isinstance(total_claims, int):
        widgets.append(
            {
                "id": "claims-total",
                "type": "kpi",
                "label": "Claims (import)",
                "value": total_claims,
                "unit": "count",
                "deltaLabel": f"Denied {ct.get('deniedCount', 0)}",
                "hint": str(ct.get("followUpHint") or "From SoftDent claims import."),
            }
        )
    else:
        widgets.append(
            _empty_kpi(
                "claims-total",
                "Claims (import)",
                hint="Claims import not available.",
            )
        )

    denied = ct.get("deniedCount")
    if isinstance(denied, int):
        widgets.append(
            {
                "id": "claims-denied",
                "type": "kpi",
                "label": "Denied Claims",
                "value": denied,
                "unit": "count",
                "deltaLabel": f"Aging 30+ {ct.get('deniedAgingPast30Days', 0)}",
                "hint": "Counts from SoftDent claims import — not invented.",
            }
        )

    tp = reports.get("treatmentPlans") if isinstance(reports.get("treatmentPlans"), dict) else {}
    ca = reports.get("caseAcceptance") if isinstance(reports.get("caseAcceptance"), dict) else {}
    widgets.append(
        {
            "id": "treatment-plans",
            "type": "kpi",
            "label": "Treatment Plans",
            "value": tp.get("rowCount") if tp.get("available") else None,
            "unit": "count",
            "status": "empty" if not tp.get("available") else "ok",
            "emptyMessage": "No data",
            "hint": "Practice export treatment plans." if tp.get("available") else "Treatment plan export not loaded.",
        }
    )
    widgets.append(
        {
            "id": "case-acceptance",
            "type": "kpi",
            "label": "Case Acceptance Rows",
            "value": ca.get("rowCount") if ca.get("available") else None,
            "unit": "count",
            "status": "empty" if not ca.get("available") else "ok",
            "emptyMessage": "No data",
            "hint": "Practice export case acceptance." if ca.get("available") else "Case acceptance export not loaded.",
        }
    )

    prod_vals = _spark_from_rows(rows, "production")
    if len(prod_vals) >= 2:
        widgets.append(
            {
                "id": "prod-trend",
                "type": "chart",
                "chartType": "line",
                "label": "Production Trend",
                "values": prod_vals,
                "hint": "Last periods from SoftDent dashboard import.",
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
        from apex_deep_audit_pack import deep_audit_widget

        widgets.append(deep_audit_widget(bundle))
    except Exception:
        pass
    try:
        from apex_reconciliation_pack import reconciliation_widget

        widgets.append(reconciliation_widget(bundle))
    except Exception:
        pass

    widgets[0:0] = _visual_boost_financial(reports, bundle)
    widgets.insert(0, build_period_scrubber(bundle, page="financial"))
    widgets.insert(0, build_import_freshness(bundle))
    widgets.append(build_provider_horizontal_bars(bundle))
    widgets.append(build_payer_donut(bundle))
    widgets.append(build_collection_bullet(bundle))
    widgets.append(build_ins_patient_split(bundle))
    widgets.append(build_ebitda_waterfall(bundle))
    widgets.append(build_ebitda_scrubber(bundle))
    # Threshold alert on A/R KPI when 90+ share > 20%
    for w in widgets:
        if isinstance(w, dict) and w.get("id") == "ar-outstanding":
            ninety_pct = ar.get("ninetyPlusPct")
            if isinstance(ninety_pct, (int, float)) and float(ninety_pct) > 20.0:
                w["alert"] = True
                w["alertReason"] = f"90+ share {float(ninety_pct):.1f}% exceeds 20%"
    _apply_threshold_alerts(widgets, reports)
    return widgets


def _taxes_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
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

    if has_book:
        widgets.append(
            _money_kpi(
                "tax-book-net",
                "Book Net Income",
                _parse_money(plan.get("bookNetIncome")),
                hint=f"From QuickBooks P&L import ({period or 'period unknown'}).",
                delta_label=period or None,
            )
        )
        widgets.append(
            _money_kpi(
                "tax-est-owner",
                "Est. Owner Tax (planning)",
                _parse_money(plan.get("totalOwnerTaxEstimate")),
                hint=str(plan.get("disclaimer") or "Planning estimate from book income — CPA review required."),
            )
        )
        widgets.append(
            _money_kpi(
                "tax-k1-ordinary",
                "Est. K-1 Ordinary",
                _parse_money(plan.get("k1Ordinary")),
                hint="Derived from book net after book-to-tax bridge lines.",
            )
        )
        # Do not surface modeledOfficerW2 as money — tax_engine clamps to planning
        # floors (e.g. $180k) that are not payroll imports.
        widgets.append(
            _empty_kpi(
                "tax-modeled-w2",
                "Modeled Officer W-2",
                hint="No payroll W-2 import — planning salary scenarios are notes only (not shown as $).",
            )
        )
        quarterly = plan.get("quarterlyEstimates") if isinstance(plan.get("quarterlyEstimates"), list) else []
        if quarterly:
            q1 = quarterly[0] if isinstance(quarterly[0], dict) else {}
            fed = _parse_money(q1.get("federal"))
            ks = _parse_money(q1.get("kansas"))
            if fed is not None and ks is not None:
                widgets.append(
                    _money_kpi(
                        "tax-q-estimate",
                        "Quarterly Estimate (Q1 split)",
                        fed + ks,
                        hint=f"Federal {fed:,.0f} + Kansas {ks:,.0f} · planning only.",
                        delta_label=str(q1.get("due") or "Q1"),
                    )
                )
            else:
                widgets.append(
                    _empty_kpi(
                        "tax-q-estimate",
                        "Quarterly Estimate",
                        hint="Quarterly estimate lines missing from tax plan.",
                    )
                )
    else:
        widgets.append(
            _empty_kpi(
                "tax-book-net",
                "Book Net Income",
                hint="QuickBooks P&L net income not imported — tax KPIs stay empty.",
            )
        )
        widgets.append(
            _empty_kpi(
                "tax-est-owner",
                "Est. Owner Tax (planning)",
                hint="S-corp estimates require QuickBooks book net income.",
            )
        )
        widgets.append(
            _empty_kpi(
                "tax-k1-ordinary",
                "Est. K-1 Ordinary",
                hint="Import QuickBooks P&L to unlock book-to-tax planning KPIs.",
            )
        )
        widgets.append(
            _empty_kpi(
                "tax-modeled-w2",
                "Modeled Officer W-2",
                hint="No book income — W-2 scenarios not shown (would invent dollars).",
            )
        )
        widgets.append(
            _empty_kpi(
                "tax-q-estimate",
                "Quarterly Estimate",
                hint="Estimated tax quarters appear after QB net income is available.",
            )
        )

    if plan.get("disclaimer"):
        widgets.append(
            _status_widget(
                "tax-disclaimer",
                "TAX PLANNING — CPA REVIEW",
                message="PLANNING ESTIMATES ONLY — NOT FOR FILING",
                hint=str(plan.get("disclaimer")),
            )
        )
    # Federal + Kansas split (planning)
    if has_book:
        fed = _parse_money(plan.get("federalTaxEstimate"))
        ks = _parse_money(plan.get("kansasTaxEstimate"))
        if fed is not None:
            widgets.append(
                _money_kpi(
                    "tax-federal-est",
                    "Federal Tax (planning)",
                    fed,
                    hint=str(plan.get("federalRateLabel") or "Federal planning rate") + " — CPA review required.",
                )
            )
        if ks is not None:
            widgets.append(
                _money_kpi(
                    "tax-kansas-est",
                    "Kansas Tax (planning)",
                    ks,
                    hint=str(plan.get("kansasRateLabel") or "Kansas planning rate") + " — CPA review required.",
                )
            )
        # Book-to-tax bridge as waterfall when lines present
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
                    "size": "xl",
                    "steps": bridge_steps,
                    "status": "ok",
                    "hint": "Planning bridge from tax_engine — citations are import sources, not invented dollars.",
                    "showCitations": True,
                }
            )
        widgets.append(build_ebitda_waterfall(bundle))
        widgets.append(build_ebitda_scrubber(bundle))
        widgets.append(build_scenario_manager_widget())
        widgets.append(build_filing_workflow_widget())
        widgets.append(build_workpaper_widget(plan, bundle))
        widgets.append(build_variance_alert_widget(bundle))
    try:
        from apex_cpa_pack import build_c0_import_guidance

        widgets.append(build_c0_import_guidance(bundle))
    except Exception:
        pass
    scenarios = plan.get("compScenarios") if isinstance(plan.get("compScenarios"), list) else []
    if scenarios and has_book:
        notes = [
            str(s.get("note") or "").strip()
            for s in scenarios
            if isinstance(s, dict) and str(s.get("note") or "").strip()
        ]
        widgets.append(
            _status_widget(
                "tax-comp-note",
                "Compensation scenario",
                message=f"{len(scenarios)} planning scenarios",
                hint=(notes[0] if notes else "Document with BLS/MGMA · CPA review.")
                + " — salary dollars not shown (not from payroll import).",
            )
        )
    elif not has_book:
        widgets.append(
            _status_widget(
                "tax-comp-note",
                "Compensation scenario",
                message="Awaiting book data",
                hint="S-corp reasonable-comp scenarios unlock after QuickBooks P&L import.",
                status="empty",
            )
        )

    widgets.extend(_visual_boost_taxes(plan))
    widgets.insert(0, build_period_scrubber(bundle, page="taxes"))
    return widgets


def _softdent_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports
    widgets: list[dict[str, Any]] = []
    rows = _dashboard_rows(bundle)
    latest = _latest_period_row(rows)
    period = str((latest or {}).get("period") or (latest or {}).get("year_month") or "")

    prod = _parse_money((latest or {}).get("production")) if latest else None
    widgets.append(
        _money_kpi(
            "sd-production",
            "Production",
            prod,
            hint="SoftDent dashboard import." if prod is not None else "SoftDent dashboard production not loaded.",
            delta_label=period or None,
            sparkline=_spark_from_rows(rows, "production") or None,
        )
    )

    coll = None
    coll_gap: dict[str, Any] = {}
    if latest:
        if latest.get("collectionsReported") is False or latest.get("collectionsPending") is True:
            coll = None
        elif "collections" in latest:
            coll = _parse_money(latest.get("collections"))
    try:
        from apex_softdent_hardening_pack import assess_collections_gap, enrich_widget_with_collections_gap

        coll_gap = assess_collections_gap(bundle)
    except Exception:
        coll_gap = {}
    coll_widget = _money_kpi(
        "sd-collections",
        "Collections",
        coll,
        hint=(
            "SoftDent dashboard collections."
            if coll is not None
            else "Collections pending for latest SoftDent period — not $0. Import SoftDent collections/daysheet."
        ),
        delta_label=period or None,
    )
    if coll is None and coll_gap:
        coll_widget = enrich_widget_with_collections_gap(coll_widget, coll_gap)
    widgets.append(coll_widget)

    np_rows = _section_rows(bundle, "softdent", "newPatients")
    np_latest = _latest_period_row(np_rows)
    np_count = None
    np_period = ""
    if np_latest:
        np_count = _parse_int(np_latest.get("Count") or np_latest.get("count") or np_latest.get("NewPatients"))
        np_period = str(np_latest.get("Period") or np_latest.get("period") or "")
    widgets.append(
        _count_kpi(
            "sd-new-patients",
            "New Patients",
            np_count,
            hint="SoftDent new-patients export." if np_count is not None else "New-patients export not loaded.",
            delta_label=np_period or None,
        )
    )

    providers = {
        str(r.get("provider") or r.get("Provider") or "").strip()
        for r in rows
        if str(r.get("provider") or r.get("Provider") or "").strip()
    }
    widgets.append(
        _count_kpi(
            "sd-providers",
            "Providers (dashboard)",
            len(providers) if providers else None,
            hint="Distinct provider labels in SoftDent dashboard rows."
            if providers
            else "No provider labels in SoftDent dashboard import.",
        )
    )

    op = _section(bundle, "softdent", "operatory")
    chairs = op.get("operatoryChairs") if isinstance(op.get("operatoryChairs"), list) else []
    slot_count = 0
    for chair in chairs:
        if isinstance(chair, dict) and isinstance(chair.get("slots"), list):
            slot_count += len(chair["slots"])
    if chairs:
        widgets.append(
            _count_kpi(
                "sd-operatory-chairs",
                "Operatory Chairs",
                len(chairs),
                hint=f"{slot_count} scheduled slot(s) in SoftDent operatory import.",
                delta_label=f"{slot_count} slots",
            )
        )
        widgets.append(
            _status_widget(
                "sd-operatory-status",
                "Operatory / daysheet",
                message="Schedule loaded",
                hint=f"{len(chairs)} chair(s), {slot_count} slot(s) from SoftDent operatory import.",
            )
        )
    else:
        widgets.append(
            _empty_kpi(
                "sd-operatory-chairs",
                "Operatory Chairs",
                hint="SoftDent operatory_schedule.json with operatoryChairs[] not present — run practice exports / Sensei schedule sync.",
            )
        )
        widgets.append(
            _status_widget(
                "sd-operatory-status",
                "Operatory / daysheet",
                message="No schedule",
                hint="Need operatoryChairs[] in SoftDent operatory import (not a row table).",
                status="empty",
            )
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

    procedures = _section_rows(bundle, "softdent", "procedures")
    widgets.append(
        _count_kpi(
            "sd-procedures",
            "Procedure Rows",
            len(procedures) if procedures else None,
            hint="SoftDent procedures import." if procedures else "Procedures export not loaded.",
        )
    )
    widgets.append(build_provider_horizontal_bars(bundle))
    try:
        from apex_softdent_hardening_pack import collections_gap_widget

        widgets.insert(0, collections_gap_widget(bundle))
    except Exception:
        pass
    try:
        from apex_softdent_production_pack import production_widgets
        from apex_softdent_aging_schedule_pack import aging_schedule_widgets

        widgets.extend(production_widgets(bundle))
        widgets.extend(aging_schedule_widgets(bundle))
    except Exception:
        pass
    try:
        from apex_era835_pack import era835_widget

        widgets.append(era835_widget(bundle))
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
        widgets.append(
            _empty_kpi("qb-net-income", "Net Income", hint="QuickBooks not imported — P&L / revenue missing.")
        )
        widgets.append(
            _empty_kpi("qb-revenue", "Revenue", hint="Import QuickBooks revenue or P&L to populate.")
        )
        widgets.append(
            _empty_kpi("qb-expenses", "Total Expenses", hint="Import QuickBooks expenses or P&L to populate.")
        )
        widgets.append(
            _status_widget(
                "qb-pl-summary",
                "P&L Summary",
                message="Not imported",
                hint="Drop QuickBooks exports into the document inbox and sync.",
                status="empty",
            )
        )
        widgets.append(
            _empty_chart(
                "qb-expense-breakdown",
                "Expense Breakdown",
                hint="Expense category rows appear after QuickBooks category import.",
            )
        )
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

    widgets.append(
        _money_kpi(
            "qb-net-income",
            "Net Income",
            net,
            hint="QuickBooks P&L import." if net is not None else "Net income field missing on P&L row.",
            delta_label=period or None,
        )
    )
    widgets.append(
        _money_kpi(
            "qb-revenue",
            "Revenue",
            revenue,
            hint="QuickBooks revenue / P&L import." if revenue is not None else "Revenue field missing.",
            delta_label=period or None,
        )
    )
    widgets.append(
        _money_kpi(
            "qb-expenses",
            "Total Expenses",
            expenses,
            hint="QuickBooks expenses / P&L import." if expenses is not None else "Expense field missing.",
            delta_label=period or None,
        )
    )

    summary_bits = []
    if period:
        summary_bits.append(period)
    if net is not None:
        summary_bits.append(f"Net ${net:,.0f}")
    widgets.append(
        _status_widget(
            "qb-pl-summary",
            "P&L Summary",
            message=" · ".join(summary_bits) if summary_bits else "Loaded",
            hint="Read-only QuickBooks import snapshot — not a live ledger.",
        )
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

    ninety_pct = ar.get("ninetyPlusPct")
    if isinstance(ninety_pct, (int, float)) and isinstance(ar_total, (int, float)):
        widgets.append(
            {
                "id": "ar-90-plus-pct",
                "type": "kpi",
                "label": "90+ % of A/R",
                "value": float(ninety_pct),
                "unit": "percent",
                "hint": f"90+ outstanding ${float(ar.get('ninetyPlusOutstanding') or 0):,.2f}.",
            }
        )
    else:
        widgets.append(
            _empty_kpi(
                "ar-90-plus-pct",
                "90+ % of A/R",
                hint="90+ share appears after SoftDent A/R aging import.",
            )
        )

    series = []
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

    lag: dict[str, Any] = {}
    try:
        from nr2_analytics import collection_lag

        lag = collection_lag(bundle=bundle) or {}
    except Exception:
        lag = {}

    if lag.get("hasData") and lag.get("avgLagDays") is not None:
        widgets.append(
            {
                "id": "ar-collection-lag",
                "type": "kpi",
                "label": "Collection Lag (days)",
                "value": float(lag["avgLagDays"]),
                "unit": "count",
                "deltaLabel": str(lag.get("caption") or ""),
                "hint": str(lag.get("summary") or lag.get("source") or "Collection lag from import."),
            }
        )
    else:
        widgets.append(
            _empty_kpi(
                "ar-collection-lag",
                "Collection Lag (days)",
                hint=str(lag.get("summary") or "Collection lag appears when A/R aging or collections export is loaded."),
            )
        )

    widgets.append(
        _status_widget(
            "ar-follow-up",
            "A/R Follow-up",
            message="Guidance",
            hint=str(ar.get("followUpHint") or "Prioritize 90+ balances when aging import is present."),
            status="ok" if isinstance(ar_total, (int, float)) else "empty",
        )
    )

    widgets[0:0] = _visual_boost_ar(reports, bundle)
    widgets.append(build_ar_waterfall(reports, bundle))
    widgets.append(build_ar_aging_outlook(reports, bundle))
    widgets.append(build_collection_bullet(bundle))
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
    widgets.append(
        _count_kpi(
            "claims-aging-count",
            "Aging Past 30 Days",
            summary.get("agingPast30") if summary.get("available") else None,
            hint="Rows aged ≥30 days from SoftDent Age/Days or ServiceDate — not invented."
            if summary.get("available")
            else "Aging days appear when claim export includes Age/Days or ServiceDate.",
        )
    )

    by_status = summary.get("byStatus") if isinstance(summary.get("byStatus"), dict) else {}
    if by_status:
        top = sorted(by_status.items(), key=lambda kv: kv[1], reverse=True)[:4]
        status_msg = ", ".join(f"{k}: {v}" for k, v in top)
    else:
        status_msg = "No status breakdown"
    widgets.append(
        _status_widget(
            "claims-follow-up",
            "Claims Follow-up",
            message=status_msg,
            hint=str(summary.get("followUpHint") or ct.get("followUpHint") or "Review open and denied claims."),
            status="ok" if summary.get("available") else "empty",
        )
    )

    widgets[0:0] = _visual_boost_claims(bundle, reports)
    widgets.append(build_ins_patient_split(bundle))

    # Moonshot C1–C2: 30 / 60 / 90 day claim tile shelves
    try:
        from apex_claims_narratives_pack import apply_aging_threshold_alerts, shelf_widget

        buckets = summary.get("agingBuckets") if isinstance(summary.get("agingBuckets"), dict) else {}
        meta = summary.get("agingMeta") if isinstance(summary.get("agingMeta"), dict) else {}
        missing_age = bool(meta.get("missingAgeField"))
        for bucket in ("30", "60", "90"):
            tiles = buckets.get(bucket) if isinstance(buckets.get(bucket), list) else []
            widgets.append(shelf_widget(bucket, tiles, missing_age=missing_age and not tiles))
        apply_aging_threshold_alerts(
            widgets,
            {"counts": summary.get("agingCounts") or {}},
        )
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

    return widgets


def _documents_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports, bundle
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
    return widgets


def _library_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    del reports, bundle
    widgets: list[dict[str, Any]] = []
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

    widgets.append(
        _count_kpi(
            "om-partial",
            "Partial Imports",
            partial if isinstance(partial, int) else None,
            hint="Datasets present but incomplete." if isinstance(partial, int) else "Diagnostics missing.",
        )
    )
    widgets.append(
        _count_kpi(
            "om-missing",
            "Missing Imports",
            missing if isinstance(missing, int) else None,
            hint="Required/optional datasets not found in cache."
            if isinstance(missing, int)
            else "Diagnostics missing.",
        )
    )
    if isinstance(stale, int):
        widgets.append(
            _count_kpi(
                "om-stale",
                "Stale Imports",
                stale,
                hint="Datasets older than freshness window.",
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
        _status_widget(
            "om-readiness",
            "Import Readiness",
            message=posture,
            hint=posture_hint,
            status=posture_status,
        )
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
    return widgets


def _hal_widgets(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    widgets: list[dict[str, Any]] = []

    widgets.append(
        {
            "id": "hal-ask",
            "type": "hal-chat",
            "label": "Ask HAL",
            "status": "ok",
            "hint": "Local HAL command surface",
        }
    )

    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    connected = summary.get("connected")
    total = summary.get("total")
    missing = summary.get("missing")
    if isinstance(connected, int) and isinstance(total, int) and total > 0:
        widgets.append(
            _count_kpi(
                "hal-import-health",
                "Import Health",
                connected,
                hint=f"{connected}/{total} datasets connected"
                + (f"; {missing} missing" if missing else "")
                + ".",
                delta_label=f"{round(100.0 * connected / total, 0):.0f}%",
            )
        )
    else:
        widgets.append(
            _empty_kpi(
                "hal-import-health",
                "Import Health",
                hint="Import diagnostics not available.",
            )
        )

    if isinstance(connected, int) and isinstance(total, int) and total > 0 and missing == 0:
        posture_msg = "Operational"
        posture_hint = "Imports connected — Apex P5 automation + live widgets."
        posture_status = "ok"
    elif isinstance(connected, int):
        posture_msg = "Degraded"
        posture_hint = "Some imports missing/partial — HAL answers stay grounded to available data."
        posture_status = "ok"
    else:
        posture_msg = "Standby"
        posture_hint = "Awaiting import diagnostics."
        posture_status = "empty"

    widgets.append(
        _status_widget(
            "hal-program-posture",
            "Program Posture",
            message=posture_msg,
            hint=posture_hint,
            status=posture_status,
        )
    )

    widgets.append(
        _status_widget(
            "hal-suggestion",
            "HAL Suggestion",
            message="Ready",
            hint=HAL_STATUS_SUGGESTION,
        )
    )

    # Mosaic of key metrics (production, collections, AR, claims)
    rows = _dashboard_rows(bundle)
    latest = _latest_period_row(rows)
    prod = _parse_money((latest or {}).get("production")) if latest else None
    coll = None
    if latest and not (latest.get("collectionsReported") is False or latest.get("collectionsPending") is True):
        if "collections" in latest:
            coll = _parse_money(latest.get("collections"))

    widgets.append(
        _money_kpi(
            "hal-mosaic-prod",
            "Production",
            prod,
            hint="SoftDent dashboard." if prod is not None else "Production not in latest SoftDent period.",
        )
    )
    widgets.append(
        _money_kpi(
            "hal-mosaic-coll",
            "Collections",
            coll,
            hint="SoftDent dashboard." if coll is not None else "Collections pending/missing.",
        )
    )

    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    ar_total = ar.get("totalOutstanding")
    widgets.append(
        _money_kpi(
            "hal-mosaic-ar",
            "A/R",
            float(ar_total) if isinstance(ar_total, (int, float)) else None,
            hint="SoftDent A/R." if isinstance(ar_total, (int, float)) else "A/R import missing.",
        )
    )

    claims = _claims_summary_from_bundle(bundle)
    widgets.append(
        _count_kpi(
            "hal-mosaic-claims",
            "Claims",
            claims.get("totalClaims") if claims.get("available") else None,
            hint="SoftDent claims." if claims.get("available") else "Claims import missing.",
        )
    )

    widgets.append(build_categorize_assist(bundle))
    try:
        from apex_hal_said_improve_pack import append_hal_page_hal_said

        append_hal_page_hal_said(widgets)
    except Exception:
        pass
    try:
        from apex_structured_insight_pack import ai_insight_widget

        widgets.append(ai_insight_widget())
    except Exception:
        pass
    try:
        from apex_unified_db_pack import unified_db_widget

        widgets.append(unified_db_widget(bundle))
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
    "narratives": _narratives_widgets,
    "documents": _documents_widgets,
    "library": _library_widgets,
    "office-manager": _office_manager_widgets,
    "hal": _hal_widgets,
}


def build_apex_widgets(page_id: str) -> dict[str, Any]:
    pid = re.sub(r"[^a-z0-9\-]", "", str(page_id or "").strip().lower())
    if pid not in APEX_PAGES:
        return {
            "page": pid or "unknown",
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

    reports, bundle, errors = _load_reports_and_bundle()
    builder = _PAGE_BUILDERS[pid]
    widgets = builder(reports, bundle)

    source_note = f"{pid}: financial_reports + import_loader"
    if errors:
        source_note += f" (partial: {'; '.join(errors)})"

    return {
        "page": pid,
        "refreshedAt": reports.get("generatedAt") or bundle.get("loadedAt") or _utc_now(),
        "buildId": BUILD_ID,
        "widgets": widgets,
        "sourceNote": source_note,
        "errors": errors or None,
        "widgetCensus": summarize_widget_census(widgets),
    }


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
    if wtype == "kpi":
        return w.get("value") is not None and w.get("value") != ""
    if wtype in {"chart", "bar", "line"}:
        series = w.get("series") if isinstance(w.get("series"), list) else []
        return bool(series)
    if wtype == "funnel":
        return bool(w.get("stages"))
    if wtype in {"donut", "stacked-bar", "horizontal-bar"}:
        return bool(w.get("slices") or w.get("bars") or w.get("segments"))
    if wtype == "waterfall":
        return bool(w.get("steps"))
    if wtype == "status":
        return status == "ok" or bool(w.get("message"))
    # Default: non-empty status counts as showing
    return status != "empty"


def summarize_widget_census(widgets: list[dict[str, Any]]) -> dict[str, Any]:
    populated: list[dict[str, str]] = []
    empty: list[dict[str, str]] = []
    for w in widgets:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("id") or "")
        if not wid or wid.startswith("hal-chat"):
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
            "Preferred: Direct-First / ODBC lane (Sensei DataSync or SoftDent ODBC) — HAL Sync reloads the live extract cache.",
            "File path: export SoftDent CSVs (claims, claim status, A/R aging, procedures, dashboard/daysheet, clinical notes) into app_data/nr2/document_inbox/softdent/ (or configured SoftDent import dir).",
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
            "How do I get QuickBooks exports?",
        ],
        "honesty": "HAL syncs/refreshes from imports only — it does not log into SoftDent or QuickBooks UI for you.",
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
        lines.append("Fix: place SoftDent/QB exports in the inbox (or refresh ODBC), then Sync imports. Ask: how do I get SoftDent/QuickBooks exports?")
    else:
        lines.append("All listed instruments on this page currently show data from the import cache.")
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

    # 2) Dashboard period sync from analytics DB
    try:
        from softdent_dashboard_period_sync import sync_dashboard_period_rows

        dash = sync_dashboard_period_rows()
        result["steps"].append({"step": "dashboard_period_sync", "ok": bool(dash.get("ok")), "detail": {
            "periods": dash.get("periods"),
            "rowCount": dash.get("rowCount"),
            "mergeLog": dash.get("mergeLog"),
        }})
    except Exception as exc:  # noqa: BLE001
        result["steps"].append({"step": "dashboard_period_sync", "ok": False, "error": str(exc)})

    # 3) Practice exports (operatory date filter)
    try:
        from softdent_practice_exports import sync_practice_exports

        op = sync_practice_exports()
        result["steps"].append({"step": "practice_exports", "ok": bool(op.get("ok")), "written": op.get("written")})
    except Exception as exc:  # noqa: BLE001
        result["steps"].append({"step": "practice_exports", "ok": False, "error": str(exc)})

    # 4) Status snapshot
    try:
        status_path = _Path(r"C:\SoftDentFinancialExports\softdent_period_export_automation_status.json")
        if status_path.is_file():
            result["periodStatus"] = json.loads(status_path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass

    result["ok"] = any(bool(s.get("ok")) for s in result["steps"])
    result["completedAt"] = _utc_now()
    result["nextStep"] = (
        "If July still pending: SoftDent → Reports → Accounting → Register for a Period (07/01/2026–today) "
        "to C:\\SoftDentReportExports, then run this refresh again."
    )
    return result


def _build_hal_status_payload() -> dict[str, Any]:
    """HAL operational state + grounded suggestion (no invented dollars)."""
    suggestion = HAL_STATUS_SUGGESTION
    status = "idle"
    status_label = "HAL Standby"
    confidence = None
    extras: dict[str, Any] = {}
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
            status = "ready" if (isinstance(missing, int) and missing == 0) else "degraded"
            status_label = "HAL Live" if status == "ready" else "HAL Degraded"

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
        status = "idle"
        status_label = "HAL Standby"
        suggestion = HAL_STATUS_SUGGESTION

    return {
        "status": status,
        "statusLabel": status_label,
        "suggestion": suggestion,
        "confidence": confidence,
        "buildId": BUILD_ID,
        "refreshedAt": _utc_now(),
        "metrics": extras or None,
        "orchestrator": _orchestrator_status_safe(),
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
            "If July is still pending, export Register for a Period MTD from SoftDent first."
        )
        handled = True

    # --- Refresh widgets only (no file sync) ---
    if re.search(r"\b(refresh (the )?(widgets|page|mosaic|board)|reload (the )?(page|widgets))\b", q) and not any(
        a.get("type") == "sync_imports" for a in actions
    ):
        actions.append({"type": "refresh_page"})
        notes.append("Refreshing widgets from the current import cache (no new file sync).")
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
        (r"\bebitda\b", "ebitda-scrubber", "taxes"),
        (r"\b(provider production|production by provider)\b", "provider-hbar", "financial"),
        (r"\b(payer mix|insurance vs patient)\b", "payer-donut", "financial"),
        (r"\b(collection efficiency|collections? ratio)\b", "collection-bullet", "financial"),
        (r"\b(a/?r (aging )?flow|aging waterfall|collectible)\b", "ar-waterfall", "ar"),
        (r"\b(categorize|categoris|expense categor)\b", "hal-categorize-assist", "quickbooks"),
        (r"\b(tax (returns? )?library|upload (tax )?return)\b", "tax-returns-library", "documents"),
        (r"\b(book.?to.?tax|tax bridge)\b", "tax-bridge-waterfall", "taxes"),
        (r"\b(import (sync )?verify|import status|import readiness)\b", "import-freshness", "financial"),
        (r"\b(morning brief)\b", "morning-brief", "financial"),
        (r"\b(liquidity|collections pulse|production pulse)\b", "liquidity-pulse", "financial"),
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
    )
    if re.search(r"\b(focus|highlight|show me|point (me )?to|look at|open widget)\b", q) or any(
        re.search(pat, q) for pat, _wid, _pg in focus_rules
    ):
        for pat, wid, pg in focus_rules:
            if re.search(pat, q):
                if pg != page and not any(a.get("type") == "navigate" for a in actions):
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
            actions.append({"type": "navigate", "page": "financial"})
            actions.append({"type": "focus_widget", "widgetId": "import-freshness"})
        notes.append(str(fresh.get("message") or "Import diagnostics loaded from cache."))
        notes.append(str(fresh.get("hint") or ""))
        handled = True

    # --- Surface categorize suggestions (already computed from imports; not inventing $) ---
    if re.search(r"\b(categorize|suggest categor|expense categor|remap categor)\b", q):
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
    wants_all_pages = bool(
        re.search(r"\b(all pages|every page|whole (app|program|bridge)|program.?wide|across (all )?pages)\b", q)
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
        re.search(r"\b(what|which|list)\s+widgets\b|\bwidget(s)?\s+(on|for|list|inventory|map)\b|\bwidgets on\b", q)
    )
    wants_census = bool(
        re.search(
            r"\b("
            r"which widgets (are )?(empty|populated|showing|have data)|"
            r"do(es)? (the )?widgets? (show|have|display) data|"
            r"widget (health|census|status|data)|"
            r"are (the )?widgets? empty|"
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

    # --- DEF-001 / Phase I2: why collections empty ---
    if (not handled) and re.search(
        r"\b(why .{0,40}collections|collections (empty|pending|missing|gap)|def-?001|daysheet (gap|missing))\b",
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
            if page != "softdent" and not any(a.get("type") == "navigate" for a in actions):
                actions.append({"type": "navigate", "page": "softdent"})
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

    # --- Treatment planning estimate (InsCo × ADA from payment-line aggregates) ---
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
                reply_txt = format_treatment_estimate_reply(est)
                notes.append(reply_txt)
                tone = "ok" if est.get("sufficient") else "warn"
                actions.append(
                    {
                        "type": "set_status_banner",
                        "message": f"Tx plan estimate · {parsed['payer']} × {parsed['adaCode']}",
                        "hint": "Historical SoftDent payment-line averages — not a benefits guarantee.",
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
                    f"{st.get('estimates', 0)} InsCo×ADA estimates "
                    f"({st.get('estimatesWithMinSample', 0)} with n>=10). "
                    f"{st.get('hint') or ''}"
                )
                actions.append(
                    {
                        "type": "set_status_banner",
                        "message": (
                            f"Tx planning: {st.get('estimatesWithMinSample', 0)} ready estimates "
                            f"/ {st.get('estimates', 0)} total"
                        ),
                        "hint": st.get("hint") or "",
                        "tone": "ok" if int(st.get("estimatesWithMinSample") or 0) else "warn",
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
                "hint": "HAL can sync/refill after files land; does not log into SoftDent/QB for you.",
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
    """Trigger import refresh using existing NR2 sync path when available."""
    body = payload if isinstance(payload, dict) else {}
    started = _utc_now()
    result: dict[str, Any] = {
        "ok": True,
        "startedAt": started,
        "status": "syncing",
        "sources": ["softdent", "quickbooks"],
        "page": body.get("page"),
        "buildId": BUILD_ID,
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
        bundle = load_import_bundle(sync=sync, deep=False)
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
        # Phase I3 — mirror import bundle into additive unified SQLite
        try:
            from apex_unified_db_pack import ingest_from_bundle

            result["unifiedIngest"] = ingest_from_bundle(bundle)
        except Exception as exc:  # noqa: BLE001
            result["unifiedIngest"] = {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["status"] = "error"
        result["error"] = str(exc)
        result["completedAt"] = _utc_now()
    return result


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
            return json_response_fn(build_apex_widgets(page_id))
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
            return json_response_fn(apex_sync_trigger(payload))
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

    @app.get("/api/apex/hal/era835-status")
    def apex_era835_status():
        try:
            from apex_era835_pack import era835_status

            result = era835_status()
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

