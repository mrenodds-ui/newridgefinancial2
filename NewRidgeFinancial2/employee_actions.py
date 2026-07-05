"""HAL employee tier — work log, standing consent policies, and shift runner."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

WORK_LOG_KEY = "nr2:hal:employee-work-log"
STANDING_POLICIES_KEY = "nr2:hal:employee-standing-policies"
EMPLOYEE_STATE_KEY = "nr2:hal:employee-state"

LEVEL_NAMES = {
    1: "Digital clerk",
    2: "Bookkeeping assistant",
    3: "Billing / ops coordinator",
    4: "Back-office employee",
    5: "Full peer employee",
    6: "Practice director",
    7: "Executive partner",
}

DEFAULT_POLICIES: dict[int, dict[str, Any]] = {
    1: {
        "email": False,
        "qb-export": False,
        "qbo-post": False,
        "qbo-post-max-usd": 0,
        "claim-submit": False,
        "payer-portal-rpa": False,
        "softdent-writeback": False,
        "narrative-portal": False,
    },
    2: {
        "email": False,
        "qb-export": True,
        "qbo-post": True,
        "qbo-post-max-usd": 5000,
        "claim-submit": False,
        "payer-portal-rpa": False,
        "softdent-writeback": False,
        "narrative-portal": False,
    },
    3: {
        "email": True,
        "qb-export": True,
        "qbo-post": True,
        "qbo-post-max-usd": 10000,
        "claim-submit": True,
        "payer-portal-rpa": True,
        "softdent-writeback": False,
        "narrative-portal": True,
    },
    4: {
        "email": True,
        "qb-export": True,
        "qbo-post": True,
        "qbo-post-max-usd": 25000,
        "claim-submit": True,
        "payer-portal-rpa": True,
        "softdent-writeback": True,
        "narrative-portal": True,
        "scheduled-posting": True,
        "execute-softdent-queue": True,
    },
    5: {
        "email": True,
        "qb-export": True,
        "qbo-post": True,
        "qbo-post-max-usd": 100000,
        "claim-submit": True,
        "payer-portal-rpa": True,
        "softdent-writeback": True,
        "narrative-portal": True,
        "scheduled-posting": True,
        "execute-softdent-queue": True,
        "cross-system-sync": True,
        "auto-task-ownership": True,
    },
    6: {
        "email": True,
        "qb-export": True,
        "qbo-post": True,
        "qbo-post-max-usd": 250000,
        "claim-submit": True,
        "payer-portal-rpa": True,
        "softdent-writeback": True,
        "narrative-portal": True,
        "scheduled-posting": True,
        "execute-softdent-queue": True,
        "cross-system-sync": True,
        "auto-task-ownership": True,
        "director-delegation": True,
        "predictive-alerts": True,
        "executive-briefing": True,
    },
    7: {
        "email": True,
        "qb-export": True,
        "qbo-post": True,
        "qbo-post-max-usd": 0,
        "claim-submit": True,
        "payer-portal-rpa": True,
        "softdent-writeback": True,
        "narrative-portal": True,
        "scheduled-posting": True,
        "execute-softdent-queue": True,
        "cross-system-sync": True,
        "auto-task-ownership": True,
        "director-delegation": True,
        "predictive-alerts": True,
        "executive-briefing": True,
        "continuous-shift": True,
        "executive-partner-rpa": True,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_list(store, key: str) -> list[dict[str, Any]]:
    raw = store.get(key) if store else None
    try:
        data = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        data = []
    return data if isinstance(data, list) else []


def _save_json_list(store, key: str, items: list[dict[str, Any]], *, cap: int = 500) -> None:
    if not store:
        return
    store.set(key, json.dumps(items[-cap:]))


def append_employee_work_log(
    store,
    *,
    action: str,
    summary: str,
    level: int = 1,
    actor: str = "HAL",
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = {
        "at": _utc_now(),
        "action": str(action or "shift"),
        "summary": str(summary or "")[:2000],
        "level": int(level or 1),
        "actor": str(actor or "HAL"),
        "result": result if isinstance(result, dict) else {},
    }
    items = _load_json_list(store, WORK_LOG_KEY)
    items.append(entry)
    _save_json_list(store, WORK_LOG_KEY, items)
    return {"ok": True, "entry": entry}


def list_employee_work_log(store=None, *, limit: int = 20) -> dict[str, Any]:
    items = _load_json_list(store, WORK_LOG_KEY)
    cap = max(1, min(int(limit or 20), 100))
    return {"ok": True, "items": list(reversed(items[-cap:])), "count": len(items)}


def get_standing_policies(store=None, *, target_level: int = 7) -> dict[str, Any]:
    raw = store.get(STANDING_POLICIES_KEY) if store else None
    try:
        saved = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        saved = {}
    level = max(1, min(int(target_level or 5), 7))
    merged = dict(DEFAULT_POLICIES.get(level, DEFAULT_POLICIES[1]))
    if isinstance(saved, dict):
        merged.update({k: v for k, v in saved.items() if not str(k).startswith("_")})
    merged["targetLevel"] = level
    return {"ok": True, "level": level, "levelName": LEVEL_NAMES.get(level, "Unknown"), "policies": merged}


def set_standing_policies(store, policies: dict[str, Any], *, target_level: int | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store", "message": "Storage unavailable."}
    payload = policies if isinstance(policies, dict) else {}
    if target_level is not None:
        payload["targetLevel"] = max(1, min(int(target_level), 7))
    store.set(STANDING_POLICIES_KEY, json.dumps(payload))
    return get_standing_policies(store, target_level=int(payload.get("targetLevel") or target_level or 7))


def standing_allows(kind: str, *, target_level: int = 1, policies: dict[str, Any] | None = None) -> bool:
    pol = policies if isinstance(policies, dict) else DEFAULT_POLICIES.get(max(1, min(target_level, 7)), {})
    key = str(kind or "").strip().lower()
    if key in pol:
        return bool(pol[key])
    return False


def get_employee_status(store=None, *, target_level: int = 7) -> dict[str, Any]:
    from outbound_actions import quickbooks_online_status, softdent_writeback_status

    level = max(1, min(int(target_level or 5), 7))
    pol = get_standing_policies(store, target_level=level)
    work = list_employee_work_log(store, limit=5)
    qbo = quickbooks_online_status()
    sd = softdent_writeback_status()
    achieved = 1
    if qbo.get("configured") or qbo.get("ready"):
        achieved = max(achieved, 2)
    if qbo.get("ready"):
        achieved = max(achieved, 2)
    if sd.get("configured"):
        achieved = max(achieved, 4)
    if pol.get("policies", {}).get("cross-system-sync"):
        achieved = max(achieved, 5)
    achieved = min(achieved, level)
    return {
        "ok": True,
        "name": "HAL",
        "title": "Office Operations Specialist",
        "targetLevel": level,
        "targetLevelName": LEVEL_NAMES.get(level, "Unknown"),
        "achievedLevel": achieved,
        "achievedLevelName": LEVEL_NAMES.get(achieved, "Unknown"),
        "standingPolicies": pol.get("policies"),
        "recentWork": work.get("items") or [],
        "integrations": {"qbo": qbo, "softdentWriteback": sd},
        "message": f"HAL employee tier {achieved}/5 ({LEVEL_NAMES.get(achieved, '')}) — target level {level}.",
    }


def run_employee_shift(
    store_path: Any,
    store=None,
    *,
    target_level: int = 7,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute standing-consent shift actions for the configured employee level."""
    from outbound_actions import export_posting_queue_iif, post_qbo_journal_with_consent

    level = max(1, min(int(target_level or 5), 7))
    pol_resp = get_standing_policies(store, target_level=level)
    policies = pol_resp.get("policies") or {}
    steps: list[dict[str, Any]] = []
    consent = f"Standing policy employee level {level}"

    if level >= 2 and standing_allows("qb-export", target_level=level, policies=policies):
        if dry_run:
            steps.append({"action": "qb-export", "dryRun": True, "ok": True})
        else:
            result = export_posting_queue_iif(store_path, consent_text=consent, actor="HAL", store=store)
            steps.append({"action": "qb-export", **result})
            append_employee_work_log(
                store,
                action="qb-export",
                summary="Export approved journals (standing consent)",
                level=level,
                result=result,
            )

    if level >= 2 and standing_allows("qbo-post", target_level=level, policies=policies):
        if dry_run:
            steps.append({"action": "qbo-post", "dryRun": True, "ok": True})
        else:
            result = post_qbo_journal_with_consent(
                store_path,
                limit=25,
                consent_text=consent,
                actor="HAL",
                store=store,
                dry_run=False,
            )
            steps.append({"action": "qbo-post", **result})
            append_employee_work_log(
                store,
                action="qbo-post",
                summary="Post approved journals to QBO (standing consent)",
                level=level,
                result=result,
            )

    if level >= 4 and policies.get("execute-softdent-queue"):
        from softdent_writeback_bridge import execute_queued_writebacks

        if dry_run:
            steps.append({"action": "softdent-writeback", "dryRun": True, "ok": True})
        else:
            result = execute_queued_writebacks(limit=10, dry_run=False)
            steps.append({"action": "softdent-writeback", **result})
            append_employee_work_log(
                store,
                action="softdent-writeback",
                summary="Execute SoftDent writeback queue (level 4+)",
                level=level,
                result=result,
            )

    ok = all(s.get("ok") is not False for s in steps) if steps else True
    summary = {
        "ok": ok,
        "level": level,
        "dryRun": dry_run,
        "steps": steps,
        "message": f"Employee shift level {level}: {len(steps)} action(s){' (dry run)' if dry_run else ''}.",
    }
    if store and steps:
        append_employee_work_log(
            store,
            action="shift",
            summary=summary["message"],
            level=level,
            result={"stepCount": len(steps), "ok": ok},
        )
    return summary
