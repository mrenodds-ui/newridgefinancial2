"""
Phase U2b — Import quarantine & alerting (Moonshot REAUDIT3 SHOULD).

On persistent ingest failure: move file to quarantine + sidecar reason,
log to import_health_log, emit admin alert (SSE-capable insight).
Never invent dollars; no SoftDent write-back; quarantine holds originals only.
Flag: NR2_IMPORT_QUARANTINE (default ON).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GAP_IMPORT_QUARANTINED = "IMPORT_QUARANTINED"
DEFAULT_FAIL_THRESHOLD = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def quarantine_enabled() -> bool:
    raw = str(os.getenv("NR2_IMPORT_QUARANTINE") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def fail_threshold() -> int:
    raw = str(os.getenv("NR2_IMPORT_FAIL_THRESHOLD") or "").strip()
    try:
        return max(1, int(raw)) if raw else DEFAULT_FAIL_THRESHOLD
    except ValueError:
        return DEFAULT_FAIL_THRESHOLD


def _nr2_data_dir() -> Path:
    try:
        from document_sync import NR2_DATA_DIR

        return Path(NR2_DATA_DIR)
    except Exception:
        return Path(__file__).resolve().parent / "app_data" / "nr2"


def quarantine_dir() -> Path:
    override = str(os.getenv("NR2_QUARANTINE_DIR") or "").strip()
    if override:
        path = Path(override)
    else:
        path = _nr2_data_dir() / "import_quarantine"
    path.mkdir(parents=True, exist_ok=True)
    return path


def failure_state_path() -> Path:
    override = str(os.getenv("NR2_QUARANTINE_DIR") or "").strip()
    if override:
        return Path(override) / "import_failure_state.json"
    return _nr2_data_dir() / "import_failure_state.json"


def _load_failure_state() -> dict[str, Any]:
    path = failure_state_path()
    if not path.is_file():
        return {"files": {}, "updatedAt": None}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {"files": {}}
    except Exception:
        return {"files": {}}


def _save_failure_state(state: dict[str, Any]) -> None:
    path = failure_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updatedAt"] = _utc_now()
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _safe_stem(name: str) -> str:
    stem = Path(name).name
    stem = re.sub(r"[^\w.\-]+", "_", stem)
    return stem[:180] or "unknown"


def record_failure(path: str | Path, *, error: str | None = None) -> dict[str, Any]:
    """Increment failure count for basename; return state row."""
    p = Path(path)
    key = p.name.lower()
    state = _load_failure_state()
    files = state.get("files") if isinstance(state.get("files"), dict) else {}
    row = files.get(key) if isinstance(files.get(key), dict) else {}
    count = int(row.get("count") or 0) + 1
    files[key] = {
        "path": str(p),
        "name": p.name,
        "count": count,
        "lastError": (error or "")[:500],
        "lastFailedAt": _utc_now(),
    }
    state["files"] = files
    _save_failure_state(state)
    return files[key]


def clear_failure(path: str | Path) -> None:
    key = Path(path).name.lower()
    state = _load_failure_state()
    files = state.get("files") if isinstance(state.get("files"), dict) else {}
    if key in files:
        del files[key]
        state["files"] = files
        _save_failure_state(state)


def list_quarantine(*, limit: int = 50) -> list[dict[str, Any]]:
    root = quarantine_dir()
    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not child.is_file():
            continue
        if child.suffix.lower() == ".json" and child.name.endswith(".reason.json"):
            continue
        reason_path = root / f"{child.name}.reason.json"
        reason: dict[str, Any] = {}
        if reason_path.is_file():
            try:
                reason = json.loads(reason_path.read_text(encoding="utf-8"))
            except Exception:
                reason = {}
        items.append(
            {
                "name": child.name,
                "path": str(child),
                "size": child.stat().st_size,
                "quarantinedAt": reason.get("quarantinedAt") or datetime.fromtimestamp(
                    child.stat().st_mtime, tz=timezone.utc
                ).replace(microsecond=0).isoformat(),
                "error": reason.get("error"),
                "attempts": reason.get("attempts"),
                "originalPath": reason.get("originalPath"),
                "gapCode": GAP_IMPORT_QUARANTINED,
            }
        )
        if len(items) >= max(1, min(int(limit), 200)):
            break
    return items


def quarantine_file(
    path: str | Path,
    *,
    error: str | None = None,
    attempts: int | None = None,
) -> dict[str, Any]:
    """Move poisoned/unreadable export into quarantine with reason sidecar."""
    if not quarantine_enabled():
        return {
            "ok": False,
            "reason": "quarantine_disabled",
            "hint": "Set NR2_IMPORT_QUARANTINE=1 (default on).",
            "phase": "U2b",
        }

    src = Path(path)
    if not src.is_file():
        return {
            "ok": False,
            "gap": GAP_IMPORT_QUARANTINED,
            "error": f"missing:{src}",
            "phase": "U2b",
        }

    fail_row = record_failure(src, error=error)
    qdir = quarantine_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_name = f"{stamp}__{_safe_stem(src.name)}"
    dest = qdir / dest_name
    reason = {
        "originalPath": str(src),
        "originalName": src.name,
        "error": (error or "ingest_failed")[:500],
        "attempts": attempts if attempts is not None else fail_row.get("count"),
        "failureCount": fail_row.get("count"),
        "quarantinedAt": _utc_now(),
        "gapCode": GAP_IMPORT_QUARANTINED,
        "phase": "U2b",
        "softDentWriteBack": False,
    }
    try:
        shutil.move(str(src), str(dest))
    except Exception as exc:  # noqa: BLE001
        # Fallback copy+unlink if cross-device move issues
        try:
            shutil.copy2(str(src), str(dest))
            src.unlink(missing_ok=True)
        except Exception as exc2:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"quarantine_move_failed:{exc};{exc2}",
                "phase": "U2b",
            }

    reason_path = qdir / f"{dest_name}.reason.json"
    reason_path.write_text(json.dumps(reason, indent=2), encoding="utf-8")

    # Health log
    try:
        from apex_unified_db_pack import open_unified

        flags = json.dumps(
            {
                "gap": GAP_IMPORT_QUARANTINED,
                "file": src.name,
                "error": reason["error"],
                "failureCount": fail_row.get("count"),
            }
        )
        with open_unified() as conn:
            conn.execute(
                """
                INSERT INTO import_health_log
                    (source, export_type, row_count, staleness_hours, gap_flags, detected_at)
                VALUES (?,?,?,?,?,?)
                """,
                ("import_quarantine", src.suffix.lstrip(".") or "file", 0, None, flags, _utc_now()),
            )
            conn.commit()
    except Exception:
        pass

    alert = None
    threshold = fail_threshold()
    if int(fail_row.get("count") or 0) >= threshold:
        alert = emit_admin_alert(
            filename=src.name,
            error=reason["error"],
            failure_count=int(fail_row.get("count") or 0),
            quarantine_path=str(dest),
        )

    return {
        "ok": True,
        "phase": "U2b",
        "quarantined": True,
        "gapCode": GAP_IMPORT_QUARANTINED,
        "path": str(dest),
        "reasonPath": str(reason_path),
        "failureCount": fail_row.get("count"),
        "threshold": threshold,
        "adminAlert": alert,
        "refreshedAt": _utc_now(),
    }


def emit_admin_alert(
    *,
    filename: str,
    error: str,
    failure_count: int,
    quarantine_path: str,
) -> dict[str, Any]:
    """Persist alert-banner insight for SSE / hal-ai-insight (no PHI, no $)."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {
        "widget_type": "alert-banner",
        "title": "Import quarantine alert",
        "data": {
            "severity": "critical" if failure_count >= fail_threshold() + 2 else "warn",
            "message": (
                f"{filename} failed {failure_count}× — quarantined. "
                f"Error: {(error or 'unknown')[:200]}. Empty ≠ $0; fix export then re-drop."
            )[:400],
            "value": None,
            "unit": "text",
        },
        "source_refs": [f"import:quarantine:{day}"],
        "confidence": "high",
        "explanation": f"U2b quarantine: {Path(quarantine_path).name}",
        "action_cta": {"label": "Open SoftDent", "route": "softdent"},
    }
    from apex_structured_insight_pack import ai_insight_widget, save_last_insight, validate_insight

    validated = validate_insight(payload)
    if validated.get("ok") and isinstance(validated.get("insight"), dict):
        save_last_insight(validated["insight"])
        return {
            "ok": True,
            "insight": validated["insight"],
            "insightWidget": ai_insight_widget(validated["insight"]),
        }
    return {"ok": False, "error": validated.get("error")}


