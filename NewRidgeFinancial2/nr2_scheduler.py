"""Autonomous morning / EOD scheduler — local work only (no dial/submit/email)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

AUTONOMOUS_RUNS_KEY = "nr2:scheduler:autonomous-state"
MAX_AUTONOMOUS_TICKS_PER_DAY = 3
MAX_APPEALS_PER_TICK = 5
UNDO_WINDOW_HOURS = 4

WORK_KINDS = frozenset(
    {
        "collections_seed",
        "month_end_task",
        "appeal_staged",
        "era_pending",
        "posting_pending",
        "eod_handoff",
        "carrier_gap",
    }
)


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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nr2_autonomous_work (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            kind TEXT NOT NULL,
            source_id TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'normal',
            status TEXT NOT NULL DEFAULT 'open',
            meta_json TEXT NOT NULL DEFAULT '{}',
            updated_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_nr2_autonomous_work_source
        ON nr2_autonomous_work(kind, source_id)
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
    open_work = 0
    try:
        open_work = int(list_autonomous_work(store, open_only=True, limit=200).get("count") or 0)
    except Exception:
        open_work = 0
    return {
        "ok": True,
        "autonomous": bool(state.get("running")),
        "runId": state.get("runId"),
        "ticksToday": int(state.get("ticksToday") or 0),
        "haltedByUser": bool(state.get("haltedByUser")),
        "openWorkCount": open_work,
        "lastEodHandoffId": state.get("lastEodHandoffId"),
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
    """Mark an autonomous run undone within UNDO_WINDOW_HOURS (does not reverse side effects)."""
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


def upsert_autonomous_work(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Insert or refresh a durable autonomous work row (stable kind+source_id)."""
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    kind = str(data.get("kind") or "").strip()
    source_id = str(data.get("sourceId") or data.get("source_id") or "").strip()
    title = str(data.get("title") or "").strip()
    if kind not in WORK_KINDS:
        return {"ok": False, "error": "invalid_kind", "allowed": sorted(WORK_KINDS)}
    if not source_id or not title:
        return {"ok": False, "error": "source_id_and_title_required"}
    detail = str(data.get("detail") or "")[:2000]
    priority = str(data.get("priority") or "normal").strip().lower() or "normal"
    if priority not in {"urgent", "high", "normal", "low"}:
        priority = "normal"
    status = str(data.get("status") or "open").strip().lower() or "open"
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    now = _utc_now()
    with store._connect() as conn:
        ensure_scheduler_schema(conn)
        existing = conn.execute(
            "SELECT id, status FROM nr2_autonomous_work WHERE kind = ? AND source_id = ?",
            (kind, source_id),
        ).fetchone()
        if existing:
            entry_id = str(existing[0])
            # Do not reopen staff-acked/closed rows unless explicitly forced
            prior_status = str(existing[1] or "open")
            next_status = status
            if prior_status in {"acked", "closed", "done"}:
                if data.get("forceReopen") in (True, "true", "1"):
                    next_status = status
                else:
                    next_status = prior_status
            conn.execute(
                """
                UPDATE nr2_autonomous_work
                SET title = ?, detail = ?, priority = ?, status = ?, meta_json = ?, updated_at_utc = ?
                WHERE id = ?
                """,
                (title, detail, priority, next_status, json.dumps(meta), now, entry_id),
            )
            conn.commit()
            return {
                "ok": True,
                "id": entry_id,
                "created": False,
                "kind": kind,
                "sourceId": source_id,
                "status": next_status,
            }
        entry_id = str(data.get("id") or f"aw-{uuid.uuid4().hex[:12]}")
        conn.execute(
            """
            INSERT INTO nr2_autonomous_work
            (id, created_at_utc, kind, source_id, title, detail, priority, status, meta_json, updated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_id, now, kind, source_id, title, detail, priority, status, json.dumps(meta), now),
        )
        conn.commit()
    return {
        "ok": True,
        "id": entry_id,
        "created": True,
        "kind": kind,
        "sourceId": source_id,
        "status": status,
    }


def list_autonomous_work(
    store,
    *,
    open_only: bool = True,
    limit: int = 50,
    kind: str = "",
) -> dict[str, Any]:
    if not store:
        return {"ok": True, "items": [], "count": 0}
    with store._connect() as conn:
        ensure_scheduler_schema(conn)
        cap = max(1, min(int(limit or 50), 200))
        kind_f = str(kind or "").strip()
        if open_only and kind_f:
            rows = conn.execute(
                """
                SELECT id, created_at_utc, kind, source_id, title, detail, priority, status, meta_json, updated_at_utc
                FROM nr2_autonomous_work
                WHERE status IN ('open', 'in_progress') AND kind = ?
                ORDER BY
                  CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                  updated_at_utc DESC
                LIMIT ?
                """,
                (kind_f, cap),
            ).fetchall()
        elif open_only:
            rows = conn.execute(
                """
                SELECT id, created_at_utc, kind, source_id, title, detail, priority, status, meta_json, updated_at_utc
                FROM nr2_autonomous_work
                WHERE status IN ('open', 'in_progress')
                ORDER BY
                  CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                  updated_at_utc DESC
                LIMIT ?
                """,
                (cap,),
            ).fetchall()
        elif kind_f:
            rows = conn.execute(
                """
                SELECT id, created_at_utc, kind, source_id, title, detail, priority, status, meta_json, updated_at_utc
                FROM nr2_autonomous_work
                WHERE kind = ?
                ORDER BY updated_at_utc DESC
                LIMIT ?
                """,
                (kind_f, cap),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, created_at_utc, kind, source_id, title, detail, priority, status, meta_json, updated_at_utc
                FROM nr2_autonomous_work
                ORDER BY updated_at_utc DESC
                LIMIT ?
                """,
                (cap,),
            ).fetchall()
    items: list[dict[str, Any]] = []
    for r in rows:
        try:
            meta = json.loads(r[8] or "{}")
        except json.JSONDecodeError:
            meta = {}
        items.append(
            {
                "id": r[0],
                "createdAtUtc": r[1],
                "kind": r[2],
                "sourceId": r[3],
                "title": r[4],
                "detail": r[5],
                "priority": r[6],
                "status": r[7],
                "meta": meta,
                "updatedAtUtc": r[9],
            }
        )
    return {"ok": True, "items": items, "count": len(items)}


