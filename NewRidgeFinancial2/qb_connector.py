"""QuickBooks connector facade — Phase 2 Moonshot Priority G."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import requests

from employee_actions import check_action_consent

QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
OAUTH_STORE_KEY = "nr2:qb:oauth"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def auth_url() -> dict[str, Any]:
    client_id = os.environ.get("NR2_QBO_CLIENT_ID", "").strip()
    redirect = os.environ.get("NR2_QBO_REDIRECT_URI", "http://127.0.0.1:8765/api/qb/callback").strip()
    if not client_id:
        return {"ok": False, "error": "qbo_not_configured", "message": "Set NR2_QBO_CLIENT_ID for OAuth."}
    scope = "com.intuit.quickbooks.accounting"
    url = (
        "https://appcenter.intuit.com/connect/oauth2"
        f"?client_id={client_id}&redirect_uri={redirect}&response_type=code&scope={scope}&state=nr2"
    )
    return {"ok": True, "authUrl": url}


def exchange_authorization_code(store, *, code: str, realm_id: str = "") -> dict[str, Any]:
    """Exchange Intuit OAuth authorization code for refresh/access tokens."""
    client_id = os.environ.get("NR2_QBO_CLIENT_ID", "").strip()
    client_secret = os.environ.get("NR2_QBO_CLIENT_SECRET", "").strip()
    redirect = os.environ.get("NR2_QBO_REDIRECT_URI", "http://127.0.0.1:8765/api/qb/callback").strip()
    if not client_id or not client_secret:
        return {"ok": False, "error": "qbo_not_configured", "message": "Set NR2_QBO_CLIENT_ID and NR2_QBO_CLIENT_SECRET."}
    if not code:
        return {"ok": False, "error": "missing_code"}
    try:
        resp = requests.post(
            QBO_TOKEN_URL,
            auth=(client_id, client_secret),
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "code": str(code),
                "redirect_uri": redirect,
            },
            timeout=45,
        )
        if resp.status_code >= 400:
            return {"ok": False, "error": "token_exchange_failed", "message": resp.text[:400], "status": resp.status_code}
        payload = resp.json()
        tokens = {
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token"),
            "expires_in": payload.get("expires_in"),
            "realm_id": str(realm_id or os.environ.get("NR2_QBO_REALM_ID", "")).strip(),
            "exchangedAt": _utc_now(),
        }
        if store:
            store.set(OAUTH_STORE_KEY, json.dumps(tokens))
        return {"ok": True, "stored": True, "realmId": tokens.get("realm_id"), "expiresIn": tokens.get("expires_in")}
    except Exception as exc:
        return {"ok": False, "error": "token_exchange_exception", "message": str(exc)}


def store_oauth_tokens(store, *, code: str, realm_id: str = "") -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    exchanged = exchange_authorization_code(store, code=str(code or ""), realm_id=str(realm_id or ""))
    if exchanged.get("ok"):
        return exchanged
    payload = {"code": str(code or ""), "storedAt": _utc_now(), "note": "pending_exchange"}
    store.set(OAUTH_STORE_KEY, json.dumps(payload))
    return {"ok": True, "stored": True, "exchange": exchanged}


def load_stored_tokens(store) -> dict[str, Any]:
    if not store:
        return {}
    raw = store.get(OAUTH_STORE_KEY)
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def sync_read_only(store) -> dict[str, Any]:
    from outbound_actions import quickbooks_online_status

    status = quickbooks_online_status()
    variance = {"ledgerTotal": None, "qbTotal": None, "variance": None}
    return {"ok": True, "mode": "read_only", "status": status, "variance": variance}


def push_journal_with_consent(
    store,
    *,
    entries: list[dict[str, Any]] | None = None,
    memo: str = "",
    amount: float | None = None,
) -> dict[str, Any]:
    from outbound_actions import post_qbo_journal_with_consent

    consent = check_action_consent("HAL", "qbo-post", amount, store=store)
    if not consent.get("allowed"):
        return {"ok": False, "error": "consent_denied", "consent": consent}
    store_path = getattr(store, "db_path", None)
    result = post_qbo_journal_with_consent(
        store_path,
        limit=25,
        consent_text="HAL standing consent qbo-post",
        actor="HAL",
        store=store,
    )
    if entries:
        result["requestedEntries"] = entries
    if memo:
        result["memo"] = memo
    return {"ok": bool(result.get("ok")), "result": result, "consent": consent}


def detect_variance(ledger_total: float, qb_total: float) -> dict[str, Any]:
    diff = float(ledger_total or 0) - float(qb_total or 0)
    return {
        "ok": True,
        "ledgerTotal": ledger_total,
        "qbTotal": qb_total,
        "variance": diff,
        "requiresReview": abs(diff) > 0.01,
    }


def reconciliation_status(store) -> dict[str, Any]:
    status = sync_read_only(store)
    tokens = load_stored_tokens(store)
    return {
        "ok": True,
        "connected": bool(tokens.get("refresh_token") or (status.get("status") or {}).get("configured")),
        "status": status,
        "hasRefreshToken": bool(tokens.get("refresh_token")),
    }
