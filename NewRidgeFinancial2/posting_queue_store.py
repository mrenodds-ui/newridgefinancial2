"""SQLite journal posting queue for NR2 desktop (human review only — never posts to QuickBooks)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POSTING_QUEUE_STATUS_PENDING_REVIEW = "pending_review"
POSTING_QUEUE_STATUS_APPROVED = "approved"
POSTING_QUEUE_STATUS_REJECTED = "rejected"
ENQUEUE_MODE_MANUAL_REVIEW_QUEUE = "manual_review_queue"
ENQUEUE_MODE_AUTO_VALIDATED_AI = "auto_validated_ai"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_posting_queue_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nr2_accounting_posting_queue (
            queue_id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            actor TEXT NOT NULL,
            target_system TEXT NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            accounting_period TEXT NOT NULL,
            amount REAL NOT NULL,
            transaction_type TEXT,
            source_audit_id TEXT NOT NULL,
            enqueue_mode TEXT,
            lines_json TEXT NOT NULL,
            validation_json TEXT NOT NULL,
            reviewer_actor TEXT,
            reviewed_at_utc TEXT,
            review_note TEXT
        )
        """
    )


def _dict_row_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def _map_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "queueId": row["queue_id"],
        "createdAtUtc": row["created_at_utc"],
        "actor": row["actor"],
        "targetSystem": row["target_system"],
        "status": row["status"],
        "description": row["description"],
        "transactionDate": row["transaction_date"],
        "accountingPeriod": row["accounting_period"],
        "amount": row["amount"],
        "transactionType": row["transaction_type"],
        "sourceAuditId": row["source_audit_id"],
        "enqueueMode": row["enqueue_mode"],
        "lines": json.loads(row["lines_json"]),
        "validation": json.loads(row["validation_json"]),
        "reviewerActor": row["reviewer_actor"],
        "reviewedAtUtc": row["reviewed_at_utc"],
        "reviewNote": row["review_note"],
    }


class PostingQueueStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        from nr2_db_crypto import open_encrypted_db

        conn = open_encrypted_db(Path(self.db_path))
        conn.row_factory = _dict_row_factory
        init_posting_queue_schema(conn)
        return conn

    def insert_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO nr2_accounting_posting_queue (
                    queue_id, created_at_utc, actor, target_system, status, description,
                    transaction_date, accounting_period, amount, transaction_type,
                    source_audit_id, enqueue_mode, lines_json, validation_json,
                    reviewer_actor, reviewed_at_utc, review_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["queue_id"],
                    entry["created_at_utc"],
                    entry["actor"],
                    entry["target_system"],
                    entry["status"],
                    entry["description"],
                    entry["transaction_date"],
                    entry["accounting_period"],
                    entry["amount"],
                    entry.get("transaction_type"),
                    entry["source_audit_id"],
                    entry.get("enqueue_mode"),
                    json.dumps(entry["lines"]),
                    json.dumps(entry["validation"]),
                    entry.get("reviewer_actor"),
                    entry.get("reviewed_at_utc"),
                    entry.get("review_note"),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_entry(str(entry["queue_id"])) or {}

    def get_entry(self, queue_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM nr2_accounting_posting_queue WHERE queue_id = ?",
                (queue_id,),
            ).fetchone()
        finally:
            conn.close()
        return _map_row(row) if row else None

    def list_entries(self, *, limit: int = 20, status: str | None = None) -> list[dict[str, Any]]:
        bounded = max(1, min(limit, 100))
        query = "SELECT * FROM nr2_accounting_posting_queue"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at_utc DESC, queue_id DESC LIMIT ?"
        params.append(bounded)
        conn = self._connect()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return [_map_row(row) for row in rows]

    def metrics(self) -> dict[str, int]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM nr2_accounting_posting_queue
                GROUP BY status
                """
            ).fetchall()
        finally:
            conn.close()
        out = {"pendingReview": 0, "approved": 0, "rejected": 0, "total": 0}
        for row in rows:
            status = str(row["status"])
            count = int(row["count"])
            out["total"] += count
            if status == POSTING_QUEUE_STATUS_PENDING_REVIEW:
                out["pendingReview"] = count
            elif status == POSTING_QUEUE_STATUS_APPROVED:
                out["approved"] = count
            elif status == POSTING_QUEUE_STATUS_REJECTED:
                out["rejected"] = count
        return out

    def review_entry(self, *, queue_id: str, action: str, reviewer_actor: str, review_note: str | None = None) -> dict[str, Any]:
        status = POSTING_QUEUE_STATUS_APPROVED if action == "approved" else POSTING_QUEUE_STATUS_REJECTED
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE nr2_accounting_posting_queue
                SET status = ?, reviewer_actor = ?, reviewed_at_utc = ?, review_note = ?
                WHERE queue_id = ?
                """,
                (status, reviewer_actor, _utc_now(), review_note, queue_id),
            )
            conn.commit()
        finally:
            conn.close()
        entry = self.get_entry(queue_id)
        if entry is None:
            raise ValueError(f"Posting queue entry not found: {queue_id}")
        return entry


def new_queue_id() -> str:
    return f"pq-{uuid.uuid4().hex[:12]}"
