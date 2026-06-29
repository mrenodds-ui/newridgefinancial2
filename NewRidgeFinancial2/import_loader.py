"""Read SoftDent and QuickBooks export files for NewRidgeFinancial 2.0."""

from __future__ import annotations

import csv
import json
import os
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
    manifest_warnings,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _import_dir(env_name: str, default_rel: str) -> Path:
    configured = os.environ.get(env_name, "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve()
    return (REPO_ROOT / default_rel).resolve()


def softdent_import_dir() -> Path:
    return _import_dir("SOFTDENT_IMPORT_DIR", "app/data/imports/softdent")


def quickbooks_import_dir() -> Path:
    return _import_dir("QUICKBOOKS_IMPORT_DIR", "app/data/imports/quickbooks")


def _mtime_iso(path: Path) -> str:
    if not path.is_file():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle) if row]


def _extract_json_rows(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "items", "notes", "claims"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _read_tabular(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return _extract_json_rows(payload)
    if suffix == ".csv":
        sidecar = path.with_suffix(".json")
        if sidecar.is_file() and sidecar.stat().st_mtime >= path.stat().st_mtime:
            try:
                payload = json.loads(sidecar.read_text(encoding="utf-8-sig"))
                if isinstance(payload, list):
                    return [row for row in payload if isinstance(row, dict)]
            except json.JSONDecodeError:
                pass
        return _read_csv_rows(path)
    return []


def _newest_existing(directory: Path, names: tuple[str, ...]) -> Path | None:
    if not directory.is_dir():
        return None
    matches: list[Path] = []
    name_set = {name.casefold() for name in names}
    for path in directory.iterdir():
        if path.is_file() and path.name.casefold() in name_set:
            matches.append(path)
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def _load_dataset(directory: Path, names: tuple[str, ...]) -> dict[str, Any] | None:
    path = _newest_existing(directory, names)
    if path is None:
        return None
    rows = _read_tabular(path)
    return {
        "sourceFile": path.name,
        "modifiedAt": _mtime_iso(path),
        "rows": rows,
    }


def load_import_bundle(*, sync: bool = True) -> dict[str, Any]:
    sync_status: dict[str, Any] = {
        "attempted": sync,
        "ok": True,
        "error": None,
        "result": None,
        "warnings": manifest_warnings(),
    }
    if sync:
        try:
            from import_sync import sync_imports

            sync_status["result"] = sync_imports()
        except Exception as exc:
            sync_status["ok"] = False
            sync_status["error"] = str(exc)
    softdent_dir = softdent_import_dir()
    quickbooks_dir = quickbooks_import_dir()
    bundle: dict[str, Any] = {
        "loadedAt": datetime.now(timezone.utc).isoformat(),
        "syncStatus": sync_status,
        "softdent": {
            "dir": str(softdent_dir),
            "dashboard": _load_dataset(softdent_dir, SOFTDENT_DASHBOARD_NAMES),
            "claims": _load_dataset(softdent_dir, SOFTDENT_CLAIMS_NAMES),
            "clinicalNotes": _load_dataset(softdent_dir, SOFTDENT_CLINICAL_NAMES),
            "ar": _load_dataset(softdent_dir, SOFTDENT_AR_NAMES),
            "newPatients": _load_dataset(softdent_dir, SOFTDENT_NEW_PATIENTS_NAMES),
            "treatmentPlans": _load_dataset(softdent_dir, SOFTDENT_TREATMENT_PLANS_NAMES),
            "caseAcceptance": _load_dataset(softdent_dir, SOFTDENT_CASE_ACCEPTANCE_NAMES),
        },
        "quickbooks": {
            "dir": str(quickbooks_dir),
            "revenue": _load_dataset(quickbooks_dir, QUICKBOOKS_REVENUE_NAMES),
            "expenses": _load_dataset(quickbooks_dir, QUICKBOOKS_EXPENSE_NAMES),
            "expenseCategories": _load_dataset(quickbooks_dir, QUICKBOOKS_EXPENSE_CATEGORY_NAMES),
            "ar": _load_dataset(quickbooks_dir, QUICKBOOKS_AR_NAMES),
        },
    }
    try:
        from import_diagnostics import check_upstream_health, evaluate_bundle

        bundle["diagnostics"] = evaluate_bundle(bundle)
        bundle["upstreamHealth"] = check_upstream_health()
        if sync_status.get("result") and isinstance(sync_status["result"], dict):
            sync_status["result"].setdefault("diagnostics", bundle["diagnostics"])
            sync_status["result"].setdefault("upstreamHealth", bundle["upstreamHealth"])
    except Exception as exc:
        sync_status.setdefault("warnings", [])
        if isinstance(sync_status["warnings"], list):
            sync_status["warnings"].append(f"Import diagnostics unavailable: {exc}")
    return bundle
