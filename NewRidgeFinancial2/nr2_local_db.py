"""NR2 local SQLite store — collection notes, tasks, huddle history.

CONSULT Phase 2: MOONSHOT_SUBPAGES_EXPAND_CONSULT_2026-07-11.md
Local-only — never syncs off-box. PHI-safe: store claim IDs + initials, not full names.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def db_path() -> Path:
    try:
        from document_sync import NR2_DATA_DIR

        root = Path(NR2_DATA_DIR)
    except Exception:
        root = Path(__file__).resolve().parents[1] / "app_data" / "nr2"
    root.mkdir(parents=True, exist_ok=True)
    return root / "nr2_local.sqlite3"


def connect() -> sqlite3.Connection:
    path = db_path()
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS collection_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT NOT NULL,
            patient_initials TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            note TEXT NOT NULL DEFAULT '',
            follow_up TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_collection_claim ON collection_notes(claim_id);

        CREATE TABLE IF NOT EXISTS office_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            assignee TEXT,
            due_date TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS huddle_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            priorities_json TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payer_guidelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payer_name TEXT NOT NULL,
            appeal_deadline_days INTEGER,
            contact TEXT,
            guidelines TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_payer_name ON payer_guidelines(payer_name);
        """
    )
    conn.commit()


def list_payer_guidelines(*, limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, payer_name, appeal_deadline_days, contact, guidelines, updated_at "
            "FROM payer_guidelines ORDER BY payer_name COLLATE NOCASE ASC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [_payer_row(r) for r in rows]


def upsert_payer_guideline(payload: dict[str, Any] | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    name = str(body.get("payerName") or body.get("payer_name") or "").strip()[:120]
    if not name:
        return {"ok": False, "error": "payerName required"}
    contact = str(body.get("contact") or "").strip()[:200] or None
    guidelines = str(body.get("guidelines") or "").strip()[:4000]
    deadline = body.get("appealDeadlineDays")
    if deadline is None:
        deadline = body.get("appeal_deadline_days")
    try:
        deadline_i = int(deadline) if deadline is not None and str(deadline).strip() != "" else None
    except (TypeError, ValueError):
        deadline_i = None
    now = _utc_now()
    row_id = body.get("id")
    with connect() as conn:
        if row_id is not None:
            conn.execute(
                "UPDATE payer_guidelines SET payer_name=?, appeal_deadline_days=?, contact=?, "
                "guidelines=?, updated_at=? WHERE id=?",
                (name, deadline_i, contact, guidelines, now, int(row_id)),
            )
            rid = int(row_id)
        else:
            cur = conn.execute(
                "INSERT INTO payer_guidelines (payer_name, appeal_deadline_days, contact, guidelines, updated_at) "
                "VALUES (?,?,?,?,?)",
                (name, deadline_i, contact, guidelines, now),
            )
            rid = int(cur.lastrowid)
        conn.commit()
        row = conn.execute(
            "SELECT id, payer_name, appeal_deadline_days, contact, guidelines, updated_at "
            "FROM payer_guidelines WHERE id=?",
            (rid,),
        ).fetchone()
    return {"ok": True, "payer": _payer_row(row), "localOnly": True}


def _payer_row(r: sqlite3.Row | None) -> dict[str, Any]:
    if r is None:
        return {}
    return {
        "id": r["id"],
        "payerName": r["payer_name"],
        "appealDeadlineDays": r["appeal_deadline_days"],
        "contact": r["contact"],
        "guidelines": r["guidelines"],
        "updatedAt": r["updated_at"],
    }


def list_tax_payments(*, limit: int = 40) -> list[dict[str, Any]]:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tax_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quarter TEXT NOT NULL,
                amount REAL,
                paid_at TEXT,
                note TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        rows = conn.execute(
            "SELECT id, quarter, amount, paid_at, note, updated_at FROM tax_payments "
            "ORDER BY updated_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "quarter": r["quarter"],
            "amount": r["amount"],
            "paidAt": r["paid_at"],
            "note": r["note"],
            "updatedAt": r["updated_at"],
        }
        for r in rows
    ]


def upsert_tax_payment(payload: dict[str, Any] | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    quarter = str(body.get("quarter") or body.get("label") or "").strip()[:40]
    if not quarter:
        return {"ok": False, "error": "quarter required"}
    now = _utc_now()
    amt = body.get("amount")
    try:
        amt_f = float(amt) if amt is not None and str(amt).strip() != "" else None
    except (TypeError, ValueError):
        amt_f = None
    note = str(body.get("note") or "").strip()[:500] or None
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tax_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quarter TEXT NOT NULL,
                amount REAL,
                paid_at TEXT,
                note TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO tax_payments (quarter, amount, paid_at, note, updated_at) VALUES (?,?,?,?,?)",
            (quarter, amt_f, now, note, now),
        )
        conn.commit()
    return {"ok": True, "quarter": quarter, "localOnly": True}


def list_collection_notes(*, limit: int = 200) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, claim_id, patient_initials, status, note, follow_up, updated_at "
            "FROM collection_notes ORDER BY updated_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def upsert_collection_note(payload: dict[str, Any] | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    claim_id = str(body.get("claimId") or body.get("claim_id") or "").strip()
    if not claim_id:
        return {"ok": False, "error": "claimId required"}
    status = str(body.get("status") or "open").strip().lower() or "open"
    allowed = {"open", "called", "promised", "disputed", "closed"}
    if status not in allowed:
        status = "open"
    note = str(body.get("note") or "").strip()[:2000]
    follow = str(body.get("followUp") or body.get("follow_up") or "").strip()[:40] or None
    initials = str(body.get("patientInitials") or body.get("patient_initials") or "").strip()[:16] or None
    now = _utc_now()
    note_id = body.get("id")
    with connect() as conn:
        if note_id is not None:
            conn.execute(
                "UPDATE collection_notes SET claim_id=?, patient_initials=?, status=?, note=?, "
                "follow_up=?, updated_at=? WHERE id=?",
                (claim_id, initials, status, note, follow, now, int(note_id)),
            )
            row_id = int(note_id)
        else:
            cur = conn.execute(
                "INSERT INTO collection_notes (claim_id, patient_initials, status, note, follow_up, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (claim_id, initials, status, note, follow, now),
            )
            row_id = int(cur.lastrowid)
        conn.commit()
        row = conn.execute(
            "SELECT id, claim_id, patient_initials, status, note, follow_up, updated_at "
            "FROM collection_notes WHERE id=?",
            (row_id,),
        ).fetchone()
    return {"ok": True, "note": _row_to_dict(row), "localOnly": True}


def list_tasks(*, include_done: bool = True, limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        if include_done:
            rows = conn.execute(
                "SELECT id, title, assignee, due_date, done, created_at, updated_at "
                "FROM office_tasks ORDER BY done ASC, due_date IS NULL, due_date ASC, id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, assignee, due_date, done, created_at, updated_at "
                "FROM office_tasks WHERE done=0 ORDER BY due_date IS NULL, due_date ASC, id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
    return [_task_row(r) for r in rows]


def upsert_task(payload: dict[str, Any] | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    title = str(body.get("title") or "").strip()[:200]
    if not title and body.get("id") is None:
        return {"ok": False, "error": "title required"}
    assignee = str(body.get("assignee") or "").strip()[:80] or None
    due = str(body.get("dueDate") or body.get("due_date") or "").strip()[:40] or None
    done = 1 if body.get("done") in (True, 1, "1", "true", "yes") else 0
    now = _utc_now()
    task_id = body.get("id")
    with connect() as conn:
        if task_id is not None:
            if title:
                conn.execute(
                    "UPDATE office_tasks SET title=?, assignee=?, due_date=?, done=?, updated_at=? WHERE id=?",
                    (title, assignee, due, done, now, int(task_id)),
                )
            else:
                conn.execute(
                    "UPDATE office_tasks SET assignee=?, due_date=?, done=?, updated_at=? WHERE id=?",
                    (assignee, due, done, now, int(task_id)),
                )
            row_id = int(task_id)
        else:
            cur = conn.execute(
                "INSERT INTO office_tasks (title, assignee, due_date, done, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (title, assignee, due, done, now, now),
            )
            row_id = int(cur.lastrowid)
        conn.commit()
        row = conn.execute(
            "SELECT id, title, assignee, due_date, done, created_at, updated_at FROM office_tasks WHERE id=?",
            (row_id,),
        ).fetchone()
    return {"ok": True, "task": _task_row(row), "localOnly": True}


def record_huddle(priorities: list[str], *, note: str | None = None) -> dict[str, Any]:
    import json

    clean = [str(p).strip() for p in (priorities or []) if str(p).strip()][:12]
    now = _utc_now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO huddle_history (priorities_json, note, created_at) VALUES (?,?,?)",
            (json.dumps(clean), (note or "")[:500] or None, now),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
    return {"ok": True, "id": row_id, "createdAt": now, "count": len(clean), "localOnly": True}


def list_huddle_history(*, limit: int = 10) -> list[dict[str, Any]]:
    import json

    with connect() as conn:
        rows = conn.execute(
            "SELECT id, priorities_json, note, created_at FROM huddle_history ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            pri = json.loads(r["priorities_json"] or "[]")
        except Exception:
            pri = []
        out.append(
            {
                "id": r["id"],
                "priorities": pri if isinstance(pri, list) else [],
                "note": r["note"],
                "createdAt": r["created_at"],
            }
        )
    return out


def _row_to_dict(r: sqlite3.Row | None) -> dict[str, Any]:
    if r is None:
        return {}
    return {
        "id": r["id"],
        "claimId": r["claim_id"],
        "patientInitials": r["patient_initials"],
        "status": r["status"],
        "note": r["note"],
        "followUp": r["follow_up"],
        "updatedAt": r["updated_at"],
    }


def _task_row(r: sqlite3.Row | None) -> dict[str, Any]:
    if r is None:
        return {}
    return {
        "id": r["id"],
        "title": r["title"],
        "assignee": r["assignee"],
        "dueDate": r["due_date"],
        "done": bool(r["done"]),
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
    }
