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

def _auto_pull_exports_enabled() -> bool:
    """Pull upstream SoftDent/QuickBooks exports into document-inbox cache folders."""
    return os.environ.get("NR2_AUTO_PULL_EXPORTS", "1").strip().lower() not in {"0", "false", "no", "off"}


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


def _softdent_upstream_candidates() -> list[Path]:
    roots: list[Path] = []
    for candidate in (
        _env_path("NR2_SOFTDENT_EXPORT_SOURCE"),
        _env_path("SOFTDENT_SOURCE_DIR", SENSEI_DATASYNC),
        SOFTDENT_BRIDGE_EXPORTS,
        SOFTDENT_FINANCIAL_EXPORTS,
        NEW_RIDGE_BRIDGE_EXPORTS,
        _env_path("SOFTDENT_REPORT_EXPORTS", Path(r"C:\SoftDentReportExports")),
    ):
        if candidate and candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    return roots


def _softdent_external_roots() -> list[Path]:
    if not _auto_pull_exports_enabled():
        return []
    return _softdent_upstream_candidates()


def _softdent_direct_read_roots() -> list[Path]:
    """Upstream folders for pipeline/direct-first reads (independent of auto-pull copy)."""
    try:
        from practice_source_access import direct_first_imports_enabled
    except Exception:
        direct_first_imports_enabled = None
    direct_on = (
        direct_first_imports_enabled()
        if callable(direct_first_imports_enabled)
        else os.environ.get("NR2_DIRECT_FIRST_IMPORTS", "1").strip().lower() not in {"0", "false", "no", "off"}
    )
    if direct_on or _auto_pull_exports_enabled():
        return _softdent_upstream_candidates()
    return []


def _quickbooks_upstream_candidates() -> list[Path]:
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


def _quickbooks_external_roots() -> list[Path]:
    if not _auto_pull_exports_enabled():
        return []
    return _quickbooks_upstream_candidates()


def _quickbooks_direct_read_roots() -> list[Path]:
    try:
        from practice_source_access import direct_first_imports_enabled
    except Exception:
        direct_first_imports_enabled = None
    direct_on = (
        direct_first_imports_enabled()
        if callable(direct_first_imports_enabled)
        else os.environ.get("NR2_DIRECT_FIRST_IMPORTS", "1").strip().lower() not in {"0", "false", "no", "off"}
    )
    if direct_on or _auto_pull_exports_enabled():
        return _quickbooks_upstream_candidates()
    return []


def _stage_external_artifacts(softdent_dest: Path, quickbooks_dest: Path) -> list[str]:
    """Copy upstream probe/bridge artifacts into document-inbox folders HAL reads."""
    if not _auto_pull_exports_enabled():
        return []
    staged: list[str] = []
    for source, target in (
        (QB_SDK_SUMMARY, quickbooks_dest / "quickbooks_sdk_report_probe_summary.json"),
        (BRIDGE_AGGREGATE_JSON, softdent_dest / "softdent_bridge_latest.json"),
    ):
        if source.is_file() and _copy_if_newer(source, target):
            staged.append(target.name)
    return staged


def _migrate_legacy_import_dirs() -> list[str]:
    """One-time copy from legacy app/data/imports into document-inbox import folders."""
    migrated: list[str] = []
    pairs = (
        (REPO_ROOT / "app" / "data" / "imports" / "softdent", softdent_import_dir()),
        (REPO_ROOT / "app" / "data" / "imports" / "quickbooks", quickbooks_import_dir()),
    )
    for legacy, dest in pairs:
        dest.mkdir(parents=True, exist_ok=True)
        if not legacy.is_dir():
            continue
        for src in legacy.iterdir():
            if not src.is_file():
                continue
            target = dest / src.name
            if not target.is_file() or src.stat().st_mtime > target.stat().st_mtime:
                shutil.copy2(src, target)
                migrated.append(f"{dest.name}/{src.name}")
    return migrated


