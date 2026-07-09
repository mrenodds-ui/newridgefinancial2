#!/usr/bin/env python3
"""Ask hal-escalate:30b (GPU-pinned) 10 extremely hard questions and report."""

from __future__ import annotations

import json
import re
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"

MODEL = "hal-escalate:30b"
LANE = "escalate30b"
READINESS = {
    "level": "fresh",
    "loadedAt": datetime.now(timezone.utc).isoformat(),
    "sources": {"softdent": "ok", "quickbooks": "ok"},
}
OPTIONS = {"num_predict": 1200, "temperature": 0.15, "num_ctx": 4096}

_ANALYTICAL_PATTERN = re.compile(
    r"(?i)\b(why|how|explain|analyze|trend|pattern|compare|summary|overview|what if|strategy|plan)\b"
)
_CLINICAL_PATTERN = re.compile(
    r"(?i)\b(clinical|procedure|tooth|quadrant|cdt|crown|extraction|prophy|periodontal|narrative)\b"
)
_MONOLOGUE_START_RE = re.compile(
    r"^(?:Okay|Sure|Certainly|Hmm|Let me|Wait|Alright)[,.]?\s*(?:let me\s+)?(?:break this down|think|see|check|start|walk through)[^.!?]*[.!?]?\s*",
    re.IGNORECASE,
)


def classify_query_intent(query: str) -> str:
    q = str(query or "")
    if _CLINICAL_PATTERN.search(q):
        return "clinical"
    if _ANALYTICAL_PATTERN.search(q):
        return "analytical"
    return "general"


def build_chat_messages(
    *,
    query: str,
    readiness: dict[str, Any],
    system_prompt: str = "",
    messages: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], str, bool, str]:
    level = str(readiness.get("level") or "unknown")
    intent = classify_query_intent(query)
    chat_messages: list[dict[str, Any]] = []
    if system_prompt:
        chat_messages.append({"role": "system", "content": system_prompt})
    if messages:
        chat_messages.extend(messages)
    else:
        chat_messages.append({"role": "user", "content": str(query or "")})
    return chat_messages, intent, False, level


def clean_gateway_text(text: str) -> str:
    out = str(text or "").strip()
    out = re.sub(r"<think>[\s\S]*?</think>", "", out, flags=re.IGNORECASE)
    out = re.sub(r"</?think>", "", out, flags=re.IGNORECASE)
    out = _MONOLOGUE_START_RE.sub("", out)
    out = re.sub(
        r"^(?:Okay|Sure|Certainly)[,.]?\s*(?:from my (?:local )?)?(?:read-?only )?(?:monitoring )?perspective[,:]?\s*",
        "",
        out,
        flags=re.IGNORECASE,
    )
    return out.strip()

QUESTIONS = [
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
    (
        "Implement in Python: function reconcile_journal(debits, credits) that returns unbalanced rows, "
        "detects duplicate (date, amount, account) pairs, and flags rows where debits+credits differ by "
        "rounding within 0.01. Include edge cases for empty input and single-sided entries."
    ),
    (
        "Investigate root cause: ERA shows adjustment -$312 on claim CLM-2024-884, SoftDent import shows "
        "+$312 payment, QuickBooks deposit batch matches bank but ledger still shows $890 patient balance. "
        "List hypotheses ranked by likelihood and verification steps."
    ),
    (
        "Derive a strategy: production up 18% YoY but collections flat, operatory utilization 62%, insurance "
        "mix shifted to slower PPO, write-offs doubled. Recommend 5 interventions with expected impact and "
        "what data to pull first from NR2 imports."
    ),
    (
        "Math: Patient owes $1,240. Insurance paid $680 (80% of allowed $850). Office contracted $850 but "
        "billed $1,100. Adjustment code CO-45 $250, PR-1 $120. Compute patient responsibility, explain "
        "double-count risk if adjustment posts twice, and journal entry sketch (read-only review)."
    ),
    (
        "Code: O(n log n) algorithm to find the longest chain of claims where each next claim's service date "
        "is within 30 days of prior and same payer. Return chain length and IDs. Handle cycles and unsorted input."
    ),
    (
        "Multi-step plan: imports stale 36h, widgets empty on Financial dashboard, QuickBooks IIF out of "
        "balance by $0.03, 8 claims in Needs Review. Sequence today's work for solo operator — dependencies, "
        "parallelizable steps, and stop conditions."
    ),
    (
        "Compare escalate30b vs chat8b for this query: 'Should we appeal all 23 denied claims or focus on top 5 "
        "by amount?' Give second opinion with decision criteria, estimated staff hours, and when escalation lane "
        "is warranted. Do not invent dollar amounts or percentages not provided in the question."
    ),
    (
        "Hard policy edge case: Staff asks HAL to email payer narrative for crown D2740 without standing consent "
        "but with verbal patient OK documented in sidenotes. What is allowed, blocked, and the exact safe next "
        "steps under NR2 consent policy?"
    ),
]


def ask(query: str) -> dict:
    messages, intent, _, _ = build_chat_messages(
        query=query, readiness=READINESS, system_prompt="", messages=None
    )
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
    return {
        "ok": ok,
        "query": query,
        "lane": LANE,
        "model": MODEL,
        "intent": intent,
        "ms": ms,
        "charsRaw": len(raw),
        "chars": len(text),
        "preview": text[:200].replace("\n", " "),
        "answerRaw": raw,
        "answer": text,
        "error": err,
    }


def main() -> int:
    print(f"HAL GPU 30B extremely hard eval v2 — {len(QUESTIONS)} questions")
    print(f"Model: {MODEL} (VRAM pinned) | num_predict={OPTIONS['num_predict']} temp={OPTIONS['temperature']}\n", flush=True)
    rows = []
    for i, q in enumerate(QUESTIONS, 1):
        print(f"[{i}/10] asking...", flush=True)
        row = ask(q)
        rows.append(row)
        status = "OK" if row["ok"] else f"FAIL:{row.get('error')}"
        print(
            f"  {status} {row['ms']:7.0f}ms {row['chars']:4d} chars (raw {row['charsRaw']}) intent={row['intent']}",
            flush=True,
        )

    ok_rows = [r for r in rows if r["ok"]]
    report = {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "gpuPinned": True,
        "difficulty": "extremely_hard",
        "version": "v2_gateway_clean_1200tok",
        "options": OPTIONS,
        "gatewayClean": True,
        "total": len(rows),
        "success": len(ok_rows),
        "failed": len(rows) - len(ok_rows),
        "successRate": round(len(ok_rows) / len(rows) * 100, 1),
        "avgMs": round(statistics.mean(r["ms"] for r in ok_rows), 1) if ok_rows else 0,
        "avgChars": round(statistics.mean(r["chars"] for r in ok_rows), 1) if ok_rows else 0,
        "avgCharsRaw": round(statistics.mean(r["charsRaw"] for r in ok_rows), 1) if ok_rows else 0,
        "failures": [r for r in rows if not r["ok"]],
    }

    out = NR2 / "docs" / "HAL_30B_EXTREMELY_HARD_10Q_v2_2026-07-08.json"
    slim_rows = [{k: v for k, v in r.items() if k not in ("answerRaw",)} for r in rows]
    out.write_text(json.dumps({"report": report, "rows": slim_rows}, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(json.dumps(report, indent=2))
    print(f"\nSaved: {out}")
    return 0 if len(ok_rows) == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
