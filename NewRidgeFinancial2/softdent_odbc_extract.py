"""SoftDent ODBC extract lane → sd_* SQLite tables (hal-10070).

When ``SOFTDENT_ODBC_DSN`` / ``NR2_SOFTDENT_ODBC_DSN`` is configured and optional
env SQL queries are present, rows are pulled via pyodbc. When Sensei Gateway DataSync
JSON is present on the SoftDent server, ``sensei-datasync`` populates sd_* from live
Carestream sync files. Otherwise the JSON/daysheet/claims fallback lane fills gaps.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_loader import softdent_import_dir
from import_sync import SENSEI_DATASYNC
from quickbooks_monthly_sync import resolve_analytics_db
from softdent_operational_pipeline import (
    INSURANCE_PAYMENT_CODES,
    INSURANCE_WRITEOFF_CODES,
    PATIENT_PAYMENT_CODES,
    _money_value,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

PAYMENT_PROCEDURE_PREFIXES = ("1200", "1400", "4000", "5000")
WRITEOFF_CODES = INSURANCE_WRITEOFF_CODES
PAYMENT_CODES = INSURANCE_PAYMENT_CODES

SD_TABLES = (
    "sd_providers",
    "sd_patients",
    "sd_procedures",
    "sd_appointments",
    "sd_claims",
    "sd_payments",
    "sd_adjustments",
)

SENSEI_ENTITY_WRAPPERS = {
    "patient": "PATIENT",
    "dentist": "DENTIST",
    "appointment": "APPTS",
}
SENSEI_APPT_PROC_SLOTS = 12


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


ODBC_QUERY_ENV_BY_TABLE = {
    "sd_patients": "SOFTDENT_ODBC_PATIENTS_QUERY",
    "sd_procedures": "SOFTDENT_ODBC_PROCEDURES_QUERY",
    "sd_payments": "SOFTDENT_ODBC_PAYMENTS_QUERY",
    "sd_claims": "SOFTDENT_ODBC_CLAIMS_QUERY",
    "sd_appointments": "SOFTDENT_ODBC_APPOINTMENTS_QUERY",
    "sd_providers": "SOFTDENT_ODBC_PROVIDERS_QUERY",
    "sd_adjustments": "SOFTDENT_ODBC_ADJUSTMENTS_QUERY",
}


def discovery_output_path() -> Path:
    configured = os.environ.get("NR2_SOFTDENT_SCHEMA_DISCOVERY", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve()
    return (REPO_ROOT / "app_data" / "nr2" / "softdent_schema_discovery.json").resolve()


def load_discovery_suggested_env() -> dict[str, str]:
    """Load suggestedEnv from softdent_schema_discovery.json when present."""
    path = discovery_output_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    suggested = data.get("suggestedEnv") if isinstance(data, dict) else None
    if not isinstance(suggested, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in suggested.items():
        sql = str(value or "").strip()
        if sql:
            out[str(key)] = sql
    return out


def use_discovery_queries() -> bool:
    """When env SQL is empty, allow extract to use discovery suggestedEnv (default on)."""
    raw = os.environ.get("NR2_SOFTDENT_USE_DISCOVERY_QUERIES", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def resolve_odbc_query_map() -> dict[str, str]:
    """Env SQL wins; optionally fill gaps from discovery suggestedEnv."""
    query_map = {
        table: os.environ.get(env_key, "").strip()
        for table, env_key in ODBC_QUERY_ENV_BY_TABLE.items()
    }
    if not use_discovery_queries():
        return query_map
    if all(query_map.values()):
        return query_map
    suggested = load_discovery_suggested_env()
    if not suggested:
        return query_map
    for table, env_key in ODBC_QUERY_ENV_BY_TABLE.items():
        if not query_map.get(table) and suggested.get(env_key):
            query_map[table] = suggested[env_key]
    return query_map


def configured_odbc_query_tables() -> list[str]:
    return [table for table, sql in resolve_odbc_query_map().items() if sql]


def pyodbc_available() -> bool:
    try:
        import pyodbc  # noqa: F401

        return True
    except ImportError:
        return False


def consent_executor_enabled() -> bool:
    try:
        from nr2_consent_executor import consent_executor_enabled as _enabled

        return _enabled()
    except Exception:
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
    query_tables = configured_odbc_query_tables()
    discovery_path = discovery_output_path()
    last_extract_at = meta.get("last_extract_at")
    stale = odbc_extract_stale(db_path) if db_path else True
    sensei_root = resolve_sensei_datasync_root()
    return {
        "ok": True,
        "dbPath": str(db_path) if db_path else None,
        "lastExtractAt": last_extract_at,
        "lastMode": meta.get("last_mode"),
        "odbcConfigured": odbc_configured(),
        "pyodbcAvailable": pyodbc_available(),
        "queriesConfigured": len(query_tables),
        "configuredQueryTables": query_tables,
        "consentExecutorEnabled": consent_executor_enabled(),
        "discoveryPresent": discovery_path.is_file(),
        "discoveryPath": str(discovery_path) if discovery_path.is_file() else None,
        "senseiDatasyncAvailable": bool(sensei_root),
        "senseiDatasyncPath": str(sensei_root) if sensei_root else None,
        "tableCounts": counts,
        "populatedTables": populated,
        "stale": bool(stale),
        "nextSteps": _extract_status_next_steps(
            odbc_configured=odbc_configured(),
            query_tables=query_tables,
            discovery_present=discovery_path.is_file(),
            populated=populated,
            last_mode=meta.get("last_mode"),
            sensei_available=bool(sensei_root),
        ),
    }


def _extract_status_next_steps(
    *,
    odbc_configured: bool,
    query_tables: list[str],
    discovery_present: bool,
    populated: int,
    last_mode: str | None,
    sensei_available: bool = False,
) -> list[str]:
    steps: list[str] = []
    if not odbc_configured:
        if sensei_available:
            steps.append("Sensei DataSync JSON is available — sd_* tables refresh from live Carestream sync (no SQL ODBC required).")
        else:
            steps.append("Set SOFTDENT_ODBC_DSN (or NR2_SOFTDENT_ODBC_DSN) to a read-only System DSN.")
    elif not query_tables:
        steps.append(
            "Run scripts/discover_softdent_odbc_schema.py --out app_data/nr2/softdent_schema_discovery.json "
            "(extract can use suggestedEnv when NR2_SOFTDENT_USE_DISCOVERY_QUERIES=1) or copy SOFTDENT_ODBC_*_QUERY into .env."
        )
    if "sd_claims" not in query_tables and odbc_configured:
        steps.append(
            "SOFTDENT_ODBC_CLAIMS_QUERY is not configured — named Payer labels for claim readiness need claims ODBC or SoftDent claims CSV."
        )
    if not discovery_present and odbc_configured:
        steps.append("Save schema discovery output to app_data/nr2/softdent_schema_discovery.json for operator reference.")
    if not consent_executor_enabled():
        steps.append("Set NR2_CONSENT_EXECUTOR=1 to allow workstation Sync SoftDent / POST /api/admin/extract-softdent-odbc.")
    if populated < 3:
        steps.append("Drop SoftDent daysheet/claims exports, ensure Sensei Gateway Client is running, then sync from workstation or Financial page.")
    elif last_mode == "json-fallback" and sensei_available:
        steps.append("Last extract used daysheet fallback only — run Sync SoftDent to pull Sensei DataSync into sd_* tables.")
    elif last_mode not in ("odbc", "sensei-datasync", "sensei+json-fallback") and odbc_configured and query_tables:
        steps.append("ODBC is configured but last extract did not use SQL — verify DSN credentials and query table names.")
    if not steps:
        steps.append("Extract lane healthy — sd_* tables populated; refresh via import sync or workstation Sync SoftDent.")
    return steps


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


def _normalize_softdent_code(code: str) -> str:
    """SoftDent daysheet/JSONL sometimes emits codes as ``2.00`` instead of ``2``."""
    normalized = str(code or "").strip()
    if not normalized:
        return ""
    if normalized.replace(".", "", 1).isdigit() and "." in normalized:
        try:
            as_float = float(normalized)
            if as_float == int(as_float) and as_float < 1000:
                return str(int(as_float))
        except ValueError:
            pass
    return normalized


def _is_payment(code: str, description: str) -> bool:
    """Detect payments using SoftDent v19 transaction codes + description fallback."""
    normalized = _normalize_softdent_code(code)
    text = str(description or "").lower()
    if normalized in WRITEOFF_CODES:
        return False
    if normalized in PAYMENT_CODES or normalized in PATIENT_PAYMENT_CODES:
        return True
    if any(normalized.startswith(prefix) for prefix in PAYMENT_PROCEDURE_PREFIXES):
        return True
    return any(
        token in text
        for token in ("payment", "visa", "mastercard", "amex", "check", "cash", "insurance check")
    )


def _is_adjustment(code: str, description: str) -> bool:
    """Detect adjustments/write-offs using SoftDent codes 51/52 + description tokens."""
    normalized = _normalize_softdent_code(code)
    text = str(description or "").lower()
    if normalized in WRITEOFF_CODES:
        return True
    return any(
        token in text
        for token in ("write-off", "write off", "writeoff", "adjustment", "adjust", "courtesy")
    )


def _row_amount(row: dict[str, Any]) -> float:
    production = row.get("production")
    if production not in (None, ""):
        try:
            val = float(production)
            if val != 0:
                return abs(val)
        except (TypeError, ValueError):
            pass
    return 0.0


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
        amount = _row_amount(row)

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

        if _is_adjustment(code, description):
            if amount <= 0 and not code:
                continue
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

        if _is_payment(code, description):
            if amount <= 0:
                amount = _row_amount({"production": production})
            if amount <= 0:
                continue
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

    query_map = resolve_odbc_query_map()
    configured = [name for name, sql in query_map.items() if sql]
    if not configured:
        result["error"] = "odbc_queries_not_configured"
        return result
    result["querySources"] = {
        table: (
            "env"
            if os.environ.get(ODBC_QUERY_ENV_BY_TABLE[table], "").strip()
            else ("discovery" if sql else None)
        )
        for table, sql in query_map.items()
        if sql
    }

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


def _resolve_register_path() -> Path | None:
    try:
        from import_sync import SOFTDENT_FINANCIAL_EXPORTS, _find_newest, _softdent_direct_read_roots
    except Exception:
        return None
    candidates: list[Path] = []
    for root in _softdent_direct_read_roots():
        found = _find_newest(root, ("register_for_period.jsonl",))
        if found:
            candidates.append(found)
    direct = SOFTDENT_FINANCIAL_EXPORTS / "register_for_period.jsonl"
    if direct.is_file():
        candidates.append(direct)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _register_period_end(path: Path) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", path.name)
    if match:
        return match.group(2)
    match = re.search(r"(\d{4}-\d{2}-\d{2})", str(path))
    return match.group(1) if match else datetime.now(timezone.utc).date().isoformat()


def _populate_from_register_jsonl(conn: sqlite3.Connection, path: Path, *, extracted_at: str) -> dict[str, int]:
    counts = {"sd_payments": 0, "sd_adjustments": 0}
    if not path.is_file():
        return counts
    payment_date = _register_period_end(path)
    register_methods = frozenset(
        {
            "cash",
            "check",
            "credit card",
            "credit cards",
            "debit card",
            "eft",
            "carecredit",
            "ins plan collections",
            "regular collections",
            "insurance collections",
            "patient collections",
            "visa",
            "mastercard",
            "amex",
            "discover",
        }
    )
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(payload.get("dataset_name") or "") != "register_for_period":
                continue
            raw = payload.get("raw_row")
            if not isinstance(raw, list):
                continue
            cells = [str(cell or "").strip() for cell in raw]
            while len(cells) < 10:
                cells.append("")
            label = (cells[0] or cells[1]).strip()
            lowered = label.lower()
            amount = _money_value(cells[2]) or _money_value(cells[3])
            if lowered == "adjustment to collections" or "adjustment to collections" in lowered:
                if amount is None:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sd_adjustments
                    (practice_id, patient_id, adj_date, ada_code, amount, description, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("", "register", payment_date, "adj", abs(float(amount)), label, extracted_at),
                )
                counts["sd_adjustments"] += 1
                continue
            method = cells[1].strip() if not cells[0] else cells[1].strip()
            if method.lower() not in register_methods:
                continue
            if amount is None or amount <= 0:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_payments
                (practice_id, patient_id, payment_date, amount, payer, method, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("", f"register:{method.lower().replace(' ', '_')}", payment_date, abs(float(amount)), "", method, extracted_at),
            )
            counts["sd_payments"] += 1
    conn.commit()
    return counts


def _resolve_claims_path() -> Path | None:
    dest = softdent_import_dir()
    for name in ("softdent_claims_export.csv", "claims_export.csv"):
        candidate = dest / name
        if candidate.is_file():
            return candidate
    return None


def _is_generic_payer_label(value: str) -> bool:
    return str(value or "").strip().lower() in {"", "insurance", "unknown", "n/a", "-", "—"}


def export_sd_claims_to_inbox_csv(
    conn: sqlite3.Connection,
    *,
    destination: Path | None = None,
    limit: int = 5000,
) -> dict[str, Any]:
    """Write named-payer sd_claims rows to softdent_claims_export.csv for HAL join/readiness.

    Skips overwrite when the existing CSV already has named Payers and sd_claims
    has no named payers (avoids clobbering a better SoftDent export).
    """
    dest_dir = destination or softdent_import_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / "softdent_claims_export.csv"
    result: dict[str, Any] = {"ok": False, "path": str(out_path), "written": 0, "skipped": False}
    if not _table_exists(conn, "sd_claims"):
        result["error"] = "sd_claims_missing"
        return result
    cur = conn.cursor()
    cur.execute(
        """
        SELECT claim_id, patient_name, payer, service_date, claim_amount, claim_status
        FROM sd_claims
        ORDER BY service_date DESC, claim_id DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    )
    rows = cur.fetchall()
    named_rows = [r for r in rows if not _is_generic_payer_label(str(r[2] or ""))]
    if not named_rows:
        result["skipped"] = True
        result["error"] = "no_named_payers_in_sd_claims"
        return result

    existing_named = False
    if out_path.is_file():
        try:
            with out_path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    if not _is_generic_payer_label(str(row.get("Payer") or row.get("payer") or "")):
                        existing_named = True
                        break
        except OSError:
            existing_named = False
        # Prefer keeping an existing SoftDent CSV if sd_claims named set is empty-ish
        # (already handled) — if both have named payers, refresh from sd_claims (ODBC wins).

    fieldnames = ["ClaimId", "PatientName", "Payer", "ServiceDate", "ClaimAmount", "ClaimStatus"]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for claim_id, patient_name, payer, service_date, claim_amount, claim_status in named_rows:
            writer.writerow(
                {
                    "ClaimId": claim_id or "",
                    "PatientName": patient_name or "",
                    "Payer": payer or "",
                    "ServiceDate": service_date or "",
                    "ClaimAmount": claim_amount if claim_amount is not None else "",
                    "ClaimStatus": claim_status or "",
                }
            )
    result["ok"] = True
    result["written"] = len(named_rows)
    result["replacedExistingNamed"] = existing_named
    return result


