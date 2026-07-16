"""SoftDent ODBC extract lane → sd_* SQLite tables (hal-10070).

When ``SOFTDENT_ODBC_DSN`` / ``NR2_SOFTDENT_ODBC_DSN`` is configured and optional
env SQL queries are present, rows are pulled via pyodbc. When Sensei Gateway DataSync
JSON is present on the SoftDent server, ``sensei-datasync`` populates sd_* from live
Carestream sync files. Otherwise the JSON/daysheet/claims fallback lane fills gaps.

Program doctrine: prefer this database/extract lane when the needed SoftDent data is
reachable here. SoftDent data that cannot be reached by the database requires SoftDent
Sign On + SoftDent UI export (see softdent_signon / softdent_gui_export), then file ingest.
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
    "sd_patient_insurance",
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
    "sd_patient_insurance": "SOFTDENT_ODBC_INSURANCE_QUERY",
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
            appt_time TEXT,
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
            total_fee REAL,
            balance REAL,
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
        CREATE TABLE IF NOT EXISTS sd_patient_insurance (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 1,
            member_id TEXT,
            subscriber_id TEXT,
            subscriber_name TEXT,
            relationship_code TEXT,
            carrier_code TEXT,
            insurance_name TEXT,
            payer_id TEXT,
            group_number TEXT,
            group_name TEXT,
            effective_date TEXT,
            termination_date TEXT,
            extracted_at TEXT NOT NULL,
            PRIMARY KEY (practice_id, patient_id, priority)
        );
        CREATE TABLE IF NOT EXISTS sd_carrier_payer_map (
            practice_id TEXT NOT NULL DEFAULT '',
            carrier_code TEXT NOT NULL,
            payer_id TEXT NOT NULL,
            insurance_name TEXT,
            updated_at TEXT,
            PRIMARY KEY (practice_id, carrier_code)
        );
        CREATE TABLE IF NOT EXISTS sd_extract_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    # Existing DBs created before appt_time — add column honestly (NULL until extract fills it).
    try:
        cols = {str(r[1] or "") for r in conn.execute("PRAGMA table_info(sd_appointments)").fetchall()}
        if "appt_time" not in cols:
            conn.execute("ALTER TABLE sd_appointments ADD COLUMN appt_time TEXT")
    except sqlite3.Error:
        pass
    conn.commit()


def _normalize_appt_time_value(raw: Any) -> str:
    """Store SoftDent/Sensei time as HH:MM or empty (never invent midnight)."""
    text = str(raw or "").strip()
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if ":" in text:
        parts = text.replace(".", ":").split(":")
        try:
            hh = int(parts[0])
            mm = int(parts[1]) if len(parts) > 1 else 0
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return f"{hh:02d}:{mm:02d}"
        except ValueError:
            pass
    if len(digits) >= 3 and len(digits) <= 4:
        padded = digits.zfill(4)
        try:
            hh = int(padded[:2])
            mm = int(padded[2:4])
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return f"{hh:02d}:{mm:02d}"
        except ValueError:
            pass
    return text[:12] if any(ch.isdigit() for ch in text) else ""


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sd_extract_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


_REL_CODE_MAP = {
    "1": "SELF",
    "01": "SELF",
    "2": "SPOUSE",
    "02": "SPOUSE",
    "3": "CHILD",
    "03": "CHILD",
    "4": "OTHER",
    "04": "OTHER",
    "21": "OTHER",
    "S": "SELF",
    "SELF": "SELF",
    "SPOUSE": "SPOUSE",
    "CHILD": "CHILD",
    "OTHER": "OTHER",
}

# Daysheet/claim ids: DS-YYYYMMDD-{chart}-{proc}-{seq}
_CLAIM_CHART_RE = re.compile(r"^DS-\d{8}-(\d+)(?:-|$)", re.IGNORECASE)

DEFAULT_INSURANCE_ODBC_QUERY = """
SELECT
    p.Patient_ID AS patient_id,
    CASE
        WHEN UPPER(COALESCE(pi.Ins_Type, pi.Type, 'PRI')) IN ('SEC', '2', 'SECONDARY') THEN 2
        WHEN UPPER(COALESCE(pi.Ins_Type, pi.Type, 'PRI')) IN ('TER', '3', 'TERTIARY') THEN 3
        ELSE 1
    END AS priority,
    pi.Member_ID AS member_id,
    pi.Subscriber_ID AS subscriber_id,
    pi.Subscriber_Name AS subscriber_name,
    pi.Relationship AS relationship_code,
    c.Carrier_Code AS carrier_code,
    c.Carrier_Name AS insurance_name,
    c.EDI_Code AS payer_id,
    pi.Group_Num AS group_number,
    pi.Group_Name AS group_name,
    pi.Effective_Date AS effective_date,
    pi.Termination_Date AS termination_date
