"""Pipeline-first datasets for direct-first import (bridge, aging JSONL, analytics DB, QB probe).

Reads live pipeline outputs from upstream folders without requiring document-inbox copies
to be newer. Document-inbox remains fallback only.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_contract import (
    QUICKBOOKS_AP_NAMES,
    QUICKBOOKS_EXPENSE_CATEGORY_NAMES,
    QUICKBOOKS_EXPENSE_NAMES,
    QUICKBOOKS_PAYROLL_NAMES,
    QUICKBOOKS_PL_NAMES,
    QUICKBOOKS_REVENUE_NAMES,
    SOFTDENT_AR_NAMES,
    SOFTDENT_CASE_ACCEPTANCE_NAMES,
    SOFTDENT_CLAIMS_NAMES,
    SOFTDENT_CLINICAL_NAMES,
    SOFTDENT_DASHBOARD_NAMES,
    SOFTDENT_NEW_PATIENTS_NAMES,
    SOFTDENT_TREATMENT_PLANS_NAMES,
)
from import_loader import quickbooks_import_dir, softdent_import_dir
from import_sync import (
    BRIDGE_AGGREGATE_JSON,
    QB_SDK_SUMMARY,
    SOFTDENT_FINANCIAL_EXPORTS,
    _build_ar_rows_from_normalized,
    _build_dashboard_from_bridge,
    _find_newest,
    _is_sample_claims,
    _is_sample_clinical,
    _is_sample_dashboard,
    _jsonl_practice_total,
    _quickbooks_direct_read_roots,
    _read_json,
    _softdent_direct_read_roots,
    _trim_rows_to_relevant_periods,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def pipeline_first_imports_enabled() -> bool:
    if os.environ.get("NR2_PIPELINE_FIRST_IMPORTS", "").strip():
        return os.environ.get("NR2_PIPELINE_FIRST_IMPORTS", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
    try:
        from practice_source_access import direct_first_imports_enabled

        return direct_first_imports_enabled()
    except Exception:
        return os.environ.get("NR2_DIRECT_FIRST_IMPORTS", "1").strip().lower() not in {"0", "false", "no", "off"}


def _mtime_iso(path: Path) -> str:
    if not path.is_file():
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _path_mtime(path: Path | None) -> float:
    if not path or not path.is_file():
        return 0.0
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def dataset_mtime(dataset: dict[str, Any] | None) -> float:
    if not dataset:
        return 0.0
    source_path = str(dataset.get("sourcePath") or "").strip()
    if source_path:
        mt = _path_mtime(Path(source_path))
        if mt:
            return mt
    modified_at = str(dataset.get("modifiedAt") or "").strip()
    if modified_at:
        try:
            return datetime.fromisoformat(modified_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return 0.0


def inline_dataset(
    rows: list[dict[str, Any]],
    *,
    source_path: Path | str,
    source_file: str,
    source_kind: str,
) -> dict[str, Any] | None:
    if not rows:
        return None
    path = Path(source_path)
    return {
        "sourceFile": source_file,
        "sourcePath": str(path),
        "modifiedAt": _mtime_iso(path) if path.is_file() else datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "readSource": "direct",
        "sourceKind": source_kind,
    }


def _dataset_is_usable(dataset: dict[str, Any] | None) -> bool:
    if not dataset:
        return False
    rows = dataset.get("rows")
    if not isinstance(rows, list) or not rows:
        return False
    source_kind = str(dataset.get("sourceKind") or "")
    if source_kind == "pipeline-daysheet":
        return True
    if _is_sample_claims(rows) or _is_sample_clinical(rows) or _is_sample_dashboard(rows):
        return False
    return True


def pick_freshest_dataset(*candidates: dict[str, Any] | None) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_mtime = -1.0
    for candidate in candidates:
        if not _dataset_is_usable(candidate):
            continue
        mt = dataset_mtime(candidate)
        if mt >= best_mtime:
            best = candidate
            best_mtime = mt
    return best


def _upstream_roots(system: str) -> list[Path]:
    return _softdent_direct_read_roots() if system == "softdent" else _quickbooks_direct_read_roots()


def _load_file_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = _read_json(path)
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            nested = payload.get("notes") or payload.get("claims") or payload.get("rows")
            if isinstance(nested, list):
                return [row for row in nested if isinstance(row, dict)]
    elif path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle) if row]
    return []


def load_upstream_export_dataset(system: str, names: tuple[str, ...]) -> dict[str, Any] | None:
    """Newest named export from upstream roots only (excludes document-inbox cache)."""
    newest: Path | None = None
    for root in _upstream_roots(system):
        candidate = _find_newest(root, names)
        if candidate and (newest is None or candidate.stat().st_mtime > newest.stat().st_mtime):
            newest = candidate
    if not newest:
        return None
    rows = _load_file_rows(newest)
    if not rows:
        return None
    return inline_dataset(
        rows,
        source_path=newest,
        source_file=newest.name,
        source_kind="export-file",
    )


def load_cache_fallback_dataset(system: str, names: tuple[str, ...]) -> dict[str, Any] | None:
    from import_loader import _load_dataset

    directory = softdent_import_dir() if system == "softdent" else quickbooks_import_dir()
    dataset = _load_dataset(directory, names)
    if dataset:
        dataset = dict(dataset)
        dataset["readSource"] = "cache"
    return dataset


def resolve_bridge_path() -> Path | None:
    candidates: list[Path] = []
    for root in _upstream_roots("softdent"):
        found = _find_newest(root, ("softdent_bridge_latest.json",))
        if found:
            candidates.append(found)
    if BRIDGE_AGGREGATE_JSON.is_file():
        candidates.append(BRIDGE_AGGREGATE_JSON)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def resolve_aging_jsonl_path() -> Path | None:
    candidates: list[Path] = []
    for root in _upstream_roots("softdent"):
        found = _find_newest(root, ("account_aging.jsonl",))
        if found:
            candidates.append(found)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def resolve_qb_probe_path() -> Path | None:
    candidates: list[Path] = []
    for root in _upstream_roots("quickbooks"):
        found = _find_newest(root, ("quickbooks_sdk_report_probe_summary.json",))
        if found:
            candidates.append(found)
    if QB_SDK_SUMMARY.is_file():
        candidates.append(QB_SDK_SUMMARY)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def build_dashboard_pipeline_dataset() -> dict[str, Any] | None:
    from import_cache_ttl import relevant_period_labels
    from quickbooks_monthly_sync import resolve_analytics_db
    from softdent_dashboard_period_sync import _month_rows

    periods = relevant_period_labels()
    db_path = resolve_analytics_db()
    bridge_path = resolve_bridge_path()
    rows: list[dict[str, Any]] = []

    if bridge_path and bridge_path.is_file():
        bridge_rows = _build_dashboard_from_bridge(bridge_path)
        if bridge_rows and not _is_sample_dashboard(bridge_rows):
            rows = _trim_rows_to_relevant_periods(bridge_rows)

    analytics_rows = _month_rows(db_path, periods) if db_path else []
    if analytics_rows:
        by_period = {str(row.get("period")): row for row in rows if row.get("period")}
        for row in analytics_rows:
            period = str(row.get("period") or "")
            if period:
                by_period[period] = row
        rows = [by_period[p] for p in sorted(by_period.keys()) if p in periods] or list(by_period.values())

    if not rows:
        return None

    source_path = bridge_path or db_path or SOFTDENT_FINANCIAL_EXPORTS
    mtime_candidates = [_path_mtime(bridge_path), _path_mtime(db_path)]
    mtimes = [value for value in mtime_candidates if value]
    source_mtime = max(mtimes) if mtimes else 0
    return {
        "sourceFile": "softdent_dashboard_data.json",
        "sourcePath": str(source_path),
        "modifiedAt": datetime.fromtimestamp(source_mtime, tz=timezone.utc).isoformat()
        if source_mtime
        else _mtime_iso(source_path),
        "rows": rows,
        "readSource": "direct",
        "sourceKind": "pipeline-dashboard",
    }


def build_ar_pipeline_dataset() -> dict[str, Any] | None:
    aging_path = resolve_aging_jsonl_path()
    csv_path = None
    try:
        from softdent_outstanding_claims_bridge import find_account_aging_export

        csv_path = find_account_aging_export()
    except Exception:
        csv_path = None
    jsonl_mtime = aging_path.stat().st_mtime if aging_path and aging_path.is_file() else 0.0
    csv_mtime = csv_path.stat().st_mtime if csv_path and csv_path.is_file() else 0.0
    prefer_csv = bool(csv_path) and (csv_mtime >= jsonl_mtime or not aging_path)

    if prefer_csv:
        try:
            from import_sync import _build_ar_rows_from_account_aging_csv

            rows = _build_ar_rows_from_account_aging_csv()
            if rows and csv_path:
                return inline_dataset(
                    rows,
                    source_path=csv_path,
                    source_file="softdent_ar_aging.csv",
                    source_kind="pipeline-account-aging-csv",
                )
        except Exception:
            pass

    if aging_path:
        normalized = _jsonl_practice_total(aging_path)
        if normalized:
            rows = _build_ar_rows_from_normalized(normalized)
            if rows:
                return inline_dataset(
                    rows,
                    source_path=aging_path,
                    source_file="softdent_ar_aging.csv",
                    source_kind="pipeline-jsonl",
                )

    if csv_path:
        try:
            from import_sync import _build_ar_rows_from_account_aging_csv

            rows = _build_ar_rows_from_account_aging_csv()
            if rows:
                return inline_dataset(
                    rows,
                    source_path=csv_path,
                    source_file="softdent_ar_aging.csv",
                    source_kind="pipeline-account-aging-csv",
                )
        except Exception:
            pass
    return None


def build_practice_pipeline_datasets() -> dict[str, dict[str, Any] | None]:
    from softdent_practice_exports import read_practice_export_datasets

    return read_practice_export_datasets()


def _qb_rows_from_probe(probe: dict[str, Any]) -> dict[str, dict[str, Any] | None]:
    if str(probe.get("status") or "").upper() != "QUICKBOOKS_SDK_REPORT_DATA_AVAILABLE":
        return {}
    probe_path = resolve_qb_probe_path()
    if not probe_path:
        return {}
    revenue = probe.get("total_income")
    expenses = probe.get("total_expenses")
    out: dict[str, dict[str, Any] | None] = {}
    if revenue not in (None, "") and expenses not in (None, ""):
        out["revenue"] = inline_dataset(
            [{"TotalIncome": revenue}],
            source_path=probe_path,
            source_file="quickbooks_revenue.csv",
            source_kind="probe-json",
        )
        out["expenses"] = inline_dataset(
            [{"TotalExpense": expenses}],
            source_path=probe_path,
            source_file="quickbooks_expenses.csv",
            source_kind="probe-json",
        )
    categories = probe.get("top_expense_categories")
    if isinstance(categories, list) and categories:
        category_rows = [
            {
                "Category": str(item.get("category") or ""),
                "Amount": item.get("amount"),
                "Period": str(item.get("period") or probe.get("period") or ""),
            }
            for item in categories
            if isinstance(item, dict) and item.get("amount") not in (None, "")
        ]
        if category_rows:
            if not any(str(row.get("Period") or "").strip() for row in category_rows):
                category_rows = [{**row, "Scope": "YTD"} for row in category_rows]
            out["expenseCategories"] = inline_dataset(
                category_rows,
                source_path=probe_path,
                source_file="quickbooks_expense_categories.csv",
                source_kind="probe-json",
            )
    return out


def build_qb_monthly_pipeline_datasets() -> dict[str, dict[str, Any] | None]:
    from quickbooks_monthly_sync import (
        _normalize_monthly_rows,
        _rows_from_analytics_db,
        _rows_from_probe_monthly,
        resolve_analytics_db,
    )

    probe_path = resolve_qb_probe_path()
    probe = _read_json(probe_path) if probe_path else None
    probe = probe if isinstance(probe, dict) else None
    monthly_rows: list[dict[str, Any]] = []
    source_path = probe_path

    probe_rows = _rows_from_probe_monthly(probe)
    if probe_rows:
        monthly_rows = probe_rows

    if len(monthly_rows) < 2:
        db_path = resolve_analytics_db()
        analytics_rows = _rows_from_analytics_db(db_path) if db_path else []
        if analytics_rows:
            monthly_rows = analytics_rows
            source_path = db_path

    monthly_rows = _normalize_monthly_rows(monthly_rows)
    if not monthly_rows or not source_path:
        return {}

    revenue_rows = [{"Period": row["Period"], "TotalIncome": row["TotalIncome"]} for row in monthly_rows]
    expense_rows = [{"Period": row["Period"], "TotalExpense": row["TotalExpense"]} for row in monthly_rows]
    pl_rows = [
        {
            "Period": row["Period"],
            "TotalIncome": row["TotalIncome"],
            "TotalExpense": row["TotalExpense"],
            "NetIncome": row["NetIncome"],
        }
        for row in monthly_rows
    ]
    return {
        "revenue": inline_dataset(
            revenue_rows,
            source_path=source_path,
            source_file="quickbooks_revenue.csv",
            source_kind="monthly-pipeline",
        ),
        "expenses": inline_dataset(
            expense_rows,
            source_path=source_path,
            source_file="quickbooks_expenses.csv",
            source_kind="monthly-pipeline",
        ),
        "profitAndLoss": inline_dataset(
            pl_rows,
            source_path=source_path,
            source_file="quickbooks_profit_and_loss.csv",
            source_kind="monthly-pipeline",
        ),
    }


def build_softdent_pipeline_datasets() -> dict[str, dict[str, Any] | None]:
    if not pipeline_first_imports_enabled():
        return {}
    from softdent_operational_pipeline import build_daysheet_claims_dataset, build_daysheet_clinical_dataset

    practice = build_practice_pipeline_datasets()
    return {
        "dashboard": build_dashboard_pipeline_dataset(),
        "ar": build_ar_pipeline_dataset(),
        "claims": build_daysheet_claims_dataset(),
        "clinicalNotes": build_daysheet_clinical_dataset(),
        "newPatients": practice.get("newPatients"),
        "treatmentPlans": practice.get("treatmentPlans"),
        "caseAcceptance": practice.get("caseAcceptance"),
    }


def build_quickbooks_pipeline_datasets() -> dict[str, dict[str, Any] | None]:
    if not pipeline_first_imports_enabled():
        return {}
    probe_path = resolve_qb_probe_path()
    probe = _read_json(probe_path) if probe_path else None
    probe_datasets = _qb_rows_from_probe(probe) if isinstance(probe, dict) else {}
    monthly_datasets = build_qb_monthly_pipeline_datasets()
    merged: dict[str, dict[str, Any] | None] = {}
    for key in ("revenue", "expenses", "profitAndLoss", "expenseCategories"):
        merged[key] = pick_freshest_dataset(monthly_datasets.get(key), probe_datasets.get(key))
    return merged


def resolve_softdent_dataset(
    key: str,
    names: tuple[str, ...],
    *,
    pipeline: dict[str, dict[str, Any] | None] | None = None,
) -> dict[str, Any] | None:
    pipe = pipeline if pipeline is not None else build_softdent_pipeline_datasets()
    return pick_freshest_dataset(
        pipe.get(key),
        load_upstream_export_dataset("softdent", names),
    )


def resolve_quickbooks_dataset(
    key: str,
    names: tuple[str, ...],
    *,
    pipeline: dict[str, dict[str, Any] | None] | None = None,
) -> dict[str, Any] | None:
    pipe = pipeline if pipeline is not None else build_quickbooks_pipeline_datasets()
    return pick_freshest_dataset(
        pipe.get(key),
        load_upstream_export_dataset("quickbooks", names),
    )


# Named export groups for assemble_direct_import_sections
SOFTDENT_EXPORT_KEYS: dict[str, tuple[str, ...]] = {
    "claims": SOFTDENT_CLAIMS_NAMES,
    "clinicalNotes": SOFTDENT_CLINICAL_NAMES,
    "newPatients": SOFTDENT_NEW_PATIENTS_NAMES,
    "treatmentPlans": SOFTDENT_TREATMENT_PLANS_NAMES,
    "caseAcceptance": SOFTDENT_CASE_ACCEPTANCE_NAMES,
}

QUICKBOOKS_EXPORT_KEYS: dict[str, tuple[str, ...]] = {
    "revenue": QUICKBOOKS_REVENUE_NAMES,
    "expenses": QUICKBOOKS_EXPENSE_NAMES,
    "profitAndLoss": QUICKBOOKS_PL_NAMES,
    "expenseCategories": QUICKBOOKS_EXPENSE_CATEGORY_NAMES,
    "payroll": QUICKBOOKS_PAYROLL_NAMES,
    "ap": QUICKBOOKS_AP_NAMES,
}
