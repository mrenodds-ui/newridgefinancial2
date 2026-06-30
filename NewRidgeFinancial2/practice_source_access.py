"""Authorized read-only direct access to practice QuickBooks and SoftDent sources for HAL.

HAL is treated as an on-device practice employee: may read upstream exports, bridge
aggregates, analytics DB rows, and QuickBooks Desktop SDK summaries. Never writes back.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_contract import (
    QUICKBOOKS_AR_NAMES,
    QUICKBOOKS_EXPENSE_CATEGORY_NAMES,
    QUICKBOOKS_EXPENSE_NAMES,
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
    _auto_pull_exports_enabled,
    _build_ar_rows_from_normalized,
    _build_dashboard_from_bridge,
    _find_newest,
    _jsonl_practice_total,
    _quickbooks_external_roots,
    _read_json,
    _softdent_external_roots,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_ROOT = REPO_ROOT / "_legacy"

QUICKBOOKS_RESOURCES: dict[str, dict[str, Any]] = {
    "revenue": {"label": "QuickBooks revenue (live SDK)", "kind": "sdk", "topic": "revenue"},
    "expenses": {"label": "QuickBooks expenses (live SDK)", "kind": "sdk", "topic": "expenses"},
    "ar": {"label": "QuickBooks A/R (live SDK)", "kind": "sdk", "topic": "ar"},
    "probe_summary": {"label": "QuickBooks SDK probe summary JSON", "kind": "probe"},
    "monthly_pnl": {"label": "QuickBooks monthly P&L rows (analytics DB + SDK)", "kind": "monthly"},
    "profit_and_loss": {"label": "QuickBooks P&L export file", "kind": "export", "names": QUICKBOOKS_PL_NAMES},
    "revenue_export": {"label": "QuickBooks revenue export file", "kind": "export", "names": QUICKBOOKS_REVENUE_NAMES},
    "expenses_export": {"label": "QuickBooks expenses export file", "kind": "export", "names": QUICKBOOKS_EXPENSE_NAMES},
    "expense_categories": {"label": "QuickBooks expense categories export", "kind": "export", "names": QUICKBOOKS_EXPENSE_CATEGORY_NAMES},
    "ar_export": {"label": "QuickBooks A/R export file", "kind": "export", "names": QUICKBOOKS_AR_NAMES},
}

SOFTDENT_RESOURCES: dict[str, dict[str, Any]] = {
    "dashboard": {"label": "SoftDent dashboard export", "kind": "export", "names": SOFTDENT_DASHBOARD_NAMES},
    "claims": {"label": "SoftDent claims export", "kind": "export", "names": SOFTDENT_CLAIMS_NAMES},
    "clinical_notes": {"label": "SoftDent clinical notes export", "kind": "export", "names": SOFTDENT_CLINICAL_NAMES},
    "ar": {"label": "SoftDent A/R aging export", "kind": "export", "names": SOFTDENT_AR_NAMES},
    "new_patients": {"label": "SoftDent new patients export", "kind": "export", "names": SOFTDENT_NEW_PATIENTS_NAMES},
    "treatment_plans": {"label": "SoftDent treatment plan export", "kind": "export", "names": SOFTDENT_TREATMENT_PLANS_NAMES},
    "case_acceptance": {"label": "SoftDent case acceptance export", "kind": "export", "names": SOFTDENT_CASE_ACCEPTANCE_NAMES},
    "bridge": {"label": "SoftDent bridge aggregate (live JSON)", "kind": "bridge"},
    "pipeline_ar": {"label": "SoftDent account_aging.jsonl pipeline", "kind": "pipeline_ar"},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scan_roots(system: str) -> list[Path]:
    roots: list[Path] = []
    if system == "quickbooks":
        roots.extend(_quickbooks_external_roots())
        cache = quickbooks_import_dir()
    else:
        roots.extend(_softdent_external_roots())
        cache = softdent_import_dir()
    if cache.is_dir() and cache not in roots:
        roots.append(cache)
    return roots


def _load_file_dataset(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if path.suffix.lower() == ".json":
        payload = _read_json(path)
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            nested = payload.get("notes") or payload.get("claims") or payload.get("rows")
            if isinstance(nested, list):
                rows = [row for row in nested if isinstance(row, dict)]
            else:
                rows = [payload]
    elif path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(path.open("r", encoding="utf-8-sig", newline="")))
    return {
        "sourceFile": path.name,
        "sourcePath": str(path),
        "modifiedAt": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "rows": rows,
        "rowCount": len(rows),
    }


def _load_newest_export(system: str, names: tuple[str, ...]) -> dict[str, Any] | None:
    newest: Path | None = None
    for root in _scan_roots(system):
        candidate = _find_newest(root, names)
        if candidate and (newest is None or candidate.stat().st_mtime > newest.stat().st_mtime):
            newest = candidate
    if not newest:
        return None
    dataset = _load_file_dataset(newest)
    dataset["sourceKind"] = "export-file"
    return dataset


def _fetch_qb_sdk(topic: str, period_start: str | None, period_end: str | None) -> dict[str, Any]:
    python = sys.executable
    command = [python, "-m", "app.quickbooks_sdk_runner", topic]
    if period_start and period_end:
        command.extend([period_start, period_end])
    cwd = LEGACY_ROOT if LEGACY_ROOT.is_dir() else REPO_ROOT
    try:
        import subprocess

        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=max(int(os.environ.get("NR2_QB_DIRECT_SDK_TIMEOUT", "120")), 30),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "sourceKind": "quickbooks-sdk", "error": str(exc), "rows": []}
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip() or f"exit {completed.returncode}"
        return {"ok": False, "sourceKind": "quickbooks-sdk", "error": detail, "rows": []}
    try:
        payload = json.loads(completed.stdout.strip() or "[]")
    except json.JSONDecodeError as exc:
        return {"ok": False, "sourceKind": "quickbooks-sdk", "error": f"invalid JSON: {exc}", "rows": []}
    rows = payload if isinstance(payload, list) else []
    return {
        "ok": True,
        "sourceKind": "quickbooks-sdk",
        "topic": topic,
        "rows": rows,
        "rowCount": len(rows),
    }


def list_catalog() -> dict[str, Any]:
    return {
        "authorized": True,
        "readOnly": True,
        "fetchedAt": _utc_now(),
        "policy": (
            "HAL may read SoftDent and QuickBooks directly as an authorized practice employee. "
            "Reads are local-only; nothing is posted or written back."
        ),
        "autoPullEnabled": _auto_pull_exports_enabled(),
        "cacheDirs": {
            "softdent": str(softdent_import_dir()),
            "quickbooks": str(quickbooks_import_dir()),
        },
        "systems": {
            "quickbooks": {
                "upstreamRoots": [str(p) for p in _quickbooks_external_roots()],
                "resources": {key: spec["label"] for key, spec in QUICKBOOKS_RESOURCES.items()},
            },
            "softdent": {
                "upstreamRoots": [str(p) for p in _softdent_external_roots()],
                "resources": {key: spec["label"] for key, spec in SOFTDENT_RESOURCES.items()},
            },
        },
    }


def _fetch_quickbooks(resource: str, options: dict[str, Any]) -> dict[str, Any]:
    spec = QUICKBOOKS_RESOURCES.get(resource)
    if not spec:
        return {"ok": False, "system": "quickbooks", "resource": resource, "error": f"Unknown QuickBooks resource: {resource}"}

    if spec["kind"] == "sdk":
        result = _fetch_qb_sdk(spec["topic"], options.get("periodStart"), options.get("periodEnd"))
        result.update({"system": "quickbooks", "resource": resource, "label": spec["label"]})
        return result

    if spec["kind"] == "probe":
        for path in (
            quickbooks_import_dir() / "quickbooks_sdk_report_probe_summary.json",
            _find_newest(quickbooks_import_dir(), ("quickbooks_sdk_report_probe_summary.json",)),
            QB_SDK_SUMMARY if QB_SDK_SUMMARY.is_file() else None,
        ):
            if path and path.is_file():
                payload = _read_json(path)
                if isinstance(payload, dict):
                    return {
                        "ok": True,
                        "system": "quickbooks",
                        "resource": resource,
                        "label": spec["label"],
                        "sourceKind": "probe-json",
                        "sourcePath": str(path),
                        "payload": payload,
                    }
        return {"ok": False, "system": "quickbooks", "resource": resource, "error": "QuickBooks probe summary not found."}

    if spec["kind"] == "monthly":
        from quickbooks_monthly_sync import sync_quickbooks_monthly_exports

        probe = None
        probe_path = _find_newest(quickbooks_import_dir(), ("quickbooks_sdk_report_probe_summary.json",))
        if probe_path:
            probe = _read_json(probe_path)
        monthly = sync_quickbooks_monthly_exports(quickbooks_import_dir(), probe_payload=probe if isinstance(probe, dict) else None)
        return {
            "ok": bool(monthly.get("written")),
            "system": "quickbooks",
            "resource": resource,
            "label": spec["label"],
            "sourceKind": "monthly-sync",
            "monthly": monthly,
        }

    if spec["kind"] == "export":
        dataset = _load_newest_export("quickbooks", tuple(spec["names"]))
        if not dataset:
            return {"ok": False, "system": "quickbooks", "resource": resource, "error": "Export file not found in upstream roots or document-inbox cache."}
        dataset.update({"ok": True, "system": "quickbooks", "resource": resource, "label": spec["label"]})
        return dataset

    return {"ok": False, "system": "quickbooks", "resource": resource, "error": "Unsupported resource kind."}


def _fetch_softdent(resource: str, options: dict[str, Any]) -> dict[str, Any]:
    spec = SOFTDENT_RESOURCES.get(resource)
    if not spec:
        return {"ok": False, "system": "softdent", "resource": resource, "error": f"Unknown SoftDent resource: {resource}"}

    if spec["kind"] == "bridge":
        for path in (
            softdent_import_dir() / "softdent_bridge_latest.json",
            _find_newest(softdent_import_dir(), ("softdent_bridge_latest.json",)),
            BRIDGE_AGGREGATE_JSON if BRIDGE_AGGREGATE_JSON.is_file() else None,
        ):
            if path and path.is_file():
                payload = _read_json(path)
                rows = _build_dashboard_from_bridge(path) or []
                return {
                    "ok": True,
                    "system": "softdent",
                    "resource": resource,
                    "label": spec["label"],
                    "sourceKind": "bridge-json",
                    "sourcePath": str(path),
                    "payload": payload,
                    "derivedDashboardRows": rows,
                    "rowCount": len(rows),
                }
        return {"ok": False, "system": "softdent", "resource": resource, "error": "SoftDent bridge aggregate not found."}

    if spec["kind"] == "pipeline_ar":
        aging = _find_newest(softdent_import_dir(), ("account_aging.jsonl",))
        if not aging:
            aging = _find_newest(SOFTDENT_FINANCIAL_EXPORTS, ("account_aging.jsonl",))
        if not aging:
            return {"ok": False, "system": "softdent", "resource": resource, "error": "account_aging.jsonl not found."}
        normalized = _jsonl_practice_total(aging)
        rows = _build_ar_rows_from_normalized(normalized) if normalized else []
        return {
            "ok": bool(rows),
            "system": "softdent",
            "resource": resource,
            "label": spec["label"],
            "sourceKind": "pipeline-jsonl",
            "sourcePath": str(aging),
            "normalized": normalized,
            "rows": rows,
            "rowCount": len(rows),
        }

    if spec["kind"] == "export":
        dataset = _load_newest_export("softdent", tuple(spec["names"]))
        if not dataset:
            return {"ok": False, "system": "softdent", "resource": resource, "error": "Export file not found in upstream roots or document-inbox cache."}
        dataset.update({"ok": True, "system": "softdent", "resource": resource, "label": spec["label"]})
        return dataset

    return {"ok": False, "system": "softdent", "resource": resource, "error": "Unsupported resource kind."}


def practice_pull_approved() -> bool:
    """Staff approval gate for HAL autonomous SoftDent/QuickBooks direct reads."""
    return os.environ.get("NR2_HAL_PRACTICE_PULL_APPROVED", "1").strip().lower() not in {"0", "false", "no", "off"}


def verify_claims_in_cache() -> dict[str, Any]:
    """Verify SoftDent claims export is present and parseable in the import cache."""
    from import_contract import SOFTDENT_CLAIMS_NAMES
    from import_loader import load_import_bundle, softdent_import_dir

    dest = softdent_import_dir()
    bundle = load_import_bundle(sync=False, deep=False)
    claims = ((bundle.get("softdent") or {}).get("claims") or {}) if isinstance(bundle, dict) else {}
    rows = claims.get("rows") if isinstance(claims, dict) else None
    rows = rows if isinstance(rows, list) else []
    statuses: dict[str, int] = {}
    claim_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("ClaimId") or row.get("claimId") or row.get("id") or "").strip()
        if cid:
            claim_ids.append(cid)
        status = str(row.get("ClaimStatus") or row.get("status") or "Unknown").strip() or "Unknown"
        statuses[status] = statuses.get(status, 0) + 1
    missing_files = [name for name in SOFTDENT_CLAIMS_NAMES if not (dest / name).is_file()]
    return {
        "ok": len(rows) > 0,
        "rowCount": len(rows),
        "claimIds": claim_ids,
        "statusCounts": statuses,
        "sourceFile": claims.get("sourceFile") if isinstance(claims, dict) else None,
        "importDir": str(dest),
        "missingExpectedFilenames": missing_files,
        "issues": [] if rows else ["No claims rows in import cache after pull."],
    }


def pull_all_practice_sources(full: bool | None = None, scan_resources: bool | None = None) -> dict[str, Any]:
    """Authorized HAL pull: upstream SoftDent/QuickBooks -> import cache -> Documents queue."""
    from import_loader import load_import_bundle
    from import_sync import sync_imports, _full_pull_enabled
    from hal_narrative_library import build_generic_draft_library, select_best_narrative_for_claim

    full = full if full is not None else _full_pull_enabled(None)
    if scan_resources is None:
        scan_resources = os.environ.get("NR2_HAL_PULL_SCAN_RESOURCES", "0").strip().lower() in {"1", "true", "yes", "on"}
    if not practice_pull_approved():
        return {
            "ok": False,
            "approved": False,
            "error": "Practice source pull is not approved. Set NR2_HAL_PRACTICE_PULL_APPROVED=1 or approve in hal-manager.json.",
        }

    import_result = sync_imports(full_pull=full)
    resource_fetch: dict[str, Any] = {}
    if scan_resources:
        for system in ("softdent", "quickbooks"):
            try:
                resource_fetch[system] = fetch(system, "all", {"refreshCache": False})
            except Exception as exc:
                resource_fetch[system] = {"ok": False, "error": str(exc)}

    documents: dict[str, Any] | None = None
    post_pull: dict[str, Any] | None = None
    try:
        from sync_document_sources import sync_document_sources

        documents = sync_document_sources(pull_imports=False, full_pull=full)
        post_pull = documents.get("postPullSetup") if isinstance(documents, dict) else None
    except Exception as exc:
        documents = {"ok": False, "error": str(exc)}

    bundle = load_import_bundle(sync=False, deep=False)
    claims_verification = verify_claims_in_cache()
    narrative_library = build_generic_draft_library()
    claim_rows = ((bundle.get("softdent") or {}).get("claims") or {}).get("rows") or []
    narrative_selections = []
    for row in claim_rows[:10]:
        if isinstance(row, dict):
            claim = {
                "id": row.get("ClaimId") or row.get("claimId") or row.get("id"),
                "patient": row.get("PatientName") or row.get("patient"),
                "procedure": row.get("Procedure") or row.get("procedure"),
                "status": row.get("ClaimStatus") or row.get("status"),
                "denialReason": row.get("DenialReason") or row.get("denialReason"),
            }
            narrative_selections.append(select_best_narrative_for_claim(claim, narrative_library))

    def _count_rows(section: dict[str, Any] | None) -> int:
        if not section:
            return 0
        total = 0
        for dataset in section.values():
            if isinstance(dataset, dict) and isinstance(dataset.get("rows"), list) and dataset["rows"]:
                total += 1
        return total

    sd_ok = _count_rows(bundle.get("softdent"))
    qb_ok = _count_rows(bundle.get("quickbooks"))
    return {
        "ok": True,
        "approved": True,
        "readOnly": True,
        "fullPull": full,
        "pulledAt": _utc_now(),
        "importSync": import_result,
        "resourceFetch": resource_fetch,
        "importBundle": {
            "softdentDir": (bundle.get("softdent") or {}).get("dir"),
            "quickbooksDir": (bundle.get("quickbooks") or {}).get("dir"),
        },
        "claimsVerification": claims_verification,
        "narrativeLibrary": {
            "count": len(narrative_library),
            "memoAiGuided": True,
            "selections": narrative_selections,
        },
        "documents": documents,
        "postPullSetup": post_pull,
        "summary": {
            "softdentResourcesOk": sd_ok,
            "quickbooksResourcesOk": qb_ok,
            "claimsOk": claims_verification.get("ok"),
            "claimsRowCount": claims_verification.get("rowCount"),
            "narrativeTemplates": len(narrative_library),
            "documentQueueCount": (documents or {}).get("queueCount") if isinstance(documents, dict) else None,
        },
    }


def job_requirements_from_bundle(bundle: dict[str, Any] | None) -> dict[str, Any]:
    """Summarize missing datasets HAL still needs for full widget coverage."""
    bundle = bundle or {}
    try:
        from import_diagnostics import evaluate_bundle

        diagnostics = evaluate_bundle(bundle, deep=False)
    except Exception as exc:
        diagnostics = {"datasets": [], "error": str(exc)}

    missing = [
        row
        for row in (diagnostics.get("datasets") or [])
        if isinstance(row, dict) and row.get("status") not in {"connected", "partial"}
    ]
    partial = [
        row
        for row in (diagnostics.get("datasets") or [])
        if isinstance(row, dict) and row.get("status") == "partial"
    ]
    staff_actions: list[str] = []
    for row in missing:
        key = str(row.get("datasetKey") or "")
        if key.startswith("softdent.claims"):
            staff_actions.append("Export SoftDent claims to app_data/nr2/document_inbox/softdent")
        elif key.startswith("softdent."):
            staff_actions.append(f"Refresh SoftDent export: {key}")
        elif key.startswith("quickbooks."):
            staff_actions.append(f"Refresh QuickBooks export: {key}")
    if not staff_actions and partial:
        staff_actions.append("Add prior-month SoftDent dashboard rows for trend/YTD widgets")
    return {
        "generatedAt": _utc_now(),
        "missingDatasets": missing,
        "partialDatasets": partial,
        "staffActions": staff_actions,
    }


def fetch(system: str, resource: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    opts = dict(options or {})
    system_key = str(system or "").strip().lower()
    resource_key = str(resource or "catalog").strip().lower()

    if resource_key in {"catalog", "list", "help"}:
        return list_catalog()

    if opts.get("refreshCache"):
        from import_sync import sync_imports

        opts["refreshResult"] = sync_imports()

    envelope: dict[str, Any] = {
        "authorized": True,
        "readOnly": True,
        "fetchedAt": _utc_now(),
        "system": system_key,
        "resource": resource_key,
    }

    if resource_key == "all":
        specs = QUICKBOOKS_RESOURCES if system_key == "quickbooks" else SOFTDENT_RESOURCES
        results: dict[str, Any] = {}
        for key in specs:
            item = fetch(system_key, key, {k: v for k, v in opts.items() if k != "refreshCache"})
            results[key] = {
                "ok": item.get("ok"),
                "rowCount": item.get("rowCount"),
                "error": item.get("error"),
                "sourcePath": item.get("sourcePath") or item.get("sourceFile"),
            }
        envelope.update({"ok": True, "results": results})
        return envelope

    if system_key == "quickbooks":
        payload = _fetch_quickbooks(resource_key, opts)
    elif system_key == "softdent":
        payload = _fetch_softdent(resource_key, opts)
    else:
        payload = {"ok": False, "error": f"Unknown system: {system}"}

    envelope.update(payload)
    return envelope


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Authorized HAL practice source fetch")
    parser.add_argument("system", nargs="?", default="catalog")
    parser.add_argument("resource", nargs="?", default="catalog")
    parser.add_argument("--refresh-cache", action="store_true")
    args = parser.parse_args()
    if args.system == "catalog":
        print(json.dumps(list_catalog(), indent=2))
    else:
        print(
            json.dumps(
                fetch(args.system, args.resource, {"refreshCache": args.refresh_cache}),
                indent=2,
                default=str,
            )
        )
