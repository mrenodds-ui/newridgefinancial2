"""Load and store governed HAL knowledge memories for the NR2 desktop app."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILTIN_MEMORIES_PATH = REPO_ROOT / "docs" / "hal_knowledge" / "memories.jsonl"
LEARNED_MEMORIES_PATH = REPO_ROOT / "app_data" / "nr2" / "learned_memories.jsonl"

APPROVED_STATUS = "approved"
INDEXABLE_CONFIDENCE = {"high", "medium"}
BLOCKED_SENSITIVITY = {"restricted", "prohibited"}
FORBIDDEN_TEXT_PATTERNS = (
    "patientname,mrn,claimid",
    "api_key",
    "password=",
    "secret=",
    "bearer ",
)

VALID_CATEGORIES = {
    "project_architecture",
    "hal_runtime_lanes",
    "known_workflows",
    "safety_policy",
    "insurance_narratives",
    "softdent_exports",
    "quickbooks_readonly",
    "known_bugs_and_fixes",
    "operator_playbooks",
    "deployment_notes",
    "test_results",
    "future_tasks",
    "tax_accounting",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug_id(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = slug[:48] or "learned-fact"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"nr2-{slug}-{stamp}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def memory_contains_forbidden(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(pattern in lowered for pattern in FORBIDDEN_TEXT_PATTERNS)


def is_memory_indexable(memory: dict[str, Any]) -> bool:
    if memory.get("status") != APPROVED_STATUS:
        return False
    if memory.get("confidence") not in INDEXABLE_CONFIDENCE:
        return False
    if memory.get("sensitivity_level") in BLOCKED_SENSITIVITY:
        return False
    text = str(memory.get("text") or "").strip()
    if len(text) < 10:
        return False
    if memory_contains_forbidden(text):
        return False
    return True


def infer_memory_category(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ("softdent", "daysheet", "carestream", "sensei")):
        return "softdent_exports"
    if any(token in lower for token in ("quickbooks", "p&l", "journal entry")):
        return "quickbooks_readonly"
    if any(
        token in lower
        for token in (
            "1120-s",
            "1120s",
            "k-1",
            "k-120s",
            "s corp",
            "s-corp",
            "kansas tax",
            "federal tax",
            "reasonable compensation",
            "pte tax",
            "pass-through",
            "estimated tax",
            "section 199a",
            "qbi",
        )
    ):
        return "tax_accounting"
    if any(token in lower for token in ("narrative", "insurance", "claim", "payer", "denial")):
        return "insurance_narratives"
    if any(token in lower for token in ("firewall", "must not", "never submit", "read-only")):
        return "safety_policy"
    if any(token in lower for token in ("bug", "fix", "workaround", "incident")):
        return "known_bugs_and_fixes"
    return "operator_playbooks"


def infer_memory_scope(text: str, category: str) -> str:
    lower = text.lower()
    if category == "softdent_exports" or "softdent" in lower:
        return "softdent"
    if category == "quickbooks_readonly" or "quickbooks" in lower:
        return "quickbooks"
    if category == "insurance_narratives":
        return "insurance_narratives"
    if category == "tax_accounting" or any(token in lower for token in ("1120-s", "k-120s", "s corp", "s-corp", "kansas tax")):
        return "taxes"
    return "hal"


def load_approved_memories() -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for path in (BUILTIN_MEMORIES_PATH, LEARNED_MEMORIES_PATH):
        for row in _read_jsonl(path):
            memory_id = str(row.get("id") or "").strip()
            if memory_id:
                merged[memory_id] = row
    return [row for row in merged.values() if is_memory_indexable(row)]


def remember_fact(
    text: str,
    *,
    source: str = "staff:remember",
    category: str | None = None,
    actor: str = "Staff",
) -> dict[str, Any]:
    body = " ".join(str(text or "").split()).strip()
    if len(body) < 10:
        raise ValueError("Memory text must be at least 10 characters.")
    if len(body) > 2000:
        body = body[:2000].rstrip()
    if memory_contains_forbidden(body):
        raise ValueError("Memory text contains blocked sensitive patterns.")

    cat = category if category in VALID_CATEGORIES else infer_memory_category(body)
    now = _utc_now()
    memory = {
        "id": _slug_id(body),
        "category": cat,
        "text": body,
        "source": str(source or "staff:remember")[:500],
        "created_at": now,
        "last_verified_at": now,
        "confidence": "medium",
        "scope": infer_memory_scope(body, cat),
        "staleness_rule": "verify_monthly",
        "sensitivity_level": "public_docs",
        "status": APPROVED_STATUS,
        "must_not_override": ["runtime_status", "guardrails", "source_availability"],
        "notes": f"Saved by {actor} in NR2 desktop app.",
    }

    LEARNED_MEMORIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEARNED_MEMORIES_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(memory, ensure_ascii=False) + "\n")

    return {
        "ok": True,
        "memory": memory,
        "path": str(LEARNED_MEMORIES_PATH),
        "approvedCount": len(load_approved_memories()),
    }


def remember_web_findings(results: list[dict[str, Any]], *, query: str, actor: str = "Staff") -> dict[str, Any]:
    snippets: list[str] = []
    sources: list[str] = []
    for row in results[:3]:
        title = str(row.get("title") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        url = str(row.get("url") or "").strip()
        if title and snippet:
            snippets.append(f"{title}: {snippet}")
        if url:
            sources.append(url)
    if not snippets:
        raise ValueError("No web findings available to remember.")

    body = f"Public reference ({query}): " + " | ".join(snippets)
    source = "web_research:" + (sources[0] if sources else "duckduckgo")
    return remember_fact(body, source=source, category=infer_memory_category(query), actor=actor)
