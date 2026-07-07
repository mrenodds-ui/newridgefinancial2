"""QuickBooks connector facade — Phase 2 Moonshot Priority G."""

from __future__ import annotations

import json
import os
from typing import Any

from employee_actions import check_action_consent


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


def store_oauth_tokens(store, *, code: str) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    payload = {"code": str(code or ""), "storedAt": "pending_exchange"}
    store.set("nr2:qb:oauth", json.dumps(payload))
    return {"ok": True, "stored": True, "note": "Exchange code with Intuit token endpoint in production."}


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
    return {"ok": True, "connected": bool((status.get("status") or {}).get("configured")), "status": status}
