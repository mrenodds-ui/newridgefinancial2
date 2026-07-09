"""Curated dental payer reference — routing, narrative hints, not member benefits."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

NR2_ROOT = Path(__file__).resolve().parent
PAYER_REFERENCE_PATH = NR2_ROOT / "data" / "payer_reference.json"

TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(str(text or "").lower()))


@lru_cache(maxsize=1)
def load_payer_reference() -> dict[str, Any]:
    if not PAYER_REFERENCE_PATH.is_file():
        return {"version": 0, "payers": []}
    try:
        data = json.loads(PAYER_REFERENCE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 0, "payers": []}
    if not isinstance(data, dict):
        return {"version": 0, "payers": []}
    payers = data.get("payers")
    if not isinstance(payers, list):
        data["payers"] = []
    return data


def list_payers(*, limit: int = 100) -> list[dict[str, Any]]:
    payers = load_payer_reference().get("payers") or []
    cap = max(1, min(int(limit or 100), 500))
    return list(payers[:cap]) if cap < len(payers) else list(payers)


def _score_payer(query: str, query_tokens: set[str], payer: dict[str, Any]) -> int:
    haystack = " ".join(
        [
            str(payer.get("name") or ""),
            " ".join(str(a) for a in (payer.get("aliases") or [])),
            " ".join(str(pid) for pid in (payer.get("payerIds") or [])),
            str(payer.get("type") or ""),
        ]
    ).lower()
    p_tokens = _tokenize(haystack)
    score = len(query_tokens & p_tokens)
    name = str(payer.get("name") or "").lower()
    q_norm = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if q_norm and q_norm == name:
        score += 12
    elif q_norm and (q_norm in name or name in q_norm):
        score += 6
    # Prefer SoftDent InsCo / office workbook rows when query looks like a SoftDent carrier label.
    source = str(payer.get("source") or "")
    if source in {"softdent-insco-sensei", "office-insurance-xlsx"}:
        score += 2
    for token in query_tokens:
        if len(token) >= 4 and token in name:
            score += 2
    for alias in payer.get("aliases") or []:
        alias_l = str(alias).lower()
        if q_norm and q_norm == alias_l:
            score += 8
        elif any(token in alias_l for token in query_tokens if len(token) >= 3):
            score += 1
    return score


def search_payers(query: str, *, limit: int = 3) -> list[dict[str, Any]]:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for payer in load_payer_reference().get("payers") or []:
        if not isinstance(payer, dict):
            continue
        score = _score_payer(query, q_tokens, payer)
        if score > 0:
            scored.append((score, payer))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [payer for _, payer in scored[: max(1, int(limit))]]


def format_payer_hits(payers: list[dict[str, Any]]) -> str:
    if not payers:
        return ""
    lines = [
        "Payer reference matches (routing and narrative hints only — not member-specific benefits; verify eligibility via 270/271 or clearinghouse):"
    ]
    for payer in payers:
        name = str(payer.get("name") or "Unknown payer")
        payer_ids = ", ".join(str(pid) for pid in (payer.get("payerIds") or [])[:3])
        ptype = str(payer.get("type") or "")
        notes = str(payer.get("narrativeNotes") or "").strip()
        elig = str(payer.get("eligibilityNotes") or "").strip()
        if len(notes) > 180:
            notes = notes[:180].rstrip() + "…"
        if len(elig) > 160:
            elig = elig[:160].rstrip() + "…"
        line = f"- {name}"
        if payer_ids:
            line += f" (IDs: {payer_ids})"
        if ptype:
            line += f" [{ptype}]"
        if notes:
            line += f" — {notes}"
        lines.append(line)
        if elig:
            # Prefer surfacing phones/contacts even when narrativeNotes already mentions them
            lines.append(f"  Eligibility / claim contacts: {elig}")
        denials = payer.get("commonDenialCodes") or []
        if denials:
            codes = ", ".join(str(c) for c in denials[:6])
            lines.append(f"  Common denial themes: {codes}")
    return "\n".join(lines)


def enrich_claim_payer(payer_label: str) -> dict[str, Any] | None:
    """Join a SoftDent claim Payer string to payer_reference (best effort)."""
    label = str(payer_label or "").strip()
    if not label or label.lower() in {"insurance", "unknown", "—", "-", "n/a"}:
        return None
    hits = search_payers(label, limit=1)
    if not hits:
        return None
    payer = hits[0]
    notes = str(payer.get("narrativeNotes") or "").strip()
    if len(notes) > 220:
        notes = notes[:220].rstrip() + "…"
    tesia_id = str(payer.get("tesiaPayerId") or "").strip()
    elig_270: bool | None = None
    if tesia_id:
        try:
            from tesia_payer_list_store import find_payer_by_any_id

            tesia = find_payer_by_any_id(tesia_id)
            if tesia:
                tesia_id = str(tesia.get("payerId") or tesia_id)
                if "eligibility270" in tesia:
                    elig_270 = tesia.get("eligibility270")
        except Exception:
            pass
    elif payer.get("payerIds"):
        try:
            from tesia_payer_list_store import find_payer_by_any_id

            for cand in payer.get("payerIds") or []:
                tesia = find_payer_by_any_id(str(cand))
                if tesia:
                    tesia_id = str(tesia.get("payerId") or cand)
                    if "eligibility270" in tesia:
                        elig_270 = tesia.get("eligibility270")
                    break
        except Exception:
            pass
    return {
        "claimPayer": label,
        "matchedName": payer.get("name"),
        "matchedId": payer.get("id"),
        "payerIds": list(payer.get("payerIds") or [])[:3],
        "tesiaPayerId": tesia_id or None,
        "eligibility270": elig_270,
        "eligibilityNotes": str(payer.get("eligibilityNotes") or "").strip()[:160],
        "narrativeNotes": notes,
        "commonDenialCodes": list(payer.get("commonDenialCodes") or [])[:6],
        "source": payer.get("source"),
    }


def enrich_claims(claims: list[dict[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    """Attach payer_reference matches to claim dicts that have a payer field."""
    out: list[dict[str, Any]] = []
    for claim in list(claims or [])[: max(1, int(limit))]:
        if not isinstance(claim, dict):
            continue
        row = dict(claim)
        match = enrich_claim_payer(str(claim.get("payer") or claim.get("Payer") or claim.get("tag") or ""))
        if match:
            row["payerMatch"] = match
        out.append(row)
    return out


def format_claim_payer_joins(claims: list[dict[str, Any]]) -> str:
    enriched = enrich_claims(claims, limit=12)
    joined = [c for c in enriched if c.get("payerMatch")]
    if not joined:
        return ""
    lines = ["Claim <-> payer reference joins (routing hints — verify card/InsCo before submit):"]
    for claim in joined[:8]:
        m = claim["payerMatch"]
        cid = claim.get("id") or claim.get("claimId") or "?"
        status = claim.get("status") or ""
        ids = ", ".join(str(x) for x in (m.get("payerIds") or [])[:2])
        line = f"- {cid}"
        if status:
            line += f" [{status}]"
        line += f": {m.get('claimPayer')} -> {m.get('matchedName')}"
        if ids:
            line += f" (IDs: {ids})"
        tesia = str(m.get("tesiaPayerId") or "").strip()
        if tesia:
            elig = m.get("eligibility270")
            elig_bit = " · 270=yes" if elig is True else (" · 270=no/verify" if elig is False else "")
            line += f" · Tesia/Vyne {tesia}{elig_bit}"
        lines.append(line)
        if m.get("eligibilityNotes"):
            lines.append(f"  Contacts: {m['eligibilityNotes']}")
    generic = sum(
        1
        for c in enriched
        if not c.get("payerMatch")
        and str(c.get("payer") or "").strip().lower() in {"", "insurance", "unknown"}
    )
    if generic:
        lines.append(
            f"- {generic} claim(s) have generic/missing Payer labels (e.g. 'Insurance') — "
            "use SoftDent InsCo / Insurance.xlsx for real carrier names."
        )
    return "\n".join(lines)


def payer_reference_summary() -> dict[str, Any]:
    data = load_payer_reference()
    payers = data.get("payers") or []
    return {
        "ok": True,
        "version": data.get("version"),
        "updatedAt": data.get("updatedAt"),
        "count": len(payers),
        "sourceNote": data.get("sourceNote"),
        "path": str(PAYER_REFERENCE_PATH),
    }
