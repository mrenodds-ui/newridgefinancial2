"""Server-side settings with HMAC integrity — Moonshot Phase E."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SETTINGS_KEY = "nr2:settings:cloudHal"
_SECRET_PATH = Path(__file__).resolve().parent.parent / "app_data" / "nr2" / "settings_hmac.key"


def _settings_secret() -> bytes:
    _SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _SECRET_PATH.is_file():
        return _SECRET_PATH.read_bytes()
    raw = secrets.token_bytes(32)
    _SECRET_PATH.write_bytes(raw)
    return raw


def _sign(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(_settings_secret(), body.encode("utf-8"), hashlib.sha256).hexdigest()


def _verify(payload: dict[str, Any], signature: str) -> bool:
    expected = _sign({k: v for k, v in payload.items() if k != "signature"})
    return hmac.compare_digest(expected, str(signature or ""))


def read_cloud_hal_settings(store) -> dict[str, Any]:
    raw = store.get(SETTINGS_KEY)
    if not raw:
        return {"enabled": False, "enabledAt": None, "enabledBy": None, "baaSignedAt": None, "signature": None}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"enabled": False, "enabledAt": None, "enabledBy": None, "baaSignedAt": None, "signature": None}
    sig = str(data.get("signature") or "")
    core = {k: data.get(k) for k in ("enabled", "enabledAt", "enabledBy", "baaSignedAt")}
    if not _verify({**core, "signature": sig}, sig):
        return {"enabled": False, "enabledAt": None, "enabledBy": None, "baaSignedAt": None, "signature": None, "tampered": True}
    return {**core, "signature": sig}


def write_cloud_hal_settings(
    store,
    *,
    enabled: bool,
    enabled_by: str = "Staff",
    baa_signed: bool = False,
) -> dict[str, Any]:
    from nr2_audit_log import append_audit_event

    payload = {
        "enabled": bool(enabled),
        "enabledAt": datetime.now(timezone.utc).isoformat(),
        "enabledBy": str(enabled_by or "Staff"),
        "baaSignedAt": datetime.now(timezone.utc).isoformat() if baa_signed and enabled else None,
    }
    if enabled and not payload.get("baaSignedAt"):
        existing = read_cloud_hal_settings(store)
        payload["baaSignedAt"] = existing.get("baaSignedAt")
    signature = _sign(payload)
    record = {**payload, "signature": signature}
    store.set(SETTINGS_KEY, json.dumps(record))
    append_audit_event("cloud_hal_settings", actor=str(enabled_by or "Staff"), detail=record)
    return record
