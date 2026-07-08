"""SoftDent ODBC extract lane → sd_* SQLite tables (hal-10070).

When ``SOFTDENT_ODBC_DSN`` / ``NR2_SOFTDENT_ODBC_DSN`` is configured and optional
env SQL queries are present, rows are pulled via pyodbc. Otherwise (or on failure)
the JSON/daysheet/claims fallback lane populates the same tables from local exports.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_loader import softdent_import_dir
from quickbooks_monthly_sync import resolve_analytics_db

REPO_ROOT = Path(__file__).resolve().parent.parent

PAYMENT_PROCEDURE_PREFIXES = ("1200", "1400", "4000", "5000")
WRITEOFF_CODES = frozenset({"51", "52"})

SD_TABLES = (
    "sd_providers",
    "sd_patients",
    "sd_procedures",
    "sd_appointments",
    "sd_claims",
    "sd_payments",
    "sd_adjustments",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _env_path(name: str, default: Path | None = None) -> Path | None:
    configured = os.environ.get(name, "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve()
    return default.resolve() if default else None


def resolve_sd_sqlite_db() -> Path | None:
    fallback = _env_path("SOFTDENT_SQLITE_FALLBACK")
    if fallback and fallback.is_file():
        return fallback
    candidate = resolve_analytics_db()
    if candidate and candidate.is_file():
        return candidate
    configured = _env_path("NR2_FINANCIAL_ANALYTICS_DB")
    if configured:
        configured.parent.mkdir(parents=True, exist_ok=True)
        return configured
    return None


def odbc_dsn() -> str:
    return (
        os.environ.get("SOFTDENT_ODBC_DSN", "").strip()
        or os.environ.get("NR2_SOFTDENT_ODBC_DSN", "").strip()
    )


def odbc_configured() -> bool:
    return bool(odbc_dsn())


def consent_executor_enabled() -> bool:
    return os.environ.get("NR2_CONSENT_EXECUTOR", "0").strip().lower() in {"1", "true", "yes", "on"}


def ensure_sd_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sd_providers (
            provider_code TEXT NOT NULL,
            provider_name TEXT,
            practice_id TEXT NOT NULL DEFAULT '',
            extracted_at TEXT,
            PRIMARY KEY (practice_id, provider_code)
        );
        CREATE TABLE IF NOT EXISTS sd_patients (
            patient_id TEXT NOT NULL,
            patient_name TEXT,
            first_visit_date TEXT,
            last_visit_date TEXT,
            practice_id TEXT NOT NULL DEFAULT '',
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id)
        );
        CREATE TABLE IF NOT EXISTS sd_procedures (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL DEFAULT '',
            proc_date TEXT NOT NULL DEFAULT '',
            ada_code TEXT NOT NULL DEFAULT '',
            tooth TEXT NOT NULL DEFAULT '',
            surface TEXT NOT NULL DEFAULT '',
            provider_code TEXT NOT NULL DEFAULT '',
            description TEXT,
            production REAL,
            extracted_at TEXT,
            PRIMARY KEY (
                practice_id, patient_id, proc_date, ada_code, tooth, surface, provider_code
            )
        );
        CREATE TABLE IF NOT EXISTS sd_appointments (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL DEFAULT '',
            appt_date TEXT NOT NULL DEFAULT '',
            provider_code TEXT NOT NULL DEFAULT '',
            status TEXT,
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id, appt_date, provider_code)
        );
        CREATE TABLE IF NOT EXISTS sd_claims (
            claim_id TEXT NOT NULL,
            patient_name TEXT,
            payer TEXT,
            service_date TEXT,
            claim_amount REAL,
            claim_status TEXT,
            practice_id TEXT NOT NULL DEFAULT '',
            extracted_at TEXT,
            PRIMARY KEY (practice_id, claim_id)
        );
        CREATE TABLE IF NOT EXISTS sd_payments (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL DEFAULT '',
            payment_date TEXT NOT NULL DEFAULT '',
            amount REAL,
            payer TEXT,
            method TEXT,
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id, payment_date, amount, method)
        );
        CREATE TABLE IF NOT EXISTS sd_adjustments (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL DEFAULT '',
            adj_date TEXT NOT NULL DEFAULT '',
            ada_code TEXT NOT NULL DEFAULT '',
            amount REAL,
            description TEXT,
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id, adj_date, ada_code, amount)
        );
        CREATE TABLE IF NOT EXISTS sd_extract_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sd_extract_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


def read_extract_meta(db_path: Path | None = None) -> dict[str, str]:
    db_path = db_path or resolve_sd_sqlite_db()
    if not db_path or not db_path.is_file():
        return {}
    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "sd_extract_meta"):
            return {}
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM sd_extract_meta")
        return {str(key): str(value or "") for key, value in cur.fetchall()}
    finally:
        conn.close()


def read_extract_status(db_path: Path | None = None) -> dict[str, Any]:
    db_path = db_path or resolve_sd_sqlite_db()
    meta = read_extract_meta(db_path)
    counts = table_row_counts(db_path) if db_path else {}
    populated = sum(1 for table in SD_TABLES if int(counts.get(table) or 0) > 0)
    return {
        "dbPath": str(db_path) if db_path else None,
        "lastExtractAt": meta.get("last_extract_at"),
        "lastMode": meta.get("last_mode"),
        "odbcConfigured": odbc_configured(),
        "tableCounts": counts,
        "populatedTables": populated,
    }


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def table_row_counts(db_path: Path | None) -> dict[str, int]:
    if not db_path or not db_path.is_file():
        return {table: 0 for table in SD_TABLES}
    conn = sqlite3.connect(db_path)
    try:
        out: dict[str, int] = {}
        for table in SD_TABLES:
            if not _table_exists(conn, table):
                out[table] = 0
                continue
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            out[table] = int(cur.fetchone()[0] or 0)
        return out
    finally:
        conn.close()


def _is_payment(code: str, description: str) -> bool:
    normalized = str(code or "").strip()
    text = str(description or "").lower()
    if normalized in WRITEOFF_CODES:
        return False
    if any(normalized.startswith(prefix) for prefix in PAYMENT_PROCEDURE_PREFIXES):
        return True
    return any(token in text for token in ("payment", "visa", "mastercard", "check", "cash"))


def _is_adjustment(code: str, description: str) -> bool:
    normalized = str(code or "").strip()
    text = str(description or "").lower()
    return normalized in WRITEOFF_CODES or "write-off" in text or "write off" in text or "adjustment" in text


def _populate_from_daysheet(conn: sqlite3.Connection, path: Path, *, extracted_at: str) -> dict[str, int]:
    from softdent_operational_pipeline import _load_daysheet_transactions

    counts = {"sd_patients": 0, "sd_providers": 0, "sd_procedures": 0, "sd_payments": 0, "sd_adjustments": 0, "sd_appointments": 0}
    if not path.is_file():
        return counts

    patients: dict[str, dict[str, Any]] = {}
    providers: dict[str, dict[str, Any]] = {}
    for row in _load_daysheet_transactions(path):
        patient_id = str(row.get("patientId") or "").strip()
        patient_name = str(row.get("patientName") or "").strip()
        proc_date = str(row.get("reportDate") or "").strip()
        provider_code = str(row.get("providerId") or "").strip() or "unknown"
        code = str(row.get("code") or "").strip()
        description = str(row.get("description") or "").strip()
        production = row.get("production")
        amount = float(production) if production not in (None, "", 0) else 0.0

        if patient_id and patient_name:
            bucket = patients.setdefault(
                patient_id,
                {
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "first_visit_date": proc_date,
                    "last_visit_date": proc_date,
                    "practice_id": "",
                    "extracted_at": extracted_at,
                },
            )
            if proc_date and (not bucket["first_visit_date"] or proc_date < bucket["first_visit_date"]):
                bucket["first_visit_date"] = proc_date
            if proc_date and (not bucket["last_visit_date"] or proc_date > bucket["last_visit_date"]):
                bucket["last_visit_date"] = proc_date

        if provider_code:
            providers.setdefault(
                provider_code,
                {
                    "provider_code": provider_code,
                    "provider_name": provider_code,
                    "practice_id": "",
                    "extracted_at": extracted_at,
                },
            )

        if not patient_id or not proc_date:
            continue

        if _is_adjustment(code, description) and amount:
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_adjustments
                (practice_id, patient_id, adj_date, ada_code, amount, description, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("", patient_id, proc_date, code, amount, description, extracted_at),
            )
            counts["sd_adjustments"] += 1
            continue

        if _is_payment(code, description) and amount:
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_payments
                (practice_id, patient_id, payment_date, amount, payer, method, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("", patient_id, proc_date, amount, "", description or code, extracted_at),
            )
            counts["sd_payments"] += 1
            continue

        if amount > 0 and code:
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_procedures
                (practice_id, patient_id, proc_date, ada_code, tooth, surface, provider_code, description, production, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("", patient_id, proc_date, code, "", "", provider_code, description, amount, extracted_at),
            )
            counts["sd_procedures"] += 1
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_appointments
                (practice_id, patient_id, appt_date, provider_code, status, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("", patient_id, proc_date, provider_code, "seen", extracted_at),
            )
            counts["sd_appointments"] += 1

    for patient in patients.values():
        conn.execute(
            """
            INSERT OR REPLACE INTO sd_patients
            (patient_id, patient_name, first_visit_date, last_visit_date, practice_id, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                patient["patient_id"],
                patient["patient_name"],
                patient["first_visit_date"],
                patient["last_visit_date"],
                patient["practice_id"],
                patient["extracted_at"],
            ),
        )
        counts["sd_patients"] += 1

    for provider in providers.values():
        conn.execute(
            """
            INSERT OR REPLACE INTO sd_providers
            (provider_code, provider_name, practice_id, extracted_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                provider["provider_code"],
                provider["provider_name"],
                provider["practice_id"],
                provider["extracted_at"],
            ),
        )
        counts["sd_providers"] += 1

    conn.commit()
    return counts


def _populate_from_claims_csv(conn: sqlite3.Connection, path: Path, *, extracted_at: str) -> int:
    if not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            claim_id = str(row.get("ClaimId") or row.get("claim_id") or "").strip()
            if not claim_id:
                continue
            amount_raw = str(row.get("ClaimAmount") or row.get("amount") or "0").replace(",", "").replace("$", "")
            try:
                amount = float(amount_raw)
            except ValueError:
                amount = 0.0
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_claims
                (claim_id, patient_name, payer, service_date, claim_amount, claim_status, practice_id, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    str(row.get("PatientName") or row.get("patient_name") or "").strip(),
                    str(row.get("Payer") or row.get("payer") or "").strip(),
                    str(row.get("ServiceDate") or row.get("service_date") or "").strip(),
                    amount,
                    str(row.get("ClaimStatus") or row.get("claim_status") or "").strip(),
                    "",
                    extracted_at,
                ),
            )
            count += 1
    conn.commit()
    return count


def _populate_from_odbc(conn: sqlite3.Connection, *, extracted_at: str) -> dict[str, Any]:
    dsn = odbc_dsn()
    result: dict[str, Any] = {"ok": False, "mode": "odbc", "dsn": dsn, "tables": {}, "error": None}
    if not dsn:
        result["error"] = "odbc_not_configured"
        return result

    try:
        import pyodbc  # type: ignore
    except ImportError:
        result["error"] = "pyodbc_missing"
        return result

    user = os.environ.get("SOFTDENT_ODBC_USER", "").strip()
    password = os.environ.get("SOFTDENT_ODBC_PASSWORD", "").strip()
    conn_str = f"DSN={dsn}"
    if user:
        conn_str += f";UID={user}"
    if password:
        conn_str += f";PWD={password}"

    query_map = {
        "sd_procedures": os.environ.get("SOFTDENT_ODBC_PROCEDURES_QUERY", "").strip(),
        "sd_patients": os.environ.get("SOFTDENT_ODBC_PATIENTS_QUERY", "").strip(),
        "sd_claims": os.environ.get("SOFTDENT_ODBC_CLAIMS_QUERY", "").strip(),
        "sd_payments": os.environ.get("SOFTDENT_ODBC_PAYMENTS_QUERY", "").strip(),
        "sd_providers": os.environ.get("SOFTDENT_ODBC_PROVIDERS_QUERY", "").strip(),
        "sd_appointments": os.environ.get("SOFTDENT_ODBC_APPOINTMENTS_QUERY", "").strip(),
        "sd_adjustments": os.environ.get("SOFTDENT_ODBC_ADJUSTMENTS_QUERY", "").strip(),
    }
    configured = [name for name, sql in query_map.items() if sql]
    if not configured:
        result["error"] = "odbc_queries_not_configured"
        return result

    try:
        odbc_conn = pyodbc.connect(conn_str, timeout=int(os.environ.get("SOFTDENT_ODBC_TIMEOUT", "30")))
    except Exception as exc:
        result["error"] = f"odbc_connect_failed:{exc}"
        return result

    try:
        cursor = odbc_conn.cursor()
        for table, sql in query_map.items():
            if not sql:
                continue
            cursor.execute(sql)
            columns = [str(col[0]) for col in (cursor.description or [])]
            rows = cursor.fetchall()
            inserted = 0
            for raw in rows:
                mapping = {columns[i]: raw[i] for i in range(len(columns))}
                if table == "sd_procedures":
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sd_procedures
                        (practice_id, patient_id, proc_date, ada_code, tooth, surface, provider_code, description, production, extracted_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(mapping.get("practice_id") or mapping.get("PracticeID") or ""),
                            str(mapping.get("patient_id") or mapping.get("PatientID") or ""),
                            str(mapping.get("proc_date") or mapping.get("ProcDate") or ""),
                            str(mapping.get("ada_code") or mapping.get("ADACode") or mapping.get("Code") or ""),
                            str(mapping.get("tooth") or mapping.get("Tooth") or ""),
                            str(mapping.get("surface") or mapping.get("Surface") or ""),
                            str(mapping.get("provider_code") or mapping.get("ProviderCode") or ""),
                            str(mapping.get("description") or mapping.get("Description") or ""),
                            float(mapping.get("production") or mapping.get("Production") or 0),
                            extracted_at,
                        ),
                    )
                    inserted += 1
                elif table == "sd_patients":
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sd_patients
                        (patient_id, patient_name, first_visit_date, last_visit_date, practice_id, extracted_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(mapping.get("patient_id") or mapping.get("PatientID") or ""),
                            str(mapping.get("patient_name") or mapping.get("PatientName") or ""),
                            str(mapping.get("first_visit_date") or mapping.get("FirstVisitDate") or ""),
                            str(mapping.get("last_visit_date") or mapping.get("LastVisitDate") or ""),
                            str(mapping.get("practice_id") or mapping.get("PracticeID") or ""),
                            extracted_at,
                        ),
                    )
                    inserted += 1
                elif table == "sd_claims":
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sd_claims
                        (claim_id, patient_name, payer, service_date, claim_amount, claim_status, practice_id, extracted_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(mapping.get("claim_id") or mapping.get("ClaimID") or mapping.get("ClaimId") or ""),
                            str(mapping.get("patient_name") or mapping.get("PatientName") or ""),
                            str(mapping.get("payer") or mapping.get("Payer") or ""),
                            str(mapping.get("service_date") or mapping.get("ServiceDate") or ""),
                            float(mapping.get("claim_amount") or mapping.get("ClaimAmount") or 0),
                            str(mapping.get("claim_status") or mapping.get("ClaimStatus") or ""),
                            str(mapping.get("practice_id") or mapping.get("PracticeID") or ""),
                            extracted_at,
                        ),
                    )
                    inserted += 1
                elif table == "sd_payments":
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sd_payments
                        (practice_id, patient_id, payment_date, amount, payer, method, extracted_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(mapping.get("practice_id") or mapping.get("PracticeID") or ""),
                            str(mapping.get("patient_id") or mapping.get("PatientID") or ""),
                            str(mapping.get("payment_date") or mapping.get("PaymentDate") or ""),
                            float(mapping.get("amount") or mapping.get("Amount") or 0),
                            str(mapping.get("payer") or mapping.get("Payer") or ""),
                            str(mapping.get("method") or mapping.get("Method") or ""),
                            extracted_at,
                        ),
                    )
                    inserted += 1
                elif table == "sd_providers":
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sd_providers
                        (provider_code, provider_name, practice_id, extracted_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            str(mapping.get("provider_code") or mapping.get("ProviderCode") or ""),
                            str(mapping.get("provider_name") or mapping.get("ProviderName") or ""),
                            str(mapping.get("practice_id") or mapping.get("PracticeID") or ""),
                            extracted_at,
                        ),
                    )
                    inserted += 1
                elif table == "sd_appointments":
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sd_appointments
                        (practice_id, patient_id, appt_date, provider_code, status, extracted_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(mapping.get("practice_id") or mapping.get("PracticeID") or ""),
                            str(mapping.get("patient_id") or mapping.get("PatientID") or ""),
                            str(mapping.get("appt_date") or mapping.get("ApptDate") or mapping.get("AppointmentDate") or ""),
                            str(mapping.get("provider_code") or mapping.get("ProviderCode") or ""),
                            str(mapping.get("status") or mapping.get("Status") or ""),
                            extracted_at,
                        ),
                    )
                    inserted += 1
                elif table == "sd_adjustments":
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sd_adjustments
                        (practice_id, patient_id, adj_date, ada_code, amount, description, extracted_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(mapping.get("practice_id") or mapping.get("PracticeID") or ""),
                            str(mapping.get("patient_id") or mapping.get("PatientID") or ""),
                            str(mapping.get("adj_date") or mapping.get("AdjDate") or ""),
                            str(mapping.get("ada_code") or mapping.get("ADACode") or ""),
                            float(mapping.get("amount") or mapping.get("Amount") or 0),
                            str(mapping.get("description") or mapping.get("Description") or ""),
                            extracted_at,
                        ),
                    )
                    inserted += 1
            result["tables"][table] = inserted
        conn.commit()
        result["ok"] = any(int(value or 0) > 0 for value in result["tables"].values())
    except Exception as exc:
        result["error"] = f"odbc_query_failed:{exc}"
    finally:
        odbc_conn.close()
    return result


def _resolve_daysheet_path() -> Path | None:
    try:
        from softdent_operational_pipeline import resolve_daysheet_jsonl_path
    except Exception:
        return None
    return resolve_daysheet_jsonl_path()


def _resolve_claims_path() -> Path | None:
    dest = softdent_import_dir()
    for name in ("softdent_claims_export.csv", "claims_export.csv"):
        candidate = dest / name
        if candidate.is_file():
            return candidate
    return None


def extract_softdent_odbc(*, db_path: Path | None = None, force: bool = False) -> dict[str, Any]:
    db_path = Path(db_path) if db_path else resolve_sd_sqlite_db()
    extracted_at = _utc_now()
    result: dict[str, Any] = {
        "ok": False,
        "refreshed": False,
        "dbPath": str(db_path) if db_path else None,
        "mode": None,
        "odbc": None,
        "fallback": {},
        "tableCounts": {},
        "warnings": [],
    }
    if not db_path:
        result["warnings"].append("No SoftDent SQLite target (set SOFTDENT_SQLITE_FALLBACK or NR2_FINANCIAL_ANALYTICS_DB).")
        return result

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        ensure_sd_schema(conn)
        odbc_result = _populate_from_odbc(conn, extracted_at=extracted_at)
        result["odbc"] = odbc_result
        fallback_counts: dict[str, int] = {}
        daysheet_path = _resolve_daysheet_path()
        if daysheet_path:
            fallback_counts = _populate_from_daysheet(conn, daysheet_path, extracted_at=extracted_at)
        claims_count = _populate_from_claims_csv(conn, _resolve_claims_path() or Path(""), extracted_at=extracted_at)
        fallback_counts["sd_claims"] = fallback_counts.get("sd_claims", 0) + claims_count
        result["fallback"] = fallback_counts

        counts = table_row_counts(db_path)
        result["tableCounts"] = counts
        populated = sum(1 for table in SD_TABLES if int(counts.get(table) or 0) > 0)
        result["ok"] = populated >= 3
        result["refreshed"] = bool(force or populated > 0)
        if odbc_result.get("ok"):
            result["mode"] = "odbc"
        elif populated > 0:
            result["mode"] = "json-fallback"
        else:
            result["mode"] = "none"
            if odbc_result.get("error"):
                result["warnings"].append(str(odbc_result["error"]))

        _set_meta(conn, "last_extract_at", extracted_at)
        _set_meta(conn, "last_mode", str(result["mode"]))
        conn.commit()
    finally:
        conn.close()

    try:
        from automation_registry import record_job_run

        record_job_run(
            "softdent-odbc-extract",
            ok=bool(result["ok"]),
            detail=f"mode={result.get('mode')} populated={sum(1 for t in SD_TABLES if int(result['tableCounts'].get(t) or 0) > 0)}",
        )
    except Exception:
        pass
    return result


def odbc_extract_stale(db_path: Path | None = None, *, max_age_minutes: int = 60) -> bool:
    db_path = db_path or resolve_sd_sqlite_db()
    meta = read_extract_meta(db_path)
    last = meta.get("last_extract_at")
    if not last:
        return True
    try:
        parsed = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return True
    age_seconds = datetime.now(timezone.utc).timestamp() - parsed.timestamp()
    return age_seconds > max(1, max_age_minutes) * 60


def ensure_softdent_odbc_fresh(
    *,
    db_path: Path | None = None,
    max_age_minutes: int = 60,
    force: bool = False,
) -> dict[str, Any]:
    db_path = db_path or resolve_sd_sqlite_db()
    stale = force or odbc_extract_stale(db_path, max_age_minutes=max_age_minutes)
    result: dict[str, Any] = {
        "stale": stale,
        "refreshed": False,
        "dbPath": str(db_path) if db_path else None,
        "extract": None,
    }
    if not stale:
        result["status"] = read_extract_status(db_path)
        return result
    extract = extract_softdent_odbc(db_path=db_path, force=force)
    result["extract"] = extract
    result["refreshed"] = bool(extract.get("refreshed"))
    result["status"] = read_extract_status(db_path)
    return result


def run_odbc_lane(*, force: bool = False) -> dict[str, Any]:
    """Entry point for softdent_practice_exports ODBC lane."""
    return extract_softdent_odbc(force=force)
