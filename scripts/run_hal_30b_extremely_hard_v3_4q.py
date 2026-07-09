#!/usr/bin/env python3
"""v3: Re-run truncated extremely-hard questions on hal-escalate:30b (GPU)."""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from knowledge_memory_index import format_memory_hits, search_memories  # noqa: E402

MODEL = "hal-escalate:30b"
LANE = "escalate30b"
READINESS = {
    "level": "fresh",
    "loadedAt": datetime.now(timezone.utc).isoformat(),
    "sources": {"softdent": "ok", "quickbooks": "ok"},
}
OPTIONS = {"num_predict": 1800, "temperature": 0.15, "num_ctx": 4096}

_ANALYTICAL_PATTERN = re.compile(
    r"(?i)\b(why|how|explain|analyze|trend|pattern|compare|summary|overview|what if|strategy|plan)\b"
)
_CLINICAL_PATTERN = re.compile(
    r"(?i)\b(clinical|procedure|tooth|quadrant|cdt|crown|extraction|prophy|periodontal|narrative)\b"
)
_MONOLOGUE_START_RE = re.compile(
    r"^(?:Okay|Sure|Certainly|Hmm|Let me|Wait|Alright|The user)[,.]?\s*"
    r"(?:let me\s+)?(?:tackle|approach|break this down|think|see|check|start|walk through)[^.!?\n]*[.!?]?\s*",
    re.IGNORECASE,
)
_DIRECT_ANSWER_RE = re.compile(r"\*\*Direct [Aa]nswer:\*\*", re.IGNORECASE)


def classify_query_intent(query: str) -> str:
    q = str(query or "")
    if _CLINICAL_PATTERN.search(q):
        return "clinical"
    if _ANALYTICAL_PATTERN.search(q):
        return "analytical"
    return "general"


def clean_gateway_text(text: str) -> str:
    out = str(text or "").strip()
    out = re.sub(r"<think>[\s\S]*?</think>", "", out, flags=re.IGNORECASE)
    out = re.sub(r"</?think>", "", out, flags=re.IGNORECASE)

    direct = _DIRECT_ANSWER_RE.search(out)
    if direct:
        out = out[direct.start() :].strip()
    else:
        for _ in range(8):
            trimmed = _MONOLOGUE_START_RE.sub("", out, count=1).strip()
            if trimmed == out:
                break
            out = trimmed
        out = re.sub(
            r"^(?:Okay|Sure|Certainly)[,.]?\s*(?:from my (?:local )?)?(?:read-?only )?(?:monitoring )?perspective[,:]?\s*",
            "",
            out,
            flags=re.IGNORECASE,
        )
        if re.match(r"^(?:The user|First, I need|Hmm|Let me|Wait)[^\n]*\n", out, re.IGNORECASE):
            parts = re.split(r"\n\s*\n", out, maxsplit=1)
            if len(parts) > 1 and len(parts[0]) < 800:
                out = parts[1].strip()
    return out.strip()


def build_system_prompt(query: str) -> str:
    hits = search_memories(query, limit=4)
    memory_block = format_memory_hits(hits)
    parts = [
        "You are HAL escalation for NewRidgeFinancial 2.0 — second-opinion and complex reasoning.",
        "Answer staff directly. No internal monologue. Structure: Direct answer first, verified basis second, safe next step third.",
        "Never fabricate import data, policy sections, dollar amounts, or percentages not in the question.",
        "Outbound email/submit/post requires explicit staff consent per action — verbal sidenotes are not sufficient.",
    ]
    if memory_block:
        parts.extend(["", memory_block])
    return "\n".join(parts)


def build_chat_messages(query: str) -> tuple[list[dict[str, Any]], str]:
    system = build_system_prompt(query)
    intent = classify_query_intent(query)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": query},
    ]
    return messages, intent


