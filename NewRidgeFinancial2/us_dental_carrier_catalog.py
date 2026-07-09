"""US dental carrier + plan-family catalog (public sources; not member benefits)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

NR2_ROOT = Path(__file__).resolve().parent
CATALOG_PATH = NR2_ROOT / "data" / "us_dental_carrier_catalog.json"

TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(str(text or "").lower()))


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.is_file():
        return {"version": 0, "carriers": []}
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 0, "carriers": []}
    if not isinstance(data, dict):
        return {"version": 0, "carriers": []}
    carriers = data.get("carriers")
    if not isinstance(carriers, list):
        data["carriers"] = []
    return data


def catalog_summary() -> dict[str, Any]:
    data = load_catalog()
    carriers = data.get("carriers") or []
    plan_count = 0
    for carrier in carriers:
        if isinstance(carrier, dict):
            plan_count += len(carrier.get("planFamilies") or [])
    return {
        "ok": True,
        "version": data.get("version"),
        "updatedAt": data.get("updatedAt"),
        "carrierCount": len(carriers),
        "planFamilyCount": plan_count,
        "sourceNote": data.get("sourceNote"),
        "marketNotes": data.get("marketNotes") or {},
        "path": str(CATALOG_PATH),
    }


def _score_carrier(query: str, query_tokens: set[str], carrier: dict[str, Any]) -> int:
    plans = " ".join(str(p) for p in (carrier.get("planFamilies") or []))
    members = " ".join(
        str(m.get("name") or "") for m in (carrier.get("memberCompanies") or []) if isinstance(m, dict)
    )
    states = " ".join(
        " ".join(str(s) for s in (m.get("states") or []))
        for m in (carrier.get("memberCompanies") or [])
        if isinstance(m, dict)
    )
    haystack = " ".join(
        [
            str(carrier.get("name") or ""),
            " ".join(str(a) for a in (carrier.get("aliases") or [])),
            str(carrier.get("tier") or ""),
            " ".join(str(c) for c in (carrier.get("channels") or [])),
            " ".join(str(t) for t in (carrier.get("planTypes") or [])),
            plans,
            members,
            states,
            str(carrier.get("notes") or ""),
        ]
    ).lower()
    c_tokens = _tokenize(haystack)
    score = len(query_tokens & c_tokens)
    name = str(carrier.get("name") or "").lower()
    q_norm = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if q_norm and q_norm == name:
        score += 12
    elif q_norm and (q_norm in name or name in q_norm):
        score += 6
    for alias in carrier.get("aliases") or []:
        alias_l = str(alias).lower()
        if q_norm and q_norm == alias_l:
            score += 10
        elif any(token in alias_l for token in query_tokens if len(token) >= 3):
            score += 2
    for plan in carrier.get("planFamilies") or []:
        plan_l = str(plan).lower()
        if q_norm and q_norm in plan_l:
            score += 5
        elif any(token in plan_l for token in query_tokens if len(token) >= 4):
            score += 1
    # State abbreviation boost (e.g. "kansas" / "ks")
    if "kansas" in query_tokens or "ks" in query_tokens:
        for member in carrier.get("memberCompanies") or []:
            if isinstance(member, dict) and "KS" in (member.get("states") or []):
                score += 4
                break
        if carrier.get("id") in {"kansas-medicaid-kancare", "delta-dental", "bcbs-state-plans"}:
            score += 2
    return score


def search_carriers(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    q_tokens = _tokenize(q)
    carriers = [c for c in (load_catalog().get("carriers") or []) if isinstance(c, dict)]
    if not q_tokens:
        return carriers[: max(1, min(int(limit or 5), 50))]
    scored: list[tuple[int, dict[str, Any]]] = []
    for carrier in carriers:
        score = _score_carrier(q, q_tokens, carrier)
        if score > 0:
            scored.append((score, carrier))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [carrier for _, carrier in scored[: max(1, int(limit))]]


def format_carrier_hits(carriers: list[dict[str, Any]]) -> str:
    if not carriers:
        return ""
    lines = [
        "US dental carrier catalog matches (plan families / market context — not member benefits; "
        "verify eligibility via 270/271 or clearinghouse; prefer SoftDent InsCo / payer_reference for claim routing):"
    ]
    for carrier in carriers:
        name = str(carrier.get("name") or "Unknown carrier")
        tier = str(carrier.get("tier") or "")
        types = ", ".join(str(t) for t in (carrier.get("planTypes") or [])[:4])
        line = f"- {name}"
        if tier:
            line += f" [{tier}]"
        if types:
            line += f" ({types})"
        lines.append(line)
        plans = [str(p) for p in (carrier.get("planFamilies") or [])[:6]]
        if plans:
            lines.append(f"  Plan families: {'; '.join(plans)}")
            extra = len(carrier.get("planFamilies") or []) - len(plans)
            if extra > 0:
                lines[-1] += f" (+{extra} more)"
        notes = str(carrier.get("notes") or "").strip()
        if notes:
            if len(notes) > 180:
                notes = notes[:180].rstrip() + "…"
            lines.append(f"  Notes: {notes}")
        members = carrier.get("memberCompanies") or []
        if members:
            ks = [
                str(m.get("name"))
                for m in members
                if isinstance(m, dict) and "KS" in (m.get("states") or [])
            ]
            if ks:
                lines.append(f"  Kansas entity: {', '.join(ks)}")
            else:
                lines.append(f"  Member companies: {len(members)} state/regional entities")
    return "\n".join(lines)
