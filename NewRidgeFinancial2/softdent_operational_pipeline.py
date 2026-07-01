"""Build SoftDent claims and clinical notes from live daysheet pipeline output."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_sync import (
    SAMPLE_PATIENT_MARKERS,
    SOFTDENT_FINANCIAL_EXPORTS,
    _find_newest,
    _is_sample_claims,
    _is_sample_clinical,
    _softdent_direct_read_roots,
)

INSURANCE_WRITEOFF_CODES = frozenset({"51"})
INSURANCE_PAYMENT_CODES = frozenset({"2"})
SKIP_CLINICAL_CODES = frozenset({"2", "11", "12", "17", "48", "60", "61"})
ACCOUNT_NAME_MARKERS = (" account",)


def resolve_daysheet_jsonl_path() -> Path | None:
    candidates: list[Path] = []
    for root in _softdent_direct_read_roots():
        found = _find_newest(root, ("daysheet.jsonl",))
        if found:
            candidates.append(found)
    direct = SOFTDENT_FINANCIAL_EXPORTS / "daysheet.jsonl"
    if direct.is_file():
        candidates.append(direct)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _parse_report_date(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def _money_value(raw: str) -> float | None:
    text = str(raw or "").strip()
    if not text or text in {"-", "—"}:
        return None
    cleaned = text.replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_account_name(name: str) -> bool:
    lowered = name.strip().lower()
    return any(marker in lowered for marker in ACCOUNT_NAME_MARKERS)


def _normalize_patient_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip())


def _iter_daysheet_transactions(formatted_rows: list[list[Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    report_date = ""

    for raw in formatted_rows or []:
        cells = [str(cell or "").strip() for cell in raw]
        while len(cells) < 15:
            cells.append("")

        joined = " ".join(part for part in cells if part).strip()
        if not joined:
            continue

        if cells[0] == "Daysheet" or cells[6] == "Daysheet":
            continue
        if cells[1] == "ID" and cells[2] == "Name":
            continue

        maybe_date = _parse_report_date(cells[0]) or _parse_report_date(cells[2]) or _parse_report_date(cells[6])
        if maybe_date and re.search(r"\d{4}", maybe_date):
            report_date = maybe_date
            continue

        patient_id = cells[1]
        patient_name = _normalize_patient_name(cells[2])
        code = cells[5]
        description = cells[6]
        production = _money_value(cells[7])
        transaction_note = cells[14]

        if patient_id and patient_name and not _is_account_name(patient_name):
            if code or description or production not in (None, 0):
                if current:
                    rows.append(current)
                current = {
                    "reportDate": report_date,
                    "patientId": patient_id,
                    "patientName": patient_name,
                    "providerId": cells[4] or "",
                    "code": code,
                    "description": description,
                    "production": production,
                    "transactionNote": transaction_note,
                    "detailLines": [],
                }
                continue

        if current and not patient_id and not patient_name:
            detail = description or transaction_note
            if detail:
                current["detailLines"].append(detail)
            continue

        if current:
            rows.append(current)
            current = None

    if current:
        rows.append(current)
    return rows


def _load_daysheet_transactions(path: Path) -> list[dict[str, Any]]:
    transactions: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            normalized = payload.get("normalized") if isinstance(payload, dict) else None
            report_date = ""
            if isinstance(normalized, dict):
                report_date = str(normalized.get("report_date") or "").strip()
            raw_row = payload.get("raw_row") if isinstance(payload, dict) else None
            formatted_rows = raw_row.get("formatted_report_rows") if isinstance(raw_row, dict) else None
            if not isinstance(formatted_rows, list):
                continue
            for row in _iter_daysheet_transactions(formatted_rows):
                if report_date and not row.get("reportDate"):
                    row["reportDate"] = report_date
                transactions.append(row)
    return transactions


def _clinical_note_text(row: dict[str, Any]) -> str:
    parts = [str(row.get("description") or "").strip()]
    parts.extend(str(item).strip() for item in row.get("detailLines") or [] if str(item).strip())
    note = str(row.get("transactionNote") or "").strip()
    if note:
        parts.append(note)
    return " ".join(part for part in parts if part).strip()


def build_clinical_notes_rows(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for idx, row in enumerate(transactions):
        code = str(row.get("code") or "").strip()
        if not code or code in SKIP_CLINICAL_CODES:
            continue
        if code in INSURANCE_WRITEOFF_CODES or code in INSURANCE_PAYMENT_CODES:
            continue
        patient = _normalize_patient_name(str(row.get("patientName") or ""))
        if not patient or patient.lower() in SAMPLE_PATIENT_MARKERS or _is_account_name(patient):
            continue
        note_text = _clinical_note_text(row)
        if not note_text:
            continue
        notes.append(
            {
                "PatientName": patient,
                "MRN": str(row.get("patientId") or ""),
                "NoteDate": str(row.get("reportDate") or ""),
                "Provider": f"Dr {row.get('providerId')}" if row.get("providerId") else "",
                "Procedure": str(row.get("description") or code),
                "ClinicalNote": note_text,
            }
        )
        if len(notes) >= 250:
            break
    return notes


def _claim_status_for_patient_day(
    patient_id: str,
    report_date: str,
    transactions: list[dict[str, Any]],
) -> str:
    same_day = [
        row
        for row in transactions
        if str(row.get("patientId") or "") == patient_id and str(row.get("reportDate") or "") == report_date
    ]
    codes = {str(row.get("code") or "").strip() for row in same_day}
    if codes & INSURANCE_PAYMENT_CODES:
        return "Paid"
    if codes & INSURANCE_WRITEOFF_CODES:
        return "Denied"
    return "Pending Review"


def build_claims_rows(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, row in enumerate(transactions):
        code = str(row.get("code") or "").strip()
        if not code or code in INSURANCE_PAYMENT_CODES or code in INSURANCE_WRITEOFF_CODES:
            continue
        if code in SKIP_CLINICAL_CODES:
            continue
        production = row.get("production")
        if production in (None, 0):
            continue
        patient = _normalize_patient_name(str(row.get("patientName") or ""))
        patient_id = str(row.get("patientId") or "")
        report_date = str(row.get("reportDate") or "")
        if not patient or not patient_id or not report_date:
            continue
        if patient.lower() in SAMPLE_PATIENT_MARKERS or _is_account_name(patient):
            continue
        claim_key = f"{patient_id}|{report_date}|{code}|{row.get('description') or ''}"
        if claim_key in seen:
            continue
        seen.add(claim_key)
        status = _claim_status_for_patient_day(patient_id, report_date, transactions)
        claim_id = f"DS-{report_date.replace('-', '')}-{patient_id}-{code}-{idx + 1}"
        claims.append(
            {
                "PatientName": patient,
                "MRN": patient_id,
                "ClaimId": claim_id,
                "ClaimStatus": status,
                "Payer": "Insurance",
                "Procedure": str(row.get("description") or code),
                "ServiceDate": report_date,
                "DenialReason": "Derived from daysheet insurance activity."
                if status == "Denied"
                else ("Insurance payment posted." if status == "Paid" else "Awaiting insurance response."),
                "ClaimAmount": f"{float(production):.2f}",
            }
        )
        if len(claims) >= 150:
            break
    return claims


def build_daysheet_clinical_dataset(path: Path | None = None) -> dict[str, Any] | None:
    path = path or resolve_daysheet_jsonl_path()
    if not path or not path.is_file():
        return None
    rows = build_clinical_notes_rows(_load_daysheet_transactions(path))
    if not rows or _is_sample_clinical(rows):
        return None
    return {
        "sourceFile": "softdent_clinical_notes_data.json",
        "sourcePath": str(path),
        "modifiedAt": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "rows": rows,
        "readSource": "direct",
        "sourceKind": "pipeline-daysheet",
    }


def build_daysheet_claims_dataset(path: Path | None = None) -> dict[str, Any] | None:
    path = path or resolve_daysheet_jsonl_path()
    if not path or not path.is_file():
        return None
    rows = build_claims_rows(_load_daysheet_transactions(path))
    if not rows or _is_sample_claims(rows):
        return None
    return {
        "sourceFile": "softdent_claims_export.csv",
        "sourcePath": str(path),
        "modifiedAt": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "rows": rows,
        "readSource": "direct",
        "sourceKind": "pipeline-daysheet",
    }