FROM PATIENT p
INNER JOIN PAT_INS pi ON p.Patient_ID = pi.Patient_ID
LEFT JOIN CARRIER c ON pi.Carrier_Code = c.Carrier_Code
WHERE pi.Carrier_Code IS NOT NULL
""".strip()


def _norm_empty(val: Any) -> str | None:
    """Honest empty→NULL; never invent member/payer IDs."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _normalize_relationship_code(raw: Any) -> str | None:
    code = _norm_empty(raw)
    if not code:
        return None
    return _REL_CODE_MAP.get(code.upper(), code.upper())


def _termination_still_active(termination_date: str | None, *, today: str | None = None) -> bool:
    """NICE: skip policies terminated before today when date is parseable."""
    term = _norm_empty(termination_date)
    if not term:
        return True
    day = today or datetime.now(timezone.utc).date().isoformat()
    digits = re.sub(r"[^0-9]", "", term)
    if len(digits) >= 8:
        iso = f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
        try:
            return iso >= day[:10]
        except Exception:
            return True
    return True


def discover_insurance_tables(odbc_conn) -> list[dict[str, str]]:
    """Read-only catalog search for SoftDent insurance/carrier tables."""
    cur = odbc_conn.cursor()
    try:
        try:
            cur.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'TABLE' AND (UPPER(TABLE_NAME) LIKE ? OR UPPER(TABLE_NAME) LIKE ?)",
                ("%INS%", "%CARR%"),
            )
            rows = cur.fetchall()
            if rows:
                return [{"table": str(r[0])} for r in rows]
        except Exception:
            pass
        cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'TABLE'")
        return [{"table": str(r[0])} for r in cur.fetchall()]
    except Exception as exc:
        return [{"error": str(exc)}]


