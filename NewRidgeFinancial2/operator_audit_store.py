"""Operator audit log in SQLite — page/widget/action trail for solo practice."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def init_operator_audit_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operator_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            page_key TEXT,
            widget_key TEXT,
            action TEXT NOT NULL,
            session_hash TEXT,
            detail_json TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_operator_audit_ts ON operator_audit_log(timestamp DESC)"
    )


def _session_hash() -> str:
    try:
        from nr2_browser_security import session_fingerprint

        return str(session_fingerprint() or "")[:16]
    except Exception:
        import os

        seed = os.environ.get("NR2_AUDIT_SECRET") or os.environ.get("COMPUTERNAME") or "nr2"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def append_operator_audit(
    conn: sqlite3.Connection,
    *,
    action: str,
    page_key: str | None = None,
    widget_key: str | None = None,
    detail: dict[str, Any] | None = None,
    session_hash: str | None = None,
) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    row = {
        "timestamp": ts,
        "page_key": page_key,
        "widget_key": widget_key,
        "action": str(action or "unknown"),
        "session_hash": session_hash or _session_hash(),
        "detail_json": json.dumps(detail or {}, separators=(",", ":"), default=str),
    }
    cur = conn.execute(
        """
        INSERT INTO operator_audit_log (timestamp, page_key, widget_key, action, session_hash, detail_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            row["timestamp"],
            row["page_key"],
            row["widget_key"],
            row["action"],
            row["session_hash"],
            row["detail_json"],
        ),
    )
    row["id"] = int(cur.lastrowid or 0)
    return row


def read_operator_audit_tail(conn: sqlite3.Connection, *, limit: int = 100) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit or 100), 500))
    rows = conn.execute(
        """
        SELECT id, timestamp, page_key, widget_key, action, session_hash, detail_json
        FROM operator_audit_log
        ORDER BY id DESC
        LIMIT ?
        """,
        (lim,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        detail = {}
        try:
            detail = json.loads(row[6] or "{}")
        except json.JSONDecodeError:
            detail = {}
        out.append(
            {
                "id": row[0],
                "timestamp": row[1],
                "pageKey": row[2],
                "widgetKey": row[3],
                "action": row[4],
                "sessionHash": row[5],
                "detail": detail,
            }
        )
    return out