def ack_autonomous_work(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    work_id = str(data.get("id") or data.get("workId") or "").strip()
    source_id = str(data.get("sourceId") or data.get("source_id") or "").strip()
    kind = str(data.get("kind") or "").strip()
    status = str(data.get("status") or "acked").strip().lower() or "acked"
    if status not in {"acked", "closed", "done", "open", "in_progress"}:
        status = "acked"
    with store._connect() as conn:
        ensure_scheduler_schema(conn)
        row = None
        if work_id:
            row = conn.execute(
                "SELECT id FROM nr2_autonomous_work WHERE id = ?",
                (work_id,),
            ).fetchone()
        if not row and kind and source_id:
            row = conn.execute(
                "SELECT id FROM nr2_autonomous_work WHERE kind = ? AND source_id = ?",
                (kind, source_id),
            ).fetchone()
        if not row:
            return {"ok": False, "error": "not_found"}
        entry_id = str(row[0])
        conn.execute(
            "UPDATE nr2_autonomous_work SET status = ?, updated_at_utc = ? WHERE id = ?",
            (status, _utc_now(), entry_id),
        )
        conn.commit()
    return {"ok": True, "id": entry_id, "status": status}


def _persist_work_from_morning(
    store,
    *,
    collections_result: dict[str, Any] | None,
    month_end: dict[str, Any] | None,
    era_count: int,
    posting_count: int,
    claims_ops: dict[str, Any] | None,
    odbc_brief: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Upsert durable work rows from morning tick outputs."""
    written: list[dict[str, Any]] = []
    coll = collections_result if isinstance(collections_result, dict) else {}
    coll_count = int(coll.get("count") or len(coll.get("items") or []) or 0)
    if coll_count > 0:
        written.append(
            upsert_autonomous_work(
                store,
                {
                    "kind": "collections_seed",
                    "sourceId": "collections-queue-open",
                    "title": f"Work seeded collections queue ({coll_count})",
                    "detail": coll.get("summary")
                    or f"{coll_count} account(s) seeded with call scripts — staff owns patient contact.",
                    "priority": "high" if int(coll.get("highPriorityCount") or 0) > 0 else "normal",
                    "meta": {"count": coll_count, "highPriorityCount": coll.get("highPriorityCount")},
                },
            )
        )

    me = month_end if isinstance(month_end, dict) else {}
    for task in (me.get("tasks") or [])[:15]:
        if not isinstance(task, dict):
            continue
        if task.get("completed"):
            continue
        tid = str(task.get("id") or task.get("title") or "").strip()
        if not tid:
            continue
        pri = str(task.get("priority") or "medium").lower()
        mapped = "high" if pri == "high" else ("urgent" if pri == "urgent" else "normal")
        written.append(
            upsert_autonomous_work(
                store,
                {
                    "kind": "month_end_task",
                    "sourceId": f"month-end-{tid}",
                    "title": str(task.get("title") or tid),
                    "detail": str(task.get("detail") or "")[:500],
                    "priority": mapped,
                    "meta": {"taskId": tid, "period": me.get("period")},
                },
            )
        )

    if era_count > 0:
        written.append(
            upsert_autonomous_work(
                store,
                {
                    "kind": "era_pending",
                    "sourceId": "era-pending-matches",
                    "title": f"Review ERA/EOB pending matches ({era_count})",
                    "detail": f"{era_count} match(es) need staff confirm before posting — ask HAL: list pending ERA matches.",
                    "priority": "high" if era_count >= 3 else "normal",
                    "meta": {"count": era_count},
                },
            )
        )

    if posting_count > 0:
        written.append(
            upsert_autonomous_work(
                store,
                {
                    "kind": "posting_pending",
                    "sourceId": "posting-queue-pending",
                    "title": f"Review posting queue ({posting_count})",
                    "detail": f"{posting_count} journal(s) awaiting staff approve/export — not posted live.",
                    "priority": "high" if posting_count >= 5 else "normal",
                    "meta": {"count": posting_count},
                },
            )
        )

    ops = claims_ops if isinstance(claims_ops, dict) else {}
    generic = int(ops.get("genericPayer") or 0)
    if generic > 0:
        written.append(
            upsert_autonomous_work(
                store,
                {
                    "kind": "carrier_gap",
                    "sourceId": "softdent-named-payer-gap",
                    "title": f"Close SoftDent named-payer gap ({generic} generic)",
                    "detail": (odbc_brief or {}).get("summary")
                    or f"{generic} claim(s) still say generic Insurance — need SoftDent claims CSV/ODBC.",
                    "priority": "high",
                    "meta": {
                        "genericPayer": generic,
                        "namedPayer": ops.get("namedPayer"),
                        "agingOver60": ops.get("agingOver60"),
                    },
                },
            )
        )
    return written


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

    collections_result: dict[str, Any] | None = None
    month_end: dict[str, Any] | None = None
    era_count = 0
    posting_count = 0
    claims_ops: dict[str, Any] | None = None
    odbc_brief: dict[str, Any] | None = None

    try:
        from accounting_bridge import list_posting_queue
        from hal_employee_workflows import (
            _claims_ops_snapshot,
            _softdent_named_payer_brief,
            generate_collections_queue,
            generate_month_end_tasks,
            list_pending_era_matches,
            stage_pending_appeal_packets,
        )

        collections_result = generate_collections_queue(store, limit=25)
        actions.append({"action": "build_collections_queue", "result": collections_result})
        month_end = generate_month_end_tasks(store)
        actions.append({"action": "generate_month_end_tasks", "result": month_end})
        era = list_pending_era_matches(store, limit=25)
        era_count = int(era.get("count") or 0)
        actions.append({"action": "list_pending_era_matches", "result": {"count": era_count, "ok": era.get("ok")}})
        claims_ops = _claims_ops_snapshot()
        actions.append(
            {
                "action": "claims_ops_snapshot",
                "result": {
                    "denied": claims_ops.get("denied"),
                    "genericPayer": claims_ops.get("genericPayer"),
                    "agingOver60": claims_ops.get("agingOver60"),
                    "agingOver90": claims_ops.get("agingOver90"),
                },
            }
        )
        try:
            pq = list_posting_queue(store.db_path, limit=25, status="pending_review")
            posting_count = len(pq.get("items") or [])
            actions.append({"action": "list_posting_queue", "result": {"count": posting_count, "ok": True}})
        except Exception as pq_exc:
            actions.append({"action": "list_posting_queue", "error": str(pq_exc)})
        odbc_brief = _softdent_named_payer_brief()
        actions.append(
            {
                "action": "softdent_named_payer_brief",
                "result": {
                    "namedPayer": odbc_brief.get("namedPayer"),
                    "genericPayer": odbc_brief.get("genericPayer"),
                    "hasClaimsQuery": odbc_brief.get("hasClaimsQuery"),
                    "summary": odbc_brief.get("summary"),
                },
            }
        )

        # Durable work ledger (survives without UI)
        work_rows = _persist_work_from_morning(
            store,
            collections_result=collections_result,
            month_end=month_end,
            era_count=era_count,
            posting_count=posting_count,
            claims_ops=claims_ops,
            odbc_brief=odbc_brief,
        )
        actions.append(
            {
                "action": "upsert_autonomous_work",
                "result": {"count": len(work_rows), "created": sum(1 for w in work_rows if w.get("created"))},
            }
        )

        # Stage local appeal packets (no zip / no portal)
        appeals = stage_pending_appeal_packets(store, limit=MAX_APPEALS_PER_TICK)
        actions.append({"action": "stage_pending_appeal_packets", "result": appeals})
        for item in appeals.get("items") or []:
            if not isinstance(item, dict) or not item.get("claimId"):
                continue
            upsert_autonomous_work(
                store,
                {
                    "kind": "appeal_staged",
                    "sourceId": f"appeal-{item['claimId']}",
                    "title": f"Review staged appeal for {item['claimId']}",
                    "detail": item.get("summary")
                    or "Local appeal packet staged — staff consent required for claim packet zip.",
                    "priority": "high" if item.get("denied") else "normal",
                    "meta": {
                        "claimId": item.get("claimId"),
                        "path": item.get("path"),
                        "payer": item.get("payer"),
                    },
                },
            )
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


def eod_handoff_tick(store, *, force: bool = False) -> dict[str, Any]:
    """Compile shift handoff without requiring clock-out (local only)."""
    if not store:
        return {"ok": False, "error": "no_store"}
    from employee_actions import get_current_shift_context
    from hal_employee_workflows import compile_shift_handoff, init_employee_workflow_schemas

    state = _load_state(store)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("eodDay") == today and not force:
        return {
            "ok": True,
            "skipped": True,
            "reason": "eod_already_ran",
            "handoffId": state.get("lastEodHandoffId"),
        }

    ctx = get_current_shift_context(store)
    # Prefer running when no human shift; allow force during shift for tests/manual
    if ctx.get("active") and not force:
        return {"ok": True, "skipped": True, "reason": "human_shift_active"}

    handoff = compile_shift_handoff(store, employee_id="HAL")
    handoff_id = f"handoff-eod-{uuid.uuid4().hex[:12]}"
    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        ensure_scheduler_schema(conn)
        conn.execute(
            """
            INSERT INTO shift_handoffs (id, created_at_utc, employee_id, report_markdown, open_item_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                handoff_id,
                _utc_now(),
                "HAL",
                str(handoff.get("reportMarkdown") or ""),
                int(handoff.get("openItemCount") or 0),
            ),
        )
        conn.execute(
            """
            INSERT INTO autonomous_runs (id, started_at_utc, ended_at_utc, status, actions_json, halted_by_user)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                f"eod-{uuid.uuid4().hex[:12]}",
                _utc_now(),
                _utc_now(),
                "completed",
                json.dumps(
                    [
                        {
                            "action": "eod_handoff",
                            "result": {
                                "handoffId": handoff_id,
                                "openItemCount": handoff.get("openItemCount"),
                            },
                        }
                    ]
                ),
            ),
        )
        conn.commit()

    upsert_autonomous_work(
        store,
        {
            "kind": "eod_handoff",
            "sourceId": f"eod-{today}",
            "title": f"EOD handoff ready ({handoff.get('openItemCount') or 0} open items)",
            "detail": "Autonomous end-of-day handoff compiled — ask HAL for last handoff report.",
            "priority": "normal",
            "meta": {"handoffId": handoff_id, "openItemCount": handoff.get("openItemCount")},
            "forceReopen": True,
        },
    )

    state["eodDay"] = today
    state["lastEodHandoffId"] = handoff_id
    _save_state(store, state)
    return {
        "ok": True,
        "handoffId": handoff_id,
        "openItemCount": handoff.get("openItemCount"),
        "reportMarkdown": handoff.get("reportMarkdown"),
    }
