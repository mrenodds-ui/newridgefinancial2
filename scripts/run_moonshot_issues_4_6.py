"""Moonshot AI — continuation for Issues 4-6 + roadmap (part 2 of mockup fix consult)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import winreg
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM = """You are Moonshot AI (kimi-k2.6) continuing a NewRidge Financial 2.0 consultation.

Part 1 already delivered Issues 1-3 (data pipeline, widget empty bodies, QuickBooks layout).
Your response was TRUNCATED at Issue 4.

Provide ONLY the remaining sections with COMPLETE ready-to-paste CODE blocks.
Use the REAL NR2 file names: page-canvas.js, page-canvas-data.js, nr2-moonshot-ui.js,
nr2-mockup-page-vocabulary.css, hal-skills.js, app.js, page-views.js.

Return markdown with EXACTLY these sections (no repetition of Issues 1-3):

## Issue 4: Missing Chart Panels (per page) — CODE
Cover: financial, softdent, ar, claims, office-manager, documents.
For each page: DOM structure with chart-container panels matching mockup counts from audit.

## Issue 5: Page Vocabulary (taxes, narratives, documents) — CODE
kpi-card/kpi-grid for taxes; multi-panel composer-grid for narratives; widget-grid for documents.

## Issue 6: Chart Mount / enhancePage — CODE
Fix NR2MoonshotUI.enhancePage skip for PageCanvas pages; replace-not-stack overlay policy;
wire app.js after page render; F5 reload guard.

## Moonshot Independent Roadmap (next 5 commits)
Table with commit focus, files, acceptance criteria.

## Operator Smoke Test
Numbered checklist the operator can run in browser + CLI validators.

Be specific to hal-10099 moonshot-mockup epoch. Provide full code blocks, not pseudocode.
"""


def _load_user_env(name: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value or "").strip()
    except OSError:
        return ""


def _candidate_keys() -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for name in ("OPENROUTER_API_KEY", "MOONSHOT_API_KEY", "KIMI_K2_API_KEY"):
        for val in (str(os.getenv(name) or "").strip(), _load_user_env(name)):
            if val and val not in seen:
                seen.add(val)
                out.append((name, val))
    return out


def _probe_key(base_url: str, api_key: str, model: str) -> bool:
    payload = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "OK"}], "max_tokens": 5}
    ).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    req = Request(base_url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=45) as response:
            return response.status == 200
    except (HTTPError, URLError, OSError):
        return False


def _resolve_endpoint() -> tuple[str, str, str, str]:
    candidates = [
        ("https://api.moonshot.ai/v1/chat/completions", "kimi-k2.6"),
        ("https://api.moonshot.ai/v1/chat/completions", "kimi-k2.5"),
    ]
    for base_url, model in candidates:
        for name, key in _candidate_keys():
            if _probe_key(base_url, key, model):
                return name, key, base_url, model
    keys = _candidate_keys()
    if keys:
        return keys[0][0], keys[0][1], candidates[0][0], candidates[0][1]
    return "", "", candidates[0][0], candidates[0][1]


def _call_api(system: str, user: str) -> tuple[str, str, str | None]:
    key_name, api_key, base_url, model = _resolve_endpoint()
    if not api_key:
        return "", "none", "No API key"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0 if "api.moonshot" in base_url else 0.15,
        "max_tokens": 16000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    req = Request(base_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(req, timeout=900) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return "", model, f"HTTP {exc.code} ({key_name}): {exc.read().decode('utf-8', errors='replace')[:1500]}"
    except URLError as exc:
        return "", model, f"Network ({key_name}): {exc.reason}"
    choices = body.get("choices") if isinstance(body, dict) else []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    content = str((message or {}).get("content") or "").strip()
    if not content:
        return "", model, f"Empty ({key_name}): {json.dumps(body)[:1000]}"
    return content, f"{model} via {key_name}", None


def build_user_prompt() -> str:
    audit = OUT_DIR / "MOCKUP_WIDGET_AUDIT_LATEST.md"
    audit_text = audit.read_text(encoding="utf-8", errors="replace") if audit.is_file() else ""
    part1 = DOCS / "MOONSHOT_MOCKUP_FIX_COMPARISON_2026-07-08.md"
    part1_text = part1.read_text(encoding="utf-8", errors="replace") if part1.is_file() else ""
    return f"""Continue the consultation. Part 1 (Issues 1-3 + verdict) is below.
Complete Issues 4-6, roadmap, and smoke test with full code.

## Part 1 already delivered (do NOT repeat)
{part1_text[:12000]}

## Current audit
{audit_text}

## Audit gaps to fix in Issue 4
- financial: chart-container mock=4 live=1, 6 empty markers
- softdent: chart-container missing (mock=4), 7 empty
- ar: kpi-grid mock=3 live=1, chart-container mock=3 live=1
- claims: chart-container missing, claim-card mock=23 live=6 (real data OK)
- office-manager: dashboard-grid + chart-container missing
- documents: widget-grid mock=3 live=1
- taxes (Issue 5): kpi-card, kpi-grid missing
- narratives (Issue 5): composer-grid mock=4 live=1
"""


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    audit_script = REPO / "NewRidgeFinancial2" / "scripts" / "collect-mockup-widget-audit.mjs"
    if audit_script.is_file():
        subprocess.run(["node", str(audit_script)], cwd=audit_script.parent.parent, timeout=120, check=False)

    content, model, err = _call_api(SYSTEM, build_user_prompt())
    out_path = OUT_DIR / f"MOONSHOT_MOCKUP_FIX_PART2_{stamp}.md"
    doc_path = DOCS / f"MOONSHOT_MOCKUP_FIX_PART2_{stamp}.md"

    if not content:
        print(f"API failed: {err}", file=sys.stderr)
        return 1

    header = (
        f"# Moonshot AI — Issues 4-6 Continuation\n\n"
        f"**Date:** {stamp}  \n**Model:** {model}  \n"
        f"**Script:** `scripts/run_moonshot_issues_4_6.py`\n\n---\n\n"
    )
    full = header + content
    out_path.write_text(full, encoding="utf-8")
    doc_path.write_text(full, encoding="utf-8")
    print(out_path)
    print(doc_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
