"""Workstation sidenotes bridge — local SQLite inbox for 8765 sidenotesProgram widget."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def init_sidenotes_local_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sidenotes_local (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            source TEXT NOT NULL,
            station TEXT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sidenotes_local_created ON sidenotes_local(created_at DESC)"
    )


def insert_sidenote_local(
    conn: sqlite3.Connection,
    *,
    text: str,
    source: str = "workstation",
    station: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    body = str(text or "").strip()
    if len(body) < 2:
        raise ValueError("sidenote text too short")
    if len(body) > 500:
        body = body[:500]
    note_id = uuid.uuid4().hex
    created = timestamp or datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO sidenotes_local (id, text, source, station, created_at, status)
        VALUES (?, ?, ?, ?, ?, 'open')
        """,
        (note_id, body, str(source or "workstation"), station, created),
    )
    return {
        "id": note_id,
        "text": body,
        "source": str(source or "workstation"),
        "station": station,
        "timestamp": created,
        "status": "open",
    }


def list_sidenotes_local(conn: sqlite3.Connection, *, limit: int = 48) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit or 48), 200))
    rows = conn.execute(
        """
        SELECT id, text, source, station, created_at, status
        FROM sidenotes_local
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (lim,),
    ).fetchall()
    return [
        {
            "id": row[0],
            "text": row[1],
            "source": row[2],
            "station": row[3],
            "timestamp": row[4],
            "status": row[5],
        }
        for row in rows
    ]
