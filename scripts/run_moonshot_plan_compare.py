"""Moonshot AI — compare Cursor Mission Control plan vs Moonshot visual consult.

Consult-only. Writes comparison report; does not apply code.
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

The operator has TWO documents:
(A) YOUR prior High-Tech Visual Polish Consult (Terminal Glass / mission-control).
(B) Cursor agent's implementation PLAN derived from (A), with DOM-reality adaptations.

Your job: COMPARE them rigorously. Do NOT rewrite a full new design system.
Do NOT assume anything is merged. CONSULT-ONLY.

HARD FACTS about live DOM (trust these over your prior CSS selectors if they conflict):
- Outer wrapper: article.ms-page (page-views.js)
- Inner shell: div.widget-grid.{pageId}-moonshot via stackOpen / dashboardPageOpen
- Kanban today uses: .kanban-board, .kanban-column, .column-header, .column-content
  (NOT .kanban-lane-mission yet)
- staffRenderMode: live-wire-pilot; build ~hal-10164
- Loopback HTTPS app — Google Fonts CDN @import is undesirable

OUTPUT FORMAT (strict markdown):
# Verdict (one paragraph — is Cursor's plan sound? APPROVE / APPROVE WITH EDITS / REJECT)
## Agreement Matrix
Table: Topic | Moonshot consult | Cursor plan | Match? | Winner / note
Cover at least: CSS file strategy, selector scoping, class injection site, kanban class strategy,
KPI mono, empty states, severity data honesty, Google Fonts, apply order P0-P3, page-by-page accents,
dashboard-grid pages (QB/office-manager), HAL scope, commit/build bump.
## Where Cursor Improved On Moonshot
Numbered list (DOM scoping, dual kanban classes, no CDN, etc.)
## Where Cursor Weakened Or Missed Moonshot
Numbered list — be specific. Include any page-by-page accent CSS Moonshot wanted that Cursor deferred.
## Required Plan Edits (must-fix before apply)
Concrete bullets Cursor must add/change in the plan. If none, say NONE.
## Optional Nice-to-Haves (defer)
## Final Recommended Apply Order
Numbered commits/steps, max 5.
## Operator One-Liner
One sentence the operator can use to approve or reject.
"""


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
            "max_tokens": 8192,
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
            headers["X-Title"] = os.getenv("OPENROUTER_X_TITLE") or "NR2 Plan Compare"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=360) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = extract_message_content(data)
            if content and len(content.strip()) > 200:
                return content, mdl, key_name or "API_KEY"
            last_err = f"empty/short from {mdl} @ {url}"
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} {mdl} @ {url}: {e.read()[:400]!r}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__} {mdl} @ {url}: {e}"
    raise RuntimeError(last_err or "Moonshot call failed")


def main() -> int:
    consult_path = DOCS / f"MOONSHOT_HIGHTECH_VISUAL_CONSULT_{DATE}.md"
    if not consult_path.is_file():
        raise SystemExit(f"Missing consult: {consult_path}")
    consult = consult_path.read_text(encoding="utf-8")

    plan_candidates = [
        Path(r"C:\Users\mreno\.cursor\plans\mission_control_visual_436207ec.plan.md"),
        REPO / ".cursor" / "plans" / "mission_control_visual_436207ec.plan.md",
    ]
    plan_path = next((p for p in plan_candidates if p.is_file()), None)
    if not plan_path:
        raise SystemExit("Plan file not found")
    plan = plan_path.read_text(encoding="utf-8")

    if len(consult) > 14000:
        head = consult[:6000]
        tail_start = consult.find("## 5. Diff vs Jul 8")
        consult_body = head + "\n\n...[CSS body truncated for compare]...\n\n" + (
            consult[tail_start:] if tail_start > 0 else consult[-4000:]
        )
    else:
        consult_body = consult

    user = f"""Compare Moonshot consult (A) vs Cursor implementation plan (B).

# (A) Moonshot High-Tech Visual Consult
{consult_body}

# (B) Cursor Mission Control Visual Plan
{plan}

Respond with the strict OUTPUT FORMAT.
"""
    OUT.mkdir(parents=True, exist_ok=True)
    prompt_path = OUT / f"PLAN_COMPARE_PROMPT_{DATE}.md"
    prompt_path.write_text(user, encoding="utf-8")
    print(f"Prompt saved: {prompt_path} ({len(user)} chars)")

    try:
        content, model, key_name = call_moonshot(SYSTEM, user)
    except Exception as e:  # noqa: BLE001
        err = f"# Moonshot Plan Compare FAILED\n\n{e}\n"
        (DOCS / f"MOONSHOT_PLAN_COMPARE_{DATE}_FAILED.md").write_text(err, encoding="utf-8")
        print(err, file=sys.stderr)
        return 1

    header = (
        f"# Moonshot AI — Plan vs Consult Comparison\n"
        f"**Date:** {DATE}\n"
        f"**Model:** {model} via {key_name}\n"
        f"**Status:** REVIEW ONLY — update Cursor plan; do not apply code yet\n"
        f"**Script:** `scripts/run_moonshot_plan_compare.py`\n\n"
        f"---\n\n"
    )
    report = header + content.strip() + "\n"
    out_docs = DOCS / f"MOONSHOT_PLAN_COMPARE_{DATE}.md"
    out_log = OUT / f"MOONSHOT_PLAN_COMPARE_{DATE}.md"
    out_docs.write_text(report, encoding="utf-8")
    out_log.write_text(report, encoding="utf-8")
    print(f"Wrote {out_docs}")
    print(f"Wrote {out_log}")
    print(f"Chars: {len(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
