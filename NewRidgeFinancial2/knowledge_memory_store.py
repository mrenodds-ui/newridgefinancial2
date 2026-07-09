"""Load and store governed HAL knowledge memories for the NR2 desktop app."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILTIN_MEMORIES_PATH = REPO_ROOT / "docs" / "hal_knowledge" / "memories.jsonl"
CORPUS_MEMORIES_PATH = REPO_ROOT / "docs" / "hal_knowledge" / "memories_corpus.jsonl"
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


def memory_source_paths() -> list[Path]:
    paths = [BUILTIN_MEMORIES_PATH, CORPUS_MEMORIES_PATH, LEARNED_MEMORIES_PATH]
    return [path for path in paths if path.is_file()]


def _memory_files_signature() -> str:
    parts: list[str] = []
    for path in memory_source_paths():
        stat = path.stat()
        parts.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts)


@lru_cache(maxsize=2)
def _load_approved_memories_cached(signature: str) -> tuple[dict[str, Any], ...]:
    merged: dict[str, dict[str, Any]] = {}
    for path in memory_source_paths():
        for row in _read_jsonl(path):
            memory_id = str(row.get("id") or "").strip()
            if memory_id:
                merged[memory_id] = row
    return tuple(row for row in merged.values() if is_memory_indexable(row))


def load_approved_memories() -> list[dict[str, Any]]:
    return list(_load_approved_memories_cached(_memory_files_signature()))


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

    _load_approved_memories_cached.cache_clear()

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


def title_from_memory_id(memory_id: str) -> str:
    return " ".join(part.capitalize() for part in str(memory_id or "").split("-") if part)


def resolve_memory_citations(ids: list[str] | tuple[str, ...]) -> list[dict[str, str]]:
    """Resolve governed memory IDs to UI citation objects (title + detail excerpt)."""
    by_id = {str(row.get("id") or ""): row for row in load_approved_memories()}
    citations: list[dict[str, str]] = []
    for raw_id in ids:
        memory_id = str(raw_id or "").strip()
        if not memory_id:
            continue
        memory = by_id.get(memory_id)
        if memory:
            text = str(memory.get("text") or "").strip()
            detail = text if len(text) <= 280 else text[:280].rstrip() + "…"
            citations.append(
                {
                    "id": memory_id,
                    "title": title_from_memory_id(memory_id),
                    "detail": detail,
                    "source": str(memory.get("source") or ""),
                    "category": str(memory.get("category") or ""),
                }
            )
        else:
            citations.append(
                {
                    "id": memory_id,
                    "title": title_from_memory_id(memory_id),
                    "detail": "",
                    "source": "",
                    "category": "",
                }
            )
    return citations


def build_browser_memo_index(*, priority_only: bool = False, limit: int = 400) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    memories = load_approved_memories()
    if priority_only:
        priority_ids = {
            "scorp-reasonable-compensation-dental",
            "scorp-section-199a-qbi",
            "kansas-pte-tax-election",
            "scorp-quickbooks-readonly-prep",
            "nr2-taxes-page-scope",
            "scorp-1120s-deadline",
            "nr2-practice-office-manager-steve",
            "nr2-practice-doctor-michael-reno",
            "insurance-narrative-local-only",
            "no-external-submit-actions",
        }
        memories = [m for m in memories if str(m.get("id") or "") in priority_ids or str(m.get("id") or "").startswith("nr2-practice-")]
        memories = memories[:limit]
    for memory in memories:
        memory_id = str(memory.get("id") or "").strip()
        if not memory_id:
            continue
        text = str(memory.get("text") or "").strip()
        index[memory_id] = {
            "title": title_from_memory_id(memory_id),
            "detail": text if len(text) <= 280 else text[:280].rstrip() + "…",
            "source": str(memory.get("source") or ""),
            "category": str(memory.get("category") or ""),
        }
    return index


def write_browser_memo_index_json(path: Path | None = None) -> Path:
    """Compact full citation index for optional browser fetch (large corpora)."""
    target = path or (REPO_ROOT / "NewRidgeFinancial2" / "site" / "data" / "hal-memo-index.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    index = build_browser_memo_index()
    payload = {
        "syncedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "count": len(index),
        "items": index,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return target


def write_browser_memo_index_js(path: Path | None = None) -> Path:
    """Emit hal-memo-index.js — priority inline index + optional full JSON sidecar."""
    target = path or (REPO_ROOT / "NewRidgeFinancial2" / "site" / "hal-memo-index.js")
    json_path = write_browser_memo_index_json()
    total = len(load_approved_memories())
    priority = build_browser_memo_index(priority_only=True)
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = json.dumps(priority, ensure_ascii=False, indent=2)
    json_rel = "data/hal-memo-index.json"
    body = f"""/** Auto-synced MemoAI index — run: python scripts/sync_hal_memo_index.py */
const HalMemoIndex = (function () {{
  const PRIORITY_BY_ID = {payload};
  let fullById = null;
  let fullLoadPromise = null;
  const syncedAt = {json.dumps(stamp)};
  const totalCount = {total};
  const priorityCount = Object.keys(PRIORITY_BY_ID).length;
  const fullIndexUrl = {json.dumps(json_rel)};

  function titleFromId(id) {{
    return String(id || "")
      .split("-")
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }}

  function lookup(id) {{
    const key = String(id || "").trim();
    if (!key) return null;
    if (PRIORITY_BY_ID[key]) return PRIORITY_BY_ID[key];
    if (fullById && fullById[key]) return fullById[key];
    return null;
  }}

  function loadFullIndex() {{
    if (fullById) return Promise.resolve(fullById);
    if (fullLoadPromise) return fullLoadPromise;
    fullLoadPromise = fetch(fullIndexUrl)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {{
        fullById = (data && data.items) || {{}};
        return fullById;
      }})
      .catch(() => {{
        fullById = {{}};
        return fullById;
      }});
    return fullLoadPromise;
  }}

  function resolveCitations(ids) {{
    return (ids || []).map((id) => {{
      const key = String(id || "").trim();
      const row = lookup(key);
      if (!row) {{
        return {{ id: key, title: titleFromId(key), detail: "", source: "", category: "" }};
      }}
      return {{
        id: key,
        title: row.title || titleFromId(key),
        detail: row.detail || "",
        source: row.source || "",
        category: row.category || "",
      }};
    }});
  }}

  return {{
    syncedAt,
    count: totalCount,
    priorityCount,
    fullIndexUrl,
    PRIORITY_BY_ID,
    get BY_ID() {{ return fullById || PRIORITY_BY_ID; }},
    titleFromId,
    lookup,
    loadFullIndex,
    resolveCitations,
  }};
}})();

if (typeof module !== "undefined" && module.exports) {{
  module.exports = HalMemoIndex;
}}
if (typeof globalThis !== "undefined") {{
  globalThis.HalMemoIndex = HalMemoIndex;
}}
"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target
