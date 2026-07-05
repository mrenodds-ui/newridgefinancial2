"""QuickBooks Online API — token refresh and consent-gated journal post."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import requests

QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QBO_API_BASE = "https://quickbooks.api.intuit.com/v3/company"


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def qbo_config() -> dict[str, str]:
    return {
        "client_id": _env("NR2_QBO_CLIENT_ID"),
        "client_secret": _env("NR2_QBO_CLIENT_SECRET"),
        "realm_id": _env("NR2_QBO_REALM_ID"),
        "refresh_token": _env("NR2_QBO_REFRESH_TOKEN"),
    }


def refresh_access_token() -> dict[str, Any]:
    cfg = qbo_config()
    if not cfg["client_id"] or not cfg["client_secret"] or not cfg["refresh_token"]:
        return {"ok": False, "error": "qbo_not_configured", "message": "QBO credentials incomplete."}
    try:
        resp = requests.post(
            QBO_TOKEN_URL,
            auth=(cfg["client_id"], cfg["client_secret"]),
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "refresh_token", "refresh_token": cfg["refresh_token"]},
            timeout=30,
        )
        if resp.status_code >= 400:
            return {
                "ok": False,
                "error": "qbo_token_refresh_failed",
                "message": resp.text[:400],
                "status": resp.status_code,
            }
        payload = resp.json()
        token = str(payload.get("access_token") or "")
        if not token:
            return {"ok": False, "error": "qbo_missing_access_token", "message": "Token response missing access_token."}
        return {"ok": True, "access_token": token, "expires_in": payload.get("expires_in")}
    except Exception as exc:
        return {"ok": False, "error": "qbo_token_exception", "message": str(exc)}


def _journal_line_payload(line: dict[str, Any]) -> dict[str, Any]:
    debit = float(line.get("debit") or 0)
    credit = float(line.get("credit") or 0)
    amount = debit if debit else credit
    posting = "Debit" if debit else "Credit"
    account = str(line.get("account_name") or line.get("accountName") or line.get("account_code") or "Misc")
    detail: dict[str, Any] = {"PostingType": posting, "Amount": round(abs(amount), 2)}
    if account.isdigit() or len(account) <= 6:
        detail["AccountRef"] = {"value": account, "name": str(line.get("account_name") or line.get("accountName") or account)}
    else:
        detail["AccountRef"] = {"name": account}
    memo = line.get("memo")
    if memo:
        detail["Description"] = str(memo)[:4000]
    return detail


def post_journal_entry(access_token: str, realm_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    lines = entry.get("lines") or []
    if len(lines) < 2:
        return {"ok": False, "error": "invalid_entry", "message": "Journal entry needs at least two lines."}
    txn_date = str(entry.get("transactionDate") or entry.get("accountingPeriod") or "")[:10]
    if len(txn_date) < 10:
        txn_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    doc_number = str(entry.get("queueId") or entry.get("description") or "NR2")[:21]
    body = {
        "Line": [_journal_line_payload(line) for line in lines],
        "TxnDate": txn_date,
        "DocNumber": doc_number,
        "PrivateNote": str(entry.get("description") or "NR2 HAL consent-gated post")[:4000],
    }
    url = f"{QBO_API_BASE}/{realm_id}/journalentry"
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=45,
        )
        if resp.status_code >= 400:
            return {
                "ok": False,
                "error": "qbo_post_failed",
                "message": resp.text[:600],
                "status": resp.status_code,
                "queueId": entry.get("queueId"),
            }
        data = resp.json()
        journal = data.get("JournalEntry") if isinstance(data, dict) else None
        return {
            "ok": True,
            "queueId": entry.get("queueId"),
            "qboId": journal.get("Id") if isinstance(journal, dict) else None,
            "message": f"Posted journal entry {entry.get('queueId') or ''} to QuickBooks Online.",
        }
    except Exception as exc:
        return {"ok": False, "error": "qbo_post_exception", "message": str(exc), "queueId": entry.get("queueId")}


def post_approved_queue_entries(store_path: Any, *, limit: int = 25, dry_run: bool = False) -> dict[str, Any]:
    from posting_queue_store import POSTING_QUEUE_STATUS_APPROVED, PostingQueueStore

    cfg = qbo_config()
    if not cfg["realm_id"]:
        return {"ok": False, "error": "qbo_realm_missing", "message": "Set NR2_QBO_REALM_ID."}
    queue = PostingQueueStore(store_path)
    entries = queue.list_entries(limit=max(1, min(limit, 50)), status=POSTING_QUEUE_STATUS_APPROVED)
    if not entries:
        return {"ok": True, "posted": 0, "skipped": 0, "results": [], "message": "No approved entries to post."}
    if dry_run:
        return {
            "ok": True,
            "dryRun": True,
            "entryCount": len(entries),
            "message": f"Dry run — would post {len(entries)} approved journal entries to QBO.",
        }
    token_result = refresh_access_token()
    if not token_result.get("ok"):
        return token_result
    access = str(token_result["access_token"])
    realm = cfg["realm_id"]
    results = []
    posted = 0
    for entry in entries:
        result = post_journal_entry(access, realm, entry)
        results.append(result)
        if result.get("ok"):
            posted += 1
    return {
        "ok": posted > 0 or not entries,
        "posted": posted,
        "skipped": len(entries) - posted,
        "results": results,
        "message": f"Posted {posted} of {len(entries)} approved entries to QuickBooks Online.",
    }
