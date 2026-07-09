#!/usr/bin/env python3
"""Discover SoftDent SQL Server schema and suggest NR2 ODBC query env vars."""

from __future__ import annotations

import argparse
import json
import os
import re
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

# Preferred SoftDent table names when keyword match is ambiguous.
PREFERRED_TABLE_NAMES = {
    "sd_claims": ("claims", "claim", "insclaim", "insuranceclaim"),
    "sd_patients": ("patient", "patients"),
    "sd_procedures": ("procedures", "procedure", "proclog"),
    "sd_payments": ("payments", "payment"),
    "sd_appointments": ("appointments", "appointment", "appts"),
    "sd_providers": ("providers", "provider", "dentist"),
    "sd_adjustments": ("adjustments", "adjustment", "adjust"),
}

# Logical alias → candidate physical column names (case-insensitive).
COLUMN_CANDIDATES: dict[str, dict[str, tuple[str, ...]]] = {
    "sd_claims": {
        "claim_id": ("claimid", "claim_id", "claimno", "claim_number", "claimnumber", "id"),
        "patient_name": ("patientname", "patient_name", "patname", "fullname", "name"),
        "payer": ("payer", "insco", "insurance", "carrier", "inscompany", "ins_co", "planname"),
        "service_date": ("servicedate", "service_date", "procdate", "dateofservice", "dos", "claimdate"),
        "claim_amount": ("claimamount", "claim_amount", "amount", "billed", "total", "fee"),
        "claim_status": ("claimstatus", "claim_status", "status", "claimstate"),
    },
    "sd_patients": {
        "patient_id": ("patientid", "patient_id", "patid", "id"),
        "patient_name": ("patientname", "patient_name", "fullname", "name"),
        "first_visit_date": ("firstvisitdate", "first_visit_date", "firstvisit"),
        "last_visit_date": ("lastvisitdate", "last_visit_date", "lastvisit"),
    },
    "sd_procedures": {
        "patient_id": ("patientid", "patient_id", "patid"),
        "proc_date": ("procdate", "proc_date", "date"),
        "ada_code": ("adacode", "ada_code", "code", "proccode"),
        "tooth": ("tooth",),
        "surface": ("surface",),
        "provider_code": ("providerid", "providercode", "provider_code", "provider"),
        "description": ("description", "desc"),
        "production": ("production", "amount", "fee"),
    },
    "sd_payments": {
        "patient_id": ("patientid", "patient_id", "patid"),
        "payment_date": ("paymentdate", "payment_date", "date"),
        "amount": ("amount", "payment"),
        "payer": ("payer", "insco", "insurance"),
        "method": ("method", "paymethod", "type"),
    },
    "sd_appointments": {
        "patient_id": ("patientid", "patient_id", "patid"),
        "appt_date": ("apptdate", "appt_date", "appointmentdate", "date"),
        "provider_code": ("providercode", "provider_code", "providerid"),
        "status": ("status",),
    },
    "sd_providers": {
        "provider_code": ("providercode", "provider_code", "providerid", "code", "id"),
        "provider_name": ("providername", "provider_name", "name"),
    },
    "sd_adjustments": {
        "patient_id": ("patientid", "patient_id", "patid"),
        "adj_date": ("adjdate", "adj_date", "date"),
        "ada_code": ("adacode", "ada_code", "code"),
        "amount": ("amount",),
        "description": ("description", "desc"),
    },
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

DATE_FILTER_COLUMNS = {
    "sd_claims": "service_date",
    "sd_procedures": "proc_date",
    "sd_payments": "payment_date",
    "sd_adjustments": "adj_date",
    "sd_appointments": "appt_date",
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
    matches: dict[str, list[str]] = {key: [] for key in KEYWORD_TABLES.values()}
    for key in matches:
        matches[key] = []
    for table in tables:
        lowered = table.lower()
        for keyword, slot in KEYWORD_TABLES.items():
            if keyword in lowered:
                matches[slot].append(table)
    for slot, names in matches.items():
        matches[slot] = sorted(set(names))
    return matches


def _pick_best_table(slot: str, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    preferred = PREFERRED_TABLE_NAMES.get(slot) or ()
    lowered = {c.lower(): c for c in candidates}
    for pref in preferred:
        if pref in lowered:
            return lowered[pref]
    # Prefer shortest exact-ish name
    return sorted(candidates, key=lambda t: (len(t), t.lower()))[0]


def _norm_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def _resolve_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    by_norm = {_norm_col(c): c for c in columns}
    for cand in candidates:
        hit = by_norm.get(_norm_col(cand))
        if hit:
            return hit
    # substring fallback for compound names
    for cand in candidates:
        needle = _norm_col(cand)
        if len(needle) < 3:
            continue
        for col in columns:
            if needle in _norm_col(col):
                return col
    return None


def _patient_name_expr(columns: list[str]) -> str | None:
    """Build patient_name expression from PatientName or LastName/FirstName."""
    last = _resolve_column(columns, ("lastname", "last_name", "lname"))
    first = _resolve_column(columns, ("firstname", "first_name", "fname"))
    if last and first:
        return f"[{last}] + ', ' + [{first}] AS patient_name"
    direct = _resolve_column(columns, ("patientname", "patient_name", "patname", "fullname", "name"))
    if direct:
        return f"[{direct}] AS patient_name"
    return None


def build_query_from_columns(slot: str, table: str, columns: list[str]) -> str | None:
    """Build a SELECT … AS alias query from discovered columns; None if required fields missing."""
    mapping = COLUMN_CANDIDATES.get(slot) or {}
    if not mapping or not table or not columns:
        return None
    select_parts: list[str] = []
    resolved_physical: dict[str, str] = {}
    for alias, candidates in mapping.items():
        if alias == "patient_name" and slot in {"sd_claims", "sd_patients"}:
            expr = _patient_name_expr(columns)
            if expr:
                select_parts.append(expr)
                resolved_physical[alias] = expr
            continue
        physical = _resolve_column(columns, candidates)
        if physical:
            select_parts.append(f"[{physical}] AS {alias}")
            resolved_physical[alias] = physical
    required = {
        "sd_claims": ("claim_id", "payer"),
        "sd_patients": ("patient_id",),
        "sd_procedures": ("patient_id", "proc_date"),
        "sd_payments": ("patient_id", "payment_date"),
        "sd_appointments": ("patient_id", "appt_date"),
        "sd_providers": ("provider_code",),
        "sd_adjustments": ("patient_id", "adj_date"),
    }.get(slot, ())
    for req in required:
        if req not in resolved_physical:
            return None
    if not select_parts:
        return None
    sql = f"SELECT {', '.join(select_parts)} FROM [{table}]"
    date_alias = DATE_FILTER_COLUMNS.get(slot)
    if date_alias and date_alias in resolved_physical:
        physical = resolved_physical[date_alias]
        if slot == "sd_appointments":
            sql += f" WHERE [{physical}] >= CAST(GETDATE() AS DATE)"
        else:
            sql += f" WHERE [{physical}] >= DATEADD(month, -24, GETDATE())"
    return sql


def suggest_queries_from_discovery(
    table_matches: dict[str, list[str]],
    column_samples: dict[str, list[str]],
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return suggestedEnv + metadata about which queries were column-built vs template."""
    suggested: dict[str, str] = {}
    meta: dict[str, Any] = {}
    for slot, env_key in ENV_KEY_BY_TABLE.items():
        candidates = table_matches.get(slot) or []
        best = _pick_best_table(slot, candidates)
        built = None
        if best and best in column_samples:
            built = build_query_from_columns(slot, best, column_samples[best])
        if built:
            suggested[env_key] = built
            meta[slot] = {"source": "columns", "table": best}
        else:
            suggested[env_key] = SUGGESTED_QUERIES[slot]
            meta[slot] = {"source": "template", "table": best}
    return suggested, meta


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
            for table in candidates[:3]:
                column_samples[table] = _list_columns(cursor, table)
        suggested_env, query_meta = suggest_queries_from_discovery(table_matches, column_samples)
        claims_meta = query_meta.get("sd_claims") or {}
        return {
            "ok": True,
            "dsn": odbc_dsn(),
            "tableCount": len(tables),
            "tables": tables[:200],
            "tableMatches": table_matches,
            "columnSamples": column_samples,
            "suggestedEnv": suggested_env,
            "queryMeta": query_meta,
            "claimsQueryReady": claims_meta.get("source") == "columns",
            "nextSteps": [
                "Copy suggestedEnv lines into repo .env (column-built queries preferred when discovery matched).",
                "Or set NR2_SOFTDENT_USE_DISCOVERY_QUERIES=1 so extract reads suggestedEnv from this JSON when env SQL is empty.",
                "SOFTDENT_ODBC_CLAIMS_QUERY is the highest-value query for named Payer labels (claim readiness / join).",
                "Set NR2_CONSENT_EXECUTOR=1 to allow POST /api/admin/extract-softdent-odbc.",
                "Run import_sync.py or sync from the SoftDent page to populate sd_* tables.",
            ],
        }
    except Exception as exc:
        return {"ok": False, "error": "discovery_failed", "message": str(exc)}
    finally:
        conn.close()


def default_discovery_path() -> Path:
    configured = os.environ.get("NR2_SOFTDENT_SCHEMA_DISCOVERY", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT.parent / candidate
        return candidate.resolve()
    return (ROOT.parent / "app_data" / "nr2" / "softdent_schema_discovery.json").resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover SoftDent ODBC schema for NR2 extract lane.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    parser.add_argument(
        "--out",
        default="",
        help="Write discovery JSON to this path (default: app_data/nr2/softdent_schema_discovery.json).",
    )
    args = parser.parse_args()
    result = discover()
    out_path = Path(args.out).expanduser() if args.out else default_discovery_path()
    if result.get("ok") and out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result["savedTo"] = str(out_path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
