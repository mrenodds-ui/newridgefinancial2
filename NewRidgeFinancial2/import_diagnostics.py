"""Dataset-level import diagnostics for NR2 financial automation."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_contract import (
    MANIFEST_PATH,
    REPO_ROOT,
    _FALLBACK_DATASET_NAMES,
    load_manifest_payload,
    pick_field,
    validate_rows_for_contract,
)

STATUS_CONNECTED = "connected"
STATUS_PARTIAL = "partial"
STATUS_STALE = "stale"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_MISSING = "missing"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _age_minutes(modified_at: str | None) -> int | None:
    parsed = _parse_iso(modified_at)
    if parsed is None:
        return None
    return max(0, int((_utc_now() - parsed).total_seconds() // 60))


def _resolve_upstream_roots(system: str, manifest: dict[str, Any]) -> list[Path]:
    upstream = (manifest.get("upstreamRoots") or {}).get(system) or {}
    roots: list[Path] = []
    for env_name in upstream.get("envVars") or []:
        configured = os.environ.get(str(env_name), "").strip()
        if configured:
            candidate = Path(configured).expanduser()
            if not candidate.is_absolute():
                candidate = REPO_ROOT / candidate
            resolved = candidate.resolve()
            if resolved.is_dir() and resolved not in roots:
                roots.append(resolved)
    for raw in upstream.get("defaultPaths") or []:
        candidate = Path(str(raw))
        if candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    return roots


def _collector_hint(manifest: dict[str, Any], contract: dict[str, Any]) -> str | None:
    system = str(contract.get("system") or "")
    upstream = (manifest.get("upstreamRoots") or {}).get(system) or {}
    hints = upstream.get("collectorHints") or {}
    generated_by = contract.get("generatedBy") or []
    if isinstance(generated_by, list):
        for key in generated_by:
            hint = hints.get(str(key))
            if hint:
                return str(hint)
    source_owner = contract.get("sourceOwner")
    if source_owner:
        hint = hints.get(str(source_owner))
        if hint:
            return str(hint)
    return None


def _upstream_scan_max_depth() -> int:
    raw = os.environ.get("NR2_UPSTREAM_SCAN_MAX_DEPTH", "4").strip()
    try:
        return max(0, min(int(raw), 12))
    except ValueError:
        return 4


def _iter_upstream_files(root: Path, *, max_depth: int):
    if not root.is_dir():
        return
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(Path(dirpath).parts) - root_depth
        if depth > max_depth:
            dirnames.clear()
            continue
        for filename in filenames:
            yield Path(dirpath) / filename


def _find_newest_upstream(roots: list[Path], filenames: tuple[str, ...]) -> dict[str, Any] | None:
    name_set = {name.casefold() for name in filenames}
    best: Path | None = None
    max_depth = _upstream_scan_max_depth()
    for root in roots:
        if not root.is_dir():
            continue
        for path in _iter_upstream_files(root, max_depth=max_depth):
            if path.name.casefold() in name_set:
                if best is None or path.stat().st_mtime > best.stat().st_mtime:
                    best = path
    if best is None:
        return None
    modified = datetime.fromtimestamp(best.stat().st_mtime, tz=timezone.utc)
    return {
        "path": str(best),
        "sourceFile": best.name,
        "modifiedAt": modified.isoformat(),
        "ageMinutes": _age_minutes(modified.isoformat()),
    }


def evaluate_dataset(
    dataset_key: str,
    contract: dict[str, Any],
    dataset_payload: dict[str, Any] | None,
    *,
    manifest: dict[str, Any] | None = None,
    upstream_roots: list[Path] | None = None,
    previous_checksums: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = manifest or load_manifest_payload()
    automated = contract.get("automated", True) is not False
    severity = str(contract.get("severity") or "warning")
    freshness_max = int(contract.get("freshnessMaxMinutes") or 1440)
    collector_hint = _collector_hint(manifest, contract)
    note = contract.get("note")

    if not automated:
        return {
            "datasetKey": dataset_key,
            "system": contract.get("system"),
            "bundleKey": contract.get("bundleKey"),
            "status": STATUS_NOT_CONFIGURED,
            "severity": severity,
            "automated": False,
            "found": False,
            "rowCount": 0,
            "sourceFile": None,
            "modifiedAt": None,
            "ageMinutes": None,
            "freshnessMaxMinutes": freshness_max,
            "requiredFieldFailures": [],
            "collectorHint": collector_hint,
            "upstreamFile": None,
            "detail": note or "No automated collector configured for this dataset.",
        }

    if not dataset_payload or not dataset_payload.get("sourceFile"):
        upstream_file = None
        if upstream_roots is not None:
            filenames = tuple(contract.get("filenames") or ())
            upstream_file = _find_newest_upstream(upstream_roots, filenames)
        detail = "Dataset file not found in import cache."
        if upstream_file:
            detail = "Import cache missing file; upstream export exists but was not copied."
        elif collector_hint:
            detail = f"Dataset file not found. Check collector: {collector_hint}."
        return {
            "datasetKey": dataset_key,
            "system": contract.get("system"),
            "bundleKey": contract.get("bundleKey"),
            "status": STATUS_MISSING,
            "severity": severity,
            "automated": True,
            "found": False,
            "rowCount": 0,
            "sourceFile": None,
            "modifiedAt": None,
            "ageMinutes": None,
            "freshnessMaxMinutes": freshness_max,
            "requiredFieldFailures": [],
            "collectorHint": collector_hint,
            "upstreamFile": upstream_file,
            "detail": detail,
        }

    rows = dataset_payload.get("rows") or []
    row_count = len(rows) if isinstance(rows, list) else 0
    modified_at = dataset_payload.get("modifiedAt")
    age_minutes = _age_minutes(str(modified_at) if modified_at else None)
    validation = validate_rows_for_contract(contract, rows if isinstance(rows, list) else [])
    required_failures = validation.get("requiredFieldFailures") or []

    upstream_file = None
    if upstream_roots is not None:
        filenames = tuple(contract.get("filenames") or ())
        upstream_file = _find_newest_upstream(upstream_roots, filenames)

    status = STATUS_CONNECTED
    detail = "Dataset loaded and required fields pass."
    if age_minutes is not None and age_minutes > freshness_max:
        status = STATUS_STALE
        detail = f"Dataset is stale ({age_minutes} min old; max {freshness_max} min)."
    elif required_failures:
        status = STATUS_PARTIAL
        detail = f"Dataset loaded but required fields missing: {', '.join(required_failures)}."
    elif row_count == 0:
        status = STATUS_PARTIAL
        detail = "Dataset file present but contains no rows."
    elif dataset_key == "softdent.dashboard" and row_count == 1 and status == STATUS_CONNECTED:
        status = STATUS_PARTIAL
        detail = "Current month only; prior month export missing for trend/YTD widgets."

    if upstream_file and upstream_file.get("ageMinutes") is not None:
        upstream_age = int(upstream_file["ageMinutes"])
        if upstream_age > freshness_max and status == STATUS_CONNECTED:
            status = STATUS_STALE
            detail = f"Upstream export is stale ({upstream_age} min old). {detail}"

    current_sha = str(dataset_payload.get("sha256") or "").strip() or None
    previous = (previous_checksums or {}).get(dataset_key) if isinstance(previous_checksums, dict) else None
    checksum_changed = False
    if isinstance(previous, dict) and current_sha:
        previous_sha = str(previous.get("sha256") or "").strip()
        previous_file = str(previous.get("sourceFile") or "").strip()
        current_file = str(dataset_payload.get("sourceFile") or "").strip()
        if previous_sha and previous_sha != current_sha:
            checksum_changed = True
        elif previous_file and current_file and previous_file != current_file:
            checksum_changed = True
    if checksum_changed and status == STATUS_CONNECTED:
        status = STATUS_PARTIAL
        detail = f"Dataset changed since last sync (checksum). {detail}"

    read_source = str(dataset_payload.get("readSource") or "").strip().lower()
    if dataset_key == "softdent.dashboard" and read_source == "bridge-fallback":
        if status == STATUS_CONNECTED:
            status = STATUS_PARTIAL
        bridge_validation = dataset_payload.get("bridgeValidation")
        bridge_validation = bridge_validation if isinstance(bridge_validation, dict) else {}
        bridge_issues = bridge_validation.get("issues") or []
        bridge_note = "Dashboard loaded from bridge fallback (not daysheet export)."
        if bridge_issues:
            bridge_note = f"{bridge_note} {'; '.join(str(issue) for issue in bridge_issues)}."
        detail = f"{bridge_note} {detail}".strip()

    return {
        "datasetKey": dataset_key,
        "system": contract.get("system"),
        "bundleKey": contract.get("bundleKey"),
        "status": status,
        "severity": severity,
        "automated": True,
        "found": True,
        "rowCount": row_count,
        "sourceFile": dataset_payload.get("sourceFile"),
        "modifiedAt": modified_at,
        "ageMinutes": age_minutes,
        "freshnessMaxMinutes": freshness_max,
        "requiredFieldFailures": required_failures,
        "collectorHint": collector_hint,
        "upstreamFile": upstream_file,
        "sha256": current_sha,
        "checksumChanged": checksum_changed,
        "detail": detail,
    }


def evaluate_bundle(
    bundle: dict[str, Any],
    *,
    manifest: dict[str, Any] | None = None,
    deep: bool = False,
    previous_checksums: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate the import cache against dataset contracts.

    When ``deep`` is False (the default, used on the UI hot path) this skips the
    recursive upstream-directory scan entirely so dashboards load instantly.
    Pass ``deep=True`` from background/sync paths to also locate the newest
    matching upstream export for each dataset.
    """
    manifest = manifest or load_manifest_payload()
    datasets_manifest = manifest.get("datasets") or {}
    items: list[dict[str, Any]] = []
    by_status: dict[str, int] = {}
    softdent_roots = _resolve_upstream_roots("softdent", manifest) if deep else None
    quickbooks_roots = _resolve_upstream_roots("quickbooks", manifest) if deep else None

    for dataset_key in _FALLBACK_DATASET_NAMES:
        contract = datasets_manifest.get(dataset_key)
        if not isinstance(contract, dict):
            contract = {"filenames": list(_FALLBACK_DATASET_NAMES[dataset_key])}
        system = str(contract.get("system") or dataset_key.split(".", 1)[0])
        bundle_key = str(contract.get("bundleKey") or dataset_key.split(".", 1)[1])
        system_payload = bundle.get(system) if isinstance(bundle.get(system), dict) else {}
        dataset_payload = system_payload.get(bundle_key) if isinstance(system_payload, dict) else None
        roots = softdent_roots if system == "softdent" else quickbooks_roots
        item = evaluate_dataset(
            dataset_key,
            contract,
            dataset_payload,
            manifest=manifest,
            upstream_roots=roots,
            previous_checksums=previous_checksums,
        )
        items.append(item)
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1

    return {
        "evaluatedAt": _utc_now().isoformat(),
        "manifestPath": str(MANIFEST_PATH),
        "datasets": items,
        "summary": {
            "total": len(items),
            "connected": by_status.get(STATUS_CONNECTED, 0),
            "partial": by_status.get(STATUS_PARTIAL, 0),
            "stale": by_status.get(STATUS_STALE, 0),
            "missing": by_status.get(STATUS_MISSING, 0),
            "notConfigured": by_status.get(STATUS_NOT_CONFIGURED, 0),
        },
    }


