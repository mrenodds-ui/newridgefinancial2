"""Two-way SMS billing reminders — Phase 2 Moonshot Priority H."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

TWILIO_AUTH_TOKEN = os.environ.get("NR2_TWILIO_AUTH_TOKEN", "").strip()
TWILIO_ACCOUNT_SID = os.environ.get("NR2_TWILIO_ACCOUNT_SID", "").strip()
TWILIO_FROM_NUMBER = os.environ.get("NR2_TWILIO_FROM_NUMBER", "").strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_sms_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sms_outbound (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            patient_id TEXT,
            phone_number TEXT NOT NULL,
            template_key TEXT,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sms_inbound (
            id TEXT PRIMARY KEY,
            received_at_utc TEXT NOT NULL,
            patient_id TEXT,
            phone_number TEXT NOT NULL,
            body TEXT NOT NULL,
            intent TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_communication_consent (
            patient_id TEXT PRIMARY KEY,
            sms_allowed INTEGER NOT NULL DEFAULT 1,
            updated_at_utc TEXT NOT NULL
        )
        """
    )
    conn.commit()


def sms_consent_allowed(conn: sqlite3.Connection, patient_id: str) -> bool:
    ensure_sms_schema(conn)
    cur = conn.execute(
        "SELECT sms_allowed FROM patient_communication_consent WHERE patient_id = ?",
        (str(patient_id or ""),),
    )
    row = cur.fetchone()
    if row is None:
        return True
    return bool(row[0])


def send_billing_sms(
    conn: sqlite3.Connection,
    *,
    patient_id: str,
    phone_number: str,
    template_key: str = "reminder",
    body: str = "",
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_sms_schema(conn)
    if not sms_consent_allowed(conn, patient_id):
        return {"ok": False, "error": "sms_consent_denied"}
    number = str(phone_number or "").strip()
    if not number:
        return {"ok": False, "error": "missing_phone_number"}
    vars_map = variables if isinstance(variables, dict) else {}
    text = str(body or "").strip()
    if not text:
        amount = vars_map.get("amount_due") or vars_map.get("amountDue") or ""
        text = f"Reminder from New Ridge Family Dental: balance due {amount}. Reply STOP to opt out."
    msg_id = f"sms-{uuid.uuid4().hex[:12]}"
    status = "queued"
    provider_id = None
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER:
        try:
            import urllib.parse
            import urllib.request

            data = urllib.parse.urlencode(
                {"To": number, "From": TWILIO_FROM_NUMBER, "Body": text}
            ).encode()
            url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
            req = urllib.request.Request(url, data=data, method="POST")
            import base64

            cred = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()).decode()
            req.add_header("Authorization", f"Basic {cred}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            provider_id = payload.get("sid")
            status = "sent"
        except Exception as exc:
            status = f"error:{str(exc)[:120]}"
    conn.execute(
        """
        INSERT INTO sms_outbound (id, created_at_utc, patient_id, phone_number, template_key, body, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (msg_id, _utc_now(), str(patient_id or ""), number, str(template_key or "reminder"), text, status),
    )
    conn.commit()
    return {"ok": True, "messageId": msg_id, "status": status, "providerId": provider_id}


def validate_twilio_signature(url: str, params: dict[str, Any], signature: str) -> bool:
    if not TWILIO_AUTH_TOKEN:
        return False
    pieces = [url] + [f"{k}{params[k]}" for k in sorted(params.keys())]
    digest = hmac.new(TWILIO_AUTH_TOKEN.encode(), "".join(pieces).encode(), hashlib.sha1).digest()
    import base64

    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, str(signature or ""))


def handle_inbound_sms(
    conn: sqlite3.Connection,
    *,
    phone_number: str,
    body: str,
    patient_id: str = "",
) -> dict[str, Any]:
    ensure_sms_schema(conn)
    text = str(body or "").strip()
    intent = "general"
    if text.upper().startswith("STOP"):
        intent = "unsubscribe"
        if patient_id:
            conn.execute(
                """
                INSERT INTO patient_communication_consent (patient_id, sms_allowed, updated_at_utc)
                VALUES (?, 0, ?)
                ON CONFLICT(patient_id) DO UPDATE SET sms_allowed = 0, updated_at_utc = excluded.updated_at_utc
                """,
                (str(patient_id), _utc_now()),
            )
    elif "pay" in text.lower():
        intent = "payment_reply"
    msg_id = f"in-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """
        INSERT INTO sms_inbound (id, received_at_utc, patient_id, phone_number, body, intent)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (msg_id, _utc_now(), str(patient_id or ""), str(phone_number or ""), text, intent),
    )
    conn.commit()
    return {"ok": True, "messageId": msg_id, "intent": intent}


def get_sms_thread(conn: sqlite3.Connection, *, patient_id: str, limit: int = 50) -> dict[str, Any]:
    ensure_sms_schema(conn)
    pid = str(patient_id or "")
    out_cur = conn.execute(
        "SELECT id, created_at_utc, body, status FROM sms_outbound WHERE patient_id = ? ORDER BY created_at_utc DESC LIMIT ?",
        (pid, limit),
    )
    in_cur = conn.execute(
        "SELECT id, received_at_utc, body, intent FROM sms_inbound WHERE patient_id = ? ORDER BY received_at_utc DESC LIMIT ?",
        (pid, limit),
    )
    outbound = [{"id": r[0], "at": r[1], "body": r[2], "status": r[3], "direction": "out"} for r in out_cur.fetchall()]
    inbound = [{"id": r[0], "at": r[1], "body": r[2], "intent": r[3], "direction": "in"} for r in in_cur.fetchall()]
    thread = sorted(outbound + inbound, key=lambda x: x.get("at") or "")
    return {"ok": True, "patientId": pid, "thread": thread}
