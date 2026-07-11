"""Moonshot AI — HAL voice programming + spoken/written reports.

CONSULT ONLY. Operator request VERBATIM. Await approval before applying code.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
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

OPERATOR_REQUEST_VERBATIM = """
ask moonshot ai how to program hal voice and report
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — senior NR2 Apex + HAL architect for
NewRidge Family Financial (Kansas dental S-corp; SoftDent + QuickBooks imports;
local Ollama single 24B on R9700; HAL tools on HTTPS loopback).

CRITICAL CONSTRAINTS:
1. Answer the OPERATOR REQUEST VERBATIM: how to program HAL **voice** and **report**.
   Cover both sides:
   A) VOICE — speak replies, listen/push-to-talk, voice commands that drive UI/actions,
      neural TTS vs browser speechSynthesis, calibration, interruption, when not to speak.
   B) REPORT — shift handoff reports, readiness/smoke reports, spoken briefings,
      and how voice + report should work together (e.g. "HAL, give me the handoff report"
      → tool → spoken summary + markdown).
2. CONSULT ONLY — DO NOT APPLY code. DO NOT invent product diffs as already shipped.
   Wait for operator approve / proceed.
3. SoftDent is READ-ONLY forever. Never invent dollars. empty ≠ $0.
4. PHI is LOCAL-ONLY. Voice must not leak PHI over cloud TTS unless explicitly local/
   loopback. Prefer existing local neural TTS endpoint / browser speechSynthesis.
   Do not recommend shipping raw patient charts to third-party cloud voice APIs.
5. Ground in EXISTING code: site/hal-voice.js (HalVoice), app.js speech hooks,
   data-hal-voice-ptt, naturalVoice config, apex voice command parsers
   (parse_voice_slider_command, parse_voice_narrative_command), HAL tools
   clock_out_shift / get_last_handoff_report, readiness diagnostics.
   Propose NEW modules only if existing pieces cannot compose; justify them.
6. Rank MUST / SHOULD / NICE. Coding plan with concrete files. End with APPROVAL CHECKLIST.

OUTPUT FORMAT (strict markdown):
# Verdict — HAL voice + report programming
## 0. Operator Intent (quote; consult-only)
## 1. Current State Audit (HalVoice, PTT, TTS, voice commands, handoff/readiness reports)
## 2. Gap Map
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Design — voice + report together
### 3A Speak path (reply → excerpt → TTS; interrupt; mute/skip rules)
### 3B Listen path (PTT / STT → query → tools → spoken report)
### 3C Report types (handoff, readiness, daily ops briefing) + spoken vs markdown
### 3D Voice command grammar (extend parsers vs free-form HAL tools)
## 4. Coding Plan by Phase (files · paste-ready sketches · validation)
## 5. MUST / SHOULD / NICE ranked table
## 6. Risks, PHI, SoftDent honesty, Rollback
## 7. Approval Checklist
DO NOT APPLY until operator says approve / proceed.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def _extract_lines(path: Path, start_marker: str, end_marker: str | None, max_lines: int) -> str:
    if not path.is_file():
        return "(missing)"
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.find(start_marker)
    if start < 0:
        return f"(marker not found: {start_marker[:80]})"
    if end_marker:
        end = text.find(end_marker, start + len(start_marker))
        chunk = text[start : (end if end > start else start + 14000)]
    else:
        chunk = text[start : start + 14000]
    return _truncate(chunk, max_lines)


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 12),
    ("NewRidgeFinancial2/docs/architecture.md", 30),
    ("NewRidgeFinancial2/docs/MOONSHOT_VOICE_PAYER_TEMPLATES_APPLIED_2026-07-10.md", 50),
    ("NewRidgeFinancial2/site/data/hal-voice-scripts.json", 40),
]


