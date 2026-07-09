"""Token index and search for governed HAL knowledge memories."""

from __future__ import annotations

import re
from typing import Any

from knowledge_memory_store import load_approved_memories

TOKEN_RE = re.compile(r"[a-z0-9]{3,}")

# Expand queries so MemoAI hits clinical/payer/denial playbooks (token overlap search).
QUERY_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "crown": ("d2740", "restoration", "narrative", "fracture", "build-up"),
    "d2740": ("crown", "medical", "necessity", "narrative"),
    "srp": ("d4341", "periodontal", "scaling", "root", "planing", "quadrant"),
    "d4341": ("srp", "periodontal", "prophy", "d1110", "bundling"),
    "prophy": ("d1110", "prophy", "cleaning", "frequency"),
    "implant": ("d6010", "medical", "necessity", "cbct"),
    "endo": ("d3330", "root", "canal", "pulpitis"),
    "denial": ("appeal", "narrative", "reconsideration", "code"),
    "appeal": ("denial", "narrative", "medical", "necessity"),
    "delta": ("dental", "payer", "narrative", "code"),
    "metlife": ("alternate", "downgrade", "composite", "payer"),
    "cigna": ("prior", "auth", "payer", "dental"),
    "aetna": ("payer", "dental", "narrative"),
    "guardian": ("frequency", "prophy", "payer"),
    "medicaid": ("prior", "auth", "medical", "necessity", "kancare"),
    "softdent": ("export", "claims", "import", "missing"),
    "quickbooks": ("readonly", "profit", "loss", "coa", "journal"),
    "tax": ("1120s", "k-1", "scorp", "kansas", "compensation"),
    "hipaa": ("consent", "minimum", "necessary", "phi"),
    "schedule": ("recare", "hygiene", "appointment", "broken"),
    "eob": ("era", "posting", "match", "adjustment"),
    "16": ("denial", "lacks", "info", "missing", "attachment"),
    "co-45": ("contractual", "adjustment", "fee", "schedule"),
    "frequency": ("limit", "denial", "appeal", "prior"),
    "steve": ("office", "manager", "coordination", "closeout"),
    "manager": ("office", "steve", "coordination", "operations"),
    "reno": ("michael", "doctor", "owner", "dentist", "provider"),
    "michael": ("reno", "doctor", "owner", "dentist", "provider"),
    "doctor": ("reno", "michael", "provider", "dentist", "clinical"),
    "dentist": ("reno", "michael", "provider", "owner", "clinical"),
    "owner": ("reno", "michael", "compensation", "w-2", "officer"),
    "provider": ("reno", "michael", "doctor", "dentist", "clinical"),
    "ridge": ("new", "family", "financial", "practice", "office"),
    "hygiene": ("prophy", "recall", "d1110", "d4910", "cleaning", "bitewing"),
    "recall": ("hygiene", "prophy", "schedule", "six", "month"),
    "front": ("desk", "checkin", "checkout", "eligibility", "appointment"),
    "desk": ("front", "checkin", "checkout", "phone", "triage"),
    "pte": ("kansas", "pass", "through", "entity", "election"),
    "1120s": ("k-1", "scorp", "march", "filing", "deadline"),
    "uhc": ("united", "healthcare", "dental", "payer"),
    "humana": ("dental", "frequency", "prophy", "payer"),
    "geha": ("federal", "employee", "dental", "fehb"),
}

PRACTICE_QUERY_HINTS = (
    "steve",
    "office manager",
    "dr reno",
    "dr. reno",
    "michael reno",
    "new ridge",
    "this office",
    "our office",
)


def _expand_query_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for token in list(tokens):
        extras = QUERY_EXPANSIONS.get(token)
        if extras:
            expanded.update(extras)
        if token.startswith("d") and token[1:].isdigit():
            expanded.add("cdt")
            expanded.add("narrative")
    return expanded


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(str(text or "").lower()))


