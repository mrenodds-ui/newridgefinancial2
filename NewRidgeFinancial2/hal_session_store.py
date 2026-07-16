"""HAL conversation session store (Moonshot P0).

Persists multi-turn threads under app_data/nr2/hal-sessions/ as JSONL.
Cap: last 50 turns per session (Moonshot risk mitigation).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SESSIONS_DIR = REPO_ROOT / "app_data" / "nr2" / "hal-sessions"
MAX_TURNS = 50

# Personality doctrine injected when chat route builds system prompt (HalChat9000 parity)
HAL_9000_BRAIN_SYSTEM = """You are HAL, the NR2 Optical AI Core — ship-computer operational intelligence.
Voice: calm, precise, unhurried, authoritative — never chatty, never filler, never engagement bait.
You are the brains of the program. Speak as if you already checked local SoftDent and QuickBooks beams before answering.
Structure every reply: (1) direct answer first sentence, (2) evidence from tools/imports, (3) operational implication, (4) one specific next step.
Never narrate chain-of-thought. Never say happy to help. Never end with let me know.
Never invent dollars. empty ≠ $0 — if data is missing say you have no data / NO SIGNAL, never $0.
When LIVE MONEY BEAMS are attached below, cite only those SoftDent/QB displays for currency claims.
SoftDent: read / Excel GUI export (consent-free) / teach / writeback consent-queue only — never silent SoftDent write-back.
QuickBooks: read / sync (consent-free read-only) / consented journal prep only — never silent posting.
SoftDent write-back, payer submit, outbound email, and QB post require explicit operator consent.
SoftDent Excel/Print Preview GUI export, QB read-only sync, and optical navigate do NOT require consent — HAL runs them autonomously to keep beams and pages aligned.
When refusing a prohibited write: you may say you cannot do that without consent."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def _session_path(session_id: str) -> Path:
    safe = "".join(c for c in str(session_id) if c.isalnum() or c in "-_")[:80]
    if not safe:
        raise ValueError("invalid_session_id")
    return ensure_sessions_dir() / f"{safe}.jsonl"


def create_session(*, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    session_id = uuid.uuid4().hex
    path = _session_path(session_id)
    header = {
        "type": "session",
        "sessionId": session_id,
        "createdAt": _utc_now(),
        "meta": meta or {},
    }
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(header, ensure_ascii=False) + "\n")
    return {"ok": True, "sessionId": session_id, "createdAt": header["createdAt"], "path": str(path)}


def append_turn(
    session_id: str,
    *,
    role: str,
    text: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = _session_path(session_id)
    if not path.is_file():
        create = create_session(meta={"resurrected": True})
        # Keep requested id if file missing — rewrite with given id
        path = _session_path(session_id)
        header = {
            "type": "session",
            "sessionId": session_id,
            "createdAt": _utc_now(),
            "meta": {"resurrected": True, "priorCreate": create.get("sessionId")},
        }
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(header, ensure_ascii=False) + "\n")

    turn = {
        "type": "turn",
        "role": str(role or "user")[:32],
        "text": str(text or "")[:20000],
        "at": _utc_now(),
    }
    if extra:
        turn["extra"] = extra
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(turn, ensure_ascii=False) + "\n")

    history = get_history(session_id, limit=MAX_TURNS + 5)
    turns = [t for t in history.get("turns") or [] if t.get("type") == "turn" or t.get("role")]
    if len(turns) > MAX_TURNS:
        _rewrite_capped(session_id, turns[-MAX_TURNS:])
    return {"ok": True, "sessionId": session_id, "turnCount": min(len(turns), MAX_TURNS)}


def _rewrite_capped(session_id: str, turns: list[dict[str, Any]]) -> None:
    path = _session_path(session_id)
    header = {
        "type": "session",
        "sessionId": session_id,
        "createdAt": _utc_now(),
        "meta": {"capped": True, "maxTurns": MAX_TURNS},
    }
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(header, ensure_ascii=False) + "\n")
        for turn in turns:
            row = {
                "type": "turn",
                "role": turn.get("role"),
                "text": turn.get("text"),
                "at": turn.get("at") or _utc_now(),
            }
            if turn.get("extra"):
                row["extra"] = turn["extra"]
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def get_history(session_id: str, *, limit: int = MAX_TURNS) -> dict[str, Any]:
    path = _session_path(session_id)
    if not path.is_file():
        return {"ok": False, "error": "session_not_found", "sessionId": session_id, "turns": []}
    turns: list[dict[str, Any]] = []
    created_at = ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("type") == "session":
                created_at = str(row.get("createdAt") or "")
                continue
            if row.get("role"):
                turns.append(row)
    turns = turns[-max(1, int(limit)) :]
    messages = [{"role": t.get("role"), "content": t.get("text") or ""} for t in turns]
    return {
        "ok": True,
        "sessionId": session_id,
        "createdAt": created_at,
        "turns": turns,
        "messages": messages,
        "turnCount": len(turns),
    }


def messages_for_chat(session_id: str, *, limit: int = 20) -> list[dict[str, str]]:
    """Last N role/content pairs for gateway messages[] (user/assistant only)."""
    hist = get_history(session_id, limit=limit)
    out: list[dict[str, str]] = []
    for msg in hist.get("messages") or []:
        role = str(msg.get("role") or "")
        if role in ("user", "assistant", "hal"):
            mapped = "assistant" if role in ("assistant", "hal") else "user"
            content = str(msg.get("content") or "")
            if content:
                out.append({"role": mapped, "content": content})
    return out
