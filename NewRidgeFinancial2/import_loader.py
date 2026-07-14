"""Read SoftDent and QuickBooks export files for NewRidgeFinancial 2.0."""

from __future__ import annotations

import copy
import csv
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_contract import (
    QUICKBOOKS_AP_NAMES,
    QUICKBOOKS_AR_NAMES,
    QUICKBOOKS_EXPENSE_CATEGORY_NAMES,
    QUICKBOOKS_EXPENSE_NAMES,
    QUICKBOOKS_PAYROLL_NAMES,
    QUICKBOOKS_PL_NAMES,
    QUICKBOOKS_REVENUE_NAMES,
    SOFTDENT_AR_NAMES,
    SOFTDENT_CASE_ACCEPTANCE_NAMES,
    SOFTDENT_HYGIENE_RECALL_NAMES,
    SOFTDENT_OPERATORY_NAMES,
    SOFTDENT_CLAIMS_NAMES,
    SOFTDENT_CLINICAL_NAMES,
    SOFTDENT_DASHBOARD_NAMES,
    SOFTDENT_NEW_PATIENTS_NAMES,
    SOFTDENT_PROCEDURES_NAMES,
    SOFTDENT_PRODUCTION_NAMES,
    SOFTDENT_CLAIM_STATUS_NAMES,
    SOFTDENT_TREATMENT_PLANS_NAMES,
    manifest_warnings,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _repo_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return path.name


NR2_DATA_DIR = REPO_ROOT / "app_data" / "nr2"
DEFAULT_SOFTDENT_IMPORT_REL = "app_data/nr2/document_inbox/softdent"
DEFAULT_QUICKBOOKS_IMPORT_REL = "app_data/nr2/document_inbox/quickbooks"


def _import_dir(env_name: str, default_rel: str) -> Path:
    configured = os.environ.get(env_name, "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve()
    return (REPO_ROOT / default_rel).resolve()


def softdent_import_dir() -> Path:
    return _import_dir("SOFTDENT_IMPORT_DIR", DEFAULT_SOFTDENT_IMPORT_REL)


def quickbooks_import_dir() -> Path:
    return _import_dir("QUICKBOOKS_IMPORT_DIR", DEFAULT_QUICKBOOKS_IMPORT_REL)


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


def _rows_from_json_probe(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    categories = payload.get("top_expense_categories")
    if not isinstance(categories, list):
        return []
    rows: list[dict[str, Any]] = []
    period = str(payload.get("period") or payload.get("period_end") or "").strip()
    for item in categories:
        if not isinstance(item, dict):
            continue
        amount = item.get("amount")
        if amount in (None, ""):
            continue
        row = {
            "Category": str(item.get("category") or ""),
            "Amount": amount,
        }
        item_period = str(item.get("period") or period or "").strip()
        if item_period:
            row["Period"] = item_period
        else:
            row["Scope"] = "YTD"
        rows.append(row)
    return rows


def _read_tabular(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        probe_rows = _rows_from_json_probe(payload)
        if probe_rows:
            return probe_rows
        return _extract_json_rows(payload)
    if suffix == ".csv":
        raw = path.read_text(encoding="utf-8-sig")
        stripped = raw.lstrip()
        if stripped.startswith("{"):
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                probe_rows = _rows_from_json_probe(payload)
                if probe_rows:
                    return probe_rows
        sidecar = path.with_suffix(".json")
        if sidecar.is_file() and sidecar.stat().st_mtime >= path.stat().st_mtime:
            try:
                payload = json.loads(sidecar.read_text(encoding="utf-8-sig"))
                if isinstance(payload, list):
                    return [row for row in payload if isinstance(row, dict)]
                probe_rows = _rows_from_json_probe(payload)
                if probe_rows:
                    return probe_rows
            except json.JSONDecodeError:
                pass
        return _read_csv_rows(path)
    return []


def _newest_existing(directory: Path, names: tuple[str, ...]) -> Path | None:
    if not directory.is_dir():
        return None
    matches = _all_existing(directory, names)
    if not matches:
        return None
    return matches[0]


def _all_existing(directory: Path, names: tuple[str, ...]) -> list[Path]:
    if not directory.is_dir():
        return []
    matches: list[Path] = []
    name_set = {name.casefold() for name in names}
    for path in directory.iterdir():
        if path.is_file() and path.name.casefold() in name_set:
            matches.append(path)
    return sorted(matches, key=lambda item: item.stat().st_mtime, reverse=True)


def _rows_are_usable(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    for row in rows[:5]:
        if not isinstance(row, dict):
            return False
        for key in row.keys():
            text = str(key)
            if text.startswith("{") or "dataset_name" in text:
                return False
    return True


def _load_operatory_dataset(directory: Path, names: tuple[str, ...]) -> dict[str, Any] | None:
    paths = _all_existing(directory, names)
    for path in paths:
        if path.suffix.lower() != ".json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        chairs = payload.get("operatoryChairs")
        if not isinstance(chairs, list):
            continue
        file_sha: str | None = None
        try:
            from import_cache_ttl import sha256_file

            file_sha = sha256_file(path)
        except Exception:
            pass
        return {
            "sourceFile": path.name,
            "modifiedAt": _mtime_iso(path),
            "sha256": file_sha,
            "operatoryChairs": chairs,
            "rows": [],
            "readSource": "cache",
        }
    return None


def _load_dataset(directory: Path, names: tuple[str, ...]) -> dict[str, Any] | None:
    paths = _all_existing(directory, names)
    if not paths:
        return None

    is_sample_claims = None
    try:
        from import_sync import _is_sample_claims as _sample_fn

        is_sample_claims = _sample_fn
    except Exception:
        is_sample_claims = None

    best_path: Path | None = None
    best_rows: list[dict[str, Any]] = []
    best_key: tuple[int, int, int, float] | None = None
    fallback_path: Path | None = None
    fallback_rows: list[dict[str, Any]] = []

    for candidate in paths:
        candidate_rows = _read_tabular(candidate)
        if not _rows_are_usable(candidate_rows):
            continue
        if fallback_path is None:
            fallback_path = candidate
            fallback_rows = candidate_rows
        sample = bool(is_sample_claims and is_sample_claims(candidate_rows))
        # Prefer non-sample, then most rows, then JSON over CSV, then newest mtime.
        key = (
            0 if sample else 1,
            len(candidate_rows),
            1 if candidate.suffix.lower() == ".json" else 0,
            candidate.stat().st_mtime,
        )
        if best_key is None or key > best_key:
            best_key = key
            best_path = candidate
            best_rows = candidate_rows

    path = best_path or fallback_path or paths[0]
    rows = best_rows if best_path is not None else (fallback_rows or _read_tabular(path))
    file_sha: str | None = None
    try:
        from import_cache_ttl import sha256_file

        file_sha = sha256_file(path)
    except Exception:
        pass
    dataset = {
        "sourceFile": path.name,
        "modifiedAt": _mtime_iso(path),
        "sha256": file_sha,
        "rows": rows,
        "readSource": "cache",
    }
    return dataset


def direct_first_imports_enabled() -> bool:
    try:
        from practice_source_access import direct_first_imports_enabled as _enabled

        return _enabled()
    except Exception:
        return os.environ.get("NR2_DIRECT_FIRST_IMPORTS", "1").strip().lower() not in {"0", "false", "no", "off"}


def _dataset_has_rows(dataset: dict[str, Any] | None) -> bool:
    if not dataset:
        return False
    rows = dataset.get("rows")
    return isinstance(rows, list) and len(rows) > 0


def _resolve_dataset(
    direct: dict[str, Any] | None,
    cached: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if direct_first_imports_enabled() and _dataset_has_rows(direct):
        picked = dict(direct)
        picked.setdefault("readSource", "direct")
        return picked
    try:
        from import_direct_pipeline import pipeline_first_imports_enabled, pick_freshest_dataset

        if pipeline_first_imports_enabled():
            picked = pick_freshest_dataset(direct, cached)
            if picked:
                if picked is cached and _dataset_has_rows(cached):
                    cached = dict(cached)
                    cached["readSource"] = "cache"
                    return cached
                return picked
    except Exception:
        pass
    if _dataset_has_rows(direct):
        return direct
    if _dataset_has_rows(cached):
        cached = dict(cached)
        cached.setdefault("readSource", "cache")
        return cached
    return direct or cached


def _load_direct_sections() -> dict[str, Any]:
    from practice_source_access import assemble_direct_import_sections

    return assemble_direct_import_sections()


def _write_direct_sections_to_cache(sections: dict[str, Any]) -> dict[str, Any]:
    """Optional cache mirror for external tools that still read document-inbox files."""
    from import_cache_ttl import CRITICAL_INBOX_FILENAMES, write_text_if_changed

    written: list[str] = []
    errors: list[str] = []
    softdent_dir = softdent_import_dir()
    quickbooks_dir = quickbooks_import_dir()
    softdent_dir.mkdir(parents=True, exist_ok=True)
    quickbooks_dir.mkdir(parents=True, exist_ok=True)

    def _write_dataset(directory: Path, dataset: dict[str, Any] | None) -> None:
        if not _dataset_has_rows(dataset):
            return
        source_path = str(dataset.get("sourcePath") or "").strip()
        source_file = str(dataset.get("sourceFile") or "").strip()
        # Do not reshape critical inbox files from direct-first (avoids array vs {rows} thrash).
        if source_file in CRITICAL_INBOX_FILENAMES and (directory / source_file).is_file():
            return
        if source_path:
            src = Path(source_path)
            dest_name = source_file or src.name
            dest = directory / dest_name
            if dest_name in CRITICAL_INBOX_FILENAMES and dest.is_file():
                return
            same_export = src.is_file() and src.name == dest_name
            if same_export:
                try:
                    if not dest.is_file() or src.stat().st_mtime > dest.stat().st_mtime:
                        import shutil

                        shutil.copy2(src, dest)
                        written.append(_repo_relative(dest))
                except OSError as exc:
                    errors.append(f"{dest.name}: {exc}")
                return
        if source_file.endswith(".json"):
            dest = directory / source_file
            if dest.name in CRITICAL_INBOX_FILENAMES and dest.is_file():
                return
            try:
                payload = {
                    "rows": dataset.get("rows") or [],
                    "sourceFile": source_file,
                    "modifiedAt": dataset.get("modifiedAt"),
                    "sha256": dataset.get("sha256"),
                }
                if write_text_if_changed(dest, json.dumps(payload, indent=2)):
                    written.append(_repo_relative(dest))
            except OSError as exc:
                errors.append(f"{dest.name}: {exc}")
        elif source_file.endswith(".csv") and _dataset_has_rows(dataset):
            dest = directory / source_file
            if dest.name in CRITICAL_INBOX_FILENAMES and dest.is_file():
                return
            try:
                rows = dataset.get("rows") or []
                if rows and isinstance(rows[0], dict):
                    from import_cache_ttl import write_bytes_if_changed

                    buf = __import__("io").StringIO()
                    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
                    if write_bytes_if_changed(dest, buf.getvalue().encode("utf-8")):
                        sidecar = dest.with_suffix(".json")
                        write_text_if_changed(sidecar, json.dumps(rows, indent=2))
                        written.append(_repo_relative(dest))
            except OSError as exc:
                errors.append(f"{dest.name}: {exc}")

    for dataset in ((sections.get("softdent") or {}).values()):
        if isinstance(dataset, dict):
            _write_dataset(softdent_dir, dataset)
    for dataset in ((sections.get("quickbooks") or {}).values()):
        if isinstance(dataset, dict):
            _write_dataset(quickbooks_dir, dataset)

    return {"written": written, "errors": errors}


def load_import_bundle(*, sync: bool = True, deep: bool = False, direct: bool | None = None) -> dict[str, Any]:
    """Load SoftDent/QB import bundle.

    direct=None → honor NR2 direct-first setting
    direct=True  → force upstream/direct sections
    direct=False → cache/document-inbox only (fast path for readiness gates)
    """
    direct_first = direct_first_imports_enabled() if direct is None else bool(direct)
    # Short in-process TTL so the single-threaded HTTP loop is not re-scanning
    # upstream on every widget/app-info hit during page load.
    cache_key = (bool(sync), bool(deep), bool(direct_first), "v1")
    if not sync:
        with _BUNDLE_CACHE_LOCK:
            hit = _BUNDLE_CACHE.get(cache_key)
            if hit and (time.monotonic() - float(hit.get("at") or 0)) < _BUNDLE_CACHE_TTL_SEC:
                return copy.deepcopy(hit["bundle"])
    bundle = _load_import_bundle_uncached(sync=sync, deep=deep, direct_first=direct_first)
    if not sync:
        with _BUNDLE_CACHE_LOCK:
            _BUNDLE_CACHE[cache_key] = {"at": time.monotonic(), "bundle": copy.deepcopy(bundle)}
    return bundle


_BUNDLE_CACHE: dict[tuple, dict[str, Any]] = {}
_BUNDLE_CACHE_LOCK = threading.Lock()
# Keep warm across page switches / silent refresh (client polls ~30s).
_BUNDLE_CACHE_TTL_SEC = 90.0


def clear_import_bundle_cache_for_tests() -> None:
    """Drop in-process import bundle cache (unit tests only)."""
    with _BUNDLE_CACHE_LOCK:
        _BUNDLE_CACHE.clear()


def _load_import_bundle_uncached(*, sync: bool, deep: bool, direct_first: bool) -> dict[str, Any]:
    sync_status: dict[str, Any] = {
        "attempted": sync and not direct_first,
        "ok": True,
        "error": None,
        "result": None,
        "warnings": manifest_warnings(),
        "importMode": "direct-first" if direct_first else "cache",
        "directFirst": direct_first,
    }
    if sync and not direct_first:
        try:
            from import_sync import sync_imports

            sync_status["result"] = sync_imports()
        except Exception as exc:
            sync_status["ok"] = False
            sync_status["error"] = str(exc)
    elif sync and direct_first:
        try:
            from practice_source_access import direct_first_write_cache_enabled

            # Refresh document-inbox from upstream/daysheet so cache-only readers
            # and scheduled tools stay on live practice data, not stale stubs.
            inbox_sync: dict[str, Any] | None = None
            try:
                from import_sync import sync_imports

                inbox_sync = sync_imports()
            except Exception as inbox_exc:
                inbox_sync = {"ok": False, "error": str(inbox_exc)}

            sync_status["attempted"] = True
            sync_status["result"] = {
                "directFirst": True,
                "refreshedAt": datetime.now(timezone.utc).isoformat(),
                "inboxSync": inbox_sync,
            }
            # Cache mirror runs after direct_sections are loaded below.
            sync_status["result"]["_pendingCacheWrite"] = direct_first_write_cache_enabled()
        except Exception as exc:
            sync_status["ok"] = False
            sync_status["error"] = str(exc)
    read_only = not sync
    softdent_dir = softdent_import_dir()
    quickbooks_dir = quickbooks_import_dir()
    direct_sections: dict[str, Any] | None = None
    direct_pipeline_error: str | None = None
    # Direct-first widgets read upstream on every load (real-time); sync=True also
    # refreshes the document-inbox cache for tools that still read files on disk.
    if direct_first:
        try:
            direct_sections = _load_direct_sections()
            if isinstance(direct_sections, dict):
                direct_pipeline_error = direct_sections.get("directPipelineError")
            pending_write = False
            if isinstance(sync_status.get("result"), dict):
                pending_write = bool(sync_status["result"].pop("_pendingCacheWrite", False))
            if pending_write and isinstance(direct_sections, dict):
                sync_status["result"]["cacheWrite"] = _write_direct_sections_to_cache(direct_sections)
        except Exception as exc:
            sync_status.setdefault("warnings", [])
            if isinstance(sync_status["warnings"], list):
                sync_status["warnings"].append(f"Direct import read failed: {exc}")

    def _softdent(key: str, names: tuple[str, ...]) -> dict[str, Any] | None:
        cached = _load_dataset(softdent_dir, names)
        direct = None
        if direct_sections:
            direct = (direct_sections.get("softdent") or {}).get(key)
        return _resolve_dataset(direct if isinstance(direct, dict) else None, cached)

    def _quickbooks(key: str, names: tuple[str, ...]) -> dict[str, Any] | None:
        cached = _load_dataset(quickbooks_dir, names)
        direct = None
        if direct_sections:
            direct = (direct_sections.get("quickbooks") or {}).get(key)
        return _resolve_dataset(direct if isinstance(direct, dict) else None, cached)

    bundle: dict[str, Any] = {
        "loadedAt": datetime.now(timezone.utc).isoformat(),
        "importMode": "direct-first" if direct_first else "cache",
        "directFirst": direct_first,
        "syncStatus": sync_status,
        "softdent": {
            "dir": str(softdent_dir),
            "dashboard": _softdent("dashboard", SOFTDENT_DASHBOARD_NAMES),
            "claims": _softdent("claims", SOFTDENT_CLAIMS_NAMES),
            "clinicalNotes": _softdent("clinicalNotes", SOFTDENT_CLINICAL_NAMES),
            "ar": _softdent("ar", SOFTDENT_AR_NAMES),
            "newPatients": _softdent("newPatients", SOFTDENT_NEW_PATIENTS_NAMES),
            "treatmentPlans": _softdent("treatmentPlans", SOFTDENT_TREATMENT_PLANS_NAMES),
            "caseAcceptance": _softdent("caseAcceptance", SOFTDENT_CASE_ACCEPTANCE_NAMES),
            "hygieneRecall": _softdent("hygieneRecall", SOFTDENT_HYGIENE_RECALL_NAMES),
            "operatory": _load_operatory_dataset(softdent_dir, SOFTDENT_OPERATORY_NAMES),
            "procedures": _softdent("procedures", SOFTDENT_PROCEDURES_NAMES),
            "production": _softdent("production", SOFTDENT_PRODUCTION_NAMES),
            "claimStatus": _softdent("claimStatus", SOFTDENT_CLAIM_STATUS_NAMES),
        },
        "quickbooks": {
            "dir": str(quickbooks_dir),
            "revenue": _quickbooks("revenue", QUICKBOOKS_REVENUE_NAMES),
            "expenses": _quickbooks("expenses", QUICKBOOKS_EXPENSE_NAMES),
            "profitAndLoss": _quickbooks("profitAndLoss", QUICKBOOKS_PL_NAMES),
            "expenseCategories": _quickbooks("expenseCategories", QUICKBOOKS_EXPENSE_CATEGORY_NAMES),
            "ar": _quickbooks("ar", QUICKBOOKS_AR_NAMES),
            "payroll": _quickbooks("payroll", QUICKBOOKS_PAYROLL_NAMES),
            "ap": _quickbooks("ap", QUICKBOOKS_AP_NAMES),
        },
    }
    if direct_pipeline_error:
        bundle["directPipelineError"] = direct_pipeline_error
    try:
        from import_cache_ttl import load_manifest
        from import_diagnostics import check_upstream_health, evaluate_bundle

        sync_diagnostics = None
        if isinstance(sync_status.get("result"), dict):
            sync_diagnostics = sync_status["result"].get("diagnostics")
        if sync_diagnostics:
            bundle["diagnostics"] = sync_diagnostics
        else:
            manifest_cache = load_manifest()
            previous_checksums = dict((manifest_cache or {}).get("datasetChecksums") or {})
            bundle["diagnostics"] = evaluate_bundle(
                bundle,
                deep=deep,
                previous_checksums=previous_checksums,
            )
        bundle["upstreamHealth"] = check_upstream_health() if deep else None
        if sync_status.get("result") and isinstance(sync_status["result"], dict):
            sync_status["result"].setdefault("diagnostics", bundle["diagnostics"])
            if bundle["upstreamHealth"] is not None:
                sync_status["result"].setdefault("upstreamHealth", bundle["upstreamHealth"])
            filt = sync_status["result"].get("filterSummary")
            if isinstance(filt, dict):
                bundle["filterSummary"] = filt
                if isinstance(bundle.get("diagnostics"), dict):
                    bundle["diagnostics"]["filterSummary"] = filt
    except Exception as exc:
        sync_status.setdefault("warnings", [])
        if isinstance(sync_status["warnings"], list):
            sync_status["warnings"].append(f"Import diagnostics unavailable: {exc}")
    if not read_only:
        try:
            from import_cache_ttl import collect_dataset_checksums, relevant_period_labels, write_manifest

            periods = relevant_period_labels()
            write_manifest(
                synced_at=str(bundle.get("loadedAt") or datetime.now(timezone.utc).isoformat()),
                periods={"softdent": periods, "quickbooks": periods},
                dataset_checksums=collect_dataset_checksums(softdent_dir, quickbooks_dir),
            )
        except Exception as exc:
            sync_status.setdefault("warnings", [])
            if isinstance(sync_status["warnings"], list):
                sync_status["warnings"].append(f"Import manifest update failed: {exc}")
    return bundle
