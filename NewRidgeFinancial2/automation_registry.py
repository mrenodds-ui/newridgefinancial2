"""Central automation job registry with last-run tracking for NR2."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "automation_registry.json"
STATE_PATH = REPO_ROOT / "app_data" / "nr2" / "automation_runs.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        return {"version": 1, "jobs": []}
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"version": 1, "jobs": []}


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        return {"runs": {}}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": {}}
    return payload if isinstance(payload, dict) else {"runs": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def record_job_run(job_id: str, *, ok: bool, detail: str = "", actor: str = "NR2") -> dict[str, Any]:
    state = _load_state()
    runs = state.setdefault("runs", {})
    if not isinstance(runs, dict):
        runs = {}
        state["runs"] = runs
    runs[job_id] = {
        "jobId": job_id,
        "ok": bool(ok),
        "detail": str(detail or "")[:2000],
        "actor": actor,
        "ranAt": _utc_now(),
    }
    _save_state(state)
    return runs[job_id]


def job_status(job: dict[str, Any], run: dict[str, Any] | None) -> str:
    if not run:
        return "never_run"
    if run.get("ok") is True:
        return "ok"
    if run.get("ok") is False:
        return "failed"
    return "unknown"


def list_automation_jobs() -> dict[str, Any]:
    registry = load_registry()
    state = _load_state()
    runs = state.get("runs") if isinstance(state.get("runs"), dict) else {}
    jobs_out: list[dict[str, Any]] = []
    ok_count = 0
    fail_count = 0
    never_count = 0
    for job in registry.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("id") or "")
        run = runs.get(job_id) if isinstance(runs, dict) else None
        status = job_status(job, run if isinstance(run, dict) else None)
        if status == "ok":
            ok_count += 1
        elif status == "failed":
            fail_count += 1
        else:
            never_count += 1
        jobs_out.append(
            {
                **job,
                "lastRun": run,
                "status": status,
            }
        )
    return {
        "registryPath": str(REGISTRY_PATH),
        "statePath": str(STATE_PATH),
        "generatedAt": _utc_now(),
        "summary": {
            "total": len(jobs_out),
            "ok": ok_count,
            "failed": fail_count,
            "neverRun": never_count,
        },
        "jobs": jobs_out,
    }
