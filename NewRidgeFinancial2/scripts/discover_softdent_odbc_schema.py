#!/usr/bin/env python3
"""Discover SoftDent SQL Server schema and suggest NR2 ODBC query env vars."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from softdent_odbc_extract import odbc_configured, odbc_dsn  # noqa: E402

KEYWORD_TABLES = {
    "patient": "sd_patients",
    "procedure": "sd_procedures",
    "payment": "sd_payments",
    "claim": "sd_claims",
    "appointment": "sd_appointments",
    "provider": "sd_providers",
    "adjust": "sd_adjustments",
}

SUGGESTED_QUERIES = {
    "sd_patients": (
        "SELECT PatientID AS patient_id, "
        "LastName + ', ' + FirstName AS patient_name, "
        "FirstVisitDate AS first_visit_date, LastVisitDate AS last_visit_date "
        "FROM Patient WHERE Active = 1"
    ),
    "sd_procedures": (
        "SELECT PatientID AS patient_id, ProcDate AS proc_date, ADACode AS ada_code, "
        "Tooth AS tooth, Surface AS surface, ProviderID AS provider_code, "
        "Description AS description, Production AS production "
        "FROM Procedures WHERE ProcDate >= DATEADD(month, -24, GETDATE())"
    ),
    "sd_payments": (
        "SELECT PatientID AS patient_id, PaymentDate AS payment_date, Amount AS amount, "
        "Payer AS payer, Method AS method "
        "FROM Payments WHERE PaymentDate >= DATEADD(month, -24, GETDATE())"
    ),
    "sd_claims": (
        "SELECT ClaimID AS claim_id, PatientName AS patient_name, Payer AS payer, "
        "ServiceDate AS service_date, ClaimAmount AS claim_amount, ClaimStatus AS claim_status "
        "FROM Claims WHERE ServiceDate >= DATEADD(month, -24, GETDATE())"
    ),
    "sd_appointments": (
        "SELECT PatientID AS patient_id, ApptDate AS appt_date, ProviderCode AS provider_code, "
        "Status AS status "
        "FROM Appointments WHERE ApptDate >= CAST(GETDATE() AS DATE)"
    ),
    "sd_providers": (
        "SELECT ProviderCode AS provider_code, ProviderName AS provider_name FROM Providers"
    ),
    "sd_adjustments": (
        "SELECT PatientID AS patient_id, AdjDate AS adj_date, ADACode AS ada_code, "
        "Amount AS amount, Description AS description "
        "FROM Adjustments WHERE AdjDate >= DATEADD(month, -24, GETDATE())"
    ),
}

ENV_KEY_BY_TABLE = {
    "sd_patients": "SOFTDENT_ODBC_PATIENTS_QUERY",
    "sd_procedures": "SOFTDENT_ODBC_PROCEDURES_QUERY",
    "sd_payments": "SOFTDENT_ODBC_PAYMENTS_QUERY",
    "sd_claims": "SOFTDENT_ODBC_CLAIMS_QUERY",
    "sd_appointments": "SOFTDENT_ODBC_APPOINTMENTS_QUERY",
    "sd_providers": "SOFTDENT_ODBC_PROVIDERS_QUERY",
    "sd_adjustments": "SOFTDENT_ODBC_ADJUSTMENTS_QUERY",
}


def _connect():
    import pyodbc

    dsn = odbc_dsn()
    user = os.environ.get("SOFTDENT_ODBC_USER", "").strip()
    password = os.environ.get("SOFTDENT_ODBC_PASSWORD", "").strip()
    timeout = int(os.environ.get("SOFTDENT_ODBC_TIMEOUT", "30"))
    parts = [f"DSN={dsn}"]
    if user:
        parts.append(f"UID={user}")
    if password:
        parts.append(f"PWD={password}")
    return pyodbc.connect(";".join(parts), timeout=timeout)


def _list_tables(cursor) -> list[str]:
    tables: list[str] = []
    for row in cursor.tables(tableType="TABLE"):
        name = str(row.table_name or "").strip()
        if name and not name.startswith("sys"):
            tables.append(name)
    return sorted(set(tables))


def _list_columns(cursor, table: str) -> list[str]:
    columns: list[str] = []
    for row in cursor.columns(table=table):
        name = str(row.column_name or "").strip()
        if name:
            columns.append(name)
    return columns


def _match_tables(tables: list[str]) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {key: [] for key in KEYWORD_TABLES}
    for table in tables:
        lowered = table.lower()
        for keyword, slot in KEYWORD_TABLES.items():
            if keyword in lowered:
                matches[slot].append(table)
    return matches


def discover() -> dict:
    if not odbc_configured():
        return {
            "ok": False,
            "error": "odbc_not_configured",
            "message": "Set SOFTDENT_ODBC_DSN or NR2_SOFTDENT_ODBC_DSN before running discovery.",
        }
    try:
        conn = _connect()
    except Exception as exc:
        return {"ok": False, "error": "odbc_connect_failed", "message": str(exc)}

    try:
        cursor = conn.cursor()
        tables = _list_tables(cursor)
        table_matches = _match_tables(tables)
        column_samples: dict[str, list[str]] = {}
        for candidates in table_matches.values():
            for table in candidates[:2]:
                column_samples[table] = _list_columns(cursor, table)
        suggested_env: dict[str, str] = {}
        for table, env_key in ENV_KEY_BY_TABLE.items():
            suggested_env[env_key] = SUGGESTED_QUERIES[table]
        return {
            "ok": True,
            "dsn": resolve_odbc_dsn(),
            "tableCount": len(tables),
            "tables": tables[:200],
            "tableMatches": table_matches,
            "columnSamples": column_samples,
            "suggestedEnv": suggested_env,
            "nextSteps": [
                "Copy suggestedEnv lines into repo .env (adjust table/column names from columnSamples).",
                "Set NR2_CONSENT_EXECUTOR=1 to allow POST /api/admin/extract-softdent-odbc.",
                "Run import_sync.py or sync from the SoftDent page to populate sd_* tables.",
            ],
        }
    except Exception as exc:
        return {"ok": False, "error": "discovery_failed", "message": str(exc)}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover SoftDent ODBC schema for NR2 extract lane.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    args = parser.parse_args()
    result = discover()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
