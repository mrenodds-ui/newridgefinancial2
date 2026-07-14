"""
Phase T3 — Import inbox watcher / poller (Moonshot REAUDIT2).

Primary: poll every N seconds (Task Scheduler–friendly; no new hard dependency).
Optional: watchdog Observer when installed (Moonshot sketch).
Debounce 2s; retry up to 3 times on lock; queue to existing sync/ingest path.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WATCH_EXTS = {".csv", ".xlsx", ".xls", ".json", ".835", ".edi", ".txt"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def import_inbox_paths() -> list[Path]:
    paths: list[Path] = []
    try:
        from import_loader import quickbooks_import_dir, softdent_import_dir

        paths.extend([softdent_import_dir(), quickbooks_import_dir()])
    except Exception:
        root = Path(__file__).resolve().parent / "app_data" / "nr2" / "document_inbox"
        paths.extend([root / "softdent", root / "quickbooks"])
    # Moonshot sketch path
    try:
        from document_sync import NR2_DATA_DIR

        paths.append(Path(NR2_DATA_DIR) / "import_inbox")
    except Exception:
        paths.append(Path(__file__).resolve().parent / "app_data" / "nr2" / "import_inbox")
    out: list[Path] = []
    for p in paths:
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        if p not in out:
            out.append(p)
    return out


def queue_import(path: str | Path) -> dict[str, Any]:
    """Debounced ingest trigger for a dropped export file."""
    p = Path(path)
    last_err = None
    for attempt in range(1, 4):
        try:
            # Ensure file is readable (Windows export lock)
            with p.open("rb") as fh:
                fh.read(1)
            from apex_unified_db_pack import ingest_from_bundle
            from import_loader import load_import_bundle

            # sync=False is the read-only path (load_import_bundle has no read_only kwarg).
            bundle = load_import_bundle(sync=False, deep=False)
            result = ingest_from_bundle(bundle)
            ok = bool(result.get("ok"))
            out = {
                "ok": ok,
                "path": str(p),
                "attempt": attempt,
                "unifiedIngest": result,
                "queuedAt": _utc_now(),
            }
            if ok:
                try:
                    from apex_import_quarantine_pack import clear_failure

                    clear_failure(p)
                except Exception:
                    pass
                return out
            last_err = str(result.get("error") or result.get("reason") or "ingest_not_ok")
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(2.0)
    # Phase U2b — persistent failure → quarantine after threshold
    quarantine = None
    try:
        from apex_import_quarantine_pack import maybe_quarantine_after_failure

        quarantine = maybe_quarantine_after_failure(
            p, error=last_err, attempts=3
        )
    except Exception as exc:  # noqa: BLE001
        quarantine = {"ok": False, "error": str(exc)}
    return {
        "ok": False,
        "path": str(p),
        "error": last_err,
        "quarantine": quarantine,
        "queuedAt": _utc_now(),
    }


def poll_once(*, since_mtime: float | None = None) -> dict[str, Any]:
    """Scan inbox dirs for new/changed CSV/Excel/JSON and queue ingest."""
    cutoff = float(since_mtime or 0)
    found: list[str] = []
    results: list[dict[str, Any]] = []
    newest = cutoff
    for folder in import_inbox_paths():
        if not folder.is_dir():
            continue
        for child in folder.iterdir():
            if not child.is_file():
                continue
            if child.suffix.lower() not in WATCH_EXTS:
                continue
            try:
                mtime = child.stat().st_mtime
            except OSError:
                continue
            newest = max(newest, mtime)
            if mtime <= cutoff:
                continue
            found.append(str(child))
            time.sleep(2.0)  # debounce per Moonshot
            results.append(queue_import(child))
    return {
        "ok": True,
        "phase": "T3",
        "found": found,
        "results": results,
        "newestMtime": newest,
        "refreshedAt": _utc_now(),
    }


_POLL_STOP = threading.Event()
_POLL_THREAD: threading.Thread | None = None


def start_poll_loop(*, interval_sec: float = 300.0) -> dict[str, Any]:
    """Background poll loop (default 5 minutes — Moonshot Task Scheduler alternative)."""
    global _POLL_THREAD
    if _POLL_THREAD and _POLL_THREAD.is_alive():
        return {"ok": True, "alreadyRunning": True}

    _POLL_STOP.clear()
    state = {"lastMtime": 0.0}

    def _run() -> None:
        while not _POLL_STOP.is_set():
            try:
                out = poll_once(since_mtime=state["lastMtime"])
                state["lastMtime"] = float(out.get("newestMtime") or state["lastMtime"])
            except Exception:
                pass
            _POLL_STOP.wait(max(30.0, float(interval_sec)))

    _POLL_THREAD = threading.Thread(target=_run, name="nr2-import-poll", daemon=True)
    _POLL_THREAD.start()
    return {"ok": True, "started": True, "intervalSec": interval_sec, "mode": "poll"}


def stop_poll_loop() -> dict[str, Any]:
    _POLL_STOP.set()
    return {"ok": True, "stopped": True}


def start_watcher() -> dict[str, Any]:
    """
    Moonshot primary sketch: watchdog Observer when available; else poll loop.
    """
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except Exception:
        return start_poll_loop(interval_sec=float(os.getenv("NR2_IMPORT_POLL_SEC") or 300))

    class ImportHandler(FileSystemEventHandler):
        def on_created(self, event):  # type: ignore[no-untyped-def]
            if getattr(event, "is_directory", False):
                return
            src = str(getattr(event, "src_path", "") or "")
            if not src.lower().endswith((".csv", ".xlsx", ".xls", ".json")):
                return
            time.sleep(2)
            queue_import(src)

        def on_modified(self, event):  # type: ignore[no-untyped-def]
            self.on_created(event)

    observer = Observer()
    for folder in import_inbox_paths():
        try:
            observer.schedule(ImportHandler(), str(folder), recursive=False)
        except Exception:
            continue
    observer.start()
    return {"ok": True, "mode": "watchdog", "paths": [str(p) for p in import_inbox_paths()]}


def watcher_status() -> dict[str, Any]:
    running = bool(_POLL_THREAD and _POLL_THREAD.is_alive())
    q = {}
    try:
        from apex_import_quarantine_pack import quarantine_status

        q = quarantine_status()
    except Exception:
        q = {}
    return {
        "ok": True,
        "phase": "T3+U2b",
        "pollRunning": running,
        "paths": [str(p) for p in import_inbox_paths()],
        "quarantine": {
            "enabled": q.get("enabled"),
            "count": q.get("quarantineCount"),
            "threshold": q.get("threshold"),
            "dir": q.get("quarantineDir"),
        },
        "note": "Poll default 300s; quarantine after persistent failures (U2b).",
        "refreshedAt": _utc_now(),
    }