def maybe_quarantine_after_failure(
    path: str | Path,
    *,
    error: str | None = None,
    attempts: int | None = None,
) -> dict[str, Any]:
    """
    Quarantine when failure count reaches threshold (persistent failure).
    Below threshold: record only (leave file for retry).
    """
    if not quarantine_enabled():
        return {"ok": False, "reason": "quarantine_disabled", "quarantined": False}

    fail_row = record_failure(path, error=error)
    count = int(fail_row.get("count") or 0)
    threshold = fail_threshold()
    if count < threshold:
        return {
            "ok": True,
            "quarantined": False,
            "failureCount": count,
            "threshold": threshold,
            "gapCode": None,
            "note": "Below threshold — file left in inbox for retry.",
            "refreshedAt": _utc_now(),
        }
    # record_failure already incremented; quarantine_file will increment again —
    # so temporarily decrement by clearing and re-setting, or quarantine without re-count.
    # Simpler: call internal move using current count without double-increment.
    return _quarantine_without_recount(path, error=error, attempts=attempts, failure_count=count)


def _quarantine_without_recount(
    path: str | Path,
    *,
    error: str | None,
    attempts: int | None,
    failure_count: int,
) -> dict[str, Any]:
    src = Path(path)
    if not src.is_file():
        return {"ok": False, "error": f"missing:{src}", "quarantined": False}

    qdir = quarantine_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_name = f"{stamp}__{_safe_stem(src.name)}"
    dest = qdir / dest_name
    reason = {
        "originalPath": str(src),
        "originalName": src.name,
        "error": (error or "ingest_failed")[:500],
        "attempts": attempts if attempts is not None else failure_count,
        "failureCount": failure_count,
        "quarantinedAt": _utc_now(),
        "gapCode": GAP_IMPORT_QUARANTINED,
        "phase": "U2b",
        "softDentWriteBack": False,
    }
    try:
        shutil.move(str(src), str(dest))
    except Exception as exc:  # noqa: BLE001
        try:
            shutil.copy2(str(src), str(dest))
            src.unlink(missing_ok=True)
        except Exception as exc2:  # noqa: BLE001
            return {"ok": False, "error": f"quarantine_move_failed:{exc};{exc2}", "quarantined": False}

    reason_path = qdir / f"{dest_name}.reason.json"
    reason_path.write_text(json.dumps(reason, indent=2), encoding="utf-8")

    try:
        from apex_unified_db_pack import open_unified

        flags = json.dumps(
            {
                "gap": GAP_IMPORT_QUARANTINED,
                "file": src.name,
                "error": reason["error"],
                "failureCount": failure_count,
            }
        )
        with open_unified() as conn:
            conn.execute(
                """
                INSERT INTO import_health_log
                    (source, export_type, row_count, staleness_hours, gap_flags, detected_at)
                VALUES (?,?,?,?,?,?)
                """,
                ("import_quarantine", src.suffix.lstrip(".") or "file", 0, None, flags, _utc_now()),
            )
            conn.commit()
    except Exception:
        pass

    alert = emit_admin_alert(
        filename=src.name,
        error=reason["error"],
        failure_count=failure_count,
        quarantine_path=str(dest),
    )
    return {
        "ok": True,
        "phase": "U2b",
        "quarantined": True,
        "gapCode": GAP_IMPORT_QUARANTINED,
        "path": str(dest),
        "reasonPath": str(reason_path),
        "failureCount": failure_count,
        "threshold": fail_threshold(),
        "adminAlert": alert,
        "refreshedAt": _utc_now(),
    }


