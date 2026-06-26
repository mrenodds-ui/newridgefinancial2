from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from app.config_runtime import get_env_setting
from app.hal.safety import resolve_within_hal_allowed_base


def get_hal_storage_path() -> Path:
    configured = get_env_setting("HAL_SQLITE_PATH", "").strip()
    candidate = Path(configured) if configured else Path("hal_local.sqlite3")
    return resolve_within_hal_allowed_base(candidate, label="HAL SQLite storage path")


@contextmanager
def hal_connection() -> Iterator[sqlite3.Connection]:
    database_path = get_hal_storage_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        initialize_hal_storage(connection)
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_hal_storage(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS hal_audits (
            audit_id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            actor TEXT NOT NULL,
            mode TEXT NOT NULL,
            sanitized_question TEXT NOT NULL,
            retrieval_ids_json TEXT NOT NULL,
            response_summary TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS hal_autonomy_runs (
            run_id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            actor TEXT NOT NULL,
            objective TEXT NOT NULL,
            sanitized_objective TEXT NOT NULL,
            status TEXT NOT NULL,
            max_steps INTEGER NOT NULL,
            current_step INTEGER NOT NULL,
            sandbox_mode TEXT NOT NULL,
            working_directory TEXT NOT NULL,
            loop_mode TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            activity_json TEXT NOT NULL,
            completion_summary TEXT
        )
        """
    )
    _ensure_hal_conversation_state_schema(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS hal_accounting_posting_queue (
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
    _ensure_column(connection, "hal_accounting_posting_queue", "reviewer_actor", "TEXT")
    _ensure_column(connection, "hal_accounting_posting_queue", "reviewed_at_utc", "TEXT")
    _ensure_column(connection, "hal_accounting_posting_queue", "review_note", "TEXT")
    _ensure_column(connection, "hal_accounting_posting_queue", "enqueue_mode", "TEXT")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS hal_softdent_record_audits (
            event_id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            actor TEXT NOT NULL,
            roles_used_json TEXT NOT NULL,
            workflow_reason TEXT NOT NULL,
            response_mode TEXT NOT NULL,
            patient_ref_hash TEXT,
            chart_ref_hash TEXT,
            patient_display_name TEXT,
            claim_ids_json TEXT NOT NULL,
            clinical_note_ids_json TEXT NOT NULL,
            ledger_record_ids_json TEXT NOT NULL,
            source_adapter TEXT NOT NULL,
            source_metadata_json TEXT NOT NULL,
            missing_data_codes_json TEXT NOT NULL,
            external_action_performed INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def _ensure_hal_conversation_state_schema(connection: sqlite3.Connection) -> None:
    columns = [
        row["name"]
        for row in connection.execute("PRAGMA table_info(hal_conversation_state)").fetchall()
    ]
    if not columns:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS hal_conversation_state (
                actor TEXT NOT NULL,
                session_id TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (actor, session_id)
            )
            """
        )
        return

    if "session_id" in columns:
        return

    connection.execute("ALTER TABLE hal_conversation_state RENAME TO hal_conversation_state_legacy")
    connection.execute(
        """
        CREATE TABLE hal_conversation_state (
            actor TEXT NOT NULL,
            session_id TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            state_json TEXT NOT NULL,
            PRIMARY KEY (actor, session_id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO hal_conversation_state (actor, session_id, updated_at_utc, state_json)
        -- Legacy rows were keyed only by actor, so preserve that compatibility key
        -- for callers that still normalize missing session_id to the actor name.
        SELECT actor, actor, updated_at_utc, state_json
        FROM hal_conversation_state_legacy
        """
    )
    connection.execute("DROP TABLE hal_conversation_state_legacy")


def _ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, column_definition: str) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in existing_columns:
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def insert_hal_audit(entry: dict[str, Any]) -> None:
    with hal_connection() as connection:
        connection.execute(
            """
            INSERT INTO hal_audits (
                audit_id,
                created_at_utc,
                actor,
                mode,
                sanitized_question,
                retrieval_ids_json,
                response_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["audit_id"],
                entry["created_at_utc"],
                entry["actor"],
                entry["mode"],
                entry["sanitized_question"],
                json.dumps(entry["retrieval_ids"]),
                entry["response_summary"],
            ),
        )


def get_recent_hal_audits(limit: int = 20) -> list[dict[str, Any]]:
    bounded_limit = max(1, limit)
    with hal_connection() as connection:
        rows = connection.execute(
            """
            SELECT audit_id, created_at_utc, actor, mode, sanitized_question, retrieval_ids_json, response_summary
            FROM hal_audits
            ORDER BY created_at_utc DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()
    return [_map_hal_audit_row(row) for row in rows]


def get_hal_audit(audit_id: str) -> dict[str, Any] | None:
    with hal_connection() as connection:
        row = connection.execute(
            """
            SELECT audit_id, created_at_utc, actor, mode, sanitized_question, retrieval_ids_json, response_summary
            FROM hal_audits
            WHERE audit_id = ?
            """,
            (audit_id,),
        ).fetchone()
    if row is None:
        return None
    return _map_hal_audit_row(row)


def insert_softdent_record_audit(entry: dict[str, Any]) -> None:
    with hal_connection() as connection:
        connection.execute(
            """
            INSERT INTO hal_softdent_record_audits (
                event_id,
                created_at_utc,
                actor,
                roles_used_json,
                workflow_reason,
                response_mode,
                patient_ref_hash,
                chart_ref_hash,
                patient_display_name,
                claim_ids_json,
                clinical_note_ids_json,
                ledger_record_ids_json,
                source_adapter,
                source_metadata_json,
                missing_data_codes_json,
                external_action_performed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["event_id"],
                entry["created_at_utc"],
                entry["actor"],
                json.dumps(entry.get("roles_used", [])),
                entry["workflow_reason"],
                entry["response_mode"],
                entry.get("patient_ref_hash"),
                entry.get("chart_ref_hash"),
                entry.get("patient_display_name"),
                json.dumps(entry.get("claim_ids", [])),
                json.dumps(entry.get("clinical_note_ids", [])),
                json.dumps(entry.get("ledger_record_ids", [])),
                entry.get("source_adapter", "exports"),
                json.dumps(entry.get("source_metadata", [])),
                json.dumps(entry.get("missing_data_codes", [])),
                1 if entry.get("external_action_performed") else 0,
            ),
        )


def get_recent_softdent_record_audits(limit: int = 20) -> list[dict[str, Any]]:
    bounded_limit = max(1, limit)
    with hal_connection() as connection:
        rows = connection.execute(
            """
            SELECT event_id, created_at_utc, actor, roles_used_json, workflow_reason, response_mode,
                   patient_ref_hash, chart_ref_hash, patient_display_name, claim_ids_json,
                   clinical_note_ids_json, ledger_record_ids_json, source_adapter,
                   source_metadata_json, missing_data_codes_json, external_action_performed
            FROM hal_softdent_record_audits
            ORDER BY created_at_utc DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()
    return [_map_softdent_record_audit_row(row) for row in rows]


def get_softdent_record_audit(event_id: str) -> dict[str, Any] | None:
    with hal_connection() as connection:
        row = connection.execute(
            """
            SELECT event_id, created_at_utc, actor, roles_used_json, workflow_reason, response_mode,
                   patient_ref_hash, chart_ref_hash, patient_display_name, claim_ids_json,
                   clinical_note_ids_json, ledger_record_ids_json, source_adapter,
                   source_metadata_json, missing_data_codes_json, external_action_performed
            FROM hal_softdent_record_audits
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
    if row is None:
        return None
    return _map_softdent_record_audit_row(row)


def _map_softdent_record_audit_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "created_at_utc": row["created_at_utc"],
        "actor": row["actor"],
        "roles_used": json.loads(row["roles_used_json"]),
        "workflow_reason": row["workflow_reason"],
        "response_mode": row["response_mode"],
        "patient_ref_hash": row["patient_ref_hash"],
        "chart_ref_hash": row["chart_ref_hash"],
        "patient_display_name": row["patient_display_name"],
        "claim_ids": json.loads(row["claim_ids_json"]),
        "clinical_note_ids": json.loads(row["clinical_note_ids_json"]),
        "ledger_record_ids": json.loads(row["ledger_record_ids_json"]),
        "source_adapter": row["source_adapter"],
        "source_metadata": json.loads(row["source_metadata_json"]),
        "missing_data_codes": json.loads(row["missing_data_codes_json"]),
        "external_action_performed": bool(row["external_action_performed"]),
    }


def _map_hal_audit_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "audit_id": row["audit_id"],
        "created_at_utc": row["created_at_utc"],
        "actor": row["actor"],
        "mode": row["mode"],
        "sanitized_question": row["sanitized_question"],
        "retrieval_ids": json.loads(row["retrieval_ids_json"]),
        "response_summary": row["response_summary"],
    }


def save_hal_conversation_state(*, actor: str, session_id: str, state: dict[str, Any]) -> None:
    with hal_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO hal_conversation_state (
                actor,
                session_id,
                updated_at_utc,
                state_json
            ) VALUES (?, ?, ?, ?)
            """,
            (
                actor,
                session_id,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(state),
            ),
        )


def get_hal_conversation_state(actor: str, session_id: str) -> dict[str, Any] | None:
    with hal_connection() as connection:
        row = connection.execute(
            """
            SELECT actor, session_id, state_json
            FROM hal_conversation_state
            WHERE actor = ? AND session_id = ?
            """,
            (actor, session_id),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["state_json"] or "{}")


def save_hal_autonomy_run(entry: dict[str, Any]) -> None:
    with hal_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO hal_autonomy_runs (
                run_id,
                created_at_utc,
                updated_at_utc,
                actor,
                objective,
                sanitized_objective,
                status,
                max_steps,
                current_step,
                sandbox_mode,
                working_directory,
                loop_mode,
                plan_json,
                activity_json,
                completion_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["run_id"],
                entry["created_at_utc"],
                entry["updated_at_utc"],
                entry["actor"],
                entry["objective"],
                entry["sanitized_objective"],
                entry["status"],
                entry["max_steps"],
                entry["current_step"],
                entry["sandbox_mode"],
                entry["working_directory"],
                entry["loop_mode"],
                json.dumps(entry.get("plan", [])),
                json.dumps(entry.get("activity", [])),
                entry.get("completion_summary"),
            ),
        )


def get_hal_autonomy_run(run_id: str) -> dict[str, Any] | None:
    with hal_connection() as connection:
        row = connection.execute(
            """
            SELECT
                run_id,
                created_at_utc,
                updated_at_utc,
                actor,
                objective,
                sanitized_objective,
                status,
                max_steps,
                current_step,
                sandbox_mode,
                working_directory,
                loop_mode,
                plan_json,
                activity_json,
                completion_summary
            FROM hal_autonomy_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return _map_hal_autonomy_run_row(row)


def get_recent_hal_autonomy_runs(limit: int = 20) -> list[dict[str, Any]]:
    bounded_limit = max(1, limit)
    with hal_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                run_id,
                created_at_utc,
                updated_at_utc,
                actor,
                objective,
                sanitized_objective,
                status,
                max_steps,
                current_step,
                sandbox_mode,
                working_directory,
                loop_mode,
                plan_json,
                activity_json,
                completion_summary
            FROM hal_autonomy_runs
            ORDER BY updated_at_utc DESC, run_id DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()
    return [_map_hal_autonomy_run_row(row) for row in rows]


def _map_hal_autonomy_run_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "created_at_utc": row["created_at_utc"],
        "updated_at_utc": row["updated_at_utc"],
        "actor": row["actor"],
        "objective": row["objective"],
        "sanitized_objective": row["sanitized_objective"],
        "status": row["status"],
        "max_steps": int(row["max_steps"] or 0),
        "current_step": int(row["current_step"] or 0),
        "sandbox_mode": row["sandbox_mode"],
        "working_directory": row["working_directory"],
        "loop_mode": row["loop_mode"],
        "plan": json.loads(row["plan_json"] or "[]"),
        "activity": json.loads(row["activity_json"] or "[]"),
        "completion_summary": row["completion_summary"],
    }


def insert_accounting_posting_queue_entry(entry: dict[str, Any]) -> None:
    with hal_connection() as connection:
        connection.execute(
            """
            INSERT INTO hal_accounting_posting_queue (
                queue_id,
                created_at_utc,
                actor,
                target_system,
                status,
                description,
                transaction_date,
                accounting_period,
                amount,
                transaction_type,
                source_audit_id,
                enqueue_mode,
                lines_json,
                validation_json,
                reviewer_actor,
                reviewed_at_utc,
                review_note
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


def get_accounting_posting_queue_entry(queue_id: str) -> dict[str, Any] | None:
    with hal_connection() as connection:
        row = connection.execute(
            """
            SELECT
                queue_id,
                created_at_utc,
                actor,
                target_system,
                status,
                description,
                transaction_date,
                accounting_period,
                amount,
                transaction_type,
                source_audit_id,
                enqueue_mode,
                lines_json,
                validation_json,
                reviewer_actor,
                reviewed_at_utc,
                review_note
            FROM hal_accounting_posting_queue
            WHERE queue_id = ?
            """,
            (queue_id,),
        ).fetchone()
    if row is None:
        return None
    return _map_accounting_posting_queue_row(row)


def update_accounting_posting_queue_review(
    *,
    queue_id: str,
    status: str,
    reviewer_actor: str,
    reviewed_at_utc: str,
    review_note: str | None,
) -> None:
    with hal_connection() as connection:
        connection.execute(
            """
            UPDATE hal_accounting_posting_queue
            SET status = ?, reviewer_actor = ?, reviewed_at_utc = ?, review_note = ?
            WHERE queue_id = ?
            """,
            (status, reviewer_actor, reviewed_at_utc, review_note, queue_id),
        )


def get_recent_accounting_posting_queue_entries(*, limit: int = 20, cursor: str | None = None, status: str | None = None) -> tuple[list[dict[str, Any]], int, str | None]:
    bounded_limit = max(1, limit)
    base_where_clause = ""
    base_parameters: list[object] = []
    if status is not None:
        base_where_clause = "WHERE status = ?"
        base_parameters.append(status)
    where_clause = base_where_clause
    parameters = list(base_parameters)
    cursor_created_at: str | None = None
    cursor_queue_id: str | None = None
    items_before_page = 0
    if cursor:
        cursor_created_at, cursor_queue_id = _parse_accounting_posting_queue_cursor(cursor)
        cursor_clause = "(created_at_utc < ? OR (created_at_utc = ? AND queue_id < ?))"
        if where_clause:
            where_clause = f"{where_clause} AND {cursor_clause}"
        else:
            where_clause = f"WHERE {cursor_clause}"
        parameters.extend([cursor_created_at, cursor_created_at, cursor_queue_id])
    with hal_connection() as connection:
        count_row = connection.execute(
            f"""
            SELECT COUNT(*) AS total_count
            FROM hal_accounting_posting_queue
            {base_where_clause}
            """,
            tuple(base_parameters),
        ).fetchone()
        if cursor_created_at and cursor_queue_id:
            before_row = connection.execute(
                f"""
                SELECT COUNT(*) AS items_before_page
                FROM hal_accounting_posting_queue
                {base_where_clause}
                {"AND" if base_where_clause else "WHERE"} (created_at_utc > ? OR (created_at_utc = ? AND queue_id >= ?))
                """,
                (*base_parameters, cursor_created_at, cursor_created_at, cursor_queue_id),
            ).fetchone()
            items_before_page = int(before_row["items_before_page"] or 0)
        rows = connection.execute(
            f"""
            SELECT
                queue_id,
                created_at_utc,
                actor,
                target_system,
                status,
                description,
                transaction_date,
                accounting_period,
                amount,
                transaction_type,
                source_audit_id,
                enqueue_mode,
                lines_json,
                validation_json,
                reviewer_actor,
                reviewed_at_utc,
                review_note
            FROM hal_accounting_posting_queue
            {where_clause}
            ORDER BY created_at_utc DESC, queue_id DESC
            LIMIT ?
            """,
            (*parameters, bounded_limit + 1),
        ).fetchall()
    has_more = len(rows) > bounded_limit
    page_rows = rows[:bounded_limit]
    next_cursor = None
    if has_more and page_rows:
        last_row = page_rows[-1]
        next_cursor = _build_accounting_posting_queue_cursor(last_row["created_at_utc"], last_row["queue_id"])
    total_count = int(count_row["total_count"] or 0)
    range_start = items_before_page + 1 if page_rows else 0
    range_end = items_before_page + len(page_rows)
    return [_map_accounting_posting_queue_row(row) for row in page_rows], total_count, next_cursor, range_start, range_end


def get_recent_accounting_posting_queue_activity(limit: int = 10) -> list[dict[str, Any]]:
    bounded_limit = max(1, limit)
    with hal_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                queue_id,
                created_at_utc,
                actor,
                target_system,
                status,
                description,
                transaction_date,
                accounting_period,
                amount,
                transaction_type,
                source_audit_id,
                enqueue_mode,
                reviewer_actor,
                reviewed_at_utc,
                review_note
            FROM hal_accounting_posting_queue
            ORDER BY created_at_utc DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()
    return [_map_accounting_posting_queue_activity_row(row) for row in rows]


def get_accounting_posting_queue_metrics() -> dict[str, int]:
    with hal_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN status = 'pending_review' THEN 1 ELSE 0 END) AS pending_review_count,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved_count,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected_count
            FROM hal_accounting_posting_queue
            """
        ).fetchone()
    return {
        "total_count": int(row["total_count"] or 0),
        "pending_review_count": int(row["pending_review_count"] or 0),
        "approved_count": int(row["approved_count"] or 0),
        "rejected_count": int(row["rejected_count"] or 0),
    }


def _map_accounting_posting_queue_row(row: sqlite3.Row) -> dict[str, Any]:
    status = row["status"]
    return {
        "queue_id": row["queue_id"],
        "created_at_utc": row["created_at_utc"],
        "actor": row["actor"],
        "target_system": row["target_system"],
        "status": status,
        "description": row["description"],
        "transaction_date": row["transaction_date"],
        "accounting_period": row["accounting_period"],
        "amount": row["amount"],
        "transaction_type": row["transaction_type"],
        "source_audit_id": row["source_audit_id"],
        "enqueue_mode": row["enqueue_mode"],
        "lines": json.loads(row["lines_json"]),
        "validation": json.loads(row["validation_json"]),
        "reviewer_actor": row["reviewer_actor"],
        "reviewed_at_utc": row["reviewed_at_utc"],
        "review_note": row["review_note"],
        "review_required": status != "approved",
    }


def _map_accounting_posting_queue_activity_row(row: sqlite3.Row) -> dict[str, Any]:
    status = row["status"]
    return {
        "queue_id": row["queue_id"],
        "created_at_utc": row["created_at_utc"],
        "actor": row["actor"],
        "target_system": row["target_system"],
        "status": status,
        "description": row["description"],
        "transaction_date": row["transaction_date"],
        "accounting_period": row["accounting_period"],
        "amount": row["amount"],
        "transaction_type": row["transaction_type"],
        "source_audit_id": row["source_audit_id"],
        "enqueue_mode": row["enqueue_mode"],
        "reviewer_actor": row["reviewer_actor"],
        "reviewed_at_utc": row["reviewed_at_utc"],
        "review_note": row["review_note"],
        "review_required": status != "approved",
    }


def _build_accounting_posting_queue_cursor(created_at_utc: str, queue_id: str) -> str:
    return f"{created_at_utc}|{queue_id}"


def _parse_accounting_posting_queue_cursor(cursor: str) -> tuple[str, str]:
    try:
        created_at_utc, queue_id = cursor.split("|", 1)
    except ValueError as exc:
        raise ValueError("Posting queue cursor is invalid.") from exc
    if not created_at_utc or not queue_id:
        raise ValueError("Posting queue cursor is invalid.")
    return created_at_utc, queue_id