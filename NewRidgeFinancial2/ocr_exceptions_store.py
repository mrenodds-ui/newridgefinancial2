"""OCR exception queue — Moonshot Sprint 3."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

OCR_EXCEPTIONS_KEY = "nr2:ocr:exceptions"


def init_ocr_exceptions_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_exceptions (
            id TEXT PRIMARY KEY,
            source_doc TEXT NOT NULL,
            confidence_label TEXT,
            captured_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            preview TEXT,
            assigned_to TEXT,
            resolution_notes TEXT
        )
        """
    )


def upsert_exception(conn, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO ocr_exceptions (id, source_doc, confidence_label, captured_at, status, preview, assigned_to)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            confidence_label = excluded.confidence_label,
            preview = excluded.preview,
            status = CASE WHEN ocr_exceptions.status = 'resolved' THEN ocr_exceptions.status ELSE excluded.status END
        """,
        (
            str(row.get("id") or ""),
            str(row.get("source_doc") or ""),
            str(row.get("confidence_label") or ""),
            str(row.get("captured_at") or datetime.now(timezone.utc).isoformat()),
            str(row.get("status") or "pending"),
            str(row.get("preview") or "")[:500],
            row.get("assigned_to"),
        ),
    )


def list_exceptions(conn, *, status: str | None = "pending", limit: int = 200) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute(
            "SELECT id, source_doc, confidence_label, captured_at, status, preview, assigned_to, resolution_notes "
            "FROM ocr_exceptions WHERE status = ? ORDER BY captured_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, source_doc, confidence_label, captured_at, status, preview, assigned_to, resolution_notes "
            "FROM ocr_exceptions ORDER BY captured_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "sourceDoc": r[1],
            "confidenceLabel": r[2],
            "capturedAt": r[3],
            "status": r[4],
            "preview": r[5],
            "assignedTo": r[6],
            "resolutionNotes": r[7],
        }
        for r in rows
    ]


def resolve_exception(conn, exc_id: str, *, action: str, notes: str = "") -> dict[str, Any]:
    status = "resolved" if action == "enqueue" else "discarded" if action == "discard" else "resolved"
    conn.execute(
        "UPDATE ocr_exceptions SET status = ?, resolution_notes = ? WHERE id = ?",
        (status, notes, exc_id),
    )
    row = conn.execute(
        "SELECT id, source_doc, confidence_label, captured_at, status, preview FROM ocr_exceptions WHERE id = ?",
        (exc_id,),
    ).fetchone()
    if not row:
        return {"ok": False, "error": "not_found"}
    return {
        "ok": True,
        "item": {
            "id": row[0],
            "sourceDoc": row[1],
            "confidenceLabel": row[2],
            "capturedAt": row[3],
            "status": row[4],
            "preview": row[5],
        },
    }