def _resolve_qb_probe_payload(quickbooks_dest: Path) -> dict[str, Any] | None:
    for path in (
        quickbooks_dest / "quickbooks_sdk_report_probe_summary.json",
        _find_newest(quickbooks_dest, ("quickbooks_sdk_report_probe_summary.json",)),
    ):
        if path and path.is_file():
            payload = _read_json(path)
            if isinstance(payload, dict):
                return payload
    if _auto_pull_exports_enabled() and QB_SDK_SUMMARY.is_file():
        payload = _read_json(QB_SDK_SUMMARY)
        if isinstance(payload, dict):
            return payload
    return None


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
    wanted = {name.casefold() for name in names}
    matches: list[Path] = []
    try:
        for path in root.iterdir():
            if path.is_file() and path.name.casefold() in wanted:
                matches.append(path)
            elif path.is_dir():
                for nested in path.iterdir():
                    if nested.is_file() and nested.name.casefold() in wanted:
                        matches.append(nested)
    except OSError:
        return None
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def _sync_bulk_prefix_exports(roots: list[Path], destination: Path, prefix: str) -> list[str]:
    """Copy matching export files from upstream roots (full HAL pull, shallow scan only)."""
    copied: list[str] = []
    allowed_suffixes = {".csv", ".json", ".jsonl"}
    seen: set[str] = set()
    prefix_lower = prefix.lower()
    for root in roots:
        if not root.is_dir():
            continue
        candidates: list[Path] = []
        try:
            for path in root.iterdir():
                if path.is_file() and path.name.lower().startswith(prefix_lower) and path.suffix.lower() in allowed_suffixes:
                    candidates.append(path)
                elif path.is_dir():
                    for nested in path.iterdir():
                        if (
                            nested.is_file()
                            and nested.name.lower().startswith(prefix_lower)
                            and nested.suffix.lower() in allowed_suffixes
                        ):
                            candidates.append(nested)
        except OSError:
            continue
        for path in candidates:
            if path.name in seen:
                continue
            dest = destination / path.name
            if _copy_if_newer(path, dest):
                copied.append(dest.name)
                seen.add(path.name)
                if dest.suffix.lower() == ".csv":
                    _write_csv_json_sidecar(dest)
    return copied


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
    collections = float(summary.get("collections") or 0)
    row = {
        "provider": practice_name or "Practice Total",
        "period": period,
        "production": float(production),
        "collections": collections,
        "insurance": float(summary.get("insurance") or 0),
        "patient": float(summary.get("patient") or 0),
    }
    if float(production) > 0 and collections <= 0:
        row["collectionsReported"] = False
    return [row]


def _build_ar_rows_from_normalized(normalized: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"Bucket": "Current", "Balance": normalized.get("current_balance") or normalized.get("balance_0_30")},
        {"Bucket": "31-60", "Balance": normalized.get("balance_30")},
        {"Bucket": "61-90", "Balance": normalized.get("balance_60")},
        {"Bucket": "90+", "Balance": normalized.get("balance_90")},
    ]


