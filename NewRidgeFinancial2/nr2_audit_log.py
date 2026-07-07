"""Append-only audit log with HMAC chain — Moonshot Sprint 2."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_AUDIT_DIR = Path(__file__).resolve().parent.parent / "app_data" / "nr2" / "audit"
_MUTATIONS_LOG = _AUDIT_DIR / "nr2_mutations.log"
_READS_LOG = _AUDIT_DIR / "nr2_reads.log"
_FINANCIAL_MUTATIONS_LOG = _AUDIT_DIR / "nr2_financial_mutations.log"
_last_mutation_hmac = ""
_last_read_hmac = ""
_last_financial_hmac = ""

FINANCIAL_MUTATION_ACTIONS = frozenset(
    {
        "posting_queue_enqueue",
        "posting_queue_review",
        "posting_queue_bulk_review",
        "posting_queue_export_approved",
        "posting_batch_approve",
        "eob_era_match",
        "era_parse_apply",
        "deposit_reconciliation",
        "qb_journal_post",
        "patient_payment_webhook",
        "collections_adjustment",
    }
)


def read_audit_tail(kind: str, *, limit: int = 100) -> list[dict[str, Any]]:
    if kind == "reads":
        path = _READS_LOG
    elif kind == "financial":
        path = _FINANCIAL_MUTATIONS_LOG
    else:
        path = _MUTATIONS_LOG
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _audit_secret() -> bytes:
    try:
        from nr2_db_crypto import get_master_key

        return get_master_key().encode("utf-8")
    except Exception:
        raw = os.environ.get("NR2_AUDIT_SECRET", "").strip()
        if raw:
            return raw.encode("utf-8")
        path = _AUDIT_DIR / "audit_hmac.key"
        _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            return path.read_bytes()
        secret = os.urandom(32)
        path.write_bytes(secret)
        return secret


def _chain_hmac(prev: str, entry: dict[str, Any]) -> str:
    payload = json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    material = (prev or "").encode("utf-8") + payload
    return hmac.new(_audit_secret(), material, hashlib.sha256).hexdigest()


def _read_last_hmac(log_path: Path) -> str:
    if not log_path.is_file():
        return ""
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if not line.strip():
                continue
            record = json.loads(line)
            return str(record.get("hmac") or "")
    except Exception:
        return ""
    return ""


def _append_chained(log_path: Path, entry: dict[str, Any], *, global_prev: str) -> str:
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    prev = global_prev or _read_last_hmac(log_path)
    core = dict(entry)
    core["prev_hmac"] = prev
    hm = _chain_hmac(prev, core)
    core["hmac"] = hm
    line = json.dumps(core, separators=(",", ":"), default=str)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return hm


def append_audit_event(
    action: str,
    *,
    actor: str = "Staff",
    detail: dict[str, Any] | None = None,
    path: str | None = None,
) -> None:
    global _last_mutation_hmac
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": str(action or "unknown"),
        "actor": str(actor or "Staff"),
    }
    if path:
        record["path"] = str(path)
    if detail:
        record["detail"] = detail
    _last_mutation_hmac = _append_chained(_MUTATIONS_LOG, record, global_prev=_last_mutation_hmac)


def append_financial_mutation(
    action: str,
    *,
    actor: str = "Staff",
    patient_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    amount: float | None = None,
    hal_involved: bool = False,
    detail: dict[str, Any] | None = None,
    path: str | None = None,
) -> None:
    global _last_financial_hmac
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": str(action or "unknown"),
        "actor": str(actor or "Staff"),
        "halInvolved": bool(hal_involved),
    }
    if path:
        record["path"] = str(path)
    if patient_id:
        record["patientId"] = str(patient_id)
    if amount is not None:
        record["amount"] = float(amount)
    if before:
        record["before"] = before
    if after:
        record["after"] = after
    if detail:
        record["detail"] = detail
    _last_financial_hmac = _append_chained(_FINANCIAL_MUTATIONS_LOG, record, global_prev=_last_financial_hmac)


def append_read_audit(*, token_fingerprint: str, path: str, role: str = "unknown", params: dict[str, Any] | None = None) -> None:
    global _last_read_hmac
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "token_fp": str(token_fingerprint or "anon"),
        "path": str(path or ""),
        "role": str(role or "unknown"),
    }
    if params:
        record["params"] = params
    _last_read_hmac = _append_chained(_READS_LOG, record, global_prev=_last_read_hmac)


def verify_financial_audit_chain(*, limit: int = 500) -> dict[str, Any]:
    if not _FINANCIAL_MUTATIONS_LOG.is_file():
        return {"ok": True, "count": 0, "verified": True}
    lines = _FINANCIAL_MUTATIONS_LOG.read_text(encoding="utf-8").splitlines()
    prev = ""
    count = 0
    for line in lines[-limit:]:
        if not line.strip():
            continue
        record = json.loads(line)
        core = {k: v for k, v in record.items() if k != "hmac"}
        expected_prev = str(core.get("prev_hmac") or "")
        if expected_prev != prev:
            return {"ok": False, "error": "chain_break", "count": count}
        hm = str(record.get("hmac") or "")
        check = _chain_hmac(prev, core)
        if hm != check:
            return {"ok": False, "error": "hmac_mismatch", "count": count}
        prev = hm
        count += 1
    return {"ok": True, "count": count, "verified": True}


HAL_SESSIONS_KEY = "nr2:hal:audit-sessions"


def _load_hal_sessions(store) -> dict[str, Any]:
    if not store:
        return {}
    raw = store.get(HAL_SESSIONS_KEY)
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}


def record_hal_session(store, session_id: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    sid = str(session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "session_id_required"}
    sessions = _load_hal_sessions(store)
    entry = {
        "sessionId": sid,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "events": [],
    }
    if sid in sessions:
        entry = sessions[sid]
        if not isinstance(entry.get("events"), list):
            entry["events"] = []
    event = {"ts": datetime.now(timezone.utc).isoformat(), **(detail or {})}
    entry["events"] = (entry.get("events") or [])[-49:] + [event]
    entry["updatedAt"] = event["ts"]
    sessions[sid] = entry
    store.set(HAL_SESSIONS_KEY, json.dumps(sessions))
    return {"ok": True, "session": entry}


def get_hal_session(store, session_id: str) -> dict[str, Any]:
    sid = str(session_id or "").strip()
    sessions = _load_hal_sessions(store)
    entry = sessions.get(sid)
    if not entry:
        return {"ok": False, "error": "session_not_found", "sessionId": sid}
    return {"ok": True, "session": entry}


def explain_hal_block(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    error = str(data.get("error") or data.get("code") or "HAL_UNAVAILABLE_STALE_DATA")
    readiness = data.get("readiness") if isinstance(data.get("readiness"), dict) else {}
    level = str(readiness.get("level") or "unknown")
    explanations = {
        "HAL_UNAVAILABLE_STALE_DATA": (
            f"Import data is {level}. Transactional financial answers require fresh imports. "
            "Analytical questions may proceed in soft-stale mode within the configured TTL."
        ),
        "direct_ollama_rejected": "All LLM calls must route through the NR2 HAL gateway on loopback.",
        "consent_denied": "Standing consent policy or tier amount cap blocked this action.",
    }
    text = explanations.get(error, f"Request blocked: {error}")
    record_hal_session(
        store,
        str(data.get("sessionId") or "anonymous"),
        {"type": "block_explain", "error": error, "explanation": text},
    )
    return {"ok": True, "error": error, "explanation": text, "readinessLevel": level}
