"""Moonshot AI — REC-009 Voice Context Carry: CODE the whole program + REPORT.

Operator request (verbatim): ask moonshot to code the whole program and report.
Produces complete implementable patches + engineer report. Does NOT apply to disk.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

HELPER = (
    REPO
    / "_archive"
    / "2026-07-10"
    / ".local_logs"
    / "moonshot_financial_eval"
    / "_run_moonshot_eval.py"
)
sys.path.insert(0, str(HELPER.parent))
from _run_moonshot_eval import extract_message_content, resolve_api_and_endpoint  # noqa: E402

OPERATOR_REQUEST_VERBATIM = (
    "ask moonshot to code the whole program and reoort"
).strip()

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex (hal-10561 + hal-local:32b).

Operator asked you to CODE THE WHOLE PROGRAM and REPORT for Expert SE REC-009
(Voice context carry). This is a CODING consult: produce complete, copy-pasteable
implementation patches for the real Apex stack — not a vague plan.

REC-009 definition (Expert SE):
"HAL, draft appeal for the high-risk claim I just clicked" — carries claim context
into narrative voice input without manual lock.

Constraints:
- Prefer additive Apex fixes on REAL paths (no fictional hal/modules trees)
- Empty ≠ $0; no invented dollars/PHI; no SoftDent write-back
- Avoid GitHub/PR work; local engineering only
- Extend existing IMP-009 / session context plumbing — do NOT reinvent from scratch
- No PII in localStorage keys; claim IDs staff already see are OK in sessionStorage
- Keep zero-scroll / REC-008 batch narratives intact

Already exists (USE IT):
1) sessionStorage `nr2-apex-focused-claim` set on claim click / generate-narrative
2) sessionStorage `nr2-apex-narrative-seed` with `{claimId, voiceCarry:true}`
3) HAL board action `narrative_from_focused_claim` in apex-core.js
4) `hal_learning.update_session_context` + `format_session_context_block` →
   injected in nr2_hal_gateway chat build
5) POST `/api/hal-learning/session` (nr2_http_server) + DesktopBridge.updateHalSessionContext
6) Narratives page Voice dictation (SpeechRecognition) → askHalFromBridge / applyVoiceText
7) REC-008 batch narratives just shipped (consent + batch-generate)

Likely gaps to close for true REC-009:
- Claim card click must POST session context to backend (not only sessionStorage)
- Voice phrases like "draft appeal for this claim / the claim I just clicked" must
  resolve focused claim → narrative seed without requiring Narratives lock UI
- Narratives voice path should auto-load focused claim seed into composer status
- Tests covering carry across turns + refresh survival for session handoff

OUTPUT (strict markdown):
# Verdict
## 0. Operator Intent (verbatim + what you will code)
## 1. Gap Analysis (what IMP-009 already does vs what REC-009 still needs)
## 2. Architecture (data flow: click → session → HAL voice → narratives)
## 3. COMPLETE CODE PACKAGE
For each file: path, then either full replacement functions or unified-diff style
patches that are complete enough to apply without guessing. Include:
- NewRidgeFinancial2/hal_learning.py (if needed)
- NewRidgeFinancial2/site/apex-core.js
- NewRidgeFinancial2/site/apex-narratives.js
- NewRidgeFinancial2/site/hal-agent.js and/or desktop-bridge.js if needed
- NewRidgeFinancial2/nr2_http_server.py / apex_backend.py only if new routes required
- NewRidgeFinancial2/test_rec009_voice_context_carry.py (new tests)
## 4. Validation Gate (manual + pytest)
## 5. Report Summary (executive bullets for operator)
## 6. Apply checklist
DO NOT claim you applied to disk — this response is the code+report artifact only.
"""


def _clip(path: Path, start: int, end: int) -> str:
    if not path.is_file():
        return f"(missing: {path})"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    chunk = lines[max(0, start - 1) : end]
    return "\n".join(f"{i+start}|{ln}" for i, ln in enumerate(chunk))


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    if "moonshot" not in (base_url or "").lower():
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")

    nr2 = REPO / "NewRidgeFinancial2"
    excerpts = {
        "hal_learning.py update_session_context": _clip(nr2 / "hal_learning.py", 101, 160),
        "apex-core.js generate-narrative + focused claim": _clip(nr2 / "site" / "apex-core.js", 4520, 4555),
        "apex-core.js narrative_from_focused_claim": _clip(nr2 / "site" / "apex-core.js", 5173, 5196),
        "apex-narratives.js voice": _clip(nr2 / "site" / "apex-narratives.js", 610, 678),
        "hal-agent.js updateHalSessionContext": _clip(nr2 / "site" / "hal-agent.js", 3926, 3944),
        "nr2_http_server session API": _clip(nr2 / "nr2_http_server.py", 1892, 1909),
        "gateway session block": _clip(nr2 / "nr2_hal_gateway.py", 838, 845),
    }
    excerpt_blob = "\n\n".join(f"### {k}\n```\n{v}\n```" for k, v in excerpts.items())

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CODE THE WHOLE REC-009 VOICE CONTEXT CARRY PROGRAM and produce a REPORT.\n"
        "Complete patches for real files. Extend existing wiring; do not invent trees.\n\n"
        f"### Live code excerpts\n\n{excerpt_blob}\n"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 16000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 REC-009 Code Whole Program"
    import urllib.request

    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:
        content = str(exc)
        status = "error"
    header = (
        f"# Moonshot AI — REC-009 Voice Context Carry (CODE + REPORT)\n\n"
        f"**Date:** {DATE}  \n**Model:** {model}  \n**Key:** {key_name}  \n"
        f"**Status:** {status}  \n**Build:** hal-10561 + hal-local:32b  \n"
        f"**Script:** `scripts/run_moonshot_rec009_code_whole_program_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_REC009_VOICE_CONTEXT_CARRY_CODE_REPORT_{DATE}.md"
    doc = DOCS / f"MOONSHOT_REC009_VOICE_CONTEXT_CARRY_CODE_REPORT_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
