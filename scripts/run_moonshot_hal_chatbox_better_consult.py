"""Moonshot AI — Better chat box for HAL page (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code. Await operator approval before coding.
"""

from __future__ import annotations

import json
import os
import sys
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
ask moonshot ai if there ia a better chat box to use with hal page and report with code dont code until approved
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — UX + frontend architect for NewRidge
Financial 2.0 (NR2) Apex HAL command center (local HTTPS starship-bridge app).

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: Is there a BETTER chat box for the HAL page?
   REPORT WITH CODE (paste-ready snippets). DO NOT APPLY — wait for approval.
2. CONSULT ONLY — do not claim you edited the live repo.
3. Ground recommendations in the CURRENT HAL chat implementation provided in context
   (apex-core.js hal-chat widget + apex-tokens.css .apex-hal-chat* + board-actions
   pipeline + evaluate-query endpoint). Do not invent APIs.
4. Prefer evolving the existing custom Apex HAL chat over pulling a third-party chat
   library UNLESS a specific library clearly wins on UX AND can stay local/offline-friendly
   with zero SaaS dependency. If recommending a library, justify vs custom upgrade.
5. HAL chat is a COMMAND SURFACE (board actions: sync, navigate, focus widgets) plus
   conversational replies — not a generic ChatGPT clone. Preserve: transcript persistence,
   suggestion chips, Enter-to-send / Shift+Enter newline, Thinking… pending, askHalAboutWidget,
   softRenderHalMain rail preservation, honesty (no invented $).
6. Compare: (A) keep + polish current, (B) redesigned custom composer (recommended
   patterns), (C) optional library. Pick ONE primary recommendation with clear why.
7. Include paste-ready HTML/CSS/JS snippets labeled CONSULT ONLY for the recommended
   chat box (structure, composer, message bubbles, chips, status, a11y).
8. Call out risks: remount wiping transcript, sticky input, chip overflow, mobile, a11y,
   focus traps with HAL highlight overlay.
9. End with APPROVAL CHECKLIST — STOP until operator says approve/proceed.

OUTPUT FORMAT (strict markdown):
# Verdict — Is there a better chat box? (yes/no + one-line why)
## 0. Operator Intent (quote; confirm consult-only)
## 1. Current Chat Box Audit (what works / what hurts)
## 2. Options Compared (A keep+polish / B redesigned custom / C library)
## 3. Primary Recommendation (pick one)
## 4. Proposed UI Spec (layout, composer, messages, chips, status)
## 5. Paste-Ready Code (CONSULT ONLY) — HTML template, CSS, JS wiring deltas
## 6. Files to Touch + Migration Notes (preserve askHal / board-actions)
## 7. Phased Plan + Validation Gates (DO NOT APPLY)
## 8. Approval Checklist
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
        return f"(marker not found: {start_marker[:60]})"
    if end_marker:
        end = text.find(end_marker, start + len(start_marker))
        chunk = text[start : (end if end > start else start + 12000)]
    else:
        chunk = text[start : start + 12000]
    return _truncate(chunk, max_lines)


def build_context() -> str:
    apex = REPO / "NewRidgeFinancial2" / "site" / "apex-core.js"
    tokens = REPO / "NewRidgeFinancial2" / "site" / "apex-tokens.css"
    backend = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    parts: list[str] = []

    parts.append(
        "### EXTRACT: apex-core.js — hal-chat widget template\n```js\n"
        + _extract_lines(apex, 'if (this.type === "hal-chat") {\n        return `', "if (this.type === \"status\"", 40)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: apex-core.js — appendHalMessage / askHal / wireHalChat\n```js\n"
        + _extract_lines(apex, "function appendHalMessage(logEl, role, text, opts)", "function sameWidgetIds", 220)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: apex-tokens.css — .apex-hal-chat*\n```css\n"
        + _extract_lines(tokens, ".apex-hal-chat {", ".apex-widget {", 140)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: apex_backend.py — hal-chat widget spec\n```python\n"
        + _extract_lines(backend, '"type": "hal-chat"', None, 40)
        + "\n```"
    )
    # Also note legacy app.js chat if present
    app = REPO / "NewRidgeFinancial2" / "site" / "app.js"
    if app.is_file():
        parts.append(
            "### NOTE: Legacy app.js also has .hal-chat (older manager UI)\n```js\n"
            + _extract_lines(app, '<div class="hal-chat">', None, 25)
            + "\n```"
        )

    parts.append(
        """### LIVE FACTS
- Apex HAL page uses a right rail with type "hal-chat" widget (not a third-party chat SDK).
- Messages: plain textContent bubbles (user/hal); no markdown, no streaming tokens UI,
  no copy button, no regenerate, no voice affordance in the composer itself.
- Suggestion chips: large hardcoded list + optional /hal/status suggestion; max-height 72px.
- Pipeline: /api/hal/board-actions first (deterministic), else /api/hal/evaluate-query (chat8b).
- Transcript: in-memory halTranscript[] restored across soft remounts; HAL_TRANSCRIPT_MAX=80.
- softRenderHalMain preserves chat host in .apex-hal-rail across silent refreshes.
- Ask-HAL on other widgets routes into this chat via askHal / loadPage("hal").
- Starship aesthetic: cyan accents, elevated surfaces, Apex tokens.
- Operator wants: better chat box recommendation WITH code; do not code until approved.
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
        "Is there a better chat box for the HAL page? Report with paste-ready code. "
        "CONSULT ONLY — do not apply. Wait for approval.\n\n"
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
        headers["X-Title"] = "NR2 HAL Better Chat Box Consult"

    print("Calling Moonshot AI (consult only — will not apply)...")
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(body)
        status = "ok"
    except urllib.error.HTTPError as exc:
        content = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}"
        status = f"HTTP {exc.code}"
    except Exception as exc:
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — Better HAL Chat Box (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_hal_chatbox_better_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / WAIT FOR OPERATOR APPROVAL.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_HAL_CHATBOX_BETTER_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_HAL_CHATBOX_BETTER_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