def build_context() -> str:
    parts: list[str] = []
    for rel, max_lines in CONTEXT_FILES:
        path = REPO / rel
        if not path.is_file():
            parts.append(f"### FILE: {rel}\n(missing)")
            continue
        body = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
        ext = path.suffix.lstrip(".") or "txt"
        parts.append(f"### FILE: {rel}\n```{ext}\n{body}\n```")

    nr2 = REPO / "NewRidgeFinancial2"
    voice = nr2 / "site" / "hal-voice.js"
    app = nr2 / "site" / "app.js"
    agent = nr2 / "site" / "hal-agent.js"

    if voice.is_file():
        parts.append(
            "### EXTRACT: hal-voice.js — HAL_CHAT + speakHalReply + exports\n```javascript\n"
            + _extract_lines(voice, "const HAL_CHAT = {", "function beginSpeechGeneration", 40)
            + "\n```"
        )
        parts.append(
            "### EXTRACT: hal-voice.js — speakHalReply\n```javascript\n"
            + _extract_lines(voice, "function speakHalReply", "function listVoices", 55)
            + "\n```"
        )
        parts.append(
            "### EXTRACT: hal-voice.js — checkNeuralTts / speak\n```javascript\n"
            + _extract_lines(voice, "async function checkNeuralTts", "function playNeuralAudio", 40)
            + "\n```"
        )
        parts.append(
            "### EXTRACT: hal-voice.js — public API\n```javascript\n"
            + _extract_lines(voice, "global.HalVoice = {", None, 40)
            + "\n```"
        )

    if app.is_file():
        parts.append(
            "### EXTRACT: app.js — voice PTT + speechSynthesis fallback\n```javascript\n"
            + _extract_lines(app, 'const voicePtt = event.target.closest("[data-hal-voice-ptt]")', None, 25)
            + "\n```"
        )
        parts.append(
            "### EXTRACT: app.js — speakHalReply after reply\n```javascript\n"
            + _extract_lines(app, "HalVoice.speakHalReply", None, 35)
            + "\n```"
        )
        parts.append(
            "### EXTRACT: app.js — naturalVoiceConfig\n```javascript\n"
            + _extract_lines(app, "function naturalVoiceConfig()", "function ", 35)
            + "\n```"
        )

    if agent.is_file():
        parts.append(
            "### EXTRACT: hal-agent.js — clock_out_shift / handoff report tools\n```javascript\n"
            + _extract_lines(agent, "clock_out_shift: {", "get_last_handoff_report: {", 30)
            + "\n```"
        )
        parts.append(
            "### EXTRACT: hal-agent.js — get_last_handoff_report\n```javascript\n"
            + _extract_lines(agent, "get_last_handoff_report: {", None, 25)
            + "\n```"
        )

    parts.append(
        "### EXTRACT: apex_backend.py — voice command routing\n```python\n"
        + _extract_lines(
            nr2 / "apex_backend.py",
            "from apex_cpa_pack import parse_voice_slider_command",
            None,
            50,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: apex_cpa_pack.py — parse_voice_slider_command\n```python\n"
        + _extract_lines(
            nr2 / "apex_cpa_pack.py",
            "def parse_voice_slider_command",
            None,
            40,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: apex_claims_narratives_pack.py — parse_voice_narrative_command\n```python\n"
        + _extract_lines(
            nr2 / "apex_claims_narratives_pack.py",
            "def parse_voice_narrative_command",
            None,
            45,
        )
        + "\n```"
    )

    parts.append(
        """### LIVE FACTS
- SoftDent READ-ONLY forever. Never invent dollars. empty ≠ $0.
- PHI local-only; production HAL uses local 24B on loopback; cloud off by default.
- HalVoice (site/hal-voice.js): browser speechSynthesis + optional Edge neural TTS
  via loopback TTS API; speakHalReply excerpts long answers; interrupt/cancel;
  boot greeting; sidenote/office announce.
- UI: data-hal-voice-ptt chip on HAL page; data-hal-voice-test; app.js wires reply
  speech after HAL answers (skippable via _halRandomQaSkipSpeech).
- Voice → action already exists for EBITDA scrubber (parse_voice_slider_command)
  and claims narratives (parse_voice_narrative_command) via apex_backend.
- Reports: clock_out_shift / get_last_handoff_report tools; readiness diagnostics
  in hal-core.js; reportStyle preference in long-term prefs.
- Operator asked how to PROGRAM "hal voice and report" — recommend concrete
  programming plan to strengthen speak/listen + spoken/written reports together.
- Prefer compose/extend existing HalVoice + tools over new cloud voice vendors.
"""
    )
    return "\n\n".join(parts)


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No Moonshot/OpenRouter API key.", file=sys.stderr)
        return 1

    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()

    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        "OPERATOR REQUEST (VERBATIM — do not rewrite):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CONSULT ONLY — recommend how to program HAL voice (speak/listen/commands) "
        "and reports (handoff, readiness, spoken briefings). Do not apply. "
        "SoftDent READ-ONLY; empty ≠ $0; PHI local TTS / loopback only.\n\n"
        "## Codebase context\n\n"
        + build_context()
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 14000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 HAL Voice and Report Consult"

    print("Calling Moonshot AI (consult only — will not apply)...")
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    content = ""
    status = "error"
    last_err = ""
    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(req, timeout=3600) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = extract_message_content(body)
            status = "ok"
            break
        except urllib.error.HTTPError as exc:
            content = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}"
            status = f"HTTP {exc.code}"
            break
        except Exception as exc:
            last_err = str(exc)
            content = last_err
            status = "error"
            print(f"Attempt {attempt}/4 failed: {last_err}", file=sys.stderr)
            if attempt < 4:
                time.sleep(5 * attempt)

    header = (
        f"# Moonshot AI — HAL Voice + Report Programming (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_hal_voice_report_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_HAL_VOICE_REPORT_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_HAL_VOICE_REPORT_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
