"""Sync real SoftDent and QuickBooks exports into HAL's local import cache.

Reads only from configured export roots and live pipeline outputs. Never writes
sample data. Rejects known demo provider/patient signatures.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_contract import (
    QUICKBOOKS_AR_NAMES,
    QUICKBOOKS_EXPENSE_CATEGORY_NAMES,
    QUICKBOOKS_EXPENSE_NAMES,
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

REPO_ROOT = Path(__file__).resolve().parent.parent

SOFTDENT_BRIDGE_EXPORTS = Path(r"C:\Users\mreno\SoftDentBridge\exports")
NEW_RIDGE_BRIDGE_EXPORTS = Path(r"C:\NewRidgeBridge\exports")
SOFTDENT_FINANCIAL_EXPORTS = Path(r"C:\SoftDentFinancialExports")
QUICKBOOKS_EXPORTS = Path(r"C:\Users\mreno\QuickBooksExports")
SENSEI_DATASYNC = Path(r"C:\ProgramData\Sensei Gateway Client\DataSync")

QB_SDK_SUMMARY = SOFTDENT_FINANCIAL_EXPORTS / "quickbooks_diagnostics" / "quickbooks_sdk_report_probe_summary.json"
BRIDGE_AGGREGATE_JSON = NEW_RIDGE_BRIDGE_EXPORTS / "softdent_bridge_latest.json"

SAMPLE_PROVIDER_MARKERS = frozenset({"dr. adams", "dr. lee", "hygiene team"})
SAMPLE_PATIENT_MARKERS = frozenset({"john doe", "maria santos"})


def _env_path(name: str, default: Path | None = None) -> Path | None:
    configured = os.environ.get(name, "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve()
    return default.resolve() if default else None


def _softdent_source_roots() -> list[Path]:
    roots: list[Path] = []
    for candidate in (
        _env_path("NR2_SOFTDENT_EXPORT_SOURCE"),
        _env_path("SOFTDENT_SOURCE_DIR", SENSEI_DATASYNC),
        SOFTDENT_BRIDGE_EXPORTS,
        SOFTDENT_FINANCIAL_EXPORTS,
        NEW_RIDGE_BRIDGE_EXPORTS,
    ):
        if candidate and candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    return roots


def _quickbooks_source_roots() -> list[Path]:
    roots: list[Path] = []
    for candidate in (
        _env_path("NR2_QUICKBOOKS_EXPORT_SOURCE"),
        _env_path("QUICKBOOKS_SOURCE_DIR"),
        QUICKBOOKS_EXPORTS,
        SOFTDENT_FINANCIAL_EXPORTS,
    ):
        if candidate and candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    return roots


def _read_json(path: Path) -> object | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None


def _is_sample_clinical(rows: list[dict[str, Any]]) -> bool:
    providers = {str(row.get("Provider") or row.get("provider") or "").strip().lower() for row in rows}
    patients = {str(row.get("PatientName") or row.get("patient") or "").strip().lower() for row in rows}
    return bool(providers & SAMPLE_PROVIDER_MARKERS) or bool(patients & SAMPLE_PATIENT_MARKERS)


def _is_sample_dashboard(rows: list[dict[str, Any]]) -> bool:
    providers = {str(row.get("provider") or row.get("Provider") or "").strip().lower() for row in rows}
    return SAMPLE_PROVIDER_MARKERS.issubset(providers)


def _is_sample_claims(rows: list[dict[str, Any]]) -> bool:
    patients = {str(row.get("PatientName") or row.get("patient") or "").strip().lower() for row in rows}
    return bool(patients & SAMPLE_PATIENT_MARKERS)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _write_csv_json_sidecar(csv_path: Path) -> None:
    """Normalize CSV rows to JSON sidecar for consistent JS/Python reads."""
    if not csv_path.is_file() or csv_path.suffix.lower() != ".csv":
        return
    try:
        rows = list(csv.DictReader(csv_path.open("r", encoding="utf-8-sig", newline="")))
    except Exception:
        return
    sidecar = csv_path.with_suffix(".json")
    if sidecar.is_file() and sidecar.stat().st_mtime >= csv_path.stat().st_mtime:
        return
    _write_json(sidecar, rows)


def _copy_if_newer(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    if destination.is_file() and destination.stat().st_mtime >= source.stat().st_mtime:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def _find_newest(root: Path, names: tuple[str, ...]) -> Path | None:
    if not root.is_dir():
        return None
    matches: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.name.casefold() in {name.casefold() for name in names}:
            matches.append(path)
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def _sync_named_exports(roots: list[Path], destination: Path, names: tuple[str, ...], reject_fn=None) -> list[str]:
    copied: list[str] = []
    newest = None
    for root in roots:
        candidate = _find_newest(root, names)
        if candidate and (newest is None or candidate.stat().st_mtime > newest.stat().st_mtime):
            newest = candidate
    if not newest:
        return copied
    if reject_fn:
        try:
            rows = []
            if newest.suffix.lower() == ".json":
                payload = _read_json(newest)
                if isinstance(payload, list):
                    rows = payload
                elif isinstance(payload, dict):
                    rows = payload.get("notes") or payload.get("claims") or payload.get("rows") or []
            elif newest.suffix.lower() == ".csv":
                rows = list(csv.DictReader(newest.open("r", encoding="utf-8-sig", newline="")))
            if isinstance(rows, list) and reject_fn(rows):
                return copied
        except Exception:
            return copied
    dest = destination / newest.name
    if _copy_if_newer(newest, dest):
        copied.append(dest.name)
        if dest.suffix.lower() == ".csv":
            _write_csv_json_sidecar(dest)
    return copied


def _jsonl_practice_total(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        normalized = row.get("normalized") if isinstance(row, dict) else None
        if not isinstance(normalized, dict):
            continue
        account_id = str(normalized.get("account_id") or "").strip().lower()
        if account_id in {"practice_total", "total", "practice"} or normalized.get("total_ar") is not None:
            return normalized
    return None


def _build_dashboard_from_bridge(path: Path) -> list[dict[str, Any]] | None:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return None
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        return None
    production = summary.get("grossProduction") or summary.get("netProduction")
    if production in (None, 0):
        return None
    report_range = payload.get("reportRange") if isinstance(payload.get("reportRange"), dict) else {}
    end_date = report_range.get("endDate")
    period = str(end_date)[:7] if end_date else datetime.now().strftime("%Y-%m")
    practice_name = ""
    practice = payload.get("practice")
    if isinstance(practice, dict):
        practice_name = str(practice.get("name") or "Practice Total")
    return [
        {
            "provider": practice_name or "Practice Total",
            "period": period,
            "production": float(production),
            "collections": float(summary.get("collections") or 0),
            "insurance": float(summary.get("insurance") or 0),
            "patient": float(summary.get("patient") or 0),
        }
    ]


def _build_ar_rows_from_normalized(normalized: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"Bucket": "Current", "Balance": normalized.get("current_balance") or normalized.get("balance_0_30")},
        {"Bucket": "31-60", "Balance": normalized.get("balance_30")},
        {"Bucket": "61-90", "Balance": normalized.get("balance_60")},
        {"Bucket": "90+", "Balance": normalized.get("balance_90")},
    ]


def _sync_softdent_pipeline_exports(destination: Path) -> list[str]:
    written: list[str] = []
    bridge_rows = _build_dashboard_from_bridge(BRIDGE_AGGREGATE_JSON)
    if bridge_rows and not _is_sample_dashboard(bridge_rows):
        dashboard_path = destination / "softdent_dashboard_data.json"
        _write_json(dashboard_path, bridge_rows)
        written.append(dashboard_path.name)

    aging_jsonl = _find_newest(SOFTDENT_FINANCIAL_EXPORTS, ("account_aging.jsonl",))
    if aging_jsonl:
        normalized = _jsonl_practice_total(aging_jsonl)
        if normalized:
            ar_rows = _build_ar_rows_from_normalized(normalized)
            ar_path = destination / "softdent_ar_aging.csv"
            _write_csv(ar_path, ar_rows, ["Bucket", "Balance"])
            written.append(ar_path.name)
    return written


def _sync_quickbooks_sdk_summary(destination: Path) -> list[str]:
    payload = _read_json(QB_SDK_SUMMARY)
    if not isinstance(payload, dict):
        return []
    if str(payload.get("status") or "").upper() != "QUICKBOOKS_SDK_REPORT_DATA_AVAILABLE":
        return []
    revenue = payload.get("total_income")
    expenses = payload.get("total_expenses")
    if revenue in (None, "") or expenses in (None, ""):
        return []
    written: list[str] = []
    revenue_path = destination / "quickbooks_revenue.csv"
    expense_path = destination / "quickbooks_expenses.csv"
    _write_csv(revenue_path, [{"TotalIncome": revenue}], ["TotalIncome"])
    _write_csv(expense_path, [{"TotalExpense": expenses}], ["TotalExpense"])
    written.extend([revenue_path.name, expense_path.name])
    categories = payload.get("top_expense_categories")
    if isinstance(categories, list) and categories:
        category_rows = [
            {"Category": str(item.get("category") or ""), "Amount": item.get("amount")}
            for item in categories
            if isinstance(item, dict) and item.get("amount") not in (None, "")
        ]
        if category_rows:
            categories_path = destination / "quickbooks_expense_categories.csv"
            _write_csv(categories_path, category_rows, ["Category", "Amount"])
            written.append(categories_path.name)
    return written


def _purge_sample_cache(destination: Path) -> list[str]:
    removed: list[str] = []
    dashboard = destination / "softdent_dashboard_data.json"
    if dashboard.is_file():
        try:
            rows = _read_json(dashboard)
            if isinstance(rows, list) and _is_sample_dashboard(rows):
                dashboard.unlink()
                removed.append(dashboard.name)
        except Exception:
            pass
    claims = destination / "softdent_claims_export.csv"
    if claims.is_file():
        try:
            rows = list(csv.DictReader(claims.open("r", encoding="utf-8-sig", newline="")))
            if _is_sample_claims(rows):
                claims.unlink()
                removed.append(claims.name)
        except Exception:
            pass
    clinical = destination / "softdent_clinical_notes_data.json"
    if clinical.is_file():
        try:
            payload = _read_json(clinical)
            rows = payload.get("notes") if isinstance(payload, dict) else payload
            if isinstance(rows, list) and _is_sample_clinical(rows):
                clinical.unlink()
                removed.append(clinical.name)
        except Exception:
            pass
    return removed


def _load_dataset_for_diag(directory: Path, names: tuple[str, ...]) -> dict[str, Any] | None:
    path = _find_newest(directory, names) if directory.is_dir() else None
    if path is None:
        return None
    try:
        rows: list[dict[str, Any]] = []
        if path.suffix.lower() == ".json":
            payload = _read_json(path)
            if isinstance(payload, list):
                rows = [row for row in payload if isinstance(row, dict)]
            elif isinstance(payload, dict):
                rows = payload.get("notes") or payload.get("claims") or payload.get("rows") or []
                if not isinstance(rows, list):
                    rows = []
        elif path.suffix.lower() == ".csv":
            rows = list(csv.DictReader(path.open("r", encoding="utf-8-sig", newline="")))
        return {
            "sourceFile": path.name,
            "modifiedAt": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            "rows": rows,
        }
    except Exception:
        return {"sourceFile": path.name, "modifiedAt": "", "rows": []}


def sync_imports() -> dict[str, Any]:
    """Pull the newest real export files into HAL import folders."""
    softdent_dest = softdent_import_dir()
    quickbooks_dest = quickbooks_import_dir()
    softdent_dest.mkdir(parents=True, exist_ok=True)
    quickbooks_dest.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "syncedAt": datetime.now(timezone.utc).isoformat(),
        "softdent": {"copied": [], "generated": [], "removed": []},
        "quickbooks": {"copied": [], "generated": []},
        "sourceRoots": {"softdent": [], "quickbooks": []},
        "warnings": [],
    }

    result["softdent"]["removed"] = _purge_sample_cache(softdent_dest)

    softdent_roots = _softdent_source_roots()
    quickbooks_roots = _quickbooks_source_roots()
    result["sourceRoots"]["softdent"] = [str(path) for path in softdent_roots]
    result["sourceRoots"]["quickbooks"] = [str(path) for path in quickbooks_roots]
    if not softdent_roots:
        result["warnings"].append(
            "No SoftDent export roots found. Configure NR2_SOFTDENT_EXPORT_SOURCE or SOFTDENT_SOURCE_DIR."
        )
    if not quickbooks_roots:
        result["warnings"].append(
            "No QuickBooks export roots found. Configure NR2_QUICKBOOKS_EXPORT_SOURCE or QUICKBOOKS_SOURCE_DIR."
        )

    result["softdent"]["copied"].extend(_sync_named_exports(softdent_roots, softdent_dest, SOFTDENT_DASHBOARD_NAMES, _is_sample_dashboard))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_roots, softdent_dest, SOFTDENT_CLAIMS_NAMES, _is_sample_claims))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_roots, softdent_dest, SOFTDENT_CLINICAL_NAMES, _is_sample_clinical))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_roots, softdent_dest, SOFTDENT_AR_NAMES))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_roots, softdent_dest, SOFTDENT_NEW_PATIENTS_NAMES))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_roots, softdent_dest, SOFTDENT_TREATMENT_PLANS_NAMES))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_roots, softdent_dest, SOFTDENT_CASE_ACCEPTANCE_NAMES))
    result["softdent"]["generated"].extend(_sync_softdent_pipeline_exports(softdent_dest))

    result["quickbooks"]["copied"].extend(_sync_named_exports(quickbooks_roots, quickbooks_dest, QUICKBOOKS_REVENUE_NAMES))
    result["quickbooks"]["copied"].extend(_sync_named_exports(quickbooks_roots, quickbooks_dest, QUICKBOOKS_EXPENSE_NAMES))
    result["quickbooks"]["copied"].extend(_sync_named_exports(quickbooks_roots, quickbooks_dest, QUICKBOOKS_EXPENSE_CATEGORY_NAMES))
    result["quickbooks"]["copied"].extend(_sync_named_exports(quickbooks_roots, quickbooks_dest, QUICKBOOKS_AR_NAMES))
    result["quickbooks"]["generated"].extend(_sync_quickbooks_sdk_summary(quickbooks_dest))

    try:
        from import_diagnostics import check_upstream_health, evaluate_bundle

        softdent_dest = softdent_import_dir()
        quickbooks_dest = quickbooks_import_dir()
        bundle_for_diag = {
            "loadedAt": result["syncedAt"],
            "softdent": {
                "dashboard": _load_dataset_for_diag(softdent_dest, SOFTDENT_DASHBOARD_NAMES),
                "claims": _load_dataset_for_diag(softdent_dest, SOFTDENT_CLAIMS_NAMES),
                "clinicalNotes": _load_dataset_for_diag(softdent_dest, SOFTDENT_CLINICAL_NAMES),
                "ar": _load_dataset_for_diag(softdent_dest, SOFTDENT_AR_NAMES),
                "newPatients": _load_dataset_for_diag(softdent_dest, SOFTDENT_NEW_PATIENTS_NAMES),
                "treatmentPlans": _load_dataset_for_diag(softdent_dest, SOFTDENT_TREATMENT_PLANS_NAMES),
                "caseAcceptance": _load_dataset_for_diag(softdent_dest, SOFTDENT_CASE_ACCEPTANCE_NAMES),
            },
            "quickbooks": {
                "revenue": _load_dataset_for_diag(quickbooks_dest, QUICKBOOKS_REVENUE_NAMES),
                "expenses": _load_dataset_for_diag(quickbooks_dest, QUICKBOOKS_EXPENSE_NAMES),
                "expenseCategories": _load_dataset_for_diag(quickbooks_dest, QUICKBOOKS_EXPENSE_CATEGORY_NAMES),
                "ar": _load_dataset_for_diag(quickbooks_dest, QUICKBOOKS_AR_NAMES),
            },
        }
        result["diagnostics"] = evaluate_bundle(bundle_for_diag)
        result["upstreamHealth"] = check_upstream_health()
    except Exception as exc:
        result["warnings"].append(f"Import diagnostics unavailable: {exc}")

    return result


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(sync_imports(), indent=2))
