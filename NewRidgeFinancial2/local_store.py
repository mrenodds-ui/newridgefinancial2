"""Local SQLite storage for NewRidgeFinancial 2.0 desktop app."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class LocalStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "nr2.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        from nr2_db_crypto import db_encryption_enabled, open_encrypted_db

        if db_encryption_enabled():
            conn = open_encrypted_db(self.db_path)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA wal_autocheckpoint=1000")
        conn.execute("PRAGMA secure_delete=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            from posting_queue_store import init_posting_queue_schema
            from ocr_exceptions_store import init_ocr_exceptions_schema
            from hal_employee_workflows import init_employee_workflow_schemas
            from operator_audit_store import init_operator_audit_schema
            from sidenotes_local_store import init_sidenotes_local_schema
            from website_leads_store import init_website_leads_schema

            init_posting_queue_schema(conn)
            init_ocr_exceptions_schema(conn)
            init_employee_workflow_schemas(conn)
            init_operator_audit_schema(conn)
            init_sidenotes_local_schema(conn)
            init_website_leads_schema(conn)

    def get(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
