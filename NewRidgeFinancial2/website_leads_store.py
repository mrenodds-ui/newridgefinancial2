"""Website appointment-request leads (Gravity Forms → NR2 → HAL sidenotes)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def init_website_leads_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS website_leads (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL DEFAULT 'gravity_forms',
            external_id TEXT,
            name TEXT,
            email TEXT,
            phone TEXT,
            interests TEXT,
            preferred_time TEXT,
            preferred_days TEXT,
            heard_about TEXT,
            comments TEXT,
            raw_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            handled_at TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_website_leads_created ON website_leads(created_at DESC)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_website_leads_external "
        "ON website_leads(source, external_id) WHERE external_id IS NOT NULL AND external_id != ''"
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def webhook_secret_configured() -> str:
    return str(os.environ.get("NR2_WEBSITE_WEBHOOK_SECRET") or "").strip()


def webhook_secret_valid(provided: str | None) -> bool:
    expected = webhook_secret_configured()
    got = str(provided or "").strip()
    if not expected:
        # Dev/local: allow only when secret is unset (operator must set for public tunnel).
        return True
    if not got:
        return False
    return hmac.compare_digest(expected, got)


def _first_str(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key not in payload:
            continue
        val = payload.get(key)
        if val is None:
            continue
        if isinstance(val, (list, tuple)):
            parts = [str(x).strip() for x in val if str(x).strip()]
            if parts:
                return ", ".join(parts)
            continue
        text = str(val).strip()
        if text:
            return text
    return ""


def _looks_like_email(text: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text or ""))


def _looks_like_phone(text: str) -> bool:
    digits = re.sub(r"\D", "", text or "")
    return 7 <= len(digits) <= 15


def normalize_gravity_forms_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Map Gravity Forms webhook / entry JSON into a stable lead dict."""
    raw = dict(payload or {})
    # Nested entry payloads from some GF webhook plugins
    if isinstance(raw.get("entry"), dict):
        entry = dict(raw["entry"])
        for k, v in raw.items():
            if k != "entry" and k not in entry:
                entry[k] = v
        raw = entry

    name = _first_str(
        raw,
        "name",
        "Name",
        "Your Name",
        "full_name",
        "fullName",
        "1",
        "input_1",
    )
    email = _first_str(
        raw,
        "email",
        "Email",
        "Your E-mail Address",
        "Your Email Address",
        "e-mail",
        "2",
        "input_2",
    )
    phone = _first_str(
        raw,
        "phone",
        "Phone",
        "Your Phone Number",
        "telephone",
        "3",
        "input_3",
    )
    interests = _first_str(
        raw,
        "interests",
        "I am interested in",
        "interest",
        "4",
        "input_4",
    )
    preferred_time = _first_str(
        raw,
        "preferred_time",
        "Best Time for Appointment",
        "best_time",
        "5",
        "input_5",
    )
    preferred_days = _first_str(
        raw,
        "preferred_days",
        "Preferred Day of Week",
        "preferred_day",
        "6",
        "input_6",
    )
    heard_about = _first_str(
        raw,
        "heard_about",
        "How did you hear about us?",
        "source",
        "7",
        "input_7",
    )
    comments = _first_str(
        raw,
        "comments",
        "Comments/Questions",
        "message",
        "8",
        "input_8",
    )

    # Heuristic fallback: scan unlabeled string values
    if not name or not email:
        for key, val in raw.items():
            if key in ("form_id", "entry_id", "id", "status", "date_created", "ip", "source_url"):
                continue
            text = str(val).strip() if val is not None and not isinstance(val, (dict, list)) else ""
            if not text:
                continue
            if not email and _looks_like_email(text):
                email = text
            elif not phone and _looks_like_phone(text) and "@" not in text:
                phone = text
            elif not name and len(text) >= 2 and "@" not in text and not _looks_like_phone(text):
                # Prefer keys that look like name fields
                if re.search(r"name", str(key), re.I) or (not name and key in ("1", "input_1")):
                    name = text

    external_id = _first_str(raw, "entry_id", "id", "Entry Id", "entryId")
    form_id = _first_str(raw, "form_id", "formId", "Form Id")

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "interests": interests,
        "preferred_time": preferred_time,
        "preferred_days": preferred_days,
        "heard_about": heard_about,
        "comments": comments,
        "external_id": external_id,
        "form_id": form_id,
        "raw": raw,
    }