def lookup_carrier_payer_id(
    sqlite_conn: sqlite3.Connection, *, practice_id: str, carrier_code: str | None
) -> str | None:
    """SHOULD: map SoftDent carrier_code → Availity payerId when EDI code missing."""
    code = _norm_empty(carrier_code)
    if not code or not _table_exists(sqlite_conn, "sd_carrier_payer_map"):
        return None
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        SELECT payer_id FROM sd_carrier_payer_map
        WHERE practice_id = ? AND carrier_code = ? LIMIT 1
        """,
        (practice_id or "", code),
    )
    row = cur.fetchone()
    return _norm_empty(row[0]) if row else None


def upsert_carrier_payer_map(
    sqlite_conn: sqlite3.Connection,
    *,
    practice_id: str,
    carrier_code: str,
    payer_id: str,
    insurance_name: str | None = None,
) -> None:
    ensure_sd_schema(sqlite_conn)
    sqlite_conn.execute(
        """
        INSERT INTO sd_carrier_payer_map (practice_id, carrier_code, payer_id, insurance_name, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(practice_id, carrier_code) DO UPDATE SET
            payer_id=excluded.payer_id,
            insurance_name=COALESCE(excluded.insurance_name, sd_carrier_payer_map.insurance_name),
            updated_at=excluded.updated_at
        """,
        (
            practice_id or "",
            str(carrier_code).strip(),
            str(payer_id).strip(),
            _norm_empty(insurance_name),
            _utc_now(),
        ),
    )


def resolve_insurance_odbc_query() -> str:
    env_sql = os.environ.get("SOFTDENT_ODBC_INSURANCE_QUERY", "").strip()
    if env_sql:
        return env_sql
    discovery = load_discovery_suggested_env()
    suggested = str(discovery.get("SOFTDENT_ODBC_INSURANCE_QUERY") or "").strip()
    return suggested or DEFAULT_INSURANCE_ODBC_QUERY


def extract_patient_insurance(
    odbc_conn,
    sqlite_conn: sqlite3.Connection,
    practice_id: str = "",
    *,
    dry_run: bool = False,
    sql: str | None = None,
) -> int:
    """Extract insurance policies from SoftDent → sd_patient_insurance.

    Honest: empty strings stored as NULL. No invented payer/member IDs.
    SoftDent READ-ONLY (SELECT only on ODBC).
    """
    ensure_sd_schema(sqlite_conn)
    extracted_at = _utc_now()
    count = 0
    query = (sql or resolve_insurance_odbc_query()).strip()
    if not query:
        return 0

    cur_odbc = odbc_conn.cursor()
    cur_odbc.execute(query)
    cols = [str(desc[0]) for desc in (cur_odbc.description or [])]
    practice = str(practice_id or "").strip()

    for row in cur_odbc.fetchall():
        row_dict = {cols[i]: row[i] for i in range(len(cols))}
        patient_id = _norm_empty(
            row_dict.get("patient_id") or row_dict.get("Patient_ID") or row_dict.get("PatientID")
        )
        if not patient_id:
            continue

        try:
            priority = int(row_dict.get("priority") or 1)
        except (TypeError, ValueError):
            priority = 1
        if priority < 1:
            priority = 1

        member_id = _norm_empty(row_dict.get("member_id") or row_dict.get("Member_ID") or row_dict.get("PolicyNumber"))
        subscriber_id = _norm_empty(row_dict.get("subscriber_id") or row_dict.get("Subscriber_ID"))
        subscriber_name = _norm_empty(row_dict.get("subscriber_name") or row_dict.get("Subscriber_Name"))
        relationship_code = _normalize_relationship_code(
            row_dict.get("relationship_code") or row_dict.get("Relationship")
        )
        carrier_code = _norm_empty(row_dict.get("carrier_code") or row_dict.get("Carrier_Code"))
        insurance_name = _norm_empty(
            row_dict.get("insurance_name") or row_dict.get("Carrier_Name") or row_dict.get("InsuranceCompany")
        )
        payer_id = _norm_empty(row_dict.get("payer_id") or row_dict.get("EDI_Code") or row_dict.get("PayerId"))
        group_number = _norm_empty(row_dict.get("group_number") or row_dict.get("Group_Num") or row_dict.get("GroupNumber"))
        group_name = _norm_empty(row_dict.get("group_name") or row_dict.get("Group_Name"))
        effective_date = _norm_empty(row_dict.get("effective_date") or row_dict.get("Effective_Date"))
        termination_date = _norm_empty(row_dict.get("termination_date") or row_dict.get("Termination_Date"))

        if not _termination_still_active(termination_date):
            continue

        if not payer_id and carrier_code:
            payer_id = lookup_carrier_payer_id(sqlite_conn, practice_id=practice, carrier_code=carrier_code)

        if dry_run:
            count += 1
            continue

        sqlite_conn.execute(
            """
            INSERT INTO sd_patient_insurance (
                practice_id, patient_id, priority, member_id, subscriber_id,
                subscriber_name, relationship_code, carrier_code, insurance_name,
                payer_id, group_number, group_name, effective_date, termination_date, extracted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(practice_id, patient_id, priority) DO UPDATE SET
                member_id=excluded.member_id,
                subscriber_id=excluded.subscriber_id,
                subscriber_name=excluded.subscriber_name,
                relationship_code=excluded.relationship_code,
                carrier_code=excluded.carrier_code,
                insurance_name=excluded.insurance_name,
                payer_id=excluded.payer_id,
                group_number=excluded.group_number,
                group_name=excluded.group_name,
                effective_date=excluded.effective_date,
                termination_date=excluded.termination_date,
                extracted_at=excluded.extracted_at
            """,
            (
                practice,
                patient_id,
                priority,
                member_id,
                subscriber_id,
                subscriber_name,
                relationship_code,
                carrier_code,
                insurance_name,
                payer_id,
                group_number,
                group_name,
                effective_date,
                termination_date,
                extracted_at,
            ),
        )
        count += 1

    if not dry_run:
        sqlite_conn.commit()
    return count


def resolve_insurance_csv_path() -> Path | None:
    configured = _env_path("SOFTDENT_INSURANCE_CSV_PATH")
    if configured and configured.is_file():
        return configured
    roots: list[Path] = []
    try:
        from import_sync import SOFTDENT_FINANCIAL_EXPORTS, _softdent_direct_read_roots

        if SOFTDENT_FINANCIAL_EXPORTS:
            roots.append(Path(SOFTDENT_FINANCIAL_EXPORTS))
        roots.extend(_softdent_direct_read_roots())
    except Exception:
        pass
    patterns = (
        "patient_insurance*.csv",
        "PatientInsurance*.csv",
        "insurance_patients*.csv",
        "*patient*insurance*.csv",
    )
    matches: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in patterns:
            matches.extend(root.glob(pattern))
    files = [p for p in matches if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda item: item.stat().st_mtime)


def load_insurance_csv(
    csv_path: Path,
    sqlite_conn: sqlite3.Connection,
    practice_id: str = "",
) -> int:
    """SHOULD: ingest SoftDent Financial Export Patient Insurance CSV."""
    ensure_sd_schema(sqlite_conn)
    if not csv_path or not Path(csv_path).is_file():
        return 0
    extracted_at = _utc_now()
    practice = str(practice_id or "").strip()
    count = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            patient_id = _norm_empty(
                row.get("PatientID")
                or row.get("Patient ID")
                or row.get("patient_id")
                or row.get("PatID")
            )
            if not patient_id:
                continue
            member_id = _norm_empty(
                row.get("PolicyNumber")
                or row.get("Member ID")
                or row.get("MemberID")
                or row.get("member_id")
            )
            insurance_name = _norm_empty(
                row.get("InsuranceCompany")
                or row.get("Insurance Company")
                or row.get("Carrier")
                or row.get("insurance_name")
            )
            carrier_code = _norm_empty(row.get("CarrierCode") or row.get("Carrier Code") or row.get("carrier_code"))
            payer_id = _norm_empty(row.get("PayerID") or row.get("Payer Id") or row.get("EDI_Code") or row.get("payer_id"))
            group_number = _norm_empty(row.get("GroupNumber") or row.get("Group Number") or row.get("group_number"))
            priority_raw = row.get("Priority") or row.get("InsType") or "1"
            try:
                priority = 2 if str(priority_raw).strip().upper() in ("2", "SEC", "SECONDARY") else 1
            except Exception:
                priority = 1
            if not payer_id and carrier_code:
                payer_id = lookup_carrier_payer_id(sqlite_conn, practice_id=practice, carrier_code=carrier_code)
            term = _norm_empty(row.get("TerminationDate") or row.get("termination_date"))
            if not _termination_still_active(term):
                continue
            sqlite_conn.execute(
                """
                INSERT INTO sd_patient_insurance (
                    practice_id, patient_id, priority, member_id, insurance_name,
                    carrier_code, payer_id, group_number, termination_date, extracted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(practice_id, patient_id, priority) DO UPDATE SET
                    member_id=excluded.member_id,
                    insurance_name=excluded.insurance_name,
                    carrier_code=excluded.carrier_code,
                    payer_id=excluded.payer_id,
                    group_number=excluded.group_number,
                    termination_date=excluded.termination_date,
                    extracted_at=excluded.extracted_at
                """,
                (
                    practice,
                    patient_id,
                    priority,
                    member_id,
                    insurance_name,
                    carrier_code,
                    payer_id,
                    group_number,
                    term,
                    extracted_at,
                ),
            )
            count += 1
    sqlite_conn.commit()
    return count


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
        allowed = frozenset(SD_TABLES)
        for table in SD_TABLES:
            if table not in allowed or not _table_exists(conn, table):
                out[table] = 0
                continue
            cur = conn.cursor()
            # Whitelist-only table name from SD_TABLES (not user input).
            cur.execute("SELECT COUNT(*) FROM {}".format(table))
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
                (practice_id, patient_id, appt_date, provider_code, status, appt_time, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("", patient_id, proc_date, provider_code, "seen", "", extracted_at),
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
            try:
                from softdent_outstanding_claims_bridge import ensure_sd_claims_bridge_columns

                ensure_sd_claims_bridge_columns(conn)
            except Exception:
                pass
            bal_raw = str(row.get("Balance") or row.get("balance") or "").replace(",", "").replace("$", "").strip()
            try:
                balance = float(bal_raw) if bal_raw else None
            except ValueError:
                balance = None
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_claims
                (claim_id, patient_name, payer, service_date, claim_amount, claim_status,
                 practice_id, extracted_at, total_fee, balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    amount,
                    balance,
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
            if not sql or table == "sd_patient_insurance":
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
                    try:
                        from softdent_outstanding_claims_bridge import ensure_sd_claims_bridge_columns

                        ensure_sd_claims_bridge_columns(conn)
                    except Exception:
                        pass
                    amount = float(mapping.get("claim_amount") or mapping.get("ClaimAmount") or 0)
                    total_fee_raw = mapping.get("total_fee") or mapping.get("TotalFee") or mapping.get("Fee")
                    balance_raw = mapping.get("balance") or mapping.get("Balance") or mapping.get("AmountDue")
                    try:
                        total_fee = float(total_fee_raw) if total_fee_raw not in (None, "") else amount
                    except (TypeError, ValueError):
                        total_fee = amount
                    try:
                        balance = float(balance_raw) if balance_raw not in (None, "") else None
                    except (TypeError, ValueError):
                        balance = None
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sd_claims
                        (claim_id, patient_name, payer, service_date, claim_amount, claim_status,
                         practice_id, extracted_at, total_fee, balance)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(mapping.get("claim_id") or mapping.get("ClaimID") or mapping.get("ClaimId") or ""),
                            str(mapping.get("patient_name") or mapping.get("PatientName") or ""),
                            str(mapping.get("payer") or mapping.get("Payer") or ""),
                            str(mapping.get("service_date") or mapping.get("ServiceDate") or ""),
                            amount,
                            str(mapping.get("claim_status") or mapping.get("ClaimStatus") or ""),
                            str(mapping.get("practice_id") or mapping.get("PracticeID") or ""),
                            extracted_at,
                            total_fee,
                            balance,
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
                    appt_time = _normalize_appt_time_value(
                        mapping.get("appt_time")
                        or mapping.get("ApptTime")
                        or mapping.get("AppointmentTime")
                        or mapping.get("Time")
                        or ""
                    )
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sd_appointments
                        (practice_id, patient_id, appt_date, provider_code, status, appt_time, extracted_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(mapping.get("practice_id") or mapping.get("PracticeID") or ""),
                            str(mapping.get("patient_id") or mapping.get("PatientID") or ""),
                            str(mapping.get("appt_date") or mapping.get("ApptDate") or mapping.get("AppointmentDate") or ""),
                            str(mapping.get("provider_code") or mapping.get("ProviderCode") or ""),
                            str(mapping.get("status") or mapping.get("Status") or ""),
                            appt_time,
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

        # Moonshot SoftDent insurance extract (MUST) — separate path; honest NULLs
        try:
            discovered = discover_insurance_tables(odbc_conn)
            _set_meta(
                conn,
                "insurance_discovered_tables",
                json.dumps([d.get("table") for d in discovered if d.get("table")][:40]),
            )
        except Exception as disc_exc:
            _set_meta(conn, "insurance_discovery_error", str(disc_exc)[:400])
        try:
            ins_count = extract_patient_insurance(odbc_conn, conn, practice_id="")
            result["tables"]["sd_patient_insurance"] = ins_count
            _set_meta(conn, "insurance_extracted_count", str(ins_count))
            _set_meta(conn, "insurance_extracted_at", extracted_at)
            _set_meta(conn, "insurance_extract_error", "")
        except Exception as ins_exc:
            result["tables"]["sd_patient_insurance"] = 0
            _set_meta(conn, "insurance_extract_error", str(ins_exc)[:500])
            # Continue — do not fail entire ODBC extract for insurance alone

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


def _sensei_plan_array(insco_entity: dict[str, Any]) -> list[dict[str, Any]]:
    plan_array = insco_entity.get("PlanArray")
    if not isinstance(plan_array, dict):
        return []
    raw = plan_array.get("ArrayOfPLAN")
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    plans: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        plan = item.get("PLAN") if isinstance(item.get("PLAN"), dict) else item
        if isinstance(plan, dict):
            plans.append(plan)
    return plans


def load_sensei_plan_carrier_map(root: Path) -> dict[str, dict[str, str | None]]:
    """Map InsurancePlanKey → carrier fields from Sensei Reference insco_*.json (read-only)."""
    out: dict[str, dict[str, str | None]] = {}
    for path in _iter_sensei_entity_files(root, "insco"):
        entity = _load_sensei_entity(path, "INSURCO")
        if not entity:
            continue
        carrier_code = _norm_empty(entity.get("Id") or entity.get("InsCo"))
        carrier_name = _norm_empty(entity.get("Name") or entity.get("InsCoName"))
        for plan in _sensei_plan_array(entity):
            plan_id = _norm_empty(plan.get("Id") or plan.get("PlanId"))
            if not plan_id:
                continue
            plan_name = _norm_empty(plan.get("Name"))
            plan_insco = _norm_empty(plan.get("InsCo")) or carrier_code
            # Prefer InsCo display name; fall back to plan product name. Never invent.
            insurance_name = carrier_name or plan_name
            out[plan_id] = {
                "carrier_code": plan_insco or carrier_code,
                "insurance_name": insurance_name,
                "payer_id": None,  # honest: no invented EDI/Availity IDs
                "group_number": _norm_empty(plan.get("GroupNo")),
                "plan_name": plan_name,
            }
    return out


def _sensei_coverage_priority(policy: dict[str, Any]) -> int:
    raw = policy.get("CoverageType")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 1
    if value < 1:
        return 1
    if value > 3:
        return 3
    return value


def _sensei_patient_chart_ids(entity: dict[str, Any]) -> list[str]:
    """SoftDent chart / interface ids used in daysheet claim MRNs (distinct from UniqueID)."""
    ids: list[str] = []
    for key in ("Id", "InterfaceId", "ChartNo", "ulAccountId"):
        value = _norm_empty(entity.get(key))
        if value and value not in ids:
            ids.append(value)
    return ids


def _upsert_patient_insurance_row(
    conn: sqlite3.Connection,
    *,
    practice_id: str,
    patient_id: str,
    priority: int,
    member_id: str | None,
    subscriber_id: str | None,
    relationship_code: str | None,
    carrier_code: str | None,
    insurance_name: str | None,
    payer_id: str | None,
    group_number: str | None,
    extracted_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO sd_patient_insurance (
            practice_id, patient_id, priority, member_id, subscriber_id,
            subscriber_name, relationship_code, carrier_code, insurance_name,
            payer_id, group_number, group_name, effective_date, termination_date, extracted_at
        ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?)
        ON CONFLICT(practice_id, patient_id, priority) DO UPDATE SET
            member_id=excluded.member_id,
            subscriber_id=excluded.subscriber_id,
            relationship_code=excluded.relationship_code,
            carrier_code=excluded.carrier_code,
            insurance_name=excluded.insurance_name,
            payer_id=excluded.payer_id,
            group_number=excluded.group_number,
            extracted_at=excluded.extracted_at
        """,
        (
            practice_id or "",
            patient_id,
            priority,
            member_id,
            subscriber_id,
            relationship_code,
            carrier_code,
            insurance_name,
            payer_id,
            group_number,
            extracted_at,
        ),
    )


def populate_sensei_patient_insurance(
    conn: sqlite3.Connection,
    root: Path,
    *,
    extracted_at: str | None = None,
    practice_id: str = "",
) -> dict[str, int]:
    """Populate sd_patient_insurance (+ carrier map names) from Sensei patient policies.

    Keys rows by UniqueID and by chart Id so daysheet claim MRNs can resolve payers.
    Never invents member/payer IDs — empty Sensei fields stay NULL.
    """
    ensure_sd_schema(conn)
    at = extracted_at or _utc_now()
    plan_map = load_sensei_plan_carrier_map(root)
    insurance_rows = 0
    carriers_named = 0
    policies_seen = 0
    policies_resolved = 0

    for path in _iter_sensei_entity_files(root, "patient"):
        entity = _load_sensei_entity(path, SENSEI_ENTITY_WRAPPERS["patient"])
        if not entity:
            continue
        unique_id = _sensei_patient_id(entity)
        if not unique_id:
            continue
        policies = entity.get("InsurancePolicies")
        if not isinstance(policies, list) or not policies:
            continue

        patient_keys = [unique_id]
        for chart in _sensei_patient_chart_ids(entity):
            if chart not in patient_keys:
                patient_keys.append(chart)

        # One row per priority; primary dental first.
        by_priority: dict[int, dict[str, Any]] = {}
        for policy in policies:
            if not isinstance(policy, dict):
                continue
            policies_seen += 1
            plan_key = _norm_empty(policy.get("InsurancePlanKey") or policy.get("PlanId"))
            if not plan_key:
                continue
            carrier = plan_map.get(plan_key) or {}
            insurance_name = _norm_empty(carrier.get("insurance_name"))
            if not insurance_name:
                continue
            policies_resolved += 1
            priority = _sensei_coverage_priority(policy)
            if priority in by_priority:
                continue
            member_id = _norm_empty(policy.get("MemberId") or policy.get("MemberID"))
            subscriber_id = _norm_empty(policy.get("PolicyHolderKey"))
            relationship_code = _normalize_relationship_code(
                policy.get("RelationshipToPolicyHolderType") or policy.get("Relationship")
            )
            carrier_code = _norm_empty(carrier.get("carrier_code"))
            group_number = _norm_empty(policy.get("GroupNo") or carrier.get("group_number"))
            by_priority[priority] = {
                "member_id": member_id,
                "subscriber_id": subscriber_id,
                "relationship_code": relationship_code,
                "carrier_code": carrier_code,
                "insurance_name": insurance_name,
                "group_number": group_number,
            }

        for priority, row in by_priority.items():
            for patient_key in patient_keys:
                _upsert_patient_insurance_row(
                    conn,
                    practice_id=practice_id,
                    patient_id=patient_key,
                    priority=priority,
                    member_id=row["member_id"],
                    subscriber_id=row["subscriber_id"],
                    relationship_code=row["relationship_code"],
                    carrier_code=row["carrier_code"],
                    insurance_name=row["insurance_name"],
                    payer_id=None,
                    group_number=row["group_number"],
                    extracted_at=at,
                )
                insurance_rows += 1
            if row.get("carrier_code") and row.get("insurance_name"):
                # Name-only map entry; payer_id stays unset (no invented EDI).
                carriers_named += 1

    conn.commit()
    _set_meta(conn, "sensei_insurance_at", at)
    _set_meta(conn, "sensei_insurance_rows", str(insurance_rows))
    _set_meta(conn, "sensei_insurance_policies_seen", str(policies_seen))
    _set_meta(conn, "sensei_insurance_policies_resolved", str(policies_resolved))
    _set_meta(conn, "sensei_plan_map_size", str(len(plan_map)))
    return {
        "sd_patient_insurance": insurance_rows,
        "policies_seen": policies_seen,
        "policies_resolved": policies_resolved,
        "plan_map_size": len(plan_map),
        "carriers_touched": carriers_named,
    }


def _normalize_patient_name_key(name: str | None) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    if "," in text:
        last, _, rest = text.partition(",")
        first = rest.strip().split()[0] if rest.strip() else ""
        return f"{last.strip()}|{first}"
    parts = text.split()
    if len(parts) >= 2:
        return f"{parts[-1]}|{parts[0]}"
    return text


def extract_claim_chart_from_id(claim_id: str | None) -> str | None:
    match = _CLAIM_CHART_RE.match(str(claim_id or "").strip())
    return match.group(1) if match else None


def attribute_sd_claims_payers_from_insurance(
    conn: sqlite3.Connection,
    *,
    practice_id: str = "",
) -> dict[str, int]:
    """Set sd_claims.payer from sd_patient_insurance when payer is generic Insurance.

    Match order: claim chart (DS-…-{chart}-…) → patient_id; else patient_name key via
    sd_patients → insurance. Does not overwrite already-named payers. No invented carriers.
    """
    ensure_sd_schema(conn)
    if not _table_exists(conn, "sd_claims") or not _table_exists(conn, "sd_patient_insurance"):
        return {"updated": 0, "skipped_named": 0, "unmatched": 0}

    practice = practice_id or ""
    ins_rows = conn.execute(
        """
        SELECT patient_id, priority, insurance_name
        FROM sd_patient_insurance
        WHERE practice_id = ? AND insurance_name IS NOT NULL AND TRIM(insurance_name) != ''
        ORDER BY patient_id, priority
        """,
        (practice,),
    ).fetchall()
    primary_by_patient: dict[str, str] = {}
    for patient_id, _priority, insurance_name in ins_rows:
        pid = str(patient_id or "").strip()
        name = str(insurance_name or "").strip()
        if not pid or not name or pid in primary_by_patient:
            continue
        primary_by_patient[pid] = name

    name_to_patient: dict[str, str] = {}
    if _table_exists(conn, "sd_patients"):
        for pid, pname in conn.execute(
            "SELECT patient_id, patient_name FROM sd_patients WHERE practice_id = ?",
            (practice,),
        ).fetchall():
            key = _normalize_patient_name_key(str(pname or ""))
            if key and key not in name_to_patient:
                name_to_patient[key] = str(pid or "").strip()

    updated = 0
    skipped_named = 0
    unmatched = 0
    claims = conn.execute(
        """
        SELECT claim_id, patient_name, payer, practice_id
        FROM sd_claims
        WHERE practice_id = ?
        """,
        (practice,),
    ).fetchall()
    for claim_id, patient_name, payer, claim_practice in claims:
        if not _is_generic_payer_label(str(payer or "")):
            skipped_named += 1
            continue
        carrier = None
        chart = extract_claim_chart_from_id(str(claim_id or ""))
        if chart and chart in primary_by_patient:
            carrier = primary_by_patient[chart]
        if not carrier:
            name_key = _normalize_patient_name_key(str(patient_name or ""))
            patient_id = name_to_patient.get(name_key, "")
            if patient_id and patient_id in primary_by_patient:
                carrier = primary_by_patient[patient_id]
        if not carrier:
            unmatched += 1
            continue
        conn.execute(
            """
            UPDATE sd_claims
            SET payer = ?
            WHERE practice_id = ? AND claim_id = ?
            """,
            (carrier, claim_practice or practice, claim_id),
        )
        updated += 1
    conn.commit()
    _set_meta(conn, "claims_payer_attribution_at", _utc_now())
    _set_meta(conn, "claims_payer_attribution_updated", str(updated))
    _set_meta(conn, "claims_payer_attribution_unmatched", str(unmatched))
    return {"updated": updated, "skipped_named": skipped_named, "unmatched": unmatched}


def refresh_claims_payer_attribution(
    *,
    db_path: Path | str | None = None,
    sensei_root: Path | str | None = None,
) -> dict[str, Any]:
    """Sensei insurance populate (when available) + attribute generic sd_claims payers."""
    target = Path(db_path) if db_path else resolve_sd_sqlite_db()
    result: dict[str, Any] = {
        "ok": False,
        "dbPath": str(target) if target else None,
        "insurance": {},
        "attribution": {},
    }
    if not target:
        result["error"] = "no_sqlite_target"
        return result
    root = Path(sensei_root) if sensei_root else resolve_sensei_datasync_root()
    conn = sqlite3.connect(str(target))
    try:
        ensure_sd_schema(conn)
        if root and root.is_dir():
            result["insurance"] = populate_sensei_patient_insurance(conn, root)
            result["senseiRoot"] = str(root)
        else:
            result["warnings"] = ["sensei_datasync_root_missing"]
        result["attribution"] = attribute_sd_claims_payers_from_insurance(conn)
        try:
            result["claimsExport"] = export_sd_claims_to_inbox_csv(conn)
        except Exception as exc:  # noqa: BLE001
            result["claimsExport"] = {"ok": False, "error": str(exc)}
        ins_count = int(
            conn.execute("SELECT COUNT(*) FROM sd_patient_insurance").fetchone()[0] or 0
        )
        named = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM sd_claims
                WHERE payer IS NOT NULL AND TRIM(payer) != ''
                  AND LOWER(TRIM(payer)) NOT IN ('insurance', 'unknown', 'n/a', '-', '—')
                """
            ).fetchone()[0]
            or 0
        )
        result["sd_patient_insurance_count"] = ins_count
        result["namedPayerClaimCount"] = named
        result["ok"] = ins_count > 0 and int(result["attribution"].get("updated") or 0) >= 0
        conn.commit()
    finally:
        conn.close()
    return result


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
        appt_time = _normalize_appt_time_value(entity.get("Time") or entity.get("ApptTime") or "")
        conn.execute(
            """
            INSERT OR REPLACE INTO sd_appointments
            (practice_id, patient_id, appt_date, provider_code, status, appt_time, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("", patient_id, appt_date, provider_code, status, appt_time, extracted_at),
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

    try:
        ins = populate_sensei_patient_insurance(conn, root, extracted_at=extracted_at)
        counts["sd_patient_insurance"] = int(ins.get("sd_patient_insurance") or 0)
    except Exception:
        counts["sd_patient_insurance"] = 0

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

        # SHOULD: CSV fallback for patient insurance when ODBC insurance empty/unavailable
        try:
            csv_path = resolve_insurance_csv_path()
            if csv_path:
                csv_count = load_insurance_csv(csv_path, conn, practice_id="")
                fallback_counts["sd_patient_insurance"] = (
                    int(fallback_counts.get("sd_patient_insurance") or 0) + csv_count
                )
                _set_meta(conn, "insurance_csv_path", str(csv_path))
                _set_meta(conn, "insurance_csv_count", str(csv_count))
                _set_meta(conn, "insurance_csv_at", extracted_at)
        except Exception as csv_exc:
            _set_meta(conn, "insurance_csv_error", str(csv_exc)[:400])
            result["warnings"].append(f"insurance_csv:{csv_exc}")

        # Attribute generic "Insurance" claim payers from sd_patient_insurance (Sensei/ODBC/CSV).
        try:
            result["payerAttribution"] = attribute_sd_claims_payers_from_insurance(conn)
        except Exception as attr_exc:  # noqa: BLE001
            result["payerAttribution"] = {"ok": False, "error": str(attr_exc)}
            result["warnings"].append(f"payer_attribution:{attr_exc}")

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