def release_quarantine(name: str, *, restore_dir: Path | None = None) -> dict[str, Any]:
    """Move quarantined file back to an inbox for retry."""
    qdir = quarantine_dir()
    src = qdir / Path(name).name
    if not src.is_file():
        return {"ok": False, "error": "not_found", "phase": "U2b"}
    dest_root = restore_dir
    if dest_root is None:
        try:
            from apex_import_watcher_pack import import_inbox_paths

            dest_root = import_inbox_paths()[0]
        except Exception:
            dest_root = _nr2_data_dir() / "import_inbox"
            dest_root.mkdir(parents=True, exist_ok=True)
    reason_path = qdir / f"{src.name}.reason.json"
    original = src.name
    if reason_path.is_file():
        try:
            meta = json.loads(reason_path.read_text(encoding="utf-8"))
            if isinstance(meta, dict) and meta.get("originalName"):
                original = str(meta["originalName"])
        except Exception:
            pass
    if original == src.name and "__" in original:
        original = original.split("__", 1)[1]
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / Path(original).name
    if dest.exists():
        dest = dest_root / f"restored_{Path(original).name}"
    shutil.move(str(src), str(dest))
    if reason_path.is_file():
        reason_path.unlink(missing_ok=True)
    clear_failure(Path(original).name)
    return {
        "ok": True,
        "phase": "U2b",
        "releasedTo": str(dest),
        "refreshedAt": _utc_now(),
    }


