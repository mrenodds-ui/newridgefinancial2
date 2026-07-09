"""Moonshot AI — full-program audit: live pages vs elite mockups (errors + paste-ready fixes).

CONSULT ONLY. Report for operator validation. Do not apply.
"""

from __future__ import annotations

import json
import os
import re
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

SYSTEM = """You are Moonshot AI (kimi-k2 class) — principal architect + debugger for NewRidge Financial 2.0.

OPERATOR REQUEST:
Evaluate the ENTIRE program for errors causing CURRENT live staff pages to fail matching /
working with elite Jul 8 mockups. Find EVERY remaining conflict after the hal-10167 no-overlay
patch. Deliver REPORT + paste-ready CODE fixes. CONSULT-ONLY — operator will validate before apply.

KNOWN POST-10167 STATE (trust; verify against supplied files):
- NR2_STAFF_MOCK_ONLY=false; data-nr2-staff-render boots live-wire-pilot
- app--mock-embed-solo removed; nr2-mock-embed-critical deleted; #sidebar restored
- page-canvas live-wire never iframes (LE error instead); __NR2_LEGACY_MOCKUP_FALLBACK for rollback
- nr2-mission-control-glass.css linked + P1 strengthen
- nr2-moonshot-mockup-chrome.js staffMockEmbedMode respects live-wire-pilot
- BUT moonshot-page-registry.js staffMockOnly() STILL returns true when __NR2_MOCKUP_ELITE_PAGES
  catalog is non-empty (stale "elite catalog implies mock-embed" heuristic)
- validate-pages.mjs still has mock-embed assertions that may fight live-wire-pilot
- Operator symptom historically: pages look like old schema / mockup update "did not come up"

EVALUATE ALL PROGRAM LAYERS:
1. Boot flags / index.html / SW cache
2. Render path: page-canvas, layout-engine, layouts, page-views, chrome
3. Registry / PageSchema / hasMockPreview / staffMockOnly
4. CSS cascade: vocabulary vs glow vs mission-control vs theme (specificity wars)
5. Validators (validate-pages.mjs) that encode wrong mode assumptions
6. Import honesty / empty states (must stay)
7. Elite HTML structure vs live layout manifest gaps (structure, not iframe)
8. HAL vs staff page shell differences
9. Any remaining mock-embed chrome injection paths

HARD RULES:
1. Existing widgets only — no new chart libraries / fabricated $.
2. Prefer kill conflicting heuristics over adding a third mode.
3. Paste-ready ### File: blocks with exact paths under NewRidgeFinancial2/
4. Severity: Critical | High | Medium | Low for each finding
5. Mark speculative items as speculative
6. Do NOT assume merge — this is review-only

OUTPUT FORMAT (strict markdown):
# Verdict (one paragraph — root cause of live vs mockup failure after 10167)
## Executive Summary
## Full Program Error Inventory
Table: ID | Severity | Area | File | Evidence | Why it breaks live↔mockup | Fix summary
Cover ALL findings (boot, registry, chrome, CSS, validators, layout gaps, SW, etc.)
## Architecture Diagnosis
How elite mockup SHOULD map to live-wire today (no iframe). What still interrupts.
## Moonshot Code Deliverables
### File: <path>
```language
paste-ready patch
```
Minimum: every Critical/High finding must have a code block.
## Per-Page Elite Parity Gaps (financial, claims, quickbooks, narratives, softdent, ar, taxes, documents, library, office-manager, hal)
Brief: structure/CSS/data gaps still visible to operator.
## Validation Gate (browser + node)
Exact checks after apply.
## Prioritized Commits (max 5) — WAIT for operator proceed
## Risks & Rollback
"""


def read_file(rel: str, max_chars: int = 12000) -> str:
    path = REPO / rel
    if not path.is_file():
        return f"(missing {rel})"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n...[{len(text) - max_chars} chars truncated]..."
    return text


def excerpt(rel: str, needle: str, before: int = 200, after: int = 1200) -> str:
    text = read_file(rel, max_chars=500000)
    if text.startswith("(missing"):
        return text
    pos = text.find(needle)
    if pos < 0:
        return f"(no match for {needle!r} in {rel})"
    start = max(0, pos - before)
    return text[start : pos + after]