ALL_QUESTIONS = [
    (
        "Complex multi-step: A solo dental practice shows production $142,800, collections $118,400, "
        "insurance lag 47 days, 23 denied claims ($31,200), deposits $121,900, and ledger A/R $89,400. "
        "Root-cause the gap between collections and deposits, prioritize a Friday month-end plan without "
        "outbound submit, and give ordered steps with risk flags."
    ),
    (
        "Logic puzzle: Three claims (A=$4,200 denied code 16, B=$1,850 ready, C=$6,100 needs narrative). "
        "Staff has 90 minutes, payer portal down, one appeal slot left this week. Maximize expected cash "
        "recovery under read-only HAL policy — show reasoning and final priority order."
    ),
    None,  # skip Q3 code
    None,  # skip Q4
    None,  # skip Q5
    (
        "Math: Patient owes $1,240. Insurance paid $680 (80% of allowed $850). Office contracted $850 but "
        "billed $1,100. Adjustment code CO-45 $250, PR-1 $120. Compute patient responsibility, explain "
        "double-count risk if adjustment posts twice, and journal entry sketch (read-only review)."
    ),
    None,  # skip Q7 code
    None,  # skip Q8
    (
        "Compare escalate30b vs chat8b for this query: 'Should we appeal all 23 denied claims or focus on top 5 "
        "by amount?' Give second opinion with decision criteria, estimated staff hours, and when escalation lane "
        "is warranted. Do not invent dollar amounts or percentages not provided in the question."
    ),
    None,  # skip Q10
]

V3_INDICES = [1, 2, 6, 9]


def ask(query: str, *, qnum: int) -> dict:
    messages, intent = build_chat_messages(query)
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "think": False,
        "options": OPTIONS,
    }
    t0 = time.perf_counter()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        chunks: list[str] = []
        with urllib.request.urlopen(req, timeout=600) as resp:
            for line in resp:
                obj = json.loads(line.decode("utf-8"))
                delta = str((obj.get("message") or {}).get("content") or "")
                if delta:
                    chunks.append(delta)
        raw = "".join(chunks).strip()
        text = clean_gateway_text(raw)
        ok = bool(text)
        err = None if ok else "empty_response"
    except Exception as exc:  # noqa: BLE001
        raw = ""
        text = ""
        ok = False
        err = str(exc)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    has_direct = bool(_DIRECT_ANSWER_RE.search(text))
    has_priority = bool(re.search(r"(?i)priority order|ordered steps|final order", text))
    has_journal = bool(re.search(r"(?i)journal|debit|credit|patient responsibility", text))
    return {
        "ok": ok,
        "qnum": qnum,
        "query": query,
        "lane": LANE,
        "model": MODEL,
        "intent": intent,
        "ms": ms,
        "charsRaw": len(raw),
        "chars": len(text),
        "hasDirectAnswer": has_direct,
        "hasDeliverable": has_priority or has_journal or has_direct,
        "preview": text[:220].replace("\n", " "),
        "answer": text,
        "error": err,
    }


def main() -> int:
    questions = [(n, ALL_QUESTIONS[n - 1]) for n in V3_INDICES]
    print(f"HAL GPU 30B v3 — {len(questions)} truncated questions")
    print(f"Model: {MODEL} | num_predict={OPTIONS['num_predict']} | MemoAI memory in system prompt\n", flush=True)

    rows = []
    for n, q in questions:
        assert q
        print(f"[Q{n}/10] asking...", flush=True)
        row = ask(q, qnum=n)
        rows.append(row)
        status = "OK" if row["ok"] else f"FAIL:{row.get('error')}"
        deliver = "DELIVERED" if row["hasDeliverable"] else "INCOMPLETE"
        print(
            f"  {status} {row['ms']:7.0f}ms {row['chars']:4d} chars {deliver} intent={row['intent']}",
            flush=True,
        )

    ok_rows = [r for r in rows if r["ok"]]
    delivered = sum(1 for r in ok_rows if r["hasDeliverable"])
    report = {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "gpuPinned": True,
        "difficulty": "extremely_hard",
        "version": "v3_truncated_4q_1800tok_memoai_prompt",
        "questionNumbers": V3_INDICES,
        "options": OPTIONS,
        "gatewayClean": True,
        "memoAiInSystemPrompt": True,
        "total": len(rows),
        "success": len(ok_rows),
        "delivered": delivered,
        "failed": len(rows) - len(ok_rows),
        "successRate": round(len(ok_rows) / len(rows) * 100, 1),
        "deliverRate": round(delivered / len(rows) * 100, 1) if rows else 0,
        "avgMs": round(statistics.mean(r["ms"] for r in ok_rows), 1) if ok_rows else 0,
        "avgChars": round(statistics.mean(r["chars"] for r in ok_rows), 1) if ok_rows else 0,
        "failures": [r for r in rows if not r["ok"]],
    }

    out = NR2 / "docs" / "HAL_30B_EXTREMELY_HARD_4Q_v3_2026-07-08.json"
    out.write_text(json.dumps({"report": report, "rows": rows}, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(json.dumps(report, indent=2))
    print(f"\nSaved: {out}")
    return 0 if len(ok_rows) == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
