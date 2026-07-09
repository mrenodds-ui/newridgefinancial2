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


def _score_payer(query_tokens: set[str], payer: dict[str, Any]) -> int:
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
    for token in query_tokens:
        if len(token) >= 4 and token in name:
            score += 2
    for alias in payer.get("aliases") or []:
        alias_l = str(alias).lower()
        if any(token in alias_l for token in query_tokens if len(token) >= 3):
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
        score = _score_payer(q_tokens, payer)
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
        if len(notes) > 180:
            notes = notes[:180].rstrip() + "…"
        line = f"- {name}"
        if payer_ids:
            line += f" (IDs: {payer_ids})"
        if ptype:
            line += f" [{ptype}]"
        if notes:
            line += f" — {notes}"
        lines.append(line)
        denials = payer.get("commonDenialCodes") or []
        if denials:
            codes = ", ".join(str(c) for c in denials[:6])
            lines.append(f"  Common denial themes: {codes}")
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