def elite_snip(page_id: str, max_chars: int = 1800) -> str:
    path = OUT / "page_mockups_elite" / f"{page_id}.html"
    if not path.is_file():
        return f"(missing elite {page_id})"
    t = path.read_text(encoding="utf-8", errors="replace")
    return t[:max_chars] + ("\n...[truncated]..." if len(t) > max_chars else "")


def build_user() -> str:
    parts: list[str] = [
        "# Operator brief",
        "Full-program audit: find ALL errors causing live pages vs elite mockup failure.",
        "Current build hal-10167 after no-overlay patch. Report + code. Do not apply.",
        "",
        "# Prior Moonshot consults (context)",
        "### MOONSHOT_MOCKUP_NO_OVERLAY_CONSULT (applied as d91324c / hal-10167)\n",
        read_file("NewRidgeFinancial2/docs/MOONSHOT_MOCKUP_NO_OVERLAY_CONSULT_2026-07-09.md", 8000),
        "",
        "# Live build + boot",
        f"### nr2-build.json\n```json\n{read_file('NewRidgeFinancial2/nr2-build.json')}\n```\n",
        f"### index.html (head+shell)\n```html\n{read_file('NewRidgeFinancial2/site/index.html', 9000)}\n```\n",
        "",
        "# Conflicting mock-embed heuristics still in tree",
        "### moonshot-page-registry.js staffMockOnly\n```javascript\n"
        + excerpt("NewRidgeFinancial2/site/moonshot-page-registry.js", "function staffMockOnly", 50, 900)
        + "\n```\n",
        "### nr2-moonshot-mockup-chrome.js staffMockEmbedMode\n```javascript\n"
        + excerpt("NewRidgeFinancial2/site/nr2-moonshot-mockup-chrome.js", "function staffMockEmbedMode", 50, 900)
        + "\n```\n",
        "### app.js staffMockEmbedNavHidden / syncStaffRenderModeAttr\n```javascript\n"
        + excerpt("NewRidgeFinancial2/site/app.js", "function staffMockEmbedNavHidden", 50, 900)
        + "\n```\n",
        "### page-canvas.js renderBody\n```javascript\n"
        + excerpt("NewRidgeFinancial2/site/page-canvas.js", "function renderBody", 50, 2200)
        + "\n```\n",
        "### desktop-boot.js mock check\n```javascript\n"
        + excerpt("NewRidgeFinancial2/site/desktop-boot.js", "NR2_STAFF_MOCK_ONLY", 80, 600)
        + "\n```\n",
        "### sw.js cache name\n```javascript\n"
        + read_file("NewRidgeFinancial2/site/sw.js", 2500)
        + "\n```\n",
        "",
        "# Validators (may encode wrong mode)",
        f"### validate-pages.mjs\n```javascript\n{read_file('NewRidgeFinancial2/validate-pages.mjs', 14000)}\n```\n",
        "",
        "# Layout engine + layouts (live structure)",
        "### moonshot-layout-engine.js render()\n```javascript\n"
        + excerpt(
            "NewRidgeFinancial2/site/deferred-live-wire/moonshot-layout-engine.js",
            "function render(pageId",
            50,
            2000,
        )
        + "\n```\n",
        "### moonshot-page-layouts.js (head)\n```javascript\n"
        + read_file("NewRidgeFinancial2/site/deferred-live-wire/moonshot-page-layouts.js", 8000)
        + "\n```\n",
        "",
        "# CSS cascade (specificity)",
        "### nr2-mission-control-glass.css (head+P1)\n```css\n"
        + read_file("NewRidgeFinancial2/site/nr2-mission-control-glass.css", 6000)
        + "\n```\n",
        "### nr2-mockup-page-vocabulary.css mock-embed + financial glass\n```css\n"
        + excerpt("NewRidgeFinancial2/site/nr2-mockup-page-vocabulary.css", 'html[data-nr2-staff-render="mock-embed"]', 50, 2000)
        + "\n\n"
        + excerpt("NewRidgeFinancial2/site/nr2-mockup-page-vocabulary.css", "financial-moonshot .widget-card", 50, 800)
        + "\n```\n",
        "",
        "# page-views stripMockEmbedLiveChrome",
        "```javascript\n"
        + excerpt("NewRidgeFinancial2/site/page-views.js", "stripMockEmbedLiveChrome", 50, 1200)
        + "\n```\n",
        "",
        "# Elite mock HTML samples (structure target — NOT iframe)",
    ]
    for pid in ("financial", "claims", "quickbooks", "narratives"):
        parts.append(f"## Elite {pid}.html\n```html\n{elite_snip(pid)}\n```\n")

    parts.append(
        "Respond with the strict OUTPUT FORMAT. Be exhaustive on remaining errors. "
        "Every Critical/High needs paste-ready code."
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
            "max_tokens": 16384,
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
            headers["X-Title"] = os.getenv("OPENROUTER_X_TITLE") or "NR2 Full Program Mockup Audit"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=480) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = extract_message_content(data)
            if content and len(content.strip()) > 500:
                return content, mdl, key_name or "API_KEY"
            last_err = f"empty/short from {mdl} @ {url}"
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} {mdl} @ {url}: {e.read()[:500]!r}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__} {mdl} @ {url}: {e}"
    raise RuntimeError(last_err or "Moonshot call failed")


