"""Token index and search for governed HAL knowledge memories."""

from __future__ import annotations

import re
from typing import Any

from knowledge_memory_store import load_approved_memories

TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(str(text or "").lower()))


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
                "tokens": tokens,
                "text": text,
                "source": memory.get("source"),
            }
        )
    return index


def search_memories(query: str, *, limit: int = 5, memories: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for memory in memories if memories is not None else load_approved_memories():
        text = str(memory.get("text") or "")
        m_tokens = _tokenize(text)
        if not m_tokens:
            continue
        overlap = len(q_tokens & m_tokens)
        if overlap <= 0:
            continue
        category = str(memory.get("category") or "")
        if any(token in category.lower() for token in q_tokens):
            overlap += 1
        scored.append((overlap, memory))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [memory for _, memory in scored[: max(1, int(limit))]]


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
