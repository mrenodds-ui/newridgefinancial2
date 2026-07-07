"""Autonomous morning routine scheduler — Phase 2 Moonshot Priority F."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

AUTONOMOUS_RUNS_KEY = "nr2:scheduler:autonomous-state"
MAX_AUTONOMOUS_TICKS_PER_DAY = 3
UNDO_WINDOW_HOURS = 4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_scheduler_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS autonomous_runs (
            id TEXT PRIMARY KEY,
            started_at_utc TEXT NOT NULL,
            ended_at_utc TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            actions_json TEXT NOT NULL DEFAULT '[]',
            halted_by_user INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()


def _load_state(store) -> dict[str, Any]:
    raw = store.get(AUTONOMOUS_RUNS_KEY) if store else None
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}


def _save_state(store, state: dict[str, Any]) -> None:
    if store:
        store.set(AUTONOMOUS_RUNS_KEY, json.dumps(state))


def scheduler_status(store) -> dict[str, Any]:
    state = _load_state(store)
    return {
        "ok": True,
        "autonomous": bool(state.get("running")),
        "runId": state.get("runId"),
        "ticksToday": int(state.get("ticksToday") or 0),
        "haltedByUser": bool(state.get("haltedByUser")),
    }


def halt_autonomous_run(store) -> dict[str, Any]:
    state = _load_state(store)
    state["running"] = False
    state["haltedByUser"] = True
    _save_state(store, state)
    conn = store._connect() if store and hasattr(store, "_connect") else None
    if conn and state.get("runId"):
        ensure_scheduler_schema(conn)
        conn.execute(
            "UPDATE autonomous_runs SET ended_at_utc = ?, status = ?, halted_by_user = 1 WHERE id = ?",
            (_utc_now(), "halted", str(state.get("runId"))),
        )
        conn.commit()
    return {"ok": True, "halted": True}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def undo_autonomous_run(store, *, run_id: str) -> dict[str, Any]:
    """Moonshot 2B — undo an autonomous morning run within UNDO_WINDOW_HOURS."""
    if not store or not run_id:
        return {"ok": False, "error": "missing_run_id"}
    conn = store._connect()
    ensure_scheduler_schema(conn)
    cur = conn.execute(
        "SELECT started_at_utc, status FROM autonomous_runs WHERE id = ?",
        (str(run_id),),
    )
    row = cur.fetchone()
    if not row:
        return {"ok": False, "error": "run_not_found"}
    started = _parse_ts(str(row[0] or ""))
    if started:
        elapsed_h = (datetime.now(timezone.utc) - started).total_seconds() / 3600.0
        if elapsed_h > UNDO_WINDOW_HOURS:
            return {"ok": False, "error": "undo_window_expired", "windowHours": UNDO_WINDOW_HOURS}
    if str(row[1] or "") == "undone":
        return {"ok": True, "undone": True, "runId": run_id, "alreadyUndone": True}
    conn.execute(
        "UPDATE autonomous_runs SET status = 'undone', ended_at_utc = ? WHERE id = ?",
        (_utc_now(), str(run_id)),
    )
    conn.commit()
    return {"ok": True, "undone": True, "runId": run_id, "windowHours": UNDO_WINDOW_HOURS}


def morning_routine_tick(store, *, force: bool = False) -> dict[str, Any]:
    from employee_actions import get_current_shift_context
    from import_healing import heal_import_pipeline

    if not store:
        return {"ok": False, "error": "no_store"}
    ctx = get_current_shift_context(store)
    if ctx.get("active") and not force:
        return {"ok": True, "skipped": True, "reason": "human_shift_active"}

    state = _load_state(store)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("day") != today:
        state = {"day": today, "ticksToday": 0, "running": False, "haltedByUser": False}
    if int(state.get("ticksToday") or 0) >= MAX_AUTONOMOUS_TICKS_PER_DAY and not force:
        return {"ok": True, "skipped": True, "reason": "daily_cap_reached"}

    conn = store._connect()
    ensure_scheduler_schema(conn)
    run_id = f"auto-{uuid.uuid4().hex[:12]}"
    actions: list[dict[str, Any]] = []

    heal = heal_import_pipeline(force=False)
    actions.append({"action": "heal_import_pipeline", "result": heal})

    try:
        from hal_employee_workflows import generate_collections_queue, generate_month_end_tasks

        actions.append({"action": "build_collections_queue", "result": generate_collections_queue(store, limit=25)})
        actions.append({"action": "generate_month_end_tasks", "result": generate_month_end_tasks(store)})
    except Exception as exc:
        actions.append({"action": "workflow_error", "error": str(exc)})

    conn.execute(
        """
        INSERT INTO autonomous_runs (id, started_at_utc, ended_at_utc, status, actions_json, halted_by_user)
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (run_id, _utc_now(), _utc_now(), "completed", json.dumps(actions)),
    )
    conn.commit()

    state["running"] = False
    state["runId"] = run_id
    state["ticksToday"] = int(state.get("ticksToday") or 0) + 1
    state["day"] = today
    _save_state(store, state)
    return {"ok": True, "runId": run_id, "actions": actions, "ticksToday": state["ticksToday"]}