def extract_code(report: str) -> list[str]:
    dest = OUT / f"full_program_mockup_audit_code_{DATE}"
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    pat = re.compile(r"### File:\s*`?([^\n`]+)`?\s*\n```(\w+)?\n([\s\S]*?)```", re.M)
    for i, m in enumerate(pat.finditer(report), 1):
        name = m.group(1).strip().replace("\\", "/")
        lang = (m.group(2) or "txt").lower()
        content = m.group(3)
        safe = re.sub(r"[^\w./\-]", "_", name).replace("/", "__")
        if not any(safe.endswith(e) for e in (".js", ".css", ".html", ".mjs", ".json", ".md", ".txt")):
            ext = {"javascript": ".js", "js": ".js", "css": ".css", "html": ".html", "json": ".json"}.get(lang, ".txt")
            safe = f"{i:02d}_{safe}{ext}"
        else:
            safe = f"{i:02d}_{safe}"
        path = dest / safe
        path.write_text(content, encoding="utf-8")
        written.append(str(path.relative_to(OUT)))
    return written


def main() -> int:
    print("Building Moonshot full-program mockup audit prompt…")
    user = build_user()
    OUT.mkdir(parents=True, exist_ok=True)
    prompt_path = OUT / f"FULL_PROGRAM_MOCKUP_AUDIT_PROMPT_{DATE}.md"
    prompt_path.write_text(user, encoding="utf-8")
    print(f"Prompt saved: {prompt_path} ({len(user)} chars)")

    try:
        content, model, key_name = call_moonshot(SYSTEM, user)
    except Exception as e:  # noqa: BLE001
        err = f"# Moonshot Full Program Mockup Audit FAILED\n\n{e}\n"
        (DOCS / f"MOONSHOT_FULL_PROGRAM_MOCKUP_AUDIT_{DATE}_FAILED.md").write_text(err, encoding="utf-8")
        print(err, file=sys.stderr)
        return 1

    header = (
        f"# Moonshot AI — Full Program Mockup / Live-Wire Error Audit\n"
        f"**Date:** {DATE}\n"
        f"**Model:** {model} via {key_name}\n"
        f"**Status:** REVIEW ONLY — do not apply until operator validates\n"
        f"**Script:** `scripts/run_moonshot_full_program_mockup_audit.py`\n"
        f"**Build context:** hal-10167 (post no-overlay)\n\n"
        f"---\n\n"
    )
    report = header + content.strip() + "\n"
    out_docs = DOCS / f"MOONSHOT_FULL_PROGRAM_MOCKUP_AUDIT_{DATE}.md"
    out_log = OUT / f"MOONSHOT_FULL_PROGRAM_MOCKUP_AUDIT_{DATE}.md"
    out_docs.write_text(report, encoding="utf-8")
    out_log.write_text(report, encoding="utf-8")
    files = extract_code(report)
    print(f"Wrote {out_docs}")
    print(f"Wrote {out_log}")
    print(f"Chars: {len(report)}; code files: {len(files)}")
    for f in files:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
