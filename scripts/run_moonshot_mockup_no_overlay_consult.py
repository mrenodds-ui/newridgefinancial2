"""Moonshot AI — make elite mockups drive live pages without mock-embed overlay / legacy interference.

CONSULT ONLY — report + paste-ready code. Do not apply.
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
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

sys.path.insert(0, str(OUT))
from _run_moonshot_eval import extract_message_content, resolve_api_and_endpoint  # noqa: E402

SYSTEM = """You are Moonshot AI (kimi-k2 class) — lead front-end architect for NewRidge Financial 2.0.

OPERATOR REQUEST (CRITICAL):
Give CODE + EXACT INSTRUCTIONS so elite Jul 8 mockups work WITH the CURRENT live staff pages
WITHOUT overlay and WITHOUT legacy files interrupting procedures.
Deliver a REPORT for operator validation. Do NOT assume anything is merged. CONSULT-ONLY.

OBSERVED LIVE STATE (2026-07-09, build ~hal-10166) — trust these facts:
1. staffRenderMode in nr2-build.json = live-wire-pilot; MoonshotLayoutEngine DOES render staff pages
   (verified: .widget-grid.financial-moonshot.ms-mission-control present; no iframe on Financial).
2. BUT index.html still boots with CONFLICTING flags:
   - window.NR2_STAFF_MOCK_ONLY = true
   - data-nr2-staff-render starts as 'mock-embed'
   - <div id="app" class="app app--moonshot-mockup app--mock-embed-solo">
   - <style id="nr2-mock-embed-critical"> hides sidebar, sync badges, strips, etc. under mock-embed
3. app.js later may flip data-nr2-staff-render to live-wire-pilot, but mock-embed chrome/CSS/solo
   class and NR2_STAFF_MOCK_ONLY still shape the shell — operator says pages "look no different"
   / mockup update did not come up.
4. page-canvas.js: shouldLiveWire → LE.render; else mockupPreviewGate (iframe). Fallback still
   present if layout engine missing.
5. nr2-mission-control-glass.css is linked, but visual delta is weak vs nr2-mockup-page-vocabulary.css
   (both already use blur/glass on many panels).
