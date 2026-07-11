"""
Phase W1 — Import cron scheduler (Moonshot REAUDIT5 MUST).

Task Scheduler–friendly one-shot (or optional loop) that polls import inboxes,
runs DQ-gated ingest via existing T3 poller, and appends cron logs.
Flag: NR2_IMPORT_CRON (default OFF until burn-in).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def import_cron_enabled() -> bool:
    raw = str(os.getenv("NR2_IMPORT_CRON") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def import_cron_interval_sec() -> float:
    raw = str(os.getenv("NR2_IMPORT_CRON_SEC") or "").strip()
    try:
        return max(30.0, float(raw)) if raw else 300.0
    except ValueError:
        return 300.0


def _nr2_data_dir() -> Path:
    try:
        from document_sync import NR2_DATA_DIR

        return Path(NR2_DATA_DIR)
    except Exception:
        return Path(__file__).resolve().parent / "app_data" / "nr2"


def cron_log_path() -> Path:
    override = str(os.getenv("NR2_IMPORT_CRON_LOG") or "").strip()
    if override:
        return Path(override)
    return _nr2_data_dir() / "import_cron_log.jsonl"


def poll_state_path() -> Path:
    override = str(os.getenv("NR2_IMPORT_POLL_STATE") or "").strip()
    if override:
        return Path(override)
    return _nr2_data_dir() / "import_poll_state.json"


def append_cron_log(entry: dict[str, Any]) -> None:
    path = cron_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def _load_since_mtime() -> float:
    path = poll_state_path()
    if not path.is_file():
        return 0.0
    try:
        return float(json.loads(path.read_text(encoding="utf-8")).get("newestMtime") or 0)
    except Exception:
        return 0.0


def _save_since_mtime(newest: float, *, at: str | None = None) -> None:
    path = poll_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"newestMtime": newest, "at": at or _utc_now()}, indent=2),
        encoding="utf-8",
    )


def job_poll_and_ingest(*, since_mtime: float | None = None) -> dict[str, Any]:
    """
    One cron tick: poll inboxes → queue_import (DQ inside ingest) → persist mtime.
    """
    from apex_import_watcher_pack import poll_once

    since = float(since_mtime) if since_mtime is not None else _load_since_mtime()
    poll = poll_once(since_mtime=since)
    newest = float(poll.get("newestMtime") or since)
    _save_since_mtime(newest, at=str(poll.get("refreshedAt") or _utc_now()))

    results = poll.get("results") if isinstance(poll.get("results"), list) else []
    failed = [r for r in results if isinstance(r, dict) and not r.get("ok")]
    dq_blocked = [
        r
        for r in failed
        if isinstance(r, dict)
        and (
            (r.get("unifiedIngest") or {}).get("reason") == "dq_blocked"
            or (r.get("unifiedIngest") or {}).get("gapCode") == "IMPORT_DQ_BLOCKED"
        )
    ]

    # Optional freshness stamp (no $)
    freshness = None
    try:
        from apex_sync_status_pack import build_sync_status

        st = build_sync_status(bundle=None)
        freshness = {
            "ok": st.get("ok"),
            "chipCount": len(st.get("chips") or []) if isinstance(st.get("chips"), list) else 0,
        }
    except Exception:
        freshness = None

    return {
        "ok": bool(poll.get("ok")),
        "phase": "W1",
        "poll": {
            "found": poll.get("found"),
            "resultCount": len(results),
            "failedCount": len(failed),
            "dqBlockedCount": len(dq_blocked),
            "newestMtime": newest,
        },
        "freshness": freshness,
        "refreshedAt": _utc_now(),
    }


def run_import_cron_once(*, force: bool = False) -> dict[str, Any]:
    """CLI/Task Scheduler entry — requires NR2_IMPORT_CRON unless force."""
    if not import_cron_enabled() and not force:
        entry = {
            "at": _utc_now(),
            "ok": False,
            "exit": 2,
            "reason": "import_cron_disabled",
            "hint": "Set NR2_IMPORT_CRON=1 (default OFF until burn-in).",
            "phase": "W1",
        }
        append_cron_log(entry)
        return entry

    job = job_poll_and_ingest()
    exit_code = 0 if job.get("ok") else 1
    entry = {
        "at": _utc_now(),
        "ok": bool(job.get("ok")),
        "exit": exit_code,
        "phase": "W1",
        "forced": bool(force),
        "found": (job.get("poll") or {}).get("found"),
        "failedCount": (job.get("poll") or {}).get("failedCount"),
        "dqBlockedCount": (job.get("poll") or {}).get("dqBlockedCount"),
        # no dollar fields
    }
    append_cron_log(entry)
    return {"log": entry, "job": job}


def run_scheduler_loop(*, max_ticks: int | None = None) -> dict[str, Any]:
    """Optional long-running loop (prefer Windows Task Scheduler one-shots)."""
    if not import_cron_enabled():
        return {
            "ok": False,
            "reason": "import_cron_disabled",
            "hint": "Set NR2_IMPORT_CRON=1",
        }
    interval = import_cron_interval_sec()
    ticks = 0
    while True:
        run_import_cron_once(force=True)
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            return {"ok": True, "ticks": ticks, "stopped": "max_ticks", "intervalSec": interval}
        time.sleep(interval)


def import_cron_status() -> dict[str, Any]:
    from apex_import_dq_pack import dq_status

    return {
        "ok": True,
        "phase": "W1",
        "enabled": import_cron_enabled(),
        "flag": "NR2_IMPORT_CRON",
        "intervalSec": import_cron_interval_sec(),
        "envInterval": "NR2_IMPORT_CRON_SEC",
        "logPath": str(cron_log_path()),
        "pollStatePath": str(poll_state_path()),
        "dq": dq_status(),
        "cli": "python scripts/run_nr2_import_cron.py",
        "softDentWriteBack": False,
        "refreshedAt": _utc_now(),
    }


def import_cron_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    del bundle
    st = import_cron_status()
    if not st.get("enabled"):
        return {
            "id": "import-cron-status",
            "type": "status",
            "label": "Import Cron (W1)",
            "size": "full",
            "status": "empty",
            "message": "Import cron disabled",
            "hint": "Set NR2_IMPORT_CRON=1 · Task Scheduler → run_nr2_import_cron.py",
        }
    return {
        "id": "import-cron-status",
        "type": "status",
        "label": "Import Cron (W1)",
        "size": "full",
        "status": "ok",
        "message": f"Enabled · interval {st.get('intervalSec')}s",
        "hint": f"Log: {st.get('logPath')}",
    }
