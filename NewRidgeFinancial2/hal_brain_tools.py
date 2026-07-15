"""HAL brains tool + consent action helpers (Moonshot P1/P2).

Invoked only from /api/hal/tools/* and /api/hal/actions/* routes.
SoftDent write-back forbidden; GUI export and QB sync require consent=true.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

# In-process pending consent actions (operator must click Approve)
_PENDING: dict[str, dict[str, Any]] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finite(val: Any) -> bool:
    try:
        f = float(val)
        return f == f and abs(f) != float("inf")
    except (TypeError, ValueError):
        return False


def softdent_status() -> dict[str, Any]:
    """Live SoftDent AR/claims freshness pulse (read-only)."""
    out: dict[str, Any] = {"ok": True, "emptyNotZero": True, "at": _utc_now()}
    try:
        from nr2_softdent_daily import claims_outstanding

        payload = claims_outstanding(limit=1)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc)[:240],
            "hasData": False,
            "display": "∅ NO SIGNAL",
            "emptyNotZero": True,
        }

    has_data = bool(payload.get("hasData"))
    total = payload.get("totalOutstanding")
    if not has_data:
        out.update(
            {
                "hasData": False,
                "totalOutstanding": None,
                "count": int(payload.get("count") or 0),
                "display": "∅ NO SIGNAL",
                "hint": "empty ≠ $0 — SoftDent claims beam empty or missing",
            }
        )
    elif total is None or not _finite(total):
        out.update(
            {
                "hasData": True,
                "totalOutstanding": None,
                "count": int(payload.get("count") or 0),
                "display": "LIVE (no total)",
                "hint": "beam live",
            }
        )
    else:
        out.update(
            {
                "hasData": True,
                "totalOutstanding": float(total),
                "count": int(payload.get("count") or 0),
                "display": f"${float(total):,.0f}",
                "hint": "SoftDent claims live",
            }
        )
    try:
        from softdent_gui_export import softdent_main_running

        out["guiRunning"] = bool(softdent_main_running())
    except Exception:
        out["guiRunning"] = None
    return out


def qb_summary() -> dict[str, Any]:
    """Live QB summary with freshness watermark (read-only)."""
    out: dict[str, Any] = {"ok": True, "emptyNotZero": True, "at": _utc_now()}
    try:
        from nr2_analytics import quickbooks_monthly_revenue

        rev = quickbooks_monthly_revenue()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:240], "display": "∅ NO SIGNAL", "emptyNotZero": True}

    values = list(rev.get("values") or []) if isinstance(rev, dict) else []
    has_data = bool(rev.get("hasData")) and bool(values)
    amount = values[-1] if values and _finite(values[-1]) else None

    if not has_data or amount is None:
        out.update(
            {
                "hasData": False,
                "monthlyRevenue": None,
                "display": "∅ NO SIGNAL",
                "hint": "empty ≠ $0 — QB revenue beam empty",
                "labels": (rev.get("labels") or [])[-3:] if isinstance(rev, dict) else [],
            }
        )
    else:
        out.update(
            {
                "hasData": True,
                "monthlyRevenue": float(amount),
                "display": f"${float(amount):,.0f}",
                "hint": "QuickBooks revenue live (latest month)",
                "labels": (rev.get("labels") or [])[-3:] if isinstance(rev, dict) else [],
            }
        )

    try:
        from qb_connector import get_net_income_summary

        ni = get_net_income_summary()
        out["netIncome"] = ni if isinstance(ni, dict) else {"raw": str(ni)[:200]}
    except Exception as exc:  # noqa: BLE001
        out["netIncome"] = {"error": str(exc)[:160]}
    return out


def money_beam_attestation() -> dict[str, Any]:
    """Attest SoftDent + QB money beams for HAL chat (empty ≠ $0 · no invented currency).

    Injected into the chat system prompt so HAL must cite live beam state and
    never fill ∅ with $0.
    """
    sd = softdent_status()
    qb = qb_summary()
    lines = [
        "LIVE MONEY BEAMS (cite these; never invent other dollars):",
        f"- SoftDent claims: {sd.get('display')} · hasData={bool(sd.get('hasData'))} · {sd.get('hint') or ''}",
        f"- QuickBooks revenue: {qb.get('display')} · hasData={bool(qb.get('hasData'))} · {qb.get('hint') or ''}",
    ]
    if sd.get("display") == "∅ NO SIGNAL" or qb.get("display") == "∅ NO SIGNAL":
        lines.append(
            "HONESTY: At least one money beam is empty — say NO SIGNAL / no data for that beam; never $0."
        )
    return {
        "ok": True,
        "emptyNotZero": True,
        "at": _utc_now(),
        "softdent": {
            "hasData": sd.get("hasData"),
            "display": sd.get("display"),
            "totalOutstanding": sd.get("totalOutstanding"),
        },
        "quickbooks": {
            "hasData": qb.get("hasData"),
            "display": qb.get("display"),
            "monthlyRevenue": qb.get("monthlyRevenue"),
        },
        "promptBlock": "\n".join(lines),
    }


def qb_sync(*, consent: bool, store) -> dict[str, Any]:
    if not consent:
        return {
            "ok": False,
            "error": "consent_required",
            "detail": "QB sync requires explicit operator consent (consent:true).",
        }
    try:
        from qb_connector import sync_read_only

        result = sync_read_only(store)
        return {"ok": True, "consent": True, "result": result, "at": _utc_now()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:400], "consent": True}


def softdent_export(*, consent: bool, report_id: str = "aging", days: int = 30) -> dict[str, Any]:
    """Consent-gated SoftDent GUI Excel export → C:\\SoftDentReportExports."""
    if not consent:
        return {
            "ok": False,
            "error": "consent_required",
            "detail": "SoftDent GUI export requires explicit operator consent (consent:true).",
            "reportId": report_id,
        }
    try:
        from softdent_gui_export import export_report_by_id, softdent_main_running

        if not softdent_main_running():
            return {
                "ok": False,
                "error": "softdent_gui_unreachable",
                "detail": "SoftDent desktop not running. Launch CS SoftDent Software.lnk, then retry export.",
                "fallback": "Teach mode — open SoftDent → Reports → Accounting for the requested report; Output Options Excel only.",
                "exportRoot": r"C:\SoftDentReportExports",
            }
        end = date.today()
        start = end - timedelta(days=max(1, min(int(days), 366)))
        # Map friendly aliases
        rid = str(report_id or "account_aging").strip().lower()
        aliases = {
            "aging": "aging",
            "ar": "aging",
            "account_aging": "aging",
            "register": "register",
            "collections": "collections",
            "claims": "outstanding_claims",
            "outstanding_claims": "outstanding_claims",
            "daysheet": "daysheet",
            "transactions": "transactions",
            "transactions_for_period": "transactions",
        }
        rid = aliases.get(rid, rid)
        if rid == "outstanding_claims":
            # Menu map may use a different id; fall back to aging if unknown
            from softdent_gui_export import load_menu_map

            reports = (load_menu_map().get("reports") or {})
            if rid not in reports and "aging" in reports:
                rid = "aging"
        path = export_report_by_id(rid, start=start, end=end)
        return {
            "ok": True,
            "consent": True,
            "reportId": rid,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "path": str(path),
            "exportRoot": r"C:\SoftDentReportExports",
            "at": _utc_now(),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": "softdent_export_failed",
            "detail": str(exc)[:600],
            "fallback": "GUI unreachable or report unsupported — showing cached imports only; empty ≠ $0.",
            "exportRoot": r"C:\SoftDentReportExports",
        }


def memo_search(*, query: str, limit: int = 5) -> dict[str, Any]:
    from knowledge_memory_index import search_memories

    hits = search_memories(str(query or ""), limit=max(1, min(int(limit), 20)))
    compact = []
    for m in hits:
        text = str(m.get("text") or "")
        if len(text) > 280:
            text = text[:280].rstrip() + "…"
        compact.append(
            {
                "id": m.get("id"),
                "category": m.get("category"),
                "title": m.get("title") or m.get("id"),
                "text": text,
                "source": m.get("source"),
            }
        )
    return {"ok": True, "query": query, "count": len(compact), "memories": compact, "emptyNotZero": True}


def memo_write(*, text: str, actor: str = "Operator") -> dict[str, Any]:
    from knowledge_memory_store import remember_fact

    try:
        result = remember_fact(str(text or ""), source="hal:optical-chat", actor=actor)
        return result
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


def web_research_tool(*, query: str) -> dict[str, Any]:
    from web_research import research, sanitize_query

    cleaned, blocked = sanitize_query(str(query or ""))
    if blocked:
        return {
            "ok": False,
            "error": "phi_blocked",
            "detail": "Query blocked — do not send PHI identifiers to web research.",
            "blocked": blocked,
        }
    if not cleaned.strip():
        return {"ok": False, "error": "empty_query"}
    return research(cleaned, max_results=5, enrich=True)


def propose_action(*, kind: str, label: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    action_id = uuid.uuid4().hex
    row = {
        "actionId": action_id,
        "kind": str(kind or "custom")[:64],
        "label": str(label or kind)[:240],
        "payload": payload or {},
        "status": "pending",
        "createdAt": _utc_now(),
    }
    _PENDING[action_id] = row
    return {"ok": True, "action": row, "consentRequired": True}


def list_pending_actions() -> dict[str, Any]:
    pending = [v for v in _PENDING.values() if v.get("status") == "pending"]
    return {"ok": True, "pending": pending, "count": len(pending)}


def execute_action(*, action_id: str, consent: bool, store=None) -> dict[str, Any]:
    if not consent:
        return {"ok": False, "error": "consent_required"}
    row = _PENDING.get(str(action_id))
    if not row:
        return {"ok": False, "error": "action_not_found"}
    if row.get("status") != "pending":
        return {"ok": False, "error": "action_not_pending", "action": row}

    kind = str(row.get("kind") or "")
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    result: dict[str, Any]
    if kind in ("softdent_export", "softdent-export"):
        result = softdent_export(
            consent=True,
            report_id=str(payload.get("reportId") or "aging"),
            days=int(payload.get("days") or 30),
        )
    elif kind in ("qb_sync", "qb-sync"):
        result = qb_sync(consent=True, store=store)
    elif kind == "navigate":
        href = str(payload.get("href") or payload.get("page") or "")
        result = {"ok": True, "navigate": href, "clientMustNavigate": True}
    elif kind == "web_research":
        result = web_research_tool(query=str(payload.get("query") or ""))
    elif kind == "memo_write":
        result = memo_write(text=str(payload.get("text") or ""), actor="Operator")
    else:
        result = {"ok": False, "error": "unknown_action_kind", "kind": kind}

    row["status"] = "executed" if result.get("ok") else "failed"
    row["executedAt"] = _utc_now()
    row["result"] = result
    _PENDING[action_id] = row
    return {"ok": bool(result.get("ok")), "action": row, "result": result}