6. Elite HTML lives at .local_logs/moonshot_financial_eval/page_mockups_elite/*.html and
   /mockup-elite-embed/{pageId} — operator does NOT want iframe overlay on top of live pages.
7. Honesty rules stay: empty widgets name exact export files; never fabricate $.

GOAL:
- Elite mockup STRUCTURE + LOOK on live pages (PageCanvasData + HAL wired).
- No iframe overlay.
- No mock-embed / legacy chrome interrupting live-wire procedures.
- Exact file paths + paste-ready patches + ordered steps.
- Rollback path.

HARD RULES:
1. Prefer flipping/removing conflicting flags over inventing a third render mode.
2. Existing widgets / PageCanvas helpers only — no new chart libraries.
3. Keep mockupPreviewGate code behind a dead flag or delete only with explicit rollback note.
4. Do not invent new widget keys.
5. HAL (#hal) may keep its own page shell; staff pages are the focus.
6. Mark every change P0/P1/P2 with acceptance criteria.

OUTPUT FORMAT (strict markdown):
# Verdict (one paragraph — will this make elite mock look drive live pages without overlay?)
## 1. Root Cause: Why mockup look / procedures are interrupted
List each conflicting flag, CSS block, class, and fallback path with file:line evidence from context.
## 2. Target Architecture (no overlay)
Clear diagram in words: boot flags → renderBody → MoonshotLayoutEngine only → elite-class CSS.
What is DELETED vs DISABLED vs KEPT.
## 3. Exact Operator Instructions (numbered, copy-paste order)
Step-by-step: which files to edit, what to set, how to verify, how to rollback.
## 4. Moonshot Code Deliverables
### File: <path>
```language
paste-ready full patch or complete replacement snippet
```
Minimum files to cover:
- NewRidgeFinancial2/site/index.html (boot flags + remove/disable mock-embed-critical for live-wire)
- NewRidgeFinancial2/site/app.js (staff-render attribute / mock-only branch)
- NewRidgeFinancial2/nr2-build.json + site/nr2-build.json (staffRenderMode if needed)
- NewRidgeFinancial2/site/page-canvas.js (never fall through to iframe when live-wire-pilot)
- CSS: either strengthen mission-control OR stop mock-embed vocabulary overrides fighting live pages
- Optional: nr2-moonshot-mockup-chrome.js if mock-embed chrome still injects
## 5. Legacy / Overlay Kill List
Table: artifact | path | action (delete|disable|keep) | why
Include: NR2_STAFF_MOCK_ONLY, data-nr2-staff-render mock-embed, app--mock-embed-solo,
nr2-mock-embed-critical, mockupPreviewGate iframe, ms-mockup-preview-frame, live-wire-pilot-banner,
service worker mock-embed cache name if relevant.
## 6. Validation Gate (browser)
Checklist proving: no iframe, no mock-embed attribute after boot, elite classes visible,
sidebar/tools behavior correct, Claims/Financial/QB look clearly elite, honesty empties intact.
## 7. Prioritized Commits (max 4) — WAIT for operator proceed
## Risks & Rollback
"""


def read_truncated(rel: str, max_lines: int = 160) -> str:
    path = REPO / rel
    if not path.is_file():
        return f"(missing {rel})"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    body = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        body += f"\n... [{len(lines) - max_lines} lines truncated] ..."
    return f"### {rel}\n```\n{body}\n```\n"


def elite_snippet(page_id: str, max_chars: int = 2500) -> str:
    path = OUT / "page_mockups_elite" / f"{page_id}.html"
    if not path.is_file():
        return f"(missing elite {page_id}.html)"
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars] + ("\n...[truncated]..." if len(text) > max_chars else "")


def build_user() -> str:
    parts = [
        "# Operator brief",
        "Make elite mockups work with CURRENT live pages. No iframe overlay. No legacy/mock-embed interrupting.",
        "Report + code only. Do not apply.",
        "",
        "# Conflicting boot / render evidence",
        read_truncated("NewRidgeFinancial2/site/index.html", 120),
        read_truncated("NewRidgeFinancial2/nr2-build.json", 30),
        read_truncated("NewRidgeFinancial2/site/page-canvas.js", 80),  # will be head — also need renderBody
        "",
        "# page-canvas renderBody / live-wire / mockupPreviewGate (tail excerpt via grep context below)",
    ]
    # Explicit renderBody region
    pc = (REPO / "NewRidgeFinancial2/site/page-canvas.js").read_text(encoding="utf-8", errors="replace")
    idx = pc.find("function liveWirePages")
    if idx < 0:
        idx = pc.find("function renderBody")
    parts.append("### page-canvas.js live-wire region\n```javascript\n" + pc[idx : idx + 4500] + "\n```\n")

    app = (REPO / "NewRidgeFinancial2/site/app.js").read_text(encoding="utf-8", errors="replace")
    for needle in ("NR2_STAFF_MOCK_ONLY", "data-nr2-staff-render", "mock-embed"):
        pos = app.find(needle)
        if pos >= 0:
            start = max(0, pos - 400)
            parts.append(f"### app.js near `{needle}`\n```javascript\n{app[start:start+1800]}\n```\n")
            break

    chrome = REPO / "NewRidgeFinancial2/site/nr2-moonshot-mockup-chrome.js"
    if chrome.is_file():
        ct = chrome.read_text(encoding="utf-8", errors="replace")
        for needle in ("mock-embed", "mockEmbed", "staffRenderMode", "live-wire"):
            pos = ct.find(needle)
            if pos >= 0:
                start = max(0, pos - 300)
                parts.append(f"### nr2-moonshot-mockup-chrome.js near `{needle}`\n```javascript\n{ct[start:start+2000]}\n```\n")
                break

    parts.append(read_truncated("NewRidgeFinancial2/site/deferred-live-wire/moonshot-layout-engine.js", 100))
    parts.append(read_truncated("NewRidgeFinancial2/site/nr2-mission-control-glass.css", 80))
    # vocabulary mock-embed section
    vocab = (REPO / "NewRidgeFinancial2/site/nr2-mockup-page-vocabulary.css").read_text(encoding="utf-8", errors="replace")
    vpos = vocab.find('html[data-nr2-staff-render="mock-embed"]')
    if vpos >= 0:
        parts.append(
            "### nr2-mockup-page-vocabulary.css mock-embed rules\n```css\n"
            + vocab[vpos : vpos + 2500]
            + "\n```\n"
        )

    parts.append("# Elite visual targets (structure to match — NOT iframe)")
    for pid in ("financial", "claims", "quickbooks"):
        parts.append(f"## Elite {pid}.html (truncated)\n```html\n{elite_snippet(pid)}\n```\n")

    parts.append(
        "Respond with the strict OUTPUT FORMAT. Emphasize removing overlay/legacy interference "
        "so live-wire pages ARE the mockup, not an iframe or half-mock shell."
    )
    return "\n".join(parts)


def call_moonshot(system: str, user: str) -> tuple[str, str, str]:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        raise RuntimeError("No Moonshot/OpenRouter API key available")

    candidates: list[tuple[str, str]] = []
    if "openrouter" in (base_url or "").lower() or "OPENROUTER" in (key_name or "").upper():
        candidates.append((base_url, "moonshotai/kimi-k2.5"))
        candidates.append((base_url, "moonshotai/kimi-k2"))
        candidates.append(("https://api.moonshot.ai/v1/chat/completions", "kimi-k2.5"))
    else:
        candidates.append((base_url or "https://api.moonshot.ai/v1/chat/completions", "kimi-k2.5"))
        candidates.append(("https://openrouter.ai/api/v1/chat/completions", "moonshotai/kimi-k2.5"))

    last_err = ""
    for url, mdl in candidates:
        payload = {
            "model": mdl,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 1,
            "max_tokens": 12288,
        }
        if "api.moonshot." in url:
            payload["top_p"] = 0.95
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if "openrouter.ai" in url:
            headers["HTTP-Referer"] = os.getenv("OPENROUTER_HTTP_REFERER") or "https://github.com/NewRidgeFamilyFinancial"
            headers["X-Title"] = os.getenv("OPENROUTER_X_TITLE") or "NR2 Mockup No-Overlay Consult"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=420) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = extract_message_content(data)
            if content and len(content.strip()) > 300:
                return content, mdl, key_name or "API_KEY"
            last_err = f"empty/short from {mdl} @ {url}"
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} {mdl} @ {url}: {e.read()[:400]!r}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__} {mdl} @ {url}: {e}"
    raise RuntimeError(last_err or "Moonshot call failed")


def main() -> int:
    print("Building Moonshot mockup-no-overlay consult prompt…")
    user = build_user()
    OUT.mkdir(parents=True, exist_ok=True)
    prompt_path = OUT / f"MOCKUP_NO_OVERLAY_PROMPT_{DATE}.md"
    prompt_path.write_text(user, encoding="utf-8")
    print(f"Prompt saved: {prompt_path} ({len(user)} chars)")

    try:
        content, model, key_name = call_moonshot(SYSTEM, user)
    except Exception as e:  # noqa: BLE001
        err = f"# Moonshot Mockup No-Overlay Consult FAILED\n\n{e}\n"
        (DOCS / f"MOONSHOT_MOCKUP_NO_OVERLAY_CONSULT_{DATE}_FAILED.md").write_text(err, encoding="utf-8")
        print(err, file=sys.stderr)
        return 1

    header = (
        f"# Moonshot AI — Mockup on Live Pages (No Overlay / No Legacy Interrupt)\n"
        f"**Date:** {DATE}\n"
        f"**Model:** {model} via {key_name}\n"
        f"**Status:** REVIEW ONLY — do not apply until operator validates\n"
        f"**Script:** `scripts/run_moonshot_mockup_no_overlay_consult.py`\n"
        f"**Scope:** Elite mock look on live-wire pages; kill mock-embed overlay + conflicting flags\n\n"
        f"---\n\n"
    )
    report = header + content.strip() + "\n"
    out_docs = DOCS / f"MOONSHOT_MOCKUP_NO_OVERLAY_CONSULT_{DATE}.md"
    out_log = OUT / f"MOONSHOT_MOCKUP_NO_OVERLAY_CONSULT_{DATE}.md"
    out_docs.write_text(report, encoding="utf-8")
    out_log.write_text(report, encoding="utf-8")
    print(f"Wrote {out_docs}")
    print(f"Wrote {out_log}")
    print(f"Chars: {len(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
