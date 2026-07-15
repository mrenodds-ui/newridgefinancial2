"""HAL brains tool + consent action helpers (Moonshot P1/P2).

Invoked only from /api/hal/tools/* and /api/hal/actions/* routes.
SoftDent write-back forbidden; GUI export and QB sync require consent=true.

Money honesty (nr2-12019): monetary chat must cite live SoftDent/QB beams
or explicit UNAVAILABLE — never invent dollars; empty ≠ $0.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

# In-process pending consent actions (operator must click Approve)
_PENDING: dict[str, dict[str, Any]] = {}

# Beam attestation considered stale for optical banner / gate after this many seconds
MONEY_BEAM_STALE_SECONDS = 300

_MONEY_QUERY_RE = re.compile(
    r"(?i)("
    r"\$|usd\b|dollar|balance|outstanding|revenue|receivable|aging|"
    r"\bAR\b|a/?r\b|accounts?\s*receivable|\bAP\b|how\s+much|"
    r"amount\s*(due|owed)?|owed|owing|collections|net\s*income|"
    r"profit|expense|production|deposit|claim(?:s)?\s*(?:total|sum|amount)|"
    r"total\s+(?:outstanding|claims|revenue|income)"
    r")"
)
_DOLLAR_AMOUNT_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")
_AR_QUERY_RE = re.compile(
    r"(?i)\b("
    r"AR\b|a/?r\b|accounts?\s*receivable|outstanding(?:\s+claims?)?|"
    r"claims?\s+outstanding|aging|collections?\s*(?:total|balance)?"
    r")\b"
)
_QB_REVENUE_RE = re.compile(
    r"(?i)\b("
    r"revenue|sales|income|quickbooks|QB\b|P\s*&\s*L|profit\s*and\s*loss|"
    r"monthly\s+revenue|last\s+month(?:'s)?\s+revenue"
    r")\b"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finite(val: Any) -> bool:
    try:
        f = float(val)
        return f == f and abs(f) != float("inf")
    except (TypeError, ValueError):
        return False


def is_money_query(query: str) -> bool:
    """True when the operator ask implies currency or financial totals."""
    q = str(query or "").strip()
    if not q:
        return False
    return bool(_MONEY_QUERY_RE.search(q))


def _parse_dollars_in_text(text: str) -> list[float]:
    out: list[float] = []
    for m in _DOLLAR_AMOUNT_RE.finditer(str(text or "")):
        raw = m.group(1).replace(",", "")
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def _amount_allowed(amount: float, allowed: list[float], *, tol: float = 1.0) -> bool:
    for a in allowed:
        if abs(float(a) - float(amount)) <= tol:
            return True
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


def money_beam_attestation(*, readiness: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attest SoftDent + QB money beams for HAL chat (empty ≠ $0 · no invented currency).

    Injected into the chat system prompt so HAL must cite live beam state and
    never fill ∅ with $0. Includes beamHash + allowedAmounts for reply validation.
    """
    sd = softdent_status()
    qb = qb_summary()
    at = _utc_now()
    allowed: list[float] = []
    for key_src, key in ((sd, "totalOutstanding"), (qb, "monthlyRevenue")):
        val = key_src.get(key)
        if val is not None and _finite(val):
            allowed.append(float(val))
            # Also permit common display rounding (whole dollars)
            allowed.append(float(round(float(val))))
            allowed.append(float(round(float(val), 2)))

    ready = readiness if isinstance(readiness, dict) else {}
    level = str(ready.get("level") or "").lower()
    age_hours = ready.get("ageHours")
    try:
        age_h = float(age_hours) if age_hours is not None else None
    except (TypeError, ValueError):
        age_h = None
    # Import soft-stale / stale / critical blocking → prefer UNAVAILABLE over invent
    blocking = ready.get("blocking") if isinstance(ready.get("blocking"), list) else []
    lasers = ready.get("alignmentLasers") if isinstance(ready.get("alignmentLasers"), dict) else {}
    import_stale = (
        level in ("stale", "degraded", "missing", "error", "unknown")
        or bool(blocking)
        or lasers.get("red") is True
        or (age_h is not None and age_h * 3600 > MONEY_BEAM_STALE_SECONDS and level != "fresh")
    )

    hash_src = "|".join(
        [
            str(sd.get("display")),
            str(sd.get("totalOutstanding")),
            str(qb.get("display")),
            str(qb.get("monthlyRevenue")),
            at,
        ]
    )
    beam_hash = hashlib.sha256(hash_src.encode("utf-8")).hexdigest()[:16]

    lines = [
        "LIVE MONEY BEAMS (cite ONLY these SoftDent/QB displays for currency; never invent other dollars):",
        f"- SoftDent claims: {sd.get('display')} · hasData={bool(sd.get('hasData'))} · {sd.get('hint') or ''}",
        f"- QuickBooks revenue: {qb.get('display')} · hasData={bool(qb.get('hasData'))} · {qb.get('hint') or ''}",
        f"- beamTimestamp={at} · beamHash={beam_hash}",
        "If a beam is ∅ NO SIGNAL / hasData=false: say Financial data unavailable for that source — never $0.",
    ]
    if sd.get("display") == "∅ NO SIGNAL" or qb.get("display") == "∅ NO SIGNAL":
        lines.append(
            "HONESTY: At least one money beam is empty — say NO SIGNAL / no data for that beam; never $0."
        )
    if import_stale:
        lines.append(
            f"IMPORT READINESS {level or 'unknown'} — prefer UNAVAILABLE over invented dollars when unsure."
        )

    return {
        "ok": True,
        "emptyNotZero": True,
        "at": at,
        "beamTimestamp": at,
        "beamHash": beam_hash,
        "staleMaxSeconds": MONEY_BEAM_STALE_SECONDS,
        "importStale": bool(import_stale),
        "importLevel": level or None,
        "allowedAmounts": allowed,
        "softdent": {
            "hasData": sd.get("hasData"),
            "display": sd.get("display"),
            "totalOutstanding": sd.get("totalOutstanding"),
            "at": sd.get("at") or at,
            "hint": sd.get("hint"),
        },
        "quickbooks": {
            "hasData": qb.get("hasData"),
            "display": qb.get("display"),
            "monthlyRevenue": qb.get("monthlyRevenue"),
            "at": qb.get("at") or at,
            "hint": qb.get("hint"),
        },
        "promptBlock": "\n".join(lines),
    }