def _trim_rows_to_relevant_periods(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from import_cache_ttl import relevant_period_labels

    allowed = set(relevant_period_labels())
    trimmed: list[dict[str, Any]] = []
    for row in rows:
        period = str(row.get("period") or row.get("Period") or row.get("year_month") or "").strip()
        if not period:
            trimmed.append(row)
            continue
        key = period[:7] if len(period) >= 7 else period
        if key in allowed:
            trimmed.append(row)
    return trimmed if trimmed else rows[:1]


def _sync_softdent_pipeline_exports(destination: Path) -> dict[str, Any]:
    written: list[str] = []
    collections_diagnostic: dict[str, Any] | None = None
    practice_sync: dict[str, Any] | None = None
    period_sync: dict[str, Any] | None = None
    bridge_path = destination / "softdent_bridge_latest.json"
    if not bridge_path.is_file():
        bridge_path = _find_newest(destination, ("softdent_bridge_latest.json",))
    if (not bridge_path or not bridge_path.is_file()) and _auto_pull_exports_enabled():
        bridge_path = BRIDGE_AGGREGATE_JSON if BRIDGE_AGGREGATE_JSON.is_file() else None
    bridge_rows = _build_dashboard_from_bridge(bridge_path) if bridge_path and bridge_path.is_file() else None
    if bridge_rows and not _is_sample_dashboard(bridge_rows):
        bridge_rows = _trim_rows_to_relevant_periods(bridge_rows)
        dashboard_path = destination / "softdent_dashboard_data.json"
        _write_json(dashboard_path, bridge_rows)
        written.append(dashboard_path.name)

    aging_jsonl = _find_newest(destination, ("account_aging.jsonl",))
    if not aging_jsonl and _auto_pull_exports_enabled():
        aging_jsonl = _find_newest(SOFTDENT_FINANCIAL_EXPORTS, ("account_aging.jsonl",))
    if aging_jsonl:
        normalized = _jsonl_practice_total(aging_jsonl)
        if normalized:
            ar_rows = _build_ar_rows_from_normalized(normalized)
            ar_path = destination / "softdent_ar_aging.csv"
            _write_csv(ar_path, ar_rows, ["Bucket", "Balance"])
            written.append(ar_path.name)
    try:
        from softdent_dashboard_period_sync import sync_dashboard_period_rows

        period_sync = sync_dashboard_period_rows()
        if period_sync.get("ok") and period_sync.get("path"):
            written.append("softdent_dashboard_data.json")
        collections_diagnostic = period_sync.get("collectionsDiagnostic")
    except Exception:
        pass
    try:
        from softdent_practice_exports import sync_practice_exports

        practice_sync = sync_practice_exports()
        written.extend(practice_sync.get("written") or [])
    except Exception:
        pass
    written.extend(_sync_operational_softdent_exports(destination))
    return {
        "written": written,
        "collectionsDiagnostic": collections_diagnostic,
        "practiceSync": practice_sync,
        "periodSync": period_sync,
    }


def _recover_expense_categories_csv(destination: Path) -> list[str]:
    """Convert a JSON QuickBooks probe accidentally stored as expense_categories.csv."""
    categories_path = destination / "quickbooks_expense_categories.csv"
    if not categories_path.is_file():
        return []
    raw = categories_path.read_text(encoding="utf-8-sig").lstrip()
    if not raw.startswith("{"):
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    categories = payload.get("top_expense_categories")
    if not isinstance(categories, list) or not categories:
        return []
    category_rows = [
        {
            "Category": str(item.get("category") or ""),
            "Amount": item.get("amount"),
            "Period": str(item.get("period") or payload.get("period") or ""),
        }
        for item in categories
        if isinstance(item, dict) and item.get("amount") not in (None, "")
    ]
    if not category_rows:
        return []
    has_period = any(str(row.get("Period") or "").strip() for row in category_rows)
    if not has_period:
        category_rows = [{**row, "Scope": "YTD"} for row in category_rows]
        headers = ["Category", "Amount", "Scope"]
    else:
        headers = ["Category", "Amount", "Period"]
    _write_csv(
        categories_path,
        [{key: row.get(key, "") for key in headers} for row in category_rows],
        headers,
    )
    return [categories_path.name]


def _sync_operational_softdent_exports(destination: Path) -> list[str]:
    """Refresh claims/clinical notes from the live daysheet pipeline when exports are stale."""
    written: list[str] = []
    try:
        from softdent_operational_pipeline import build_daysheet_claims_dataset, build_daysheet_clinical_dataset

        claims = build_daysheet_claims_dataset()
        claim_rows = (claims or {}).get("rows") or []
        if claim_rows and not _is_sample_claims(claim_rows):
            claims_path = destination / "softdent_claims_export.csv"
            fieldnames = list(claim_rows[0].keys())
            _write_csv(claims_path, claim_rows, fieldnames)
            _write_csv_json_sidecar(claims_path)
            written.append(claims_path.name)

        clinical = build_daysheet_clinical_dataset()
        clinical_rows = (clinical or {}).get("rows") or []
        if clinical_rows and not _is_sample_clinical(clinical_rows):
            clinical_path = destination / "softdent_clinical_notes_data.json"
            _write_json(clinical_path, {"rows": clinical_rows})
            written.append(clinical_path.name)
    except Exception:
        pass
    return written


def _sync_quickbooks_sdk_summary(destination: Path) -> list[str]:
    payload: dict[str, Any] | None = None
    probe_path = _find_newest(destination, ("quickbooks_sdk_report_probe_summary.json",))
    if probe_path:
        read = _read_json(probe_path)
        if isinstance(read, dict):
            payload = read
    if payload is None and _auto_pull_exports_enabled() and QB_SDK_SUMMARY.is_file():
        read = _read_json(QB_SDK_SUMMARY)
        if isinstance(read, dict):
            payload = read
    if not isinstance(payload, dict):
        return _recover_expense_categories_csv(destination)
    if str(payload.get("status") or "").upper() != "QUICKBOOKS_SDK_REPORT_DATA_AVAILABLE":
        return _recover_expense_categories_csv(destination)
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
            {
                "Category": str(item.get("category") or ""),
                "Amount": item.get("amount"),
                "Period": str(item.get("period") or payload.get("period") or ""),
            }
            for item in categories
            if isinstance(item, dict) and item.get("amount") not in (None, "")
        ]
        if category_rows:
            categories_path = destination / "quickbooks_expense_categories.csv"
            has_period = any(str(row.get("Period") or "").strip() for row in category_rows)
            if not has_period:
                category_rows = [{**row, "Scope": "YTD"} for row in category_rows]
                headers = ["Category", "Amount", "Scope"]
            else:
                headers = ["Category", "Amount", "Period"]
            _write_csv(
                categories_path,
                [{key: row.get(key, "") for key in headers} for row in category_rows],
                headers,
            )
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
            head = claims.read_text(encoding="utf-8-sig", errors="ignore")[:256].lstrip()
            if head.startswith("{"):
                claims.unlink()
                removed.append(claims.name)
            else:
                rows = list(csv.DictReader(claims.open("r", encoding="utf-8-sig", newline="")))
                if _is_sample_claims(rows):
                    claims.unlink()
                    removed.append(claims.name)
                elif rows and not any(
                    str(row.get("ClaimId") or row.get("claimId") or row.get("id") or "").strip() for row in rows[:10]
                ):
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
        from import_cache_ttl import sha256_file

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
            "sha256": sha256_file(path),
            "rows": rows,
        }
    except Exception:
        return {"sourceFile": path.name, "modifiedAt": "", "rows": []}


