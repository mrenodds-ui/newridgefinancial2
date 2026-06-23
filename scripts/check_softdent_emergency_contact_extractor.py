from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


LOG_PATH = Path(r"C:\ProgramData\Sensei Gateway Client\Logs\Sensei Gateway Client_20260616.jsonl")
IMPORT_REPORT_PATH = Path(r"C:\SoftDentFinancialExports\softdent_financial_source_hunt\datasync_financial_import_report.json")
INCREMENTAL_STATE_PATH = Path(r"C:\SoftDentFinancialExports\softdent_incremental_state.json")
EC_SCHEMA_PATH = Path(
    r"C:\ProgramData\Sensei Gateway Client\DataAdapters\SoftDent\Scripts\PrepareLocalDB\Tables\PatientEmergencyContact.sqlite"
)
EC_QUERY_PATH = Path(
    r"C:\ProgramData\Sensei Gateway Client\DataAdapters\SoftDent\Scripts\Extraction\EmergencyContact.sqlite"
)

TIME_PATTERN = re.compile(r'"@t":"([^"]+)"')
MESSAGE_PATTERNS = {
    "emergency_contact_errors": "Error creating Emergency Contact",
    "queue_failures": "Failed to read message from agent command queue",
    "signalr_connected": "SignalR service connected.",
    "signalr_disconnected": "SignalR disconnected.",
    "transaction_mentions": "Transaction",
}


@dataclass
class TimeWindow:
    start: str | None = None
    end: str | None = None


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_time(line: str) -> str | None:
    match = TIME_PATTERN.search(line)
    return match.group(1) if match else None


def parse_schema_columns(path: Path) -> list[str]:
    columns: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("["):
            continue
        name = line.split("]", 1)[0].lstrip("[")
        columns.append(name)
    return columns


def summarize_log(path: Path, after_hour: int = 18) -> dict:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    counts = {key: 0 for key in MESSAGE_PATTERNS}
    late_counts = {key: 0 for key in MESSAGE_PATTERNS}
    windows = {key: TimeWindow() for key in MESSAGE_PATTERNS}
    recent_matches: list[str] = []

    for line in lines:
        timestamp = extract_time(line)
        hour = None
        if timestamp:
            try:
                hour = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).hour
            except ValueError:
                hour = None

        matched = False
        for key, needle in MESSAGE_PATTERNS.items():
            if needle not in line:
                continue
            matched = True
            counts[key] += 1
            if hour is not None and hour >= after_hour:
                late_counts[key] += 1
            if windows[key].start is None and timestamp:
                windows[key].start = timestamp
            if timestamp:
                windows[key].end = timestamp
        if matched:
            recent_matches.append(line)

    return {
        "counts": counts,
        "late_day_counts": late_counts,
        "time_windows": {key: {"start": value.start, "end": value.end} for key, value in windows.items()},
        "recent_matches": recent_matches[-20:],
    }


def main() -> int:
    schema_columns = parse_schema_columns(EC_SCHEMA_PATH)
    ordinal_23 = schema_columns[23] if len(schema_columns) > 23 else None
    import_report = read_json(IMPORT_REPORT_PATH)
    incremental_state = read_json(INCREMENTAL_STATE_PATH)
    log_summary = summarize_log(LOG_PATH)

    summary = {
        "artifacts": {
            "log_path": str(LOG_PATH),
            "import_report_path": str(IMPORT_REPORT_PATH),
            "incremental_state_path": str(INCREMENTAL_STATE_PATH),
            "emergency_contact_query_path": str(EC_QUERY_PATH),
            "emergency_contact_schema_path": str(EC_SCHEMA_PATH),
        },
        "emergency_contact": {
            "query": EC_QUERY_PATH.read_text(encoding="utf-8").strip(),
            "schema_column_count": len(schema_columns),
            "ordinal_23_column": ordinal_23,
        },
        "import_report": {
            "generated_utc": import_report.get("generated_utc"),
            "entities_requested": import_report.get("entities_requested"),
            "transaction_diagnostic": import_report.get("transaction_diagnostic"),
            "patient_plan_import": import_report.get("patient_plan_import"),
            "appointment_import": import_report.get("appointment_import"),
        },
        "incremental_state": incremental_state,
        "sensei_log": log_summary,
        "assessment": {
            "local_pipeline_working": bool(import_report.get("generated_utc")) and incremental_state.get("updatedAt") is not None,
            "live_transaction_feed_present": bool(import_report.get("transaction_diagnostic", {}).get("rows_seen")),
            "likely_extractec_null_field": ordinal_23,
            "recommended_vendor_fix": "Handle NULL SoftDentEmergencyContactTextBoxValue safely in ExtractEC via IsDBNull or SQL COALESCE.",
        },
    }

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())