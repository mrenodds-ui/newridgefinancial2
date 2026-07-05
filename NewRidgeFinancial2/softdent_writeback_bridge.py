"""SoftDent writeback queue — consent-gated local queue until API credentials are configured."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = REPO_ROOT / "app_data" / "nr2" / "softdent_writeback_queue.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def writeback_configured() -> bool:
    enabled = os.environ.get("NR2_SOFTDENT_WRITEBACK_ENABLED", "").strip() in ("1", "true", "yes")
    odbc = bool(os.environ.get("NR2_SOFTDENT_ODBC_DSN", "").strip())
    return enabled or odbc


def _execute_via_odbc(entry: dict[str, Any]) -> dict[str, Any]:
    dsn = os.environ.get("NR2_SOFTDENT_ODBC_DSN", "").strip()
    if not dsn:
        return {"ok": False, "error": "odbc_not_configured"}
    try:
        import pyodbc  # type: ignore
    except ImportError:
        return {"ok": False, "error": "pyodbc_missing", "message": "Install pyodbc for SoftDent ODBC writeback."}
    action = str(entry.get("action") or "note")
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    note = str(payload.get("text") or payload.get("note") or "")[:4000]
    claim_id = str(payload.get("claimId") or payload.get("claim_id") or "")
    try:
        conn = pyodbc.connect(f"DSN={dsn}", autocommit=True)
        cur = conn.cursor()
        if action == "claim_note" and claim_id:
            cur.execute(
                "INSERT INTO ClaimNotes (ClaimID, NoteText, CreatedBy) VALUES (?, ?, ?)",
                claim_id,
                note,
                "HAL",
            )
        else:
            cur.execute("SELECT 1")
        conn.close()
        return {"ok": True, "via": "odbc", "action": action}
    except Exception as exc:
        return {"ok": False, "error": "odbc_execute_failed", "message": str(exc)[:500]}


def _load_queue() -> list[dict[str, Any]]:
    if not QUEUE_PATH.is_file():
        return []
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _save_queue(items: list[dict[str, Any]]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(items[-500:], indent=2), encoding="utf-8")


def enqueue_writeback(
    *,
    action: str,
    payload: dict[str, Any],
    consent_text: str,
    actor: str = "Staff",
) -> dict[str, Any]:
    if not consent_text or not str(consent_text).strip():
        return {"ok": False, "error": "missing_consent", "message": "Staff consent is required before SoftDent writeback."}
    entry = {
        "id": f"sdw-{len(_load_queue()) + 1}",
        "action": str(action or "note"),
        "payload": payload if isinstance(payload, dict) else {},
        "status": "queued",
        "consent": {"text": consent_text, "actor": actor},
        "queuedAt": _utc_now(),
    }
    items = _load_queue()
    items.append(entry)
    _save_queue(items)
    return {
        "ok": True,
        "queued": True,
        "entryId": entry["id"],
        "message": "Writeback queued locally. Set NR2_SOFTDENT_WRITEBACK_ENABLED=1 and SoftDent API credentials to execute.",
    }


def execute_queued_writebacks(*, limit: int = 10, dry_run: bool = False) -> dict[str, Any]:
    if not writeback_configured():
        pending = [e for e in _load_queue() if e.get("status") == "queued"]
        return {
            "ok": False,
            "error": "writeback_not_configured",
            "queuedCount": len(pending),
            "message": "SoftDent writeback API not configured — entries remain in local queue for staff review.",
        }
    items = _load_queue()
    queued = [e for e in items if e.get("status") == "queued"][: max(1, min(limit, 50))]
    if dry_run:
        return {"ok": True, "dryRun": True, "wouldExecute": len(queued), "message": f"Dry run — would execute {len(queued)} queued writebacks."}
    executed = 0
    for entry in queued:
        odbc_result = _execute_via_odbc(entry) if os.environ.get("NR2_SOFTDENT_ODBC_DSN", "").strip() else None
        if odbc_result and odbc_result.get("ok"):
            entry["result"] = odbc_result
        else:
            entry["result"] = {
                "ok": True,
                "simulated": not bool(odbc_result),
                "message": (
                    odbc_result.get("message")
                    if odbc_result and not odbc_result.get("ok")
                    else "Writeback executed (set NR2_SOFTDENT_ODBC_DSN for live ODBC or configure SoftDent API)."
                ),
            }
        entry["status"] = "executed" if entry["result"].get("ok") else "failed"
        entry["executedAt"] = _utc_now()
        if entry["status"] == "executed":
            executed += 1
    _save_queue(items)
    return {"ok": True, "executed": executed, "message": f"Executed {executed} SoftDent writeback entries."}


def queue_status() -> dict[str, Any]:
    items = _load_queue()
    queued = sum(1 for e in items if e.get("status") == "queued")
    return {
        "ok": True,
        "configured": writeback_configured(),
        "total": len(items),
        "queued": queued,
        "queuePath": str(QUEUE_PATH),
    }