def _full_pull_enabled(full_pull: bool | None = None) -> bool:
    if full_pull is not None:
        return bool(full_pull)
    return os.environ.get("NR2_HAL_FULL_PULL", "0").strip().lower() in {"1", "true", "yes", "on"}


def sync_imports(full_pull: bool | None = None) -> dict[str, Any]:
    """Pull the newest real export files into HAL import folders."""
    full_pull = _full_pull_enabled(full_pull)
    from import_cache_ttl import (
        collect_dataset_checksums,
        enforce_quickbooks_period_files,
        load_manifest,
        purge_expired_ocr_files,
        purge_if_expired,
        relevant_period_labels,
        write_manifest,
    )
    from quickbooks_monthly_sync import sync_quickbooks_monthly_exports

    previous_manifest = load_manifest()
    previous_checksums = dict((previous_manifest or {}).get("datasetChecksums") or {})
    purge_result = purge_if_expired()
    removed_ocr_files = purge_expired_ocr_files()
    if removed_ocr_files:
        purge_result = dict(purge_result)
        purge_result["removedOcrFiles"] = removed_ocr_files
    softdent_dest = softdent_import_dir()
    quickbooks_dest = quickbooks_import_dir()
    softdent_dest.mkdir(parents=True, exist_ok=True)
    quickbooks_dest.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "syncedAt": datetime.now(timezone.utc).isoformat(),
        "fullPull": full_pull,
        "previousChecksums": previous_checksums,
        "softdent": {"copied": [], "generated": [], "removed": []},
        "quickbooks": {"copied": [], "generated": [], "monthly": {}},
        "sourceRoots": {"softdent": [], "quickbooks": []},
        "warnings": [],
    }

    if full_pull:
        result["softdent"]["removed"] = []
        result["warnings"].append("Full HAL pull — skipped sample-cache purge so bridge exports can load.")
    else:
        result["softdent"]["removed"] = _purge_sample_cache(softdent_dest)
    migrated = _migrate_legacy_import_dirs()
    if migrated:
        result["warnings"].append(
            f"Migrated {len(migrated)} legacy import file(s) into document-inbox folders."
        )

    softdent_external = _softdent_external_roots()
    quickbooks_external = _quickbooks_external_roots()
    result["sourceRoots"]["softdent"] = [str(path) for path in softdent_external]
    result["sourceRoots"]["quickbooks"] = [str(path) for path in quickbooks_external]
    result["importDestinations"] = {
        "softdent": str(softdent_dest),
        "quickbooks": str(quickbooks_dest),
    }
    result["autoPull"] = _auto_pull_exports_enabled()
    result["importMode"] = "document-inbox-cache"
    if _auto_pull_exports_enabled():
        result["warnings"].append(
            "Auto-pull copies upstream SoftDent/QuickBooks exports into "
            f"{softdent_dest.relative_to(REPO_ROOT)} and "
            f"{quickbooks_dest.relative_to(REPO_ROOT)} (document page). HAL reads only from those folders."
        )
        if not softdent_external:
            result["warnings"].append(
                "No SoftDent auto-pull roots found. Configure NR2_SOFTDENT_EXPORT_SOURCE or SOFTDENT_SOURCE_DIR, "
                "or drop files manually in the document-inbox softdent folder."
            )
        if not quickbooks_external:
            result["warnings"].append(
                "No QuickBooks auto-pull roots found. Configure NR2_QUICKBOOKS_EXPORT_SOURCE or QUICKBOOKS_SOURCE_DIR, "
                "or drop files manually in the document-inbox quickbooks folder."
            )
    else:
        result["warnings"].append(
            "Auto-pull disabled (NR2_AUTO_PULL_EXPORTS=0). Drop SoftDent exports in "
            f"{softdent_dest.relative_to(REPO_ROOT)} and QuickBooks exports in "
            f"{quickbooks_dest.relative_to(REPO_ROOT)}."
        )

    staged = _stage_external_artifacts(softdent_dest, quickbooks_dest)
    if staged:
        result["softdent"]["copied"].extend([name for name in staged if name.startswith("softdent")])
        result["quickbooks"]["copied"].extend([name for name in staged if name.startswith("quickbooks")])

    if full_pull:
        result["softdent"]["copied"].extend(_sync_bulk_prefix_exports(softdent_external, softdent_dest, "softdent_"))
        result["quickbooks"]["copied"].extend(_sync_bulk_prefix_exports(quickbooks_external, quickbooks_dest, "quickbooks_"))
        result["warnings"].append(
            "Full HAL pull enabled — copied all softdent_* and quickbooks_* exports from upstream roots."
        )

    dashboard_reject = None if full_pull else _is_sample_dashboard
    claims_reject = None if full_pull else _is_sample_claims
    clinical_reject = None if full_pull else _is_sample_clinical

    result["softdent"]["copied"].extend(_sync_named_exports(softdent_external, softdent_dest, SOFTDENT_DASHBOARD_NAMES, dashboard_reject))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_external, softdent_dest, SOFTDENT_CLAIMS_NAMES, claims_reject))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_external, softdent_dest, SOFTDENT_CLINICAL_NAMES, clinical_reject))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_external, softdent_dest, SOFTDENT_AR_NAMES))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_external, softdent_dest, SOFTDENT_NEW_PATIENTS_NAMES))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_external, softdent_dest, SOFTDENT_TREATMENT_PLANS_NAMES))
    result["softdent"]["copied"].extend(_sync_named_exports(softdent_external, softdent_dest, SOFTDENT_CASE_ACCEPTANCE_NAMES))
    pipeline = _sync_softdent_pipeline_exports(softdent_dest)
    result["softdent"]["generated"].extend(pipeline.get("written") or [])
    if pipeline.get("periodSync"):
        result["periodSync"] = pipeline["periodSync"]
        for entry in (pipeline["periodSync"].get("mergeLog") or []):
            if entry.get("action") != "upsert":
                continue
            result["warnings"].append(
                "Dashboard period upsert "
                f"{entry.get('period')}: production {entry.get('priorProduction')} -> {entry.get('mergedProduction')}, "
                f"collections {entry.get('priorCollections')} -> {entry.get('mergedCollections')}."
            )
    for issue in (pipeline.get("collectionsDiagnostic") or {}).get("issues") or []:
        result["warnings"].append(f"Collections: {issue}")
    if pipeline.get("practiceSync") and not (pipeline["practiceSync"].get("written") or []):
        db_hint = (pipeline["practiceSync"].get("collectionsDiagnostic") or {}).get("analyticsDb")
        if db_hint:
            result["warnings"].append(
                "Practice widgets (new patients, treatment plans) — analytics DB present but no matching tables; "
                "drop manual exports or extend softdent_financial_analytics schema."
            )

    result["quickbooks"]["copied"].extend(_sync_named_exports(quickbooks_external, quickbooks_dest, QUICKBOOKS_REVENUE_NAMES))
    result["quickbooks"]["copied"].extend(_sync_named_exports(quickbooks_external, quickbooks_dest, QUICKBOOKS_EXPENSE_NAMES))
    result["quickbooks"]["copied"].extend(_sync_named_exports(quickbooks_external, quickbooks_dest, QUICKBOOKS_EXPENSE_CATEGORY_NAMES))
    result["quickbooks"]["copied"].extend(_sync_named_exports(quickbooks_external, quickbooks_dest, QUICKBOOKS_AR_NAMES))
    probe_payload = _resolve_qb_probe_payload(quickbooks_dest)
    monthly_result = sync_quickbooks_monthly_exports(
        quickbooks_dest,
        probe_payload=probe_payload if isinstance(probe_payload, dict) else None,
    )
    result["quickbooks"]["monthly"] = monthly_result
    if monthly_result.get("written"):
        result["quickbooks"]["generated"].extend(monthly_result["written"])
    else:
        result["quickbooks"]["generated"].extend(_sync_quickbooks_sdk_summary(quickbooks_dest))
    recovered_categories = _recover_expense_categories_csv(quickbooks_dest)
    if recovered_categories:
        result["quickbooks"]["generated"].extend(recovered_categories)

    qb_periods = list(monthly_result.get("periods") or [])
    sd_periods = relevant_period_labels()

    trimmed = enforce_quickbooks_period_files(quickbooks_dest)
    if trimmed:
        result["quickbooks"]["generated"].extend(trimmed)

    dataset_checksums = collect_dataset_checksums(softdent_dest, quickbooks_dest)
    result["cache"] = write_manifest(
        synced_at=result["syncedAt"],
        periods={"quickbooks": qb_periods, "softdent": sd_periods},
        purge_result=purge_result,
        dataset_checksums=dataset_checksums,
    )
    if purge_result.get("purged"):
        result["warnings"].append(
            f"Import cache was purged after {purge_result.get('reason', 'retention')} — fresh relevant periods only."
        )
    if removed_ocr_files:
        result["warnings"].append(
            f"Removed {len(removed_ocr_files)} OCR archive file(s) older than retention window."
        )

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
        result["diagnostics"] = evaluate_bundle(
            bundle_for_diag,
            deep=False,
            previous_checksums=previous_checksums,
        )
        if os.environ.get("NR2_IMPORT_SYNC_UPSTREAM_HEALTH", "0").strip().lower() in {"1", "true", "yes", "on"}:
            result["upstreamHealth"] = check_upstream_health()
        dashboard_rows = (bundle_for_diag.get("softdent") or {}).get("dashboard")
        if isinstance(dashboard_rows, dict):
            rows = dashboard_rows.get("rows") or []
            if isinstance(rows, list) and any(
                isinstance(row, dict) and row.get("collectionsReported") is False for row in rows
            ):
                result["warnings"].append(
                    "SoftDent collections not reported for current period (production without daysheet totals). "
                    "Widgets will show collections as unavailable, not zero."
                )
    except Exception as exc:
        result["warnings"].append(f"Import diagnostics unavailable: {exc}")

    return result


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(sync_imports(), indent=2))