def _sensei_include_reference() -> bool:
    return os.environ.get("NR2_SENSEI_INCLUDE_REFERENCE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def resolve_sensei_datasync_root() -> Path | None:
    """Resolve tenant DataSync root (e.g. .../DataSync/0000950863)."""
    configured = (
        os.environ.get("NR2_SENSEI_DATASYNC_ROOT", "").strip()
        or os.environ.get("SOFTDENT_SOURCE_DIR", "").strip()
    )
    tenant = os.environ.get("NR2_SENSEI_DATASYNC_TENANT", "").strip()
    bases: list[Path] = []
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        bases.append(candidate.resolve())
    elif SENSEI_DATASYNC.is_dir():
        bases.append(SENSEI_DATASYNC.resolve())

    def _tenant_root(base: Path) -> Path | None:
        if (base / "Reference").is_dir() or (base / "patient").is_dir():
            return base
        if tenant and (base / tenant).is_dir():
            return (base / tenant).resolve()
        for child in sorted(base.iterdir()):
            if not child.is_dir() or not child.name.isdigit():
                continue
            if (child / "Reference").is_dir() or (child / "patient").is_dir():
                return child.resolve()
        return None

    for base in bases:
        resolved = _tenant_root(base)
        if resolved:
            return resolved
    return None


def _normalize_sensei_date(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text or text.lower() in {"none", "00:00", "null"}:
        return ""
    normalized = text.replace("/", "-").split("T")[0].split(" ")[0]
    return normalized


def _sensei_person_name(first: Any, last: Any) -> str:
    first_text = str(first or "").strip()
    last_text = str(last or "").strip()
    if first_text and last_text:
        return f"{first_text} {last_text}"
    return first_text or last_text


def _load_sensei_entity(path: Path, wrapper_key: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    inner = payload.get(wrapper_key)
    if isinstance(inner, dict):
        return inner
    return payload


def _iter_sensei_entity_files(root: Path, entity: str) -> list[Path]:
    files: dict[str, Path] = {}
    entity_dir = root / entity
    if entity_dir.is_dir():
        for path in entity_dir.glob(f"{entity}_*.json"):
            if "ChangeQTrans" in str(path):
                continue
            files[str(path.resolve())] = path
    if _sensei_include_reference():
        ref_dir = root / "Reference"
        if ref_dir.is_dir():
            for path in ref_dir.glob(f"{entity}_*.json"):
                files[str(path.resolve())] = path
    return list(files.values())


def _sensei_patient_id(entity: dict[str, Any]) -> str:
    for key in ("UniqueID", "PatUniqueID", "Id", "PatientId", "PatientID"):
        value = entity.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _sensei_appt_status(entity: dict[str, Any]) -> str:
    checked_in = str(entity.get("CheckedIn") or "").strip()
    if checked_in and checked_in not in {"00:00", "None"}:
        return "checked-in"
    for key in ("Status", "ApptStatus", "Confirmed"):
        value = str(entity.get(key) or "").strip()
        if value and value.lower() not in {"none", "null"}:
            return value.lower()
    return "scheduled"


def _populate_from_sensei_datasync(
    conn: sqlite3.Connection,
    root: Path,
    *,
    extracted_at: str,
) -> dict[str, int]:
    counts = {table: 0 for table in SD_TABLES}
    if not root.is_dir():
        return counts

    for path in _iter_sensei_entity_files(root, "dentist"):
        entity = _load_sensei_entity(path, SENSEI_ENTITY_WRAPPERS["dentist"])
        if not entity:
            continue
        provider_code = str(entity.get("Id") or entity.get("Code") or "").strip()
        if not provider_code:
            continue
        provider_name = _sensei_person_name(entity.get("Firstname"), entity.get("Lastname"))
        conn.execute(
            """
            INSERT OR REPLACE INTO sd_providers
            (provider_code, provider_name, practice_id, extracted_at)
            VALUES (?, ?, ?, ?)
            """,
            (provider_code, provider_name or provider_code, "", extracted_at),
        )
        counts["sd_providers"] += 1

    for path in _iter_sensei_entity_files(root, "patient"):
        entity = _load_sensei_entity(path, SENSEI_ENTITY_WRAPPERS["patient"])
        if not entity:
            continue
        patient_id = _sensei_patient_id(entity)
        if not patient_id:
            continue
        patient_name = _sensei_person_name(entity.get("Firstname"), entity.get("Lastname"))
        first_visit = _normalize_sensei_date(entity.get("FirstVisit") or entity.get("FirstVisitDate"))
        last_visit = _normalize_sensei_date(entity.get("LastVisit") or entity.get("LastVisitDate"))
        conn.execute(
            """
            INSERT OR REPLACE INTO sd_patients
            (patient_id, patient_name, first_visit_date, last_visit_date, practice_id, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (patient_id, patient_name, first_visit, last_visit, "", extracted_at),
        )
        counts["sd_patients"] += 1

    for path in _iter_sensei_entity_files(root, "appointment"):
        entity = _load_sensei_entity(path, SENSEI_ENTITY_WRAPPERS["appointment"])
        if not entity:
            continue
        patient_id = _sensei_patient_id(entity)
        appt_date = _normalize_sensei_date(entity.get("Date") or entity.get("ApptDate"))
        provider_code = str(entity.get("Dr") or entity.get("ProviderCode") or entity.get("DentistId") or "unknown").strip()
        if not patient_id or not appt_date:
            continue
        status = _sensei_appt_status(entity)
        conn.execute(
            """
            INSERT OR REPLACE INTO sd_appointments
            (practice_id, patient_id, appt_date, provider_code, status, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("", patient_id, appt_date, provider_code, status, extracted_at),
        )
        counts["sd_appointments"] += 1

        for index in range(SENSEI_APPT_PROC_SLOTS):
            code = str(entity.get(f"Proc{index}_Code") or "").strip()
            if not code or code in {"0", "0000"}:
                continue
            fee_raw = entity.get(f"Proc{index}_Fee")
            try:
                production = abs(float(fee_raw or 0))
            except (TypeError, ValueError):
                production = 0.0
            tooth = str(entity.get(f"Proc{index}_Tooth") or "").strip()
            if tooth.lower() in {"none", "null"}:
                tooth = ""
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_procedures
                (practice_id, patient_id, proc_date, ada_code, tooth, surface, provider_code, description, production, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("", patient_id, appt_date, code, tooth, "", provider_code, "", production, extracted_at),
            )
            counts["sd_procedures"] += 1

    conn.commit()
    return counts


def _sensei_lane_populated(counts: dict[str, int]) -> bool:
    return any(int(counts.get(table) or 0) > 0 for table in ("sd_patients", "sd_appointments", "sd_providers"))


def _fallback_lane_populated(counts: dict[str, int]) -> bool:
    return any(int(counts.get(table) or 0) > 0 for table in SD_TABLES)


def _resolve_extract_mode(
    *,
    odbc_ok: bool,
    sensei_counts: dict[str, int],
    fallback_counts: dict[str, int],
    populated: int,
) -> str:
    if odbc_ok:
        return "odbc"
    sensei_ok = _sensei_lane_populated(sensei_counts)
    fallback_ok = _fallback_lane_populated(fallback_counts)
    if sensei_ok and fallback_ok:
        return "sensei+json-fallback"
    if sensei_ok:
        return "sensei-datasync"
    if populated > 0:
        return "json-fallback"
    return "none"


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
        sensei_root = resolve_sensei_datasync_root()
        sensei_counts: dict[str, int] = {table: 0 for table in SD_TABLES}
        if sensei_root:
            sensei_counts = _populate_from_sensei_datasync(conn, sensei_root, extracted_at=extracted_at)
        result["sensei"] = {"root": str(sensei_root) if sensei_root else None, "tables": sensei_counts}
        fallback_counts: dict[str, int] = {}
        daysheet_path = _resolve_daysheet_path()
        if daysheet_path:
            fallback_counts = _populate_from_daysheet(conn, daysheet_path, extracted_at=extracted_at)
        register_path = _resolve_register_path()
        if register_path:
            register_counts = _populate_from_register_jsonl(conn, register_path, extracted_at=extracted_at)
            for key, value in register_counts.items():
                fallback_counts[key] = fallback_counts.get(key, 0) + int(value or 0)
        claims_count = _populate_from_claims_csv(conn, _resolve_claims_path() or Path(""), extracted_at=extracted_at)
        fallback_counts["sd_claims"] = fallback_counts.get("sd_claims", 0) + claims_count
        result["fallback"] = fallback_counts

        # After ODBC/Sensei populate named payers, refresh inbox CSV for HAL join/readiness.
        try:
            export_result = export_sd_claims_to_inbox_csv(conn)
            result["claimsExport"] = export_result
            if export_result.get("ok") and export_result.get("written"):
                _set_meta(conn, "last_claims_export_at", extracted_at)
                _set_meta(conn, "last_claims_export_count", str(export_result.get("written") or 0))
        except Exception as exc:
            result["claimsExport"] = {"ok": False, "error": str(exc)}

        counts = table_row_counts(db_path)
        result["tableCounts"] = counts
        populated = sum(1 for table in SD_TABLES if int(counts.get(table) or 0) > 0)
        result["ok"] = populated >= 3
        result["refreshed"] = bool(force or populated > 0)
        result["mode"] = _resolve_extract_mode(
            odbc_ok=bool(odbc_result.get("ok")),
            sensei_counts=sensei_counts,
            fallback_counts=fallback_counts,
            populated=populated,
        )
        if result["mode"] == "none" and odbc_result.get("error"):
            result["warnings"].append(str(odbc_result["error"]))

        _set_meta(conn, "last_extract_at", extracted_at)
        _set_meta(conn, "last_mode", str(result["mode"]))
        if sensei_root:
            _set_meta(conn, "last_sensei_root", str(sensei_root))
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
