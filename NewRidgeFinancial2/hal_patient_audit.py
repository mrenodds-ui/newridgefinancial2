"""HAL patient-query audit — Moonshot dossier + Mon–Thu consults (2026-07-11).

Uses a local SQLite audit DB under app_data/nr2/audit/ (not SoftDent).
Also mirrors events into the existing JSONL read/mutation audit chain.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

_AUDIT_DIR = Path(__file__).resolve().parent.parent / "app_data" / "nr2" / "audit"
AUDIT_DB = _AUDIT_DIR / "hal_patient_audit.db"


def _conn() -> sqlite3.Connection:
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(AUDIT_DB))


def init_audit() -> None:
    conn = _conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hal_patient_query_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL,
                patient_hash TEXT NOT NULL,
                query_type TEXT,
                timestamp REAL,
                session_id TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hal_patient_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                patient_hash TEXT NOT NULL,
                action TEXT,
                tools_used TEXT,
                timestamp TEXT,
                ip TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def log_patient_query(
    staff_id: str,
    patient_id_or_hash: str,
    query_type: str,
    session_id: str = "",
) -> None:
    """Dossier MUST: log every patient-specific dossier request."""
    init_audit()
    from patient_dossier import patient_hash

    # Always store 4-char SHA256 hash — never raw SoftDent patient_id / name
    ph = patient_hash(patient_id_or_hash)

    conn = _conn()
    try:
        conn.execute(
            """
            INSERT INTO hal_patient_query_audit (staff_id, patient_hash, query_type, timestamp, session_id)
            VALUES (?,?,?,?,?)
            """,
            (str(staff_id or "Staff"), ph, str(query_type or "dossier"), time.time(), str(session_id or "")),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        from nr2_audit_log import append_audit_event, append_read_audit
        from nr2_rbac import current_role

        append_read_audit(
            token_fingerprint=str(session_id or staff_id or "anon")[:32],
            path="/api/apex/patient-dossier",
            role=current_role(),
            params={"patientHash": ph, "queryType": query_type},
        )
        append_audit_event(
            "patient_dossier_read",
            actor=str(staff_id or "Staff"),
            detail={"patientHash": ph, "queryType": query_type, "sessionId": session_id},
            path="/api/apex/patient-dossier",
        )
    except Exception:
        pass


def log_hal_patient_action(
    *,
    user_id: str,
    patient_hash: str,
    action: str,
    tools_used: str = "[]",
    ip: str = "",
) -> None:
    """Mon–Thu MUST: audit context set / patient-specific HAL queries."""
    init_audit()
    from datetime import datetime, timezone

    conn = _conn()
    try:
        conn.execute(
            """
            INSERT INTO hal_patient_audit (user_id, patient_hash, action, tools_used, timestamp, ip)
            VALUES (?,?,?,?,?,?)
            """,
            (
                str(user_id or "Staff"),
                str(patient_hash or "——"),
                str(action or "query"),
                str(tools_used or "[]"),
                datetime.now(timezone.utc).isoformat(),
                str(ip or ""),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        from nr2_audit_log import append_audit_event

        append_audit_event(
            "hal_patient_context",
            actor=str(user_id or "Staff"),
            detail={"patientHash": patient_hash, "action": action, "toolsUsed": tools_used},
            path="/api/audit/hal-patient-context",
        )
    except Exception:
        pass


def recent_dossier_queries(*, limit: int = 20) -> list[dict[str, Any]]:
    init_audit()
    conn = _conn()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT staff_id, patient_hash, query_type, timestamp, session_id
            FROM hal_patient_query_audit
            ORDER BY id DESC LIMIT ?
            """,
            (max(1, min(int(limit or 20), 200)),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