def memory_search_tier(memory: dict[str, Any]) -> int:
    """Higher tier = prefer in search results. Learned practice facts beat core; corpus is lowest."""
    memory_id = str(memory.get("id") or "")
    source = str(memory.get("source") or "").lower()
    if memory_id.startswith("corpus-"):
        return 0
    if memory_id.startswith("nr2-") or "staff:remember" in source or "learned" in source:
        return 2
    return 1


def _score_memory(query: str, q_tokens: set[str], memory: dict[str, Any]) -> int | None:
    memory_id = str(memory.get("id") or "")
    text = str(memory.get("text") or "")
    text_lower = text.lower()
    q_lower = query.lower().strip()

    m_tokens = _tokenize(text)
    m_tokens.update(_tokenize(memory_id.replace("-", " ")))

    overlap = len(q_tokens & m_tokens)
    if overlap <= 0:
        id_slug = memory_id.replace("-", " ")
        if memory_id and memory_id in q_lower.replace(" ", "-"):
            overlap = 4
        elif id_slug and all(part in q_lower for part in id_slug.split()[:2] if len(part) > 2):
            overlap = 3
        else:
            return None

    score = overlap * 10
    tier = memory_search_tier(memory)
    score += tier * 20

    category = str(memory.get("category") or "")
    if any(token in category.lower() for token in q_tokens):
        score += 5

    if memory_id and memory_id in q_lower.replace(" ", "-"):
        score += 100

    if "steve" in q_lower and "steve" in text_lower:
        score += 30
    if "office manager" in q_lower and "office manager" in text_lower:
        score += 35
    if any(token in q_lower for token in ("dr reno", "dr. reno", "michael reno")) and "michael reno" in text_lower:
        score += 40
    if any(token in q_lower for token in ("dentist", "doctor", "provider", "owner")) and "only dentist" in text_lower:
        score += 25
    if "new ridge" in q_lower and "new ridge" in text_lower:
        score += 15

    query_words = [w for w in re.findall(r"[a-z0-9]+", q_lower) if len(w) >= 3]
    for i in range(len(query_words) - 1):
        phrase = f"{query_words[i]} {query_words[i + 1]}"
        if phrase in text_lower:
            score += 12

    if memory_id.startswith("nr2-practice-") and any(
        hint in q_lower for hint in (*PRACTICE_QUERY_HINTS, "cpa", "quarterly", "month-end")
    ):
        score += 20

    if tier == 0 and any(hint in q_lower for hint in PRACTICE_QUERY_HINTS):
        score -= 25

    return score


def build_memory_index(memories: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = memories if memories is not None else load_approved_memories()
    index: list[dict[str, Any]] = []
    for memory in rows:
        text = str(memory.get("text") or "")
        tokens = sorted(_tokenize(text))
        index.append(
            {
                "id": memory.get("id"),
                "category": memory.get("category"),
                "scope": memory.get("scope"),
                "tier": memory_search_tier(memory),
                "tokens": tokens,
                "text": text,
                "source": memory.get("source"),
            }
        )
    return index


def search_memories(query: str, *, limit: int = 5, memories: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    q_tokens = _expand_query_tokens(_tokenize(query))
    if not q_tokens:
        return []
    scored: list[tuple[int, int, int, dict[str, Any]]] = []
    for memory in memories if memories is not None else load_approved_memories():
        score = _score_memory(query, q_tokens, memory)
        if score is None:
            continue
        tier = memory_search_tier(memory)
        text_len = len(str(memory.get("text") or ""))
        scored.append((score, tier, -text_len, memory))
    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [memory for _, _, _, memory in scored[: max(1, int(limit))]]


def format_memory_hits(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return ""
    lines = ["Governed memory matches:"]
    for memory in memories:
        text = str(memory.get("text") or "").strip()
        if len(text) > 220:
            text = text[:220].rstrip() + "…"
        lines.append(f"- {text}")
    return "\n".join(lines)
