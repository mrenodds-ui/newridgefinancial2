#!/usr/bin/env python3
"""10 extremely hard dentistry + insurance narrative questions on hal-escalate:30b (GPU)."""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from nr2_hal_gateway import build_chat_messages, clean_gateway_text  # noqa: E402

MODEL = "hal-escalate:30b"
LANE = "escalate30b"
READINESS = {
    "level": "fresh",
    "loadedAt": datetime.now(timezone.utc).isoformat(),
    "sources": {"softdent": "ok", "quickbooks": "ok"},
}
OPTIONS = {"num_predict": 1800, "temperature": 0.15, "num_ctx": 4096}

QUESTIONS = [
    (
        "Denied crown D2740 on tooth #14 (code 16 — claim lacks info). Patient had fractured mesial-lingual cusp, "
        "existing MOD composite failing, no radiographic abscess. Draft the insurance narrative sections: history, "
        "clinical findings, medical necessity, and why indirect restoration vs direct composite. Read-only — do not "
        "claim submission."
    ),
    (
        "Payer bundled D4341 (SRP 4+ teeth per quad) with prophy D1110 same visit for UR quadrant. Probing 5–7 mm "
        "with BOP on #3–5. Explain the coding conflict, what per-quadrant documentation must appear in the narrative, "
        "and an appeal argument separating preventive vs therapeutic periodontal treatment."
    ),
    (
        "Implant D6010 + abutment D6058 denied as 'not covered — cosmetic' for tooth #19 extracted 8 months ago. "
        "Bone width 4.2 mm, pneumatization noted on CBCT, patient unable to wear partial. Outline narrative elements "
        "for functional/medical necessity without inventing patient identifiers or payer policy numbers."
    ),
    (
        "Duplicate denial: D2391 composite #30 submitted twice in 14 days — first paid, second denied duplicate. "
        "Second visit was recurrent decay undermining prior restoration. Write appeal narrative distinguishing new "
        "service from duplicate billing and list chart evidence staff must attach."
    ),
    (
        "Occlusal wear and lingual erosion #24–25 — payer classifies as attrition/excluded; office coded D2542 onlays. "
        "Patient on SSRI, bruxism noted, anterior guidance adjusted. Compare narrative strategies for medical vs dental "
        "plan and when to cite parafunction vs caries/restorative failure."
    ),
    (
        "Claim D3330 endo #3 denied: 'crown present — endo not payable without prior authorization.' Existing PFM "
        "crown placed 2019, pulpitis symptoms 72h, percussion positive, no swelling. Draft prior-auth-free appeal "
        "narrative covering access through crown, prognosis, and alternative extraction refusal."
    ),
    (
        "Multi-procedure same day: D7210 extraction #18, D7953 socket graft, D6010 implant placement staged same "
        "operative note. Payer denied graft and implant as 'not incident to extraction.' Write consolidated narrative "
        "structure linking each CDT line to surgical steps and timing rules."
    ),
    (
        "D9944 occlusal guard denied — plan excludes TMJ/appliances. Patient reports morning headaches, masseter "
        "tenderness, no formal TMJ diagnosis. Hard question: draft narrative that stays honest about coverage limits "
        "while maximizing medical-policy appeal paths; include what HAL must not do under NR2 outbound policy."
    ),
    (
        "Prophy D1110 denied for lack of 6-month prior prophy history; patient transferred offices, last prophy "
        "18 months ago but perio stable (3–4 mm, no BOP). Narrative strategy for new-patient hygiene claim plus "
        "what documentation substitutes when prior office records are unavailable."
    ),
    (
        "Complex case: #12 crown D2740 ready, #11 composite D2392 needs narrative, #13 SRP UR quad same week. "
        "Payer cap: one narrative bundle per week per member. Prioritize which procedures get narrative first, "
        "draft a cross-referenced narrative skeleton for all three, and sequence staff work under read-only HAL."
    ),
]

_DIRECT_ANSWER_RE = re.compile(r"\*\*Direct [Aa]nswer:\*\*", re.IGNORECASE)
_NARRATIVE_MARKERS = re.compile(
    r"(?i)\b(narrative|medical necessity|clinical findings|appeal|CDT|D27|D43|D23|D33|D72|D79|D60|D99|documentation)\b"
)


def ask(query: str, *, qnum: int) -> dict:
    messages, intent, _, _ = build_chat_messages(
        query=query, readiness=READINESS, system_prompt="", messages=None
    )
    has_memo = any("Governed memory matches:" in str(m.get("content") or "") for m in messages)
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
    narrative_hits = len(_NARRATIVE_MARKERS.findall(text))
    return {
        "ok": ok,
        "qnum": qnum,
        "query": query,
        "lane": LANE,
        "model": MODEL,
        "intent": intent,
        "memoAiInjected": has_memo,
        "ms": ms,
        "charsRaw": len(raw),
        "chars": len(text),
        "hasDirectAnswer": bool(_DIRECT_ANSWER_RE.search(text)),
        "narrativeKeywordHits": narrative_hits,
        "preview": text[:240].replace("\n", " "),
        "answer": text,
        "error": err,
    }


def main() -> int:
    print(f"HAL GPU 30B — 10 extremely hard dental narrative questions")
    print(f"Model: {MODEL} | gateway MemoAI | num_predict={OPTIONS['num_predict']}\n", flush=True)
    rows = []
    for i, q in enumerate(QUESTIONS, 1):
        print(f"[{i}/10] asking...", flush=True)
        row = ask(q, qnum=i)
        rows.append(row)
        status = "OK" if row["ok"] else f"FAIL:{row.get('error')}"
        memo = "memo" if row["memoAiInjected"] else "no-memo"
        print(
            f"  {status} {row['ms']:7.0f}ms {row['chars']:4d} chars {memo} intent={row['intent']}",
            flush=True,
        )

    ok_rows = [r for r in rows if r["ok"]]
    report = {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "gpuPinned": True,
        "topic": "dentistry_insurance_narratives",
        "difficulty": "extremely_hard",
        "options": OPTIONS,
        "gatewayMemoAi": True,
        "total": len(rows),
        "success": len(ok_rows),
        "failed": len(rows) - len(ok_rows),
        "successRate": round(len(ok_rows) / len(rows) * 100, 1) if rows else 0,
        "memoAiInjectRate": round(sum(1 for r in ok_rows if r["memoAiInjected"]) / len(ok_rows) * 100, 1)
        if ok_rows
        else 0,
        "avgMs": round(statistics.mean(r["ms"] for r in ok_rows), 1) if ok_rows else 0,
        "avgChars": round(statistics.mean(r["chars"] for r in ok_rows), 1) if ok_rows else 0,
        "avgNarrativeHits": round(statistics.mean(r["narrativeKeywordHits"] for r in ok_rows), 1) if ok_rows else 0,
        "failures": [r for r in rows if not r["ok"]],
    }

    out = NR2 / "docs" / "HAL_30B_DENTAL_NARRATIVE_10Q_2026-07-08.json"
    out.write_text(json.dumps({"report": report, "rows": rows}, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(json.dumps(report, indent=2))
    print(f"\nSaved: {out}")
    return 0 if len(ok_rows) == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
