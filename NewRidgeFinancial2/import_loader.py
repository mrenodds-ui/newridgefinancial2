"""Read SoftDent and QuickBooks export files for NewRidgeFinancial 2.0."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# Canonical NR2 import cache (gitignored). Lives under repo-root app/data/imports
# by design — not the retired FastAPI app runtime.

SOFTDENT_DASHBOARD_NAMES = (
    "softdent_dashboard_data.json",
    "softdent_dashboard_export.json",
    "softdent_dashboard_data.csv",
    "softdent_dashboard_export.csv",
)
SOFTDENT_CLAIMS_NAMES = (
    "softdent_claims_export.csv",
    "softdent_claims_data.csv",
    "softdent_claims_export.json",
    "softdent_claims_data.json",
)
SOFTDENT_CLINICAL_NAMES = (
    "softdent_clinical_notes_data.json",
    "softdent_clinical_notes_export.json",
)
SOFTDENT_AR_NAMES = (
    "softdent_ar_aging.csv",
    "softdent_accounts_receivable.csv",
    "softdent_ar_aging.json",
    "patient_aging.csv",
    "ar_aging.csv",
)
QUICKBOOKS_REVENUE_NAMES = (
    "quickbooks_revenue.csv",
    "quickbooks_revenue.json",
    "quickbooks_profit_and_loss.csv",
    "quickbooks_profit_loss.csv",
)
QUICKBOOKS_EXPENSE_NAMES = (
    "quickbooks_expenses.csv",
    "quickbooks_expense_detail.csv",
    "quickbooks_expenses.json",
)
QUICKBOOKS_EXPENSE_CATEGORY_NAMES = (
    "quickbooks_expense_categories.csv",
)
QUICKBOOKS_AR_NAMES = (
    "quickbooks_ar.csv",
    "quickbooks_accounts_receivable.csv",
    "quickbooks_aging.csv",
)


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
        },
        "quickbooks": {
            "dir": str(quickbooks_dir),
            "revenue": _load_dataset(quickbooks_dir, QUICKBOOKS_REVENUE_NAMES),
            "expenses": _load_dataset(quickbooks_dir, QUICKBOOKS_EXPENSE_NAMES),
            "expenseCategories": _load_dataset(quickbooks_dir, QUICKBOOKS_EXPENSE_CATEGORY_NAMES),
            "ar": _load_dataset(quickbooks_dir, QUICKBOOKS_AR_NAMES),
        },
    }
    return bundle
