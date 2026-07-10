"""
NR2 Apex Claims aging tiles + Narratives insurance context (Moonshot C1–C7).
Import-backed only — never invents claim IDs, patient names, dates, or dollars.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

STORE_KEY_NARR_AUDIT = "nr2:v2:narratives:audit"
STORE_KEY_NARR_CONTEXT = "nr2:v2:narratives:context"
STORE_KEY_AGING_ALERTS = "nr2:v2:claims:aging-alerts"
STORE_KEY_PAYER_TEMPLATES = "nr2:v2:narratives:payer-templates"

# Bucket labels match operator request: 30 / 60 / 90 day shelves
BUCKET_30 = "30"  # 30–59 days
BUCKET_60 = "60"  # 60–89 days
BUCKET_90 = "90"  # 90+ days


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _store():
    from document_sync import NR2_DATA_DIR
    from local_store import LocalStore

    return LocalStore(NR2_DATA_DIR)


def _load_json(key: str) -> dict[str, Any]:
    try:
        store = _store()
        raw = store.get(key)
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}
    return {}


def _save_json(key: str, payload: dict[str, Any]) -> None:
    store = _store()
    store.set(key, json.dumps(payload))


def append_narrative_audit(event: str, detail: dict[str, Any] | None = None) -> None:
    try:
        data = _load_json(STORE_KEY_NARR_AUDIT)
        entries = data.get("entries") if isinstance(data.get("entries"), list) else []
        entries.append(
            {
                "id": str(uuid.uuid4())[:8],
                "at": _utc_now(),
                "event": str(event or ""),
                "detail": detail if isinstance(detail, dict) else {},
            }
        )
        data["entries"] = entries[-200:]
        _save_json(STORE_KEY_NARR_AUDIT, data)
    except Exception:
        pass
    try:
        from apex_cpa_pack import append_audit

        append_audit(f"narrative:{event}", detail if isinstance(detail, dict) else {})
    except Exception:
        pass


def list_narrative_audit(limit: int = 40) -> list[dict[str, Any]]:
    data = _load_json(STORE_KEY_NARR_AUDIT)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    return list(reversed(entries[-max(1, min(limit, 200)) :]))


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        val = row.get(key)
        if val is None or val == "":
            continue
        s = str(val).strip()
        if s:
            return s
    return ""


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("$", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _age_days_from_row(row: dict[str, Any], *, as_of: datetime | None = None) -> int | None:
    """Prefer explicit Age/Days; else compute from DOS if parseable. Never invent."""
    days = _parse_int(
        row.get("Age") or row.get("Days") or row.get("AgingDays") or row.get("ageDays") or row.get("AgeDays")
    )
    if days is not None and days >= 0:
        return days
    date_s = _pick(row, ("ServiceDate", "Date", "DOS", "ClaimDate", "serviceDate", "date"))
    if not date_s:
        return None
    parsed = None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(date_s[:10], fmt)
            break
        except Exception:
            continue
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(date_s.replace("Z", "+00:00").split("T")[0])
        except Exception:
            return None
    ref = as_of or datetime.now(timezone.utc).replace(tzinfo=None)
    delta = (ref.date() - parsed.date()).days
    return delta if delta >= 0 else None


def bucket_for_age(age_days: int | None) -> str | None:
    if age_days is None:
        return None
    if age_days >= 90:
        return BUCKET_90
    if age_days >= 60:
        return BUCKET_60
    if age_days >= 30:
        return BUCKET_30
    return None


def normalize_claim_row(row: dict[str, Any], *, as_of: datetime | None = None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    claim_id = _pick(
        row,
        ("ClaimId", "ClaimID", "Claim #", "Claim#", "claimId", "ClaimNumber", "claim_id", "Id", "ID"),
    )
    patient = _pick(row, ("PatientName", "Patient", "patientName", "Patient Name", "Name"))
    date_s = _pick(row, ("ServiceDate", "Date", "DOS", "ClaimDate", "serviceDate", "date"))
    if not claim_id and not patient and not date_s:
        return None
    if not claim_id:
        # Stable local key from available fields — still import-backed, not invented clinical ID
        claim_id = f"ROW-{abs(hash((patient, date_s, _pick(row, ('Payer', 'Status'))))) % 10_000_000:07d}"
    age = _age_days_from_row(row, as_of=as_of)
    status = _pick(row, ("ClaimStatus", "Status", "status", "claimStatus")) or "Unknown"
    payer = _pick(row, ("Payer", "Insurance", "Carrier", "payer", "InsuranceCompany")) or None
    procs_raw = _pick(row, ("ProcCodes", "Procedures", "ProcedureCodes", "CDT", "Codes"))
    procedures = [p.strip() for p in re.split(r"[,;|/]+", procs_raw) if p.strip()] if procs_raw else None
    billed = _parse_money(row.get("ClaimAmount") or row.get("Billed") or row.get("Amount") or row.get("billedAmount"))
    return {
        "claimId": claim_id,
        "patientName": patient or "—",
        "date": date_s or "",
        "ageDays": age,
        "bucket": bucket_for_age(age),
        "payer": payer,
        "status": status,
        "procedures": procedures,
        "billedAmount": billed,
        "source": "softdent-import",
    }


def build_aging_buckets(
    rows: list[dict[str, Any]],
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {BUCKET_30: [], BUCKET_60: [], BUCKET_90: []}
    missing_age = 0
    normalized: list[dict[str, Any]] = []
    for row in rows:
        tile = normalize_claim_row(row, as_of=as_of)
        if not tile:
            continue
        normalized.append(tile)
        b = tile.get("bucket")
        if b in buckets:
            buckets[b].append(tile)
        elif tile.get("ageDays") is None:
            missing_age += 1

    def _sort_key(t: dict[str, Any]) -> tuple[int, str]:
        age = t.get("ageDays")
        return (-(age if isinstance(age, int) else -1), str(t.get("claimId") or ""))

    for key in buckets:
        buckets[key].sort(key=_sort_key)

    return {
        "buckets": buckets,
        "counts": {k: len(v) for k, v in buckets.items()},
        "totalClaims": len(normalized),
        "missingAgeField": missing_age > 0 and (len(buckets[BUCKET_30]) + len(buckets[BUCKET_60]) + len(buckets[BUCKET_90])) == 0,
        "missingAgeCount": missing_age,
        "claims": normalized,
        "available": bool(normalized),
        "lastImport": _utc_now(),
    }


def find_claim_by_id(rows: list[dict[str, Any]], claim_id: str) -> dict[str, Any] | None:
    want = str(claim_id or "").strip()
    if not want:
        return None
    for row in rows:
        tile = normalize_claim_row(row)
        if tile and str(tile.get("claimId") or "") == want:
            tile = dict(tile)
            tile["importedAt"] = _utc_now()
            return tile
    return None


def clinical_note_summaries(rows: list[dict[str, Any]], *, limit: int = 80) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows[: max(1, min(limit, 200))]):
        if not isinstance(row, dict):
            continue
        note_id = _pick(row, ("NoteId", "NoteID", "Id", "ID", "ClinicalNoteId")) or f"NOTE-{i + 1}"
        patient = _pick(row, ("PatientName", "Patient", "patientName", "Name"))
        date_s = _pick(row, ("Date", "NoteDate", "ServiceDate", "CreatedAt"))
        provider = _pick(row, ("Provider", "ProviderName", "Doctor"))
        body = _pick(row, ("Note", "Notes", "Text", "Content", "ClinicalNote", "Body"))
        snippet = (body[:120] + ("…" if len(body) > 120 else "")) if body else ""
        out.append(
            {
                "noteId": note_id,
                "patientName": patient or "—",
                "date": date_s or "",
                "provider": provider or None,
                "snippet": snippet,
                "text": body,
            }
        )
    return out


def insurance_payers_from_claims(claim_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in claim_rows:
        tile = normalize_claim_row(row)
        if not tile:
            continue
        payer = tile.get("payer")
        if not payer:
            continue
        key = str(payer).strip().lower()
        if key not in seen:
            seen[key] = {"payerId": key, "payerName": str(payer).strip(), "claimCount": 0}
        seen[key]["claimCount"] = int(seen[key]["claimCount"]) + 1
    return sorted(seen.values(), key=lambda p: (-int(p["claimCount"]), str(p["payerName"])))


def save_narrative_context(payload: dict[str, Any]) -> dict[str, Any]:
    clinical_ids = payload.get("clinicalNoteIds") if isinstance(payload.get("clinicalNoteIds"), list) else []
    claim_id = str(payload.get("claimId") or "").strip() or None
    payer_id = str(payload.get("payerId") or payload.get("payerName") or "").strip() or None
    context_id = str(uuid.uuid4())[:12]
    record = {
        "contextId": context_id,
        "clinicalNoteIds": [str(x) for x in clinical_ids if str(x).strip()],
        "claimId": claim_id,
        "payerId": payer_id,
        "lockedAt": _utc_now(),
    }
    try:
        data = _load_json(STORE_KEY_NARR_CONTEXT)
        sessions = data.get("sessions") if isinstance(data.get("sessions"), dict) else {}
        sessions[context_id] = record
        if len(sessions) > 40:
            for old in list(sessions.keys())[: len(sessions) - 40]:
                sessions.pop(old, None)
        data["sessions"] = sessions
        data["latest"] = context_id
        _save_json(STORE_KEY_NARR_CONTEXT, data)
    except Exception:
        pass
    return {"ok": True, "contextId": context_id, "context": record}


def get_narrative_context(context_id: str | None = None) -> dict[str, Any] | None:
    data = _load_json(STORE_KEY_NARR_CONTEXT)
    sessions = data.get("sessions") if isinstance(data.get("sessions"), dict) else {}
    cid = str(context_id or data.get("latest") or "").strip()
    if not cid:
        return None
    row = sessions.get(cid)
    return row if isinstance(row, dict) else None


NARRATIVE_TYPES = ("appeal", "medical-necessity", "attachment-cover", "prior-auth")

# Operator-maintained appeal language by payer family (placeholders only — no invented clinical facts).
# Operators may override via LocalStore key nr2:v2:narratives:payer-templates.
DEFAULT_PAYER_APPEAL_TEMPLATES: dict[str, dict[str, str]] = {
    "delta dental": {
        "payerKey": "delta-dental",
        "displayName": "Delta Dental",
        "match": "delta",
        "body": (
            "Re: Appeal / Request for Reconsideration — Delta Dental\n"
            "Claim: {{claimId}}\nPatient: {{patientName}}\nDate of service: {{dos}}\n"
            "Current status (import): {{status}}\n\n"
            "Dear Delta Dental Claims Review,\n\n"
            "We respectfully request reconsideration of the determination on the above claim"
            "{{denialClause}}.\n\n"
            "Clinical documentation from SoftDent import:\n{{clinicalNotes}}\n\n"
            "Procedure codes on claim (import): {{procedures}}\n\n"
            "Please review the enclosed chart notes and advise if additional documentation is required "
            "under Delta Dental's appeal guidelines.\n\n"
            "Sincerely,\n[Provider / Office — operator complete]\n"
        ),
    },
    "guardian": {
        "payerKey": "guardian",
        "displayName": "Guardian",
        "match": "guardian",
        "body": (
            "Re: Appeal of Benefit Determination — Guardian\n"
            "Claim #: {{claimId}} · Member/Patient: {{patientName}} · DOS: {{dos}}\n\n"
            "Dear Guardian Dental Claims,\n\n"
            "Please reconsider the denial/adjustment on this claim"
            "{{denialClause}}. The clinical record supports the services billed.\n\n"
            "Supporting SoftDent clinical notes:\n{{clinicalNotes}}\n\n"
            "CDT / procedures (import): {{procedures}}\n\n"
            "Kindly confirm receipt and the expected review timeline.\n\n"
            "Respectfully,\n[Provider / Office — operator complete]\n"
        ),
    },
    "metlife": {
        "payerKey": "metlife",
        "displayName": "MetLife",
        "match": "metlife",
        "body": (
            "Re: MetLife Dental Claim Appeal\n"
            "Claim ID: {{claimId}}\nPatient: {{patientName}}\nService date: {{dos}}\n"
            "Import status: {{status}}\n\n"
            "To MetLife Dental Claims Appeals:\n\n"
            "We are appealing the decision on this claim"
            "{{denialClause}} and request full reconsideration based on the clinical documentation below.\n\n"
            "{{clinicalNotes}}\n\n"
            "Billed procedures (import): {{procedures}}\n\n"
            "Please contact our office if radiographs or narratives beyond the SoftDent notes are required.\n\n"
            "Sincerely,\n[Provider / Office — operator complete]\n"
        ),
    },
    "bcbs": {
        "payerKey": "bcbs",
        "displayName": "Blue Cross Blue Shield",
        "match": "bcbs|blue cross|bluecross",
        "body": (
            "Re: BCBS Dental Appeal — Claim {{claimId}}\n"
            "Patient: {{patientName}} · DOS: {{dos}}\n\n"
            "Dear Blue Cross Blue Shield Dental Claims,\n\n"
            "We request reconsideration of this claim"
            "{{denialClause}}.\n\n"
            "Clinical notes (SoftDent import):\n{{clinicalNotes}}\n\n"
            "Procedures (import): {{procedures}}\n\n"
            "Thank you for your prompt review.\n\n"
            "Sincerely,\n[Provider / Office — operator complete]\n"
        ),
    },
    "generic": {
        "payerKey": "generic",
        "displayName": "Generic Payer",
        "match": "",
        "body": (
            "Re: Appeal / reconsideration — Claim {{claimId}}\n"
            "Patient: {{patientName}}\nDate of service: {{dos}}\n"
            "Payer: {{payer}}\nCurrent status (import): {{status}}\n\n"
            "Dear Claims Review Department,\n\n"
            "We respectfully request reconsideration of the above claim"
            "{{denialClause}}.\n\n"
            "Clinical documentation on file (SoftDent import):\n{{clinicalNotes}}\n\n"
            "Procedures on claim (import): {{procedures}}\n\n"
            "Please advise if additional documentation is required.\n\n"
            "Sincerely,\n[Provider / Office — operator complete]\n"
        ),
    },
}


def _normalize_payer_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).strip()


def list_payer_appeal_templates() -> list[dict[str, Any]]:
    """Built-in + operator overrides (operator body wins when present)."""
    overrides = {}
    try:
        data = _load_json(STORE_KEY_PAYER_TEMPLATES)
        items = data.get("templates") if isinstance(data.get("templates"), dict) else {}
        overrides = items
    except Exception:
        overrides = {}
    out: list[dict[str, Any]] = []
    for key, base in DEFAULT_PAYER_APPEAL_TEMPLATES.items():
        row = dict(base)
        ov = overrides.get(key) if isinstance(overrides.get(key), dict) else None
        if ov and str(ov.get("body") or "").strip():
            row["body"] = str(ov["body"])
            row["operatorMaintained"] = True
        else:
            row["operatorMaintained"] = False
        row["id"] = key
        out.append(row)
    # Extra operator-only payers
    for key, ov in overrides.items():
        if key in DEFAULT_PAYER_APPEAL_TEMPLATES or not isinstance(ov, dict):
            continue
        if not str(ov.get("body") or "").strip():
            continue
        out.append(
            {
                "id": key,
                "payerKey": str(ov.get("payerKey") or key),
                "displayName": str(ov.get("displayName") or key.title()),
                "match": str(ov.get("match") or key),
                "body": str(ov["body"]),
                "operatorMaintained": True,
            }
        )
    return out


def save_payer_appeal_template(payload: dict[str, Any]) -> dict[str, Any]:
    """Operator upsert for a payer appeal template body (local store only)."""
    key = _normalize_payer_key(str(payload.get("id") or payload.get("payerKey") or payload.get("displayName") or ""))
    body = str(payload.get("body") or "").strip()
    if not key or not body:
        return {"ok": False, "error": "id/payerKey and body are required."}
    data = _load_json(STORE_KEY_PAYER_TEMPLATES)
    templates = data.get("templates") if isinstance(data.get("templates"), dict) else {}
    templates[key] = {
        "payerKey": str(payload.get("payerKey") or key),
        "displayName": str(payload.get("displayName") or key.title()),
        "match": str(payload.get("match") or key),
        "body": body,
        "updatedAt": _utc_now(),
    }
    data["templates"] = templates
    try:
        _save_json(STORE_KEY_PAYER_TEMPLATES, data)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "id": key, "template": templates[key]}


def resolve_payer_appeal_template(payer_name: str | None) -> dict[str, Any]:
    templates = list_payer_appeal_templates()
    needle = _normalize_payer_key(payer_name or "")
    if needle:
        for row in templates:
            if row.get("id") == "generic":
                continue
            match = str(row.get("match") or row.get("id") or "")
            if match and re.search(match, needle, re.I):
                return row
            display = _normalize_payer_key(str(row.get("displayName") or ""))
            if display and display in needle:
                return row
    for row in templates:
        if row.get("id") == "generic":
            return row
    return DEFAULT_PAYER_APPEAL_TEMPLATES["generic"]


def render_payer_template(body: str, fields: dict[str, str]) -> str:
    text = str(body or "")
    for key, val in fields.items():
        text = text.replace("{{" + key + "}}", val if val else "—")
    # Clear any leftover placeholders
    text = re.sub(r"\{\{[a-zA-Z0-9_]+\}\}", "—", text)
    return text


SECTION_ALIASES = {
    "intro": ("intro", "introduction"),
    "findings": ("findings", "finding", "clinical findings"),
    "treatment": ("treatment", "treatment plan", "plan"),
    "notes": ("notes", "clinical notes", "note"),
    "followup": ("followup", "follow-up", "follow up"),
    "insurance": ("insurance", "appeal", "payer", "insurance narrative"),
}


def parse_voice_narrative_command(query: str) -> dict[str, Any] | None:
    """
    Parse voice/text commands into narrative composer actions.
    Examples:
      dictate findings: fracture on #14
      append to insurance narrative: please reconsider
      HAL, write in notes: probing depths reviewed
      replace treatment with: crown #19
    """
    raw = str(query or "").strip()
    if not raw:
        return None
    q = raw.lower()
    # Must look like a dictate/append/write narrative command
    if not re.search(
        r"\b(dictate|append|write|voice|narrat|say into|put in|replace)\b",
        q,
    ):
        return None
    # Avoid stealing tax scrubber voice
    if re.search(r"\b(salary|ebitda|depreciat|scrubber|scenario)\b", q):
        return None

    mode = "append"
    if re.search(r"\breplace\b", q):
        mode = "replace"

    section = "notes"
    for sid, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", q):
                section = sid
                break

    text = ""
    m = re.search(
        r"(?:dictate|append|write|say into|put in|voice(?:\s+to)?|narrat\w*)"
        r"(?:\s+(?:to|into|in|for))?"
        r"(?:\s+(?:the\s+)?"
        + r"(?:intro|introduction|findings?|treatment(?:\s+plan)?|notes?|clinical notes?|follow[- ]?up|insurance(?:\s+narrative)?|appeal|payer)"
        + r")?"
        r"(?:\s+section)?"
        r"(?:\s+with)?"
        r"\s*[:\-–]\s*(.+)$",
        raw,
        re.I | re.S,
    )
    if m:
        text = m.group(1).strip().strip("\"'")
    else:
        m2 = re.search(r"\breplace\s+\w+(?:\s+\w+)?\s+with\s*[:\-]?\s*(.+)$", raw, re.I | re.S)
        if m2:
            text = m2.group(1).strip().strip("\"'")
            mode = "replace"
    if not text or len(text) < 2:
        return None
    # Cap length — voice dumps shouldn't invent novels
    if len(text) > 4000:
        text = text[:4000]
    return {
        "section": section,
        "text": text,
        "mode": mode,
    }


def generate_insurance_narrative(
    *,
    narrative_type: str,
    claim: dict[str, Any] | None,
    notes: list[dict[str, Any]],
    payer_name: str | None,
    denial_reason: str | None,
    attachments: list[str] | None,
    operator_consent: bool,
    build_id: str,
    template_id: str | None = None,
) -> dict[str, Any]:
    """Compose draft from import-backed context only. Requires consent. Always needs human review."""
    ntype = str(narrative_type or "").strip().lower()
    if ntype not in NARRATIVE_TYPES:
        return {"ok": False, "error": f"Unknown narrative type. Use one of: {', '.join(NARRATIVE_TYPES)}"}
    if not operator_consent:
        return {"ok": False, "error": "Operator consent required before generating an insurance narrative."}

    claim_id = str((claim or {}).get("claimId") or "").strip()
    patient = str((claim or {}).get("patientName") or "").strip()
    dos = str((claim or {}).get("date") or "").strip()
    status = str((claim or {}).get("status") or "").strip()
    procs = (claim or {}).get("procedures") if isinstance((claim or {}).get("procedures"), list) else []
    payer = (payer_name or (claim or {}).get("payer") or "").strip() or "the insurance carrier"

    note_bodies = []
    note_ids = []
    for n in notes:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("noteId") or "").strip()
        if nid:
            note_ids.append(nid)
        body = str(n.get("text") or n.get("snippet") or "").strip()
        if body:
            note_bodies.append(body)

    # Honesty: if no clinical text and no claim, refuse rather than invent
    if not claim_id and not note_bodies:
        return {
            "ok": False,
            "error": "Lock import-backed clinical notes and/or a claim before generating an insurance narrative.",
        }

    denial = (denial_reason or "").strip()
    attach_list = [str(a).strip() for a in (attachments or []) if str(a).strip()]
    clinical_block = (
        "\n---\n".join(note_bodies)
        if note_bodies
        else "[No clinical note text selected — operator must insert notes before submit.]"
    )
    proc_block = ", ".join(str(p) for p in procs) if procs else "— (not present on import)"
    denial_clause = f" denied for: {denial}" if denial else ""

    template_used = None
    if ntype == "appeal":
        if template_id:
            template_used = next(
                (t for t in list_payer_appeal_templates() if t.get("id") == template_id or t.get("payerKey") == template_id),
                None,
            )
        if not template_used:
            template_used = resolve_payer_appeal_template(payer)
        draft = render_payer_template(
            str(template_used.get("body") or ""),
            {
                "claimId": claim_id or "[claim id from import]",
                "patientName": patient or "[patient from import]",
                "dos": dos or "[DOS from import]",
                "status": status or "—",
                "payer": payer,
                "clinicalNotes": clinical_block,
                "procedures": proc_block,
                "denialClause": denial_clause,
                "denialReason": denial or "—",
            },
        )
    elif ntype == "medical-necessity":
        draft = (
            f"Medical Necessity Narrative\n"
            f"Claim: {claim_id or '—'} · Patient: {patient or '—'} · DOS: {dos or '—'}\n"
            f"Payer: {payer}\n\n"
            f"Clinical findings and justification (from selected SoftDent notes):\n"
            f"{clinical_block}\n\n"
            f"Procedure codes (import): {proc_block}\n"
            f"Diagnosis codes: [operator insert only codes present in chart — not invented]\n"
        )
    elif ntype == "attachment-cover":
        draft = (
            f"Attachment Cover Letter\n"
            f"Claim {claim_id or '—'} · Patient {patient or '—'} · DOS {dos or '—'}\n"
            f"Payer: {payer}\n\n"
            f"Enclosed please find the following supporting documentation:\n"
            + ("\n".join(f"- {a}" for a in attach_list) if attach_list else "- [Operator list attachments]\n")
            + "\n\n"
            f"These materials support the services rendered as documented in SoftDent clinical notes"
            + (f" ({', '.join(note_ids)})" if note_ids else "")
            + ".\n"
        )
    else:  # prior-auth
        draft = (
            f"Prior Authorization Request\n"
            f"Patient: {patient or '—'} · Proposed DOS / plan date: {dos or '[operator]'}\n"
            f"Payer: {payer}\n"
            f"Related claim reference (if any): {claim_id or '—'}\n\n"
            f"Clinical justification (SoftDent notes):\n{clinical_block}\n\n"
            f"Requested procedures (import or operator): {proc_block}\n"
        )

    sources = []
    if claim_id:
        sources.append(f"claim:{claim_id}")
    sources.extend(f"note:{nid}" for nid in note_ids)
    if payer:
        sources.append(f"payer:{payer}")
    if template_used:
        sources.append(f"template:{(template_used.get('id') or template_used.get('payerKey'))}")

    footer = (
        f"\n\n---\nGenerated from NR2 import · Build {build_id} · {_utc_now()}\n"
        f"Sources: {', '.join(sources) if sources else 'none'}\n"
        f"DRAFT — requires human review before submission to any payer. Dollar amounts never invented.\n"
    )
    draft_text = draft.rstrip() + footer

    append_narrative_audit(
        "insurance_narrative_generate",
        {
            "type": ntype,
            "claimId": claim_id or None,
            "noteIds": note_ids,
            "payer": payer,
            "consent": True,
            "sourcesCited": sources,
            "templateId": (template_used or {}).get("id") if template_used else None,
        },
    )

    return {
        "ok": True,
        "draftText": draft_text,
        "sourcesCited": sources,
        "generatedAt": _utc_now(),
        "requiresHumanReview": True,
        "type": ntype,
        "status": "draft",
        "templateId": (template_used or {}).get("id") if template_used else None,
        "templateName": (template_used or {}).get("displayName") if template_used else None,
    }


def get_aging_alert_config() -> dict[str, Any]:
    data = _load_json(STORE_KEY_AGING_ALERTS)
    return {
        "threshold60": int(data.get("threshold60") or 5),
        "threshold90": int(data.get("threshold90") or 3),
        "enabled": bool(data.get("enabled", True)),
    }


def set_aging_alert_config(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = get_aging_alert_config()
    if "threshold60" in payload:
        cfg["threshold60"] = max(0, int(payload["threshold60"]))
    if "threshold90" in payload:
        cfg["threshold90"] = max(0, int(payload["threshold90"]))
    if "enabled" in payload:
        cfg["enabled"] = bool(payload["enabled"])
    _save_json(STORE_KEY_AGING_ALERTS, cfg)
    return {"ok": True, "config": cfg}


def apply_aging_threshold_alerts(widgets: list[dict[str, Any]], aging: dict[str, Any]) -> None:
    cfg = get_aging_alert_config()
    if not cfg.get("enabled"):
        return
    counts = aging.get("counts") if isinstance(aging.get("counts"), dict) else {}
    c60 = int(counts.get(BUCKET_60) or 0)
    c90 = int(counts.get(BUCKET_90) or 0)
    for w in widgets:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("id") or "")
        if wid == "claims-aging-60" and c60 >= int(cfg["threshold60"]):
            w["alert"] = True
            w["alertReason"] = f"{c60} claims aged 60–89 days (threshold {cfg['threshold60']})"
        if wid == "claims-aging-90" and c90 >= int(cfg["threshold90"]):
            w["alert"] = True
            w["alertReason"] = f"{c90} claims aged 90+ days (threshold {cfg['threshold90']})"


def shelf_widget(bucket: str, tiles: list[dict[str, Any]], *, missing_age: bool) -> dict[str, Any]:
    labels = {
        BUCKET_30: "30-Day Claims",
        BUCKET_60: "60-Day Claims",
        BUCKET_90: "90-Day Claims",
    }
    ranges = {
        BUCKET_30: "30–59 days",
        BUCKET_60: "60–89 days",
        BUCKET_90: "90+ days",
    }
    has = bool(tiles)
    empty_msg = (
        f"No claims aged {ranges.get(bucket, bucket)} in current SoftDent import"
        if not missing_age
        else "Import SoftDent claims with Age/Days (or ServiceDate) to populate aging buckets"
    )
    return {
        "id": f"claims-aging-{bucket}",
        "type": "claim-shelf",
        "label": labels.get(bucket, f"{bucket}-Day Claims"),
        "size": "full",
        "bucket": bucket,
        "tiles": tiles,
        "count": len(tiles),
        "status": "ok" if has else "empty",
        "emptyMessage": empty_msg,
        "hint": f"Import-backed SoftDent claims · {ranges.get(bucket, '')} · click tile for detail · HAL can focus this shelf.",
        "bulkSelect": True,
        "halChips": [
            {"label": f"Focus {bucket}-day", "query": f"Focus {bucket}-day claims"},
            {"label": "Sync & refill", "query": "Sync imports and populate the widgets"},
        ],
    }