def format_lead_sidenote(lead: dict[str, Any]) -> str:
    name = str(lead.get("name") or "Unknown").strip() or "Unknown"
    bits = [f"WEB APPT REQUEST: {name}"]
    if lead.get("phone"):
        bits.append(str(lead["phone"]))
    if lead.get("email"):
        bits.append(str(lead["email"]))
    if lead.get("interests"):
        bits.append(f"want: {lead['interests']}")
    when_parts = [p for p in (lead.get("preferred_time"), lead.get("preferred_days")) if p]
    if when_parts:
        bits.append(f"when: {' / '.join(str(p) for p in when_parts)}")
    if lead.get("comments"):
        bits.append(f"note: {str(lead['comments'])[:120]}")
    text = " | ".join(bits)
    return text[:500]


def insert_website_lead(
    conn: sqlite3.Connection,
    *,
    normalized: dict[str, Any],
    source: str = "gravity_forms",
) -> dict[str, Any]:
    """Insert lead; returns existing row if external_id already stored (idempotent)."""
    external_id = str(normalized.get("external_id") or "").strip() or None
    source_key = str(source or "gravity_forms").strip() or "gravity_forms"
    if external_id:
        row = conn.execute(
            """
            SELECT id, source, external_id, name, email, phone, interests, preferred_time,
                   preferred_days, heard_about, comments, raw_json, status, created_at, handled_at
            FROM website_leads
            WHERE source = ? AND external_id = ?
            """,
            (source_key, external_id),
        ).fetchone()
        if row:
            return _row_to_lead(row, duplicate=True)

    lead_id = uuid.uuid4().hex
    created = _utc_now()
    raw_json = json.dumps(normalized.get("raw") or {}, ensure_ascii=False, default=str)
    conn.execute(
        """
        INSERT INTO website_leads (
            id, source, external_id, name, email, phone, interests, preferred_time,
            preferred_days, heard_about, comments, raw_json, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
        """,
        (
            lead_id,
            source_key,
            external_id,
            str(normalized.get("name") or "").strip() or None,
            str(normalized.get("email") or "").strip() or None,
            str(normalized.get("phone") or "").strip() or None,
            str(normalized.get("interests") or "").strip() or None,
            str(normalized.get("preferred_time") or "").strip() or None,
            str(normalized.get("preferred_days") or "").strip() or None,
            str(normalized.get("heard_about") or "").strip() or None,
            str(normalized.get("comments") or "").strip() or None,
            raw_json,
            created,
        ),
    )
    return {
        "id": lead_id,
        "source": source_key,
        "external_id": external_id,
        "name": normalized.get("name") or "",
        "email": normalized.get("email") or "",
        "phone": normalized.get("phone") or "",
        "interests": normalized.get("interests") or "",
        "preferred_time": normalized.get("preferred_time") or "",
        "preferred_days": normalized.get("preferred_days") or "",
        "heard_about": normalized.get("heard_about") or "",
        "comments": normalized.get("comments") or "",
        "status": "open",
        "created_at": created,
        "handled_at": None,
        "duplicate": False,
    }


def _row_to_lead(row: tuple, *, duplicate: bool = False) -> dict[str, Any]:
    return {
        "id": row[0],
        "source": row[1],
        "external_id": row[2],
        "name": row[3] or "",
        "email": row[4] or "",
        "phone": row[5] or "",
        "interests": row[6] or "",
        "preferred_time": row[7] or "",
        "preferred_days": row[8] or "",
        "heard_about": row[9] or "",
        "comments": row[10] or "",
        "raw_json": row[11],
        "status": row[12],
        "created_at": row[13],
        "handled_at": row[14],
        "duplicate": duplicate,
    }


def list_website_leads(
    conn: sqlite3.Connection,
    *,
    status: str | None = "open",
    limit: int = 50,
) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit or 50), 200))
    if status:
        rows = conn.execute(
            """
            SELECT id, source, external_id, name, email, phone, interests, preferred_time,
                   preferred_days, heard_about, comments, raw_json, status, created_at, handled_at
            FROM website_leads
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(status), lim),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, source, external_id, name, email, phone, interests, preferred_time,
                   preferred_days, heard_about, comments, raw_json, status, created_at, handled_at
            FROM website_leads
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (lim,),
        ).fetchall()
    return [_row_to_lead(r) for r in rows]


def mark_website_lead_handled(conn: sqlite3.Connection, lead_id: str) -> dict[str, Any]:
    now = _utc_now()
    cur = conn.execute(
        """
        UPDATE website_leads
        SET status = 'handled', handled_at = ?
        WHERE id = ?
        """,
        (now, str(lead_id)),
    )
    if cur.rowcount < 1:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "id": lead_id, "status": "handled", "handled_at": now}


def payload_fingerprint(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
