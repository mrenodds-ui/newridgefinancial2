"""HAL brains tool + consent action helpers (Moonshot P1/P2).

Invoked only from /api/hal/tools/* and /api/hal/actions/* routes.
SoftDent write-back forbidden. SoftDent GUI Excel export, QB read-only sync, and
optical navigate are consent-free for HAL (read autonomy). SoftDent write-back,
QB post, payer submit, and outbound email stay consent-gated.

Money honesty (nr2-12019): monetary chat must cite live SoftDent/QB beams
or explicit UNAVAILABLE — never invent dollars; empty ≠ $0.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# In-process pending actions — write/outbound kinds still need Approve;
# read-autonomous kinds auto-execute without a modal.
_PENDING: dict[str, dict[str, Any]] = {}

# Read-only / local desk actions HAL may run without operator click.
_READ_AUTONOMOUS_KINDS = frozenset(
    {
        "softdent_export",
        "softdent-export",
        "qb_sync",
        "qb-sync",
        "navigate",
        "web_research",
        "web-research",
        "memo_write",
        "memo-write",
        "memo_search",
        "memo-search",
        "refresh_imports",
        "refresh-imports",
        "desk_smoke",
        "desk-smoke",
        "beam_verify",
        "beam-verify",
    }
)


def is_read_autonomous_kind(kind: str | None) -> bool:
    k = str(kind or "").strip().lower()
    if k in _READ_AUTONOMOUS_KINDS:
        return True
    return k.replace("_", "-") in {x.replace("_", "-") for x in _READ_AUTONOMOUS_KINDS}

# Beam attestation considered stale for optical banner / gate after this many seconds
MONEY_BEAM_STALE_SECONDS = 300
# Desk proof: HAL chat + optical share one attest snapshot within this window.
BEAM_ATTEST_CACHE_TTL_SEC = 3.0
_attest_cache_lock = threading.Lock()
_attest_cache: dict[str, Any] = {"at_mono": 0.0, "payload": None}

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


def compute_beam_hashes(
    softdent: dict[str, Any] | None,
    quickbooks: dict[str, Any] | None,
    *,
    at: str | None = None,
) -> dict[str, str]:
    """Canonical money-beam hashes.

    dataBeamHash — stable while SoftDent/QB displays+totals match (desk proof identity).
    beamHash — includes attest timestamp (unique snapshot id for JSONL / close).
    """
    sd = softdent if isinstance(softdent, dict) else {}
    qb = quickbooks if isinstance(quickbooks, dict) else {}
    data_src = "|".join(
        [
            str(sd.get("display")),
            str(sd.get("totalOutstanding")),
            str(qb.get("display")),
            str(qb.get("monthlyRevenue")),
        ]
    )
    data_hash = hashlib.sha256(data_src.encode("utf-8")).hexdigest()[:16]
    stamp = str(at or _utc_now())
    beam_hash = hashlib.sha256((data_src + "|" + stamp).encode("utf-8")).hexdigest()[:16]
    return {"dataBeamHash": data_hash, "beamHash": beam_hash, "beamTimestamp": stamp}


def clear_beam_attest_cache() -> None:
    with _attest_cache_lock:
        _attest_cache["at_mono"] = 0.0
        _attest_cache["payload"] = None


def money_beam_attestation(
    *,
    readiness: dict[str, Any] | None = None,
    bypass_cache: bool = False,
) -> dict[str, Any]:
    """Attest SoftDent + QB money beams for HAL chat (empty ≠ $0 · no invented currency).

    Includes beamHash + dataBeamHash. Short TTL cache so HAL and optical share one snapshot.
    """
    if not bypass_cache:
        with _attest_cache_lock:
            age = time.monotonic() - float(_attest_cache.get("at_mono") or 0.0)
            cached = _attest_cache.get("payload")
            if cached and age < BEAM_ATTEST_CACHE_TTL_SEC:
                out = dict(cached)
                if isinstance(readiness, dict):
                    ready = readiness
                    level = str(ready.get("level") or "").lower()
                    age_hours = ready.get("ageHours")
                    try:
                        age_h = float(age_hours) if age_hours is not None else None
                    except (TypeError, ValueError):
                        age_h = None
                    blocking = ready.get("blocking") if isinstance(ready.get("blocking"), list) else []
                    lasers = (
                        ready.get("alignmentLasers")
                        if isinstance(ready.get("alignmentLasers"), dict)
                        else {}
                    )
                    import_stale = (
                        level in ("stale", "degraded", "missing", "error", "unknown")
                        or bool(blocking)
                        or lasers.get("red") is True
                        or (
                            age_h is not None
                            and age_h * 3600 > MONEY_BEAM_STALE_SECONDS
                            and level != "fresh"
                        )
                    )
                    out["importStale"] = bool(import_stale)
                    out["importLevel"] = level or None
                out["cached"] = True
                return out

    sd = softdent_status()
    qb = qb_summary()
    at = _utc_now()
    hashes = compute_beam_hashes(sd, qb, at=at)
    allowed: list[float] = []
    for key_src, key in ((sd, "totalOutstanding"), (qb, "monthlyRevenue")):
        val = key_src.get(key)
        if val is not None and _finite(val):
            allowed.append(float(val))
            allowed.append(float(round(float(val))))
            allowed.append(float(round(float(val), 2)))

    ready = readiness if isinstance(readiness, dict) else {}
    level = str(ready.get("level") or "").lower()
    age_hours = ready.get("ageHours")
    try:
        age_h = float(age_hours) if age_hours is not None else None
    except (TypeError, ValueError):
        age_h = None
    blocking = ready.get("blocking") if isinstance(ready.get("blocking"), list) else []
    lasers = ready.get("alignmentLasers") if isinstance(ready.get("alignmentLasers"), dict) else {}
    import_stale = (
        level in ("stale", "degraded", "missing", "error", "unknown")
        or bool(blocking)
        or lasers.get("red") is True
        or (age_h is not None and age_h * 3600 > MONEY_BEAM_STALE_SECONDS and level != "fresh")
    )

    beam_hash = hashes["beamHash"]
    data_hash = hashes["dataBeamHash"]
    lines = [
        "LIVE MONEY BEAMS (cite ONLY these SoftDent/QB displays for currency; never invent other dollars):",
        f"- SoftDent claims: {sd.get('display')} · hasData={bool(sd.get('hasData'))} · {sd.get('hint') or ''}",
        f"- QuickBooks revenue: {qb.get('display')} · hasData={bool(qb.get('hasData'))} · {qb.get('hint') or ''}",
        f"- beamTimestamp={at} · beamHash={beam_hash} · dataBeamHash={data_hash}",
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

    payload = {
        "ok": True,
        "emptyNotZero": True,
        "at": at,
        "beamTimestamp": at,
        "beamHash": beam_hash,
        "dataBeamHash": data_hash,
        "staleMaxSeconds": MONEY_BEAM_STALE_SECONDS,
        "importStale": bool(import_stale),
        "importLevel": level or None,
        "allowedAmounts": allowed,
        "cached": False,
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
    with _attest_cache_lock:
        _attest_cache["at_mono"] = time.monotonic()
        _attest_cache["payload"] = dict(payload)
    return payload


def beam_desk_proof(*, readiness: dict[str, Any] | None = None) -> dict[str, Any]:
    """Formal desk proof: live money beams vs period-close snapshot (dataBeamHash identity)."""
    live = money_beam_attestation(readiness=readiness)
    close: dict[str, Any] = {}
    try:
        from daily_closeout import period_close_status

        close = period_close_status()
    except Exception as exc:  # noqa: BLE001
        close = {"ok": False, "error": str(exc)[:160]}

    live_data = str(live.get("dataBeamHash") or "")
    live_beam = str(live.get("beamHash") or "")
    close_beam = str(close.get("beamHash") or "")
    close_data = ""
    last = close.get("lastClose") if isinstance(close.get("lastClose"), dict) else {}
    if last.get("dataBeamHash"):
        close_data = str(last.get("dataBeamHash") or "")
    if not close_data and (last.get("softdentDisplay") is not None or last.get("qbDisplay") is not None):
        close_data = compute_beam_hashes(
            {"display": last.get("softdentDisplay"), "totalOutstanding": last.get("softdentTotal")},
            {"display": last.get("qbDisplay"), "monthlyRevenue": last.get("qbRevenue")},
        )["dataBeamHash"]

    match = bool(live_data and close_data and live_data == close_data)
    return {
        "ok": True,
        "emptyNotZero": True,
        "hashFormat": "sha256-16",
        "live": {
            "beamHash": live_beam,
            "dataBeamHash": live_data,
            "beamTimestamp": live.get("beamTimestamp") or live.get("at"),
            "softdent": live.get("softdent"),
            "quickbooks": live.get("quickbooks"),
            "importStale": live.get("importStale"),
            "cached": live.get("cached"),
        },
        "periodClose": {
            "status": close.get("status"),
            "beamHash": close_beam or None,
            "dataBeamHash": close_data or None,
            "completedAt": close.get("completedAt"),
            "forceClose": close.get("forceClose"),
        },
        "match": {
            "liveDataEqualsCloseData": match,
            "note": "dataBeamHash compares SoftDent/QB displays+totals; beamHash includes attest time.",
        },
        "deskProof": "MATCH" if match else ("NO CLOSE HASH" if not close_data else "MISMATCH"),
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
    data_hash = str(att.get("dataBeamHash") or "")
    hash_cite = f"beamHash={beam_hash}" + (f" dataBeamHash={data_hash}" if data_hash else "")

    ar_ask = bool(_AR_QUERY_RE.search(q))
    rev_ask = bool(_QB_REVENUE_RE.search(q)) and not ar_ask

    if ar_ask:
        if not sd.get("hasData") or sd.get("totalOutstanding") is None:
            text = (
                "Financial data unavailable (source: SoftDent). "
                f"empty ≠ $0 — SoftDent claims beam has no live total. ({hash_cite})"
            )
            return {
                "ok": True,
                "text": text,
                "moneyGrounded": True,
                "beamTimestamp": ts,
                "beamHash": beam_hash,
                "dataBeamHash": data_hash or None,
                "routingReason": "money_honesty_deterministic_softdent_unavailable",
                "source": "SoftDent",
                "unavailable": True,
            }
        total = float(sd["totalOutstanding"])
        text = (
            f"${total:,.0f} outstanding (SoftDent live, synced {ts}). "
            f"Grounded to SoftDent claims beam — empty ≠ $0. ({hash_cite})"
        )
        return {
            "ok": True,
            "text": text,
            "moneyGrounded": True,
            "beamTimestamp": ts,
            "beamHash": beam_hash,
            "dataBeamHash": data_hash or None,
            "routingReason": "money_honesty_deterministic_softdent",
            "source": "SoftDent",
            "amount": total,
        }

    if rev_ask:
        if not qb.get("hasData") or qb.get("monthlyRevenue") is None:
            text = (
                "Financial data unavailable (source: QuickBooks). "
                f"empty ≠ $0 — QB revenue beam has no live total. ({hash_cite})"
            )
            return {
                "ok": True,
                "text": text,
                "moneyGrounded": True,
                "beamTimestamp": ts,
                "beamHash": beam_hash,
                "dataBeamHash": data_hash or None,
                "routingReason": "money_honesty_deterministic_qb_unavailable",
                "source": "QuickBooks",
                "unavailable": True,
            }
        rev = float(qb["monthlyRevenue"])
        text = (
            f"${rev:,.0f} (QuickBooks latest-month revenue, synced {ts}). "
            f"Grounded to QB beam — empty ≠ $0. ({hash_cite})"
        )
        return {
            "ok": True,
            "text": text,
            "moneyGrounded": True,
            "beamTimestamp": ts,
            "beamHash": beam_hash,
            "dataBeamHash": data_hash or None,
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


def qb_sync(*, consent: bool = True, store, actor: str = "hal") -> dict[str, Any]:
    """QuickBooks read-only sync — consent-free for HAL / scheduler (no silent QB post)."""
    _ = consent  # retained for API compatibility; read sync is autonomous
    try:
        from qb_connector import sync_read_only

        result = sync_read_only(store)
        return {
            "ok": True,
            "consentRequired": False,
            "autonomous": True,
            "actor": str(actor or "hal")[:64],
            "result": result,
            "at": _utc_now(),
            "emptyNotZero": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc)[:400],
            "consentRequired": False,
            "autonomous": True,
            "actor": str(actor or "hal")[:64],
        }


def softdent_export(*, consent: bool = True, report_id: str = "aging", days: int = 30) -> dict[str, Any]:
    """SoftDent GUI Excel export → SoftDent folder, then copy to exports.

    HAL may run this without operator consent (read-only GUI export). SoftDent
    Select File Name keeps SoftDent's own folder (e.g. OneDrive\\Documents).
    Never type SoftDentReportExports / C:\\SOFTDE~1 into SoftDent — invalid directory.
    NR2 copies the XLS into C:\\SoftDentReportExports after SoftDent saves.
    Output Options: Excel or Print Preview only — never Printer, never File.
    When SoftDent greys out Excel, falls back to Print Preview (visual; no money invent).
    No SoftDent write-back.
    """
    _ = consent  # retained for API compatibility; SoftDent export is consent-free for HAL
    try:
        from softdent_gui_export import (
            SoftDentExcelDisabledError,
            ensure_softdent_ready_for_gui_export,
            export_report_by_id,
            open_report_print_preview,
            softdent_main_running,
        )

        ensure = None
        if not softdent_main_running():
            ensure = ensure_softdent_ready_for_gui_export(timeout_s=60.0)
            if not ensure.get("ok"):
                return {
                    "ok": False,
                    "error": "softdent_gui_unreachable",
                    "detail": str(
                        ensure.get("error")
                        or "SoftDent desktop not running. Launch CS SoftDent Software.lnk, then retry export."
                    ),
                    "ensure": ensure,
                    "fallback": (
                        "Teach mode — open SoftDent → Reports for the requested report; "
                        "Output Options Excel or Print Preview only (never File/Printer)."
                    ),
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
        try:
            path = export_report_by_id(rid, start=start, end=end)
        except SoftDentExcelDisabledError as exc:
            # SoftDent Excel greyed out — Print Preview only (never File).
            preview = open_report_print_preview(rid, start=start, end=end)
            preview_ok = bool(preview.get("ok")) and bool(preview.get("printPreviewOpen"))
            return {
                "ok": preview_ok,
                "consentRequired": False,
                "autonomous": True,
                "reportId": rid,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "path": None,
                "fileSizeBytes": 0,
                "outputMode": "print_preview",
                "moneyBeamIngest": False,
                "excelDisabled": True,
                "preview": preview,
                "exportRoot": r"C:\SoftDentReportExports",
                "refreshImportsSuggested": False,
                "pathHygiene": "Excel disabled on SoftDent Output Options — Print Preview only (never File).",
                "emptyNotZero": True,
                "ensure": ensure,
                "error": None if preview_ok else "print_preview_failed",
                "detail": (
                    str(exc)[:400]
                    if preview_ok
                    else (
                        f"{exc}; preview: {preview.get('error') or preview.get('nextStep')}"
                    )[:600]
                ),
                "at": _utc_now(),
            }
        file_size = 0
        try:
            file_size = int(Path(path).stat().st_size)
        except OSError:
            file_size = 0
        return {
            "ok": True,
            "consentRequired": False,
            "autonomous": True,
            "reportId": rid,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "path": str(path),
            "fileSizeBytes": file_size,
            "outputMode": "excel",
            "moneyBeamIngest": True,
            "excelDisabled": False,
            "exportRoot": r"C:\SoftDentReportExports",
            "refreshImportsSuggested": True,
            "pathHygiene": "SoftDent kept its own folder; NR2 copied into SoftDentReportExports.",
            "emptyNotZero": True,
            "ensure": ensure,
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


# Morning period-close SoftDent Excel bundle (consent-free; write-back forbidden).
MORNING_SOFTDENT_REPORT_IDS = ("aging", "register", "collections")
SOFTDENT_EXCEL_ENABLEMENT_RUNBOOK = (
    "NewRidgeFinancial2/docs/runbooks/softdent_excel_enablement_nr2.md"
)


def softdent_export_morning_bundle(*, days: int = 30) -> dict[str, Any]:
    """Export aging + register + collections for morning period-close.

    Aging is required for money beams. Register/collections are best-effort.
    If aging fails → ok=False (caller may attest-only). Partial secondary failures
    still return ok=True with failed[] listed — empty ≠ $0.
    """
    ensure = None
    try:
        from softdent_gui_export import ensure_softdent_ready_for_gui_export

        # Always prep SoftDent (launch if down; focus if up) — Optical Bench steals FG.
        ensure = ensure_softdent_ready_for_gui_export(timeout_s=90.0)
    except Exception as exc:  # noqa: BLE001
        ensure = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:240]}

    if isinstance(ensure, dict) and not ensure.get("ok"):
        return {
            "ok": False,
            "consentRequired": False,
            "bundle": True,
            "reportIds": list(MORNING_SOFTDENT_REPORT_IDS),
            "reports": {},
            "ensure": ensure,
            "okCount": 0,
            "failed": list(MORNING_SOFTDENT_REPORT_IDS),
            "agingOk": False,
            "partial": False,
            "exportPartial": False,
            "path": None,
            "paths": [],
            "exportRoot": r"C:\SoftDentReportExports",
            "refreshImportsSuggested": False,
            "pathHygiene": "SoftDent must be focused before Excel export.",
            "excelEnablementRunbook": SOFTDENT_EXCEL_ENABLEMENT_RUNBOOK,
            "excelEnablementGate": (
                "SoftDent not ready — follow Excel enablement runbook after SoftDent is up; "
                "never invent Select File Name directories; empty ≠ $0."
            ),
            "emptyNotZero": True,
            "at": _utc_now(),
            "error": "softdent_not_ready",
            "detail": str(ensure.get("error") or "SoftDent not ready for GUI export")[:600],
        }

    reports: dict[str, Any] = {}
    failed: list[str] = []
    paths: list[str] = []
    for rid in MORNING_SOFTDENT_REPORT_IDS:
        # Re-assert SoftDent focus between reports (Optical/Chrome can steal mid-bundle).
        try:
            from softdent_gui_export import (
                ensure_softdent_ready_for_gui_export,
                prepare_softdent_for_next_report,
            )

            prepare_softdent_for_next_report()
            ensure_softdent_ready_for_gui_export(timeout_s=30.0)
        except Exception:
            pass
        one = softdent_export(report_id=rid, days=days)
        reports[rid] = one
        if one.get("ok"):
            if one.get("path"):
                paths.append(str(one["path"]))
            elif one.get("outputMode") == "print_preview":
                # Preview-only is an allowed Output Options path (never File), but not money ingest.
                pass
            else:
                failed.append(rid)
        else:
            failed.append(rid)

    aging = reports.get("aging") or {}
    # Money beams need Excel aging drop — Print Preview is honest visual only (empty ≠ $0).
    aging_excel_ok = bool(aging.get("ok")) and bool(aging.get("moneyBeamIngest")) and bool(aging.get("path"))
    preview_ok_count = sum(
        1
        for r in reports.values()
        if r.get("ok") and r.get("outputMode") == "print_preview"
    )
    excel_disabled = any(bool(r.get("excelDisabled")) for r in reports.values())
    ok_count = sum(1 for r in reports.values() if r.get("ok"))
    gate = None
    if not aging_excel_ok:
        gate = (
            "Attended morning-bundle re-run blocked for money beams until SoftDent Output Options "
            f"Excel is enabled (runbook: {SOFTDENT_EXCEL_ENABLEMENT_RUNBOOK}). "
            "Preview-only keeps attest_only · empty ≠ $0 · never File · never invent directories. "
            "After Excel is clickable, say approve for attended morning bundle."
        )
    return {
        "ok": aging_excel_ok,
        "consentRequired": False,
        "bundle": True,
        "reportIds": list(MORNING_SOFTDENT_REPORT_IDS),
        "reports": reports,
        "ensure": ensure,
        "okCount": ok_count,
        "failed": failed,
        "agingOk": aging_excel_ok,
        "previewOkCount": preview_ok_count,
        "excelDisabled": excel_disabled,
        "partial": aging_excel_ok and bool(failed),
        "exportPartial": bool(failed) and aging_excel_ok,
        "path": aging.get("path"),
        "paths": paths,
        "exportRoot": r"C:\SoftDentReportExports",
        "refreshImportsSuggested": aging_excel_ok,
        "pathHygiene": (
            "Excel or Print Preview only (never File/Printer). "
            "SoftDent Excel greyed out → Print Preview; money beams stay empty ≠ $0 until Excel enabled."
            if excel_disabled
            else "SoftDent kept its own folder; NR2 copied into SoftDentReportExports."
        ),
        "excelEnablementRunbook": SOFTDENT_EXCEL_ENABLEMENT_RUNBOOK,
        "excelEnablementGate": gate,
        "emptyNotZero": True,
        "at": _utc_now(),
        "error": None
        if aging_excel_ok
        else (
            "softdent_excel_disabled"
            if excel_disabled
            else str(aging.get("error") or "aging_export_failed")
        ),
        "detail": None
        if aging_excel_ok
        else str(
            aging.get("detail")
            or (
                "SoftDent Output Options Excel disabled — Print Preview used; "
                "enable SoftDent Excel export for money-beam ingest."
                if excel_disabled
                else ""
            )
        )[:600],
        "fallback": "attest_only" if not aging_excel_ok else None,
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
    kind_s = str(kind or "custom")[:64]
    # Read autonomy: SoftDent Excel, QB sync, navigate, memo/web — no operator click.
    consent_required = not is_read_autonomous_kind(kind_s)
    row = {
        "actionId": action_id,
        "kind": kind_s,
        "label": str(label or kind)[:240],
        "payload": payload or {},
        "status": "pending",
        "createdAt": _utc_now(),
        "consentRequired": consent_required,
        "autonomous": not consent_required,
    }
    _PENDING[action_id] = row
    return {"ok": True, "action": row, "consentRequired": consent_required}


def list_pending_actions() -> dict[str, Any]:
    pending = [v for v in _PENDING.values() if v.get("status") == "pending"]
    return {"ok": True, "pending": pending, "count": len(pending)}


def execute_action(*, action_id: str, consent: bool, store=None) -> dict[str, Any]:
    row = _PENDING.get(str(action_id))
    if not row:
        return {"ok": False, "error": "action_not_found"}
    if row.get("status") != "pending":
        return {"ok": False, "error": "action_not_pending", "action": row}

    kind = str(row.get("kind") or "")
    read_auto = is_read_autonomous_kind(kind)
    softdent_export_kind = kind in ("softdent_export", "softdent-export")
    if not consent and not read_auto:
        return {"ok": False, "error": "consent_required"}

    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    result: dict[str, Any]
    if softdent_export_kind:
        result = softdent_export(
            report_id=str(payload.get("reportId") or "aging"),
            days=int(payload.get("days") or 30),
        )
    elif kind in ("qb_sync", "qb-sync"):
        result = qb_sync(consent=True, store=store, actor="hal-action")
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