def purge_quarantine(name: str) -> dict[str, Any]:
    """Permanently delete a quarantined export + reason sidecar (no SoftDent write-back)."""
    qdir = quarantine_dir()
    src = qdir / Path(name).name
    if not src.is_file():
        return {"ok": False, "error": "not_found", "phase": "W2"}
    reason_path = qdir / f"{src.name}.reason.json"
    try:
        src.unlink()
    except OSError as exc:
        return {"ok": False, "error": str(exc), "phase": "W2"}
    if reason_path.is_file():
        try:
            reason_path.unlink()
        except OSError:
            pass
    clear_failure(src.name)
    return {
        "ok": True,
        "phase": "W2",
        "purged": src.name,
        "softDentWriteBack": False,
        "refreshedAt": _utc_now(),
    }


def retry_quarantine(name: str, *, restore_dir: Path | None = None) -> dict[str, Any]:
    """Release quarantined file to inbox, then queue ingest (DQ-gated)."""
    released = release_quarantine(name, restore_dir=restore_dir)
    if not released.get("ok"):
        released["phase"] = "W2"
        return released
    path = released.get("releasedTo")
    ingest: dict[str, Any] = {"ok": False, "error": "missing_path"}
    if path:
        try:
            from apex_import_watcher_pack import queue_import

            ingest = queue_import(path)
        except Exception as exc:  # noqa: BLE001
            ingest = {"ok": False, "error": str(exc)}
    return {
        "ok": bool(ingest.get("ok")),
        "phase": "W2",
        "released": released,
        "ingest": ingest,
        "softDentWriteBack": False,
        "refreshedAt": _utc_now(),
    }


def quarantine_ui_enabled() -> bool:
    raw = str(os.getenv("NR2_QUARANTINE_UI") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def quarantine_status() -> dict[str, Any]:
    items = list_quarantine(limit=20)
    state = _load_failure_state()
    files = state.get("files") if isinstance(state.get("files"), dict) else {}
    return {
        "ok": True,
        "phase": "U2b+W2",
        "enabled": quarantine_enabled(),
        "uiEnabled": quarantine_ui_enabled(),
        "flag": "NR2_IMPORT_QUARANTINE",
        "uiFlag": "NR2_QUARANTINE_UI",
        "threshold": fail_threshold(),
        "quarantineDir": str(quarantine_dir()),
        "quarantineCount": len(items),
        "trackedFailures": len(files),
        "items": items[:10],
        "gapCode": GAP_IMPORT_QUARANTINED if items else None,
        "endpoints": {
            "list": "GET /api/apex/hal/import-quarantine",
            "retry": "POST /api/apex/hal/import-quarantine-retry",
            "purge": "POST /api/apex/hal/import-quarantine-purge",
            "release": "POST /api/apex/hal/import-quarantine-release",
        },
        "note": "Persistent failures move to quarantine; W2 panel can retry or purge.",
        "refreshedAt": _utc_now(),
    }


def quarantine_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    del bundle
    st = quarantine_status()
    if not quarantine_ui_enabled():
        return {
            "id": "import-quarantine-panel",
            "type": "status",
            "label": "Quarantine Review (W2)",
            "size": "full",
            "status": "empty",
            "message": "Quarantine UI disabled",
            "hint": "Set NR2_QUARANTINE_UI=1 (default on).",
        }
    count = int(st.get("quarantineCount") or 0)
    items = st.get("items") if isinstance(st.get("items"), list) else []
    # Normalize fields for panel (error_code alias)
    panel_items = []
    for it in items:
        if not isinstance(it, dict):
            continue
        panel_items.append(
            {
                "name": it.get("name"),
                "error_code": it.get("error") or it.get("gapCode") or GAP_IMPORT_QUARANTINED,
                "row_count": it.get("attempts"),
                "size": it.get("size"),
                "quarantinedAt": it.get("quarantinedAt"),
            }
        )
    return {
        "id": "import-quarantine-panel",
        "type": "quarantine-panel",
        "label": "Quarantine Review (W2)",
        "size": "full",
        "status": "ok" if count == 0 else "warn",
        "message": (
            "No quarantined imports"
            if count <= 0
            else f"{count} file(s) quarantined — {GAP_IMPORT_QUARANTINED}"
        ),
        "hint": (
            f"Fail threshold={st.get('threshold')} · retry re-queues ingest; "
            "purge deletes local quarantine copy only. Empty ≠ $0."
        ),
        "items": panel_items,
        "gapCode": GAP_IMPORT_QUARANTINED if count else None,
        "endpoints": st.get("endpoints"),
    }