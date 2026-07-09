"""HAL learn-as-you-go: import observations, staff facts, session context."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge_memory_store import (
    LEARNED_MEMORIES_PATH,
    load_approved_memories,
    memory_contains_forbidden,
    remember_fact,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_CONTEXT_PATH = REPO_ROOT / "app_data" / "nr2" / "hal_session_context.json"
SYNC_OBSERVATION_KEY = "nr2:hal:last-sync-observation-hash"

_REMEMBER_PATTERNS = (
    re.compile(r"(?i)\b(remember|save|learn|note)\s+(this|that)\b"),
    re.compile(r"(?i)\b(always|from now on|going forward)\b"),
    re.compile(r"(?i)\b(our office|we always|we never|our policy)\b"),
)
_CONFIRM_REMEMBER = re.compile(r"(?i)\b(yes|correct|that'?s right|remember it|save it)\b")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def extract_remember_candidate(query: str) -> str | None:
    """Return fact text when staff explicitly asks HAL to remember something."""
    text = " ".join(str(query or "").split()).strip()
    if len(text) < 12:
        return None
    if not any(pattern.search(text) for pattern in _REMEMBER_PATTERNS):
        return None
    if memory_contains_forbidden(text):
        return None
    cleaned = re.sub(r"(?i)^(?:please\s+)?(?:remember|save|learn|note)\s+(?:this|that)\s*:?\s*", "", text).strip()
    return cleaned or text


def should_confirm_remember(query: str) -> bool:
    return bool(_CONFIRM_REMEMBER.search(str(query or "")))


def _recent_learned_texts(limit: int = 40) -> set[str]:
    return {str(row.get("text") or "").strip() for row in _read_jsonl(LEARNED_MEMORIES_PATH)[-limit:]}


def remember_import_sync_observation(sync_result: dict[str, Any]) -> dict[str, Any] | None:
    """Record non-PHI import sync summary into learned memory (deduped)."""
    if not isinstance(sync_result, dict):
        return None
    synced_at = str(sync_result.get("syncedAt") or _utc_now())
    diag = sync_result.get("diagnostics") if isinstance(sync_result.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    connected = summary.get("connected")
    stale = summary.get("stale")
    missing = summary.get("missing")
    softdent = sync_result.get("softdent") if isinstance(sync_result.get("softdent"), dict) else {}
    copied_sd = len(softdent.get("copied") or [])
    qb = sync_result.get("quickbooks") if isinstance(sync_result.get("quickbooks"), dict) else {}
    copied_qb = len(qb.get("copied") or [])
    warnings = len(sync_result.get("warnings") or [])

    text = (
        f"Import sync at {synced_at}: SoftDent files copied={copied_sd}, QuickBooks copied={copied_qb}, "
        f"datasets connected={connected}, stale={stale}, missing={missing}, warnings={warnings}. "
        "Use integration health for live status; this is a historical sync observation."
    )
    if text in _recent_learned_texts():
        return None
    try:
        return remember_fact(text, source="system:import-sync", category="operator_playbooks", actor="HAL")
    except ValueError:
        return None


def update_session_context(
    *,
    claim_id: str = "",
    narrative_id: str = "",
    page: str = "",
    topic: str = "",
    payer: str = "",
) -> dict[str, Any]:
    """Persist short-lived handoff context for the next HAL turn (no PHI beyond IDs staff already see)."""
    SESSION_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prior: dict[str, Any] = {}
    if SESSION_CONTEXT_PATH.is_file():
        try:
            prior = json.loads(SESSION_CONTEXT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prior = {}
    ctx = dict(prior)
    if claim_id:
        ctx["lastClaimId"] = str(claim_id)[:80]
    if narrative_id:
        ctx["lastNarrativeId"] = str(narrative_id)[:80]
    if page:
        ctx["lastPage"] = str(page)[:80]
    if topic:
        ctx["lastTopic"] = str(topic)[:200]
    if payer:
        ctx["lastPayer"] = str(payer)[:80]
    ctx["updatedAt"] = _utc_now()
    SESSION_CONTEXT_PATH.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "context": ctx}


def load_session_context() -> dict[str, Any]:
    if not SESSION_CONTEXT_PATH.is_file():
        return {}
    try:
        payload = json.loads(SESSION_CONTEXT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def format_session_context_block() -> str:
    ctx = load_session_context()
    if not ctx:
        return ""
    parts: list[str] = []
    for key, label in (
        ("lastClaimId", "Last claim"),
        ("lastNarrativeId", "Last narrative"),
        ("lastPayer", "Last payer"),
        ("lastPage", "Last page"),
        ("lastTopic", "Last topic"),
    ):
        value = str(ctx.get(key) or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    if not parts:
        return ""
    return "Session handoff context (local only):\n" + "\n".join(f"- {p}" for p in parts)


def learning_status() -> dict[str, Any]:
    learned = _read_jsonl(LEARNED_MEMORIES_PATH)
    governed = load_approved_memories()
    return {
        "ok": True,
        "governedCount": len(governed),
        "learnedCount": len(learned),
        "sessionContext": load_session_context(),
        "learnedPath": str(LEARNED_MEMORIES_PATH),
    }
