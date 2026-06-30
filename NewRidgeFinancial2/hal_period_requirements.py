"""Widget period requirements vs loaded import cache — for HAL period planning."""

from __future__ import annotations

import json
from typing import Any

from import_cache_ttl import load_manifest, relevant_period_labels
from import_loader import load_import_bundle, quickbooks_import_dir, softdent_import_dir


WIDGET_PERIOD_RULES: dict[str, dict[str, Any]] = {
    "financialProductionTrend": {
        "label": "Production Trend & YTD",
        "needs": "current + prior calendar month in SoftDent dashboard",
        "datasets": ["softdent.dashboard"],
    },
    "financialPayerMix": {
        "label": "Payer Mix & Collections",
        "needs": "current + prior month SoftDent dashboard with collections/payer fields",
        "datasets": ["softdent.dashboard"],
    },
    "practiceFinancialOverview": {
        "label": "Practice Financial Overview",
        "needs": "current month QuickBooks revenue + SoftDent dashboard",
        "datasets": ["quickbooks.revenue", "softdent.dashboard"],
    },
    "quickbooksPlDetail": {
        "label": "QuickBooks P&L Detail",
        "needs": "current month QuickBooks revenue and expenses",
        "datasets": ["quickbooks.revenue", "quickbooks.expenses"],
    },
    "periodCloseAndPosting": {
        "label": "Period Close & Posting",
        "needs": "active document queue period (from document dates, not import CSV)",
        "datasets": ["local.documents"],
    },
    "claimsPipeline": {
        "label": "Claims Pipeline",
        "needs": "claim service dates (not monthly period labels)",
        "datasets": ["softdent.claims"],
    },
}


def _periods_from_rows(rows: list[dict[str, Any]] | None, field_names: tuple[str, ...]) -> list[str]:
    found: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for name in field_names:
            raw = row.get(name)
            if raw:
                found.add(str(raw).strip()[:7])
                break
    return sorted(found)


def analyze_widget_periods(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False, deep=False)
    required = relevant_period_labels()
    sd = (bundle.get("softdent") or {}) if isinstance(bundle, dict) else {}
    qb = (bundle.get("quickbooks") or {}) if isinstance(bundle, dict) else {}
    loaded = {
        "softdent.dashboard": _periods_from_rows((sd.get("dashboard") or {}).get("rows"), ("period", "Period")),
        "quickbooks.revenue": _periods_from_rows((qb.get("revenue") or {}).get("rows"), ("Period", "period")),
        "quickbooks.expenses": _periods_from_rows((qb.get("expenses") or {}).get("rows"), ("Period", "period")),
    }
    manifest = load_manifest() or {}
    widget_status: list[dict[str, Any]] = []
    for key, rule in WIDGET_PERIOD_RULES.items():
        dataset_keys = rule.get("datasets") or []
        if "local.documents" in dataset_keys:
            ok = True
            missing = []
        elif "softdent.claims" in dataset_keys:
            ok = bool(((sd.get("claims") or {}).get("rows") or []))
            missing = [] if ok else ["claims export rows"]
        else:
            needed_periods = required if any(k.startswith("softdent.") or k.startswith("quickbooks.") for k in dataset_keys) else required
            missing = []
            for ds in dataset_keys:
                have = set(loaded.get(ds) or [])
                for period in needed_periods:
                    if period not in have:
                        missing.append(f"{ds} missing {period}")
            ok = not missing
        widget_status.append(
            {
                "widgetKey": key,
                "label": rule["label"],
                "requirement": rule["needs"],
                "ok": ok,
                "missing": missing,
                "loadedPeriods": {ds: loaded.get(ds, []) for ds in dataset_keys if ds in loaded},
            }
        )
    return {
        "requiredPeriods": required,
        "loadedPeriods": loaded,
        "manifestPeriods": manifest.get("periods"),
        "widgets": widget_status,
        "policy": "Import cache keeps current + prior calendar month only (relevant-periods-only).",
        "softdentDir": str(softdent_import_dir()),
        "quickbooksDir": str(quickbooks_import_dir()),
    }


if __name__ == "__main__":
    print(json.dumps(analyze_widget_periods(), indent=2))
