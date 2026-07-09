"""VoIP click-to-dial and call logging — Phase 2 Moonshot Priority D."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VOICE_SCRIPTS_PATH = Path(__file__).resolve().parent / "site" / "data" / "hal-voice-scripts.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_voice_scripts() -> dict[str, Any]:
    if not VOICE_SCRIPTS_PATH.is_file():
        return {"employeePhoneScripts": {}, "policy": ""}
    try:
        return json.loads(VOICE_SCRIPTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"employeePhoneScripts": {}, "policy": ""}


def get_voice_script(scenario: str, *, patient_name: str = "", balance: str = "") -> dict[str, Any]:
    data = load_voice_scripts()
    scripts = data.get("employeePhoneScripts") or {}
    key_map = {
        "collections": "arBalance",
        "ar": "arBalance",
        "ar_balance": "arBalance",
        "insurance_verify": "arVerification",
        "ar_verification": "arVerification",
        "appointment": "appointmentConfirm",
        "underpay": "feeUnderpay",
        "fee_underpay": "feeUnderpay",
        "claims_aging": "claimsAging",
        "aging": "claimsAging",
        "insurance_followup": "claimsAging",
    }
    script_key = key_map.get(str(scenario or "").lower(), str(scenario or "arBalance"))
    template = str(scripts.get(script_key) or scripts.get("arBalance") or "")
    rendered = (
        template.replace("{patientName}", patient_name or "the patient")
        .replace("{balance}", balance or "your balance")
        .replace("{shortfall}", balance or "the underpayment")
    )
    return {"ok": True, "scenario": scenario, "scriptKey": script_key, "script": rendered, "policy": data.get("policy")}


def ensure_call_log_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS voip_call_log (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            patient_id TEXT,
            phone_number TEXT NOT NULL,
            direction TEXT NOT NULL DEFAULT 'outbound',
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'initiated',
            outcome TEXT,
            duration_sec INTEGER,
            notes TEXT,
            meta_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.commit()


def initiate_call(
    conn: sqlite3.Connection,
    *,
    phone_number: str,
    patient_id: str = "",
    reason: str = "collections",
    call_id: str | None = None,
    queue_id: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_call_log_schema(conn)
    cid = str(call_id or f"call-{uuid.uuid4().hex[:12]}")
    number = str(phone_number or "").strip()
    if not number:
        return {"ok": False, "error": "missing_phone_number"}
    meta_payload = dict(meta) if isinstance(meta, dict) else {}
    if queue_id:
        meta_payload["queueId"] = str(queue_id)
    conn.execute(
        """
        INSERT INTO voip_call_log
        (id, created_at_utc, patient_id, phone_number, direction, reason, status, meta_json)
        VALUES (?, ?, ?, ?, 'outbound', ?, 'initiated', ?)
        """,
        (
            cid,
            _utc_now(),
            str(patient_id or ""),
            number,
            str(reason or "collections"),
            json.dumps(meta_payload),
        ),
    )
    conn.commit()
    tel_uri = number if number.startswith("tel:") else f"tel:{number}"
    return {
        "ok": True,
        "callId": cid,
        "telUri": tel_uri,
        "phoneNumber": number,
        "queueId": meta_payload.get("queueId") or "",
    }


def _outcome_to_queue_status(outcome: str) -> str:
    o = str(outcome or "").strip().lower().replace(" ", "_").replace("-", "_")
    mapping = {
        "no_answer": "no_answer",
        "noanswer": "no_answer",
        "voicemail": "no_answer",
        "busy": "no_answer",
        "promised": "promised",
        "promise_to_pay": "promised",
        "ptp": "promised",
        "paid": "closed",
        "resolved": "closed",
        "closed": "closed",
        "wrong_number": "closed",
        "do_not_call": "closed",
        "spoke": "called",
        "connected": "called",
        "called": "called",
        "left_message": "called",
        "callback": "called",
    }
    return mapping.get(o, "called")


def log_call_outcome(
    conn: sqlite3.Connection,
    *,
    call_id: str,
    outcome: str,
    notes: str = "",
    duration_sec: int | None = None,
    queue_id: str = "",
    store=None,
) -> dict[str, Any]:
    ensure_call_log_schema(conn)
    cid = str(call_id or "")
    row = conn.execute(
        "SELECT patient_id, meta_json FROM voip_call_log WHERE id = ?",
        (cid,),
    ).fetchone()
    meta: dict[str, Any] = {}
    patient_id = ""
    if row:
        patient_id = str(row[0] or "")
        try:
            meta = json.loads(row[1] or "{}")
        except json.JSONDecodeError:
            meta = {}
    conn.execute(
        """
        UPDATE voip_call_log
        SET status = 'completed', outcome = ?, notes = ?, duration_sec = ?
        WHERE id = ?
        """,
        (str(outcome or "unknown"), str(notes or "")[:2000], duration_sec, cid),
    )
    conn.commit()
    qid = str(queue_id or meta.get("queueId") or meta.get("queue_id") or "").strip()
    queue_update = None
    if store or qid or patient_id:
        try:
            from hal_employee_workflows import update_collections_queue_status

            payload = {
                "queueId": qid,
                "patientId": patient_id,
                "status": _outcome_to_queue_status(outcome),
                "outcome": outcome,
                "notes": notes,
                "callId": cid,
            }
            if store is not None:
                queue_update = update_collections_queue_status(store, payload)
            else:
                queue_update = update_collections_queue_status(None, payload, conn=conn)
        except Exception as exc:
            queue_update = {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "callId": call_id,
        "outcome": outcome,
        "queueStatus": (queue_update or {}).get("status"),
        "queueUpdate": queue_update,
    }


def list_call_log(conn: sqlite3.Connection, *, patient_id: str = "", limit: int = 50) -> dict[str, Any]:
    ensure_call_log_schema(conn)
    if patient_id:
        cur = conn.execute(
            """
            SELECT id, created_at_utc, patient_id, phone_number, reason, status, outcome, notes
            FROM voip_call_log WHERE patient_id = ? ORDER BY created_at_utc DESC LIMIT ?
            """,
            (str(patient_id), max(1, min(int(limit or 50), 200))),
        )
    else:
        cur = conn.execute(
            """
            SELECT id, created_at_utc, patient_id, phone_number, reason, status, outcome, notes
            FROM voip_call_log ORDER BY created_at_utc DESC LIMIT ?
            """,
            (max(1, min(int(limit or 50), 200)),),
        )
    items = [
        {
            "id": r[0],
            "createdAt": r[1],
            "patientId": r[2],
            "phoneNumber": r[3],
            "reason": r[4],
            "status": r[5],
            "outcome": r[6],
            "notes": r[7],
        }
        for r in cur.fetchall()
    ]
    return {"ok": True, "items": items, "count": len(items)}


def create_twilio_stream_twiml(*, employee_id: str = "HAL", call_sid: str = "") -> str:
    """Moonshot 2A — Twilio Media Streams TwiML stub (workstation VoIP bridge)."""
    sid = str(call_sid or "pending")
    eid = str(employee_id or "HAL")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        "  <Connect>\n"
        f'    <Stream url="wss://127.0.0.1:8766/voip/media">\n'
        f'      <Parameter name="employee_id" value="{eid}"/>\n'
        f'      <Parameter name="call_sid" value="{sid}"/>\n'
        "    </Stream>\n"
        "  </Connect>\n"
        "</Response>"
    )


class TwilioMediaStreamHandler:
    """Stub handler for Twilio Media Streams WebSocket events (2A)."""

    def __init__(self, *, employee_id: str, call_sid: str) -> None:
        self.employee_id = str(employee_id or "HAL")
        self.call_sid = str(call_sid or "")
        self.is_active = False
        self.hal_context: dict[str, Any] = {}

    def handle_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_type = str(payload.get("event") or "")
        if event_type == "start":
            start = payload.get("start") if isinstance(payload.get("start"), dict) else {}
            self.hal_context = {
                "callSid": start.get("callSid") or self.call_sid,
                "from": start.get("from"),
                "to": start.get("to"),
            }
            self.is_active = True
            return {"ok": True, "event": "start", "context": self.hal_context}
        if event_type == "stop":
            self.is_active = False
            return {"ok": True, "event": "stop"}
        if event_type == "media":
            return {"ok": True, "event": "media", "note": "stt_hal_tts_stub"}
        return {"ok": True, "event": event_type or "unknown"}