def check_upstream_health(*, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or load_manifest_payload()
    datasets_manifest = manifest.get("datasets") or {}
    systems: dict[str, Any] = {}

    for system in ("softdent", "quickbooks"):
        roots = _resolve_upstream_roots(system, manifest)
        root_reports = []
        for root in roots:
            root_reports.append({"path": str(root), "exists": root.is_dir()})
        dataset_reports = []
        for dataset_key, contract in datasets_manifest.items():
            if not isinstance(contract, dict) or str(contract.get("system")) != system:
                continue
            if contract.get("automated") is False:
                continue
            filenames = tuple(contract.get("filenames") or ())
            newest = _find_newest_upstream(roots, filenames) if filenames else None
            freshness_max = int(contract.get("freshnessMaxMinutes") or 1440)
            stale = bool(newest and newest.get("ageMinutes") is not None and newest["ageMinutes"] > freshness_max)
            dataset_reports.append(
                {
                    "datasetKey": dataset_key,
                    "newestFile": newest,
                    "stale": stale,
                    "collectorHint": _collector_hint(manifest, contract),
                }
            )
        systems[system] = {
            "roots": root_reports,
            "configuredRootCount": len(roots),
            "datasets": dataset_reports,
        }

    return {
        "checkedAt": _utc_now().isoformat(),
        "systems": systems,
    }
