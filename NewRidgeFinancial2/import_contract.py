"""Shared import filename contract for NR2 sync and load paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = Path(__file__).resolve().parent / "import-manifest.json"
SUPPORTED_MANIFEST_VERSION = 1

_FALLBACK_DATASET_NAMES: dict[str, tuple[str, ...]] = {
    "softdent.dashboard": (
        "softdent_dashboard_data.json",
        "softdent_dashboard_export.json",
        "softdent_dashboard_data.csv",
        "softdent_dashboard_export.csv",
    ),
    "softdent.claims": (
        "softdent_claims_export.csv",
        "softdent_claims_data.csv",
        "softdent_claims_export.json",
        "softdent_claims_data.json",
    ),
    "softdent.clinicalNotes": (
        "softdent_clinical_notes_data.json",
        "softdent_clinical_notes_export.json",
    ),
    "softdent.ar": (
        "softdent_ar_aging.csv",
        "softdent_accounts_receivable.csv",
        "softdent_ar_aging.json",
        "patient_aging.csv",
        "ar_aging.csv",
    ),
    "quickbooks.revenue": (
        "quickbooks_revenue.csv",
        "quickbooks_revenue.json",
    ),
    "quickbooks.expenses": (
        "quickbooks_expenses.csv",
        "quickbooks_expense_detail.csv",
        "quickbooks_expenses.json",
    ),
    "quickbooks.profitAndLoss": (
        "quickbooks_profit_and_loss.csv",
        "quickbooks_profit_loss.csv",
    ),
    "quickbooks.expenseCategories": (
        "quickbooks_expense_categories.csv",
    ),
    "quickbooks.ar": (
        "quickbooks_ar.csv",
        "quickbooks_accounts_receivable.csv",
        "quickbooks_aging.csv",
    ),
    "softdent.newPatients": (
        "softdent_new_patients.csv",
        "softdent_new_patients.json",
        "new_patients.csv",
    ),
    "softdent.treatmentPlans": (
        "treatment_plan_summary.csv",
        "softdent_treatment_plan_summary.csv",
        "treatment_plan_summary.json",
    ),
    "softdent.caseAcceptance": (
        "case_acceptance.csv",
        "softdent_case_acceptance.csv",
        "case_acceptance.json",
    ),
    "softdent.hygieneRecall": (
        "hygiene_recall_summary.csv",
        "softdent_hygiene_recall.csv",
        "hygiene_recall_summary.json",
    ),
    "softdent.operatory": (
        "operatory_schedule.json",
        "softdent_operatory_chairs.json",
    ),
}

_manifest_warnings: list[str] = []
_manifest_payload_cache: dict[str, Any] | None = None


def manifest_warnings() -> list[str]:
    return list(_manifest_warnings)


def load_manifest_payload() -> dict[str, Any]:
    global _manifest_payload_cache, _manifest_warnings
    if _manifest_payload_cache is not None:
        return _manifest_payload_cache
    if not MANIFEST_PATH.is_file():
        _manifest_warnings.append(f"Import manifest missing at {MANIFEST_PATH}; using built-in filename fallbacks.")
        _manifest_payload_cache = {
            "version": SUPPORTED_MANIFEST_VERSION,
            "datasets": {
                key: {"filenames": list(names)}
                for key, names in _FALLBACK_DATASET_NAMES.items()
            },
        }
        return _manifest_payload_cache
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _manifest_warnings.append(f"Import manifest JSON invalid: {exc}")
        payload = {
            "version": SUPPORTED_MANIFEST_VERSION,
            "datasets": {
                key: {"filenames": list(names)}
                for key, names in _FALLBACK_DATASET_NAMES.items()
            },
        }
    if payload.get("version") != SUPPORTED_MANIFEST_VERSION:
        _manifest_warnings.append(
            f"Import manifest version {payload.get('version')!r} unsupported (expected {SUPPORTED_MANIFEST_VERSION}); using fallbacks."
        )
    _manifest_payload_cache = payload
    return payload


def dataset_contract(dataset_key: str) -> dict[str, Any]:
    manifest = load_manifest_payload()
    datasets = manifest.get("datasets") or {}
    entry = datasets.get(dataset_key)
    if isinstance(entry, dict):
        return entry
    fallback = _FALLBACK_DATASET_NAMES.get(dataset_key)
    return {"filenames": list(fallback or ())}


def pick_field(row: dict[str, Any], names: list[str] | tuple[str, ...]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
        match = next((key for key in row if str(key).casefold() == str(name).casefold()), None)
        if match is not None and row[match] not in (None, ""):
            return row[match]
    return None


def _aliases_for_field(contract: dict[str, Any], field_name: str) -> list[str]:
    aliases = contract.get("fieldAliases") or {}
    configured = aliases.get(field_name)
    if isinstance(configured, list) and configured:
        return [str(name) for name in configured]
    return [field_name]


def validate_rows_for_contract(contract: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = contract.get("requiredFields") or []
    if not required:
        return {"ok": True, "requiredFieldFailures": []}
    if not rows:
        return {"ok": False, "requiredFieldFailures": list(required)}
    failures: list[str] = []
    for field_name in required:
        aliases = _aliases_for_field(contract, str(field_name))
        if not any(pick_field(row, aliases) not in (None, "") for row in rows):
            failures.append(str(field_name))
    return {"ok": not failures, "requiredFieldFailures": failures}


def _load_manifest_dataset_names() -> dict[str, tuple[str, ...]]:
    global _manifest_warnings
    manifest = load_manifest_payload()
    datasets = manifest.get("datasets") or {}
    resolved: dict[str, tuple[str, ...]] = {}
    for key, fallback in _FALLBACK_DATASET_NAMES.items():
        entry = datasets.get(key) or {}
        filenames = entry.get("filenames") if isinstance(entry, dict) else None
        if isinstance(filenames, list) and filenames:
            resolved[key] = tuple(str(name) for name in filenames)
        else:
            resolved[key] = fallback
    return resolved


_MANIFEST_NAMES = _load_manifest_dataset_names()

SOFTDENT_DASHBOARD_NAMES = _MANIFEST_NAMES["softdent.dashboard"]
SOFTDENT_CLAIMS_NAMES = _MANIFEST_NAMES["softdent.claims"]
SOFTDENT_CLINICAL_NAMES = _MANIFEST_NAMES["softdent.clinicalNotes"]
SOFTDENT_AR_NAMES = _MANIFEST_NAMES["softdent.ar"]
QUICKBOOKS_REVENUE_NAMES = _MANIFEST_NAMES["quickbooks.revenue"]
QUICKBOOKS_EXPENSE_NAMES = _MANIFEST_NAMES["quickbooks.expenses"]
QUICKBOOKS_PL_NAMES = _MANIFEST_NAMES["quickbooks.profitAndLoss"]
QUICKBOOKS_EXPENSE_CATEGORY_NAMES = _MANIFEST_NAMES["quickbooks.expenseCategories"]
QUICKBOOKS_AR_NAMES = _MANIFEST_NAMES["quickbooks.ar"]
SOFTDENT_NEW_PATIENTS_NAMES = _MANIFEST_NAMES["softdent.newPatients"]
SOFTDENT_TREATMENT_PLANS_NAMES = _MANIFEST_NAMES["softdent.treatmentPlans"]
SOFTDENT_CASE_ACCEPTANCE_NAMES = _MANIFEST_NAMES["softdent.caseAcceptance"]
SOFTDENT_HYGIENE_RECALL_NAMES = _MANIFEST_NAMES["softdent.hygieneRecall"]
SOFTDENT_OPERATORY_NAMES = _MANIFEST_NAMES["softdent.operatory"]