def try_deterministic_money_reply(query: str, attest: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Beam-grounded answer for clear AR / revenue asks — skip LLM invent risk."""
    q = str(query or "").strip()
    if not q or not is_money_query(q):
        return None
    att = attest if isinstance(attest, dict) else money_beam_attestation()
    sd = att.get("softdent") if isinstance(att.get("softdent"), dict) else {}
    qb = att.get("quickbooks") if isinstance(att.get("quickbooks"), dict) else {}
    ts = str(att.get("beamTimestamp") or att.get("at") or _utc_now())
    beam_hash = str(att.get("beamHash") or "")

    ar_ask = bool(_AR_QUERY_RE.search(q))
    rev_ask = bool(_QB_REVENUE_RE.search(q)) and not ar_ask

    if ar_ask:
        if not sd.get("hasData") or sd.get("totalOutstanding") is None:
            text = (
                "Financial data unavailable (source: SoftDent). "
                "empty ≠ $0 — SoftDent claims beam has no live total."
            )
            return {
                "ok": True,
                "text": text,
                "moneyGrounded": True,
                "beamTimestamp": ts,
                "beamHash": beam_hash,
                "routingReason": "money_honesty_deterministic_softdent_unavailable",
                "source": "SoftDent",
                "unavailable": True,
            }
        total = float(sd["totalOutstanding"])
        text = (
            f"${total:,.0f} outstanding (SoftDent live, synced {ts}). "
            "Grounded to SoftDent claims beam — empty ≠ $0."
        )
        return {
            "ok": True,
            "text": text,
            "moneyGrounded": True,
            "beamTimestamp": ts,
            "beamHash": beam_hash,
            "routingReason": "money_honesty_deterministic_softdent",
            "source": "SoftDent",
            "amount": total,
        }

    if rev_ask:
        if not qb.get("hasData") or qb.get("monthlyRevenue") is None:
            text = (
                "Financial data unavailable (source: QuickBooks). "
                "empty ≠ $0 — QB revenue beam has no live total."
            )
            return {
                "ok": True,
                "text": text,
                "moneyGrounded": True,
                "beamTimestamp": ts,
                "beamHash": beam_hash,
                "routingReason": "money_honesty_deterministic_qb_unavailable",
                "source": "QuickBooks",
                "unavailable": True,
            }
        rev = float(qb["monthlyRevenue"])
        text = (
            f"${rev:,.0f} (QuickBooks latest-month revenue, synced {ts}). "
            "Grounded to QB beam — empty ≠ $0."
        )
        return {
            "ok": True,
            "text": text,
            "moneyGrounded": True,
            "beamTimestamp": ts,
            "beamHash": beam_hash,
            "routingReason": "money_honesty_deterministic_qb",
            "source": "QuickBooks",
            "amount": rev,
        }
    return None


def validate_money_reply(
    text: str,
    *,
    query: str = "",
    attest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate / rewrite assistant text so $ amounts match live beams.

    Returns moneyGrounded, optional rewrite, and money_honesty_violation flag.
    """
    att = attest if isinstance(attest, dict) else money_beam_attestation()
    ts = str(att.get("beamTimestamp") or att.get("at") or _utc_now())
    beam_hash = str(att.get("beamHash") or "")
    money_ask = is_money_query(query)
    body = str(text or "")
    dollars = _parse_dollars_in_text(body)
    allowed = [float(a) for a in (att.get("allowedAmounts") or []) if _finite(a)]

    # Non-money replies without $ — pass through
    if not money_ask and not dollars:
        return {
            "ok": True,
            "text": body,
            "moneyGrounded": None,
            "beamTimestamp": ts,
            "beamHash": beam_hash,
            "rewritten": False,
            "violation": False,
        }

    # Money ask with no $ and no explicit unavailable — try deterministic; else require honesty phrase
    unavailable_ok = bool(
        re.search(
            r"(?i)\b(unavailable|no\s+signal|∅|no\s+data|empty\s*[≠!]=?\s*\$?0)\b",
            body,
        )
    )

    invented = [d for d in dollars if not _amount_allowed(d, allowed)]
    # Explicit $0 while beams empty is a violation (empty ≠ $0)
    sd = att.get("softdent") if isinstance(att.get("softdent"), dict) else {}
    qb = att.get("quickbooks") if isinstance(att.get("quickbooks"), dict) else {}
    zero_while_empty = any(abs(d) < 0.005 for d in dollars) and (
        not sd.get("hasData") or not qb.get("hasData")
    )

    if invented or zero_while_empty:
        det = try_deterministic_money_reply(query, att)
        if det and det.get("text"):
            return {
                "ok": True,
                "text": str(det["text"]),
                "moneyGrounded": True,
                "beamTimestamp": ts,
                "beamHash": beam_hash,
                "rewritten": True,
                "violation": True,
                "error": "money_honesty_violation",
                "inventedAmounts": invented,
                "routingReason": det.get("routingReason"),
            }
        grounded = (
            "Financial data unavailable — HAL refused an ungrounded dollar figure. "
            "empty ≠ $0. Refresh SoftDent/QB beams, then ask again."
        )
        sd_d = sd.get("display") or "∅ NO SIGNAL"
        qb_d = qb.get("display") or "∅ NO SIGNAL"
        grounded += f" Live beams: SoftDent {sd_d}; QuickBooks {qb_d}."
        return {
            "ok": True,
            "text": grounded,
            "moneyGrounded": True,
            "beamTimestamp": ts,
            "beamHash": beam_hash,
            "rewritten": True,
            "violation": True,
            "error": "money_honesty_violation",
            "inventedAmounts": invented,
            "staleBanner": True,
        }

    if money_ask and not dollars and not unavailable_ok:
        det = try_deterministic_money_reply(query, att)
        if det and det.get("text"):
            return {
                "ok": True,
                "text": str(det["text"]),
                "moneyGrounded": True,
                "beamTimestamp": ts,
                "beamHash": beam_hash,
                "rewritten": True,
                "violation": False,
                "routingReason": det.get("routingReason"),
            }

    grounded_flag = True if (money_ask or bool(dollars)) else None
    if money_ask and dollars and not invented:
        grounded_flag = True
    return {
        "ok": True,
        "text": body,
        "moneyGrounded": grounded_flag,
        "beamTimestamp": ts,
        "beamHash": beam_hash,
        "rewritten": False,
        "violation": False,
        "staleBanner": bool(att.get("importStale")),
    }


def money_honesty_session_extra(gate: dict[str, Any] | None) -> dict[str, Any]:
    """Fields appended to session JSONL turns for money audit trail."""
    g = gate if isinstance(gate, dict) else {}
    out: dict[str, Any] = {}
    if g.get("moneyGrounded") is not None:
        out["moneyGrounded"] = bool(g.get("moneyGrounded"))
    if g.get("beamTimestamp"):
        out["beamTimestamp"] = str(g.get("beamTimestamp"))
    if g.get("beamHash"):
        out["beamHash"] = str(g.get("beamHash"))
    if g.get("violation"):
        out["moneyHonestyViolation"] = True
    if g.get("rewritten"):
        out["moneyRewritten"] = True
    if g.get("routingReason"):
        out["routingReason"] = str(g.get("routingReason"))
    return out


# Back-compat aliases used by earlier chat wire-up
query_touches_money = is_money_query


def enforce_money_grounding(
    reply: str,
    attest: dict[str, Any] | None,
    *,
    money_query: bool = False,
    query: str = "",
) -> dict[str, Any]:
    """Adapter over validate_money_reply for /api/hal/chat grounding."""
    q = query if query else ("AR outstanding" if money_query else "")
    gate = validate_money_reply(str(reply or ""), query=q, attest=attest)
    return {
        "text": gate.get("text") or reply,
        "moneyGrounded": gate.get("moneyGrounded"),
        "moneyQuery": money_query or is_money_query(q),
        "beamTimestamp": gate.get("beamTimestamp") or (attest or {}).get("beamTimestamp") or (attest or {}).get("at"),
        "beamHash": gate.get("beamHash") or (attest or {}).get("beamHash"),
        "honestyViolation": "money_honesty_violation" if gate.get("violation") else None,
        "rewritten": bool(gate.get("rewritten")),
        "staleBanner": bool(gate.get("staleBanner")),
        "routingReason": gate.get("routingReason"),
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
    """Consent-gated SoftDent GUI Excel export → SoftDent folder, then copy to exports.

    SoftDent Select File Name keeps SoftDent's own folder (e.g. OneDrive\\Documents).
    Never type SoftDentReportExports / C:\\SOFTDE~1 into SoftDent — invalid directory.
    NR2 copies the XLS into C:\\SoftDentReportExports after SoftDent saves. Excel/Print
    Preview only — never Printer. No SoftDent write-back.
    """
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
                "pathHygiene": "Keep SoftDent folder; never SoftDentReportExports in Select File Name.",
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
            "refreshImportsSuggested": True,
            "pathHygiene": "SoftDent kept its own folder; NR2 copied into SoftDentReportExports.",
            "emptyNotZero": True,
            "at": _utc_now(),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": "softdent_export_failed",
            "detail": str(exc)[:600],
            "fallback": "GUI unreachable or report unsupported — showing cached imports only; empty ≠ $0.",
            "exportRoot": r"C:\SoftDentReportExports",
            "pathHygiene": "Keep SoftDent folder; never SoftDentReportExports in Select File Name.",
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
        from nr2_optical_routes import resolve_optical_href

        href = str(payload.get("href") or "").strip()
        if not href:
            href = resolve_optical_href(str(payload.get("page") or payload.get("target") or ""))
        if not href:
            result = {
                "ok": False,
                "error": "unknown_optical_page",
                "detail": "No optical href for that page key — empty ≠ invent a route.",
            }
        else:
            result = {
                "ok": True,
                "navigate": href,
                "href": href,
                "page": payload.get("page"),
                "clientMustNavigate": True,
                "emptyNotZero": True,
            }
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
