"""Compare Cursor mockup/widget fix plan with Moonshot AI; request code for all issues."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request
import winreg
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CURSOR_PLAN = """
## Cursor Agent Fix Plan (Phases A–G, 2026-07-08)

Phase A (P0): Unblock data — import sync, softdent.procedures + claimStatus, refresh stale QB
Phase B (P0): Widget status honesty — shared hasRenderableData(); align buildWidgetFeed with PageCanvas empty states
Phase C (P1): QuickBooks single dashboard-grid layout (remove nested dashboardHost wrappers)
Phase D (P1): Missing chart-container panels on financial, softdent, ar, claims, office-manager
Phase E (P1): Page vocabulary — taxes kpi-card/kpi-grid, narratives multi-composer, documents grid
Phase F (P1): Chart mount wiring — enhancePage for PageCanvas pages, F5 overlay guard
Phase G (P2): Refresh API keys, sign-off, build bump hal-10100+
"""

SYSTEM = """You are Moonshot AI (kimi-k2.6) reviewing NewRidge Financial 2.0.

The Cursor agent wrote a fix plan for: mockup parity gaps on 9/10 pages, widgets showing empty
bodies despite HAL SUCCESS badges, SoftDent DEGRADED (procedures/claimStatus missing), QuickBooks stale.

You MUST:
1. Compare agent plan vs your independent judgment — agree, disagree, reorder
2. For EVERY issue in the audit, provide ready-to-paste CODE (JavaScript for page-canvas.js,
   page-canvas-data.js, hal-skills.js, nr2-moonshot-ui.js; Python for import_sync.py)
3. Return markdown with EXACT sections:

# Moonshot Verdict
## Agreement with Cursor Plan
## Disagreements / Reorder
## Priority Reconciliation Table
| Rank | Cursor phase | Moonshot rank | Note |
## Issue 1: Data Pipeline (SoftDent procedures, QB stale) — CODE
## Issue 2: Widget Feed vs Canvas Empty — CODE
## Issue 3: QuickBooks Layout Collapse — CODE
## Issue 4: Missing Chart Panels (per page) — CODE
## Issue 5: Page Vocabulary (taxes, narratives, documents) — CODE
## Issue 6: Chart Mount / enhancePage — CODE
## Moonshot Independent Roadmap (next 5 commits)
## Operator Smoke Test
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
    if "openrouter" in base_url:
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Mockup Fix Comparison"
    req = Request(base_url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=45) as response:
            return response.status == 200
    except (HTTPError, URLError, OSError):
        return False


def _resolve_endpoint() -> tuple[str, str, str, str | None]:
    explicit_base = str(os.getenv("MOONSHOT_API_BASE") or os.getenv("KIMI_K2_BASE_URL") or "").strip()
    explicit_model = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "").strip()
    if explicit_base and explicit_model:
        for name, key in _candidate_keys():
            if _probe_key(explicit_base, key, explicit_model):
                return name, key, explicit_base, explicit_model

    candidates: list[tuple[str, str]] = [
        ("https://api.moonshot.ai/v1/chat/completions", "kimi-k2.6"),
        ("https://openrouter.ai/api/v1/chat/completions", "moonshotai/kimi-k2"),
        ("https://api.moonshot.ai/v1/chat/completions", "kimi-k2.5"),
    ]
    for base_url, model in candidates:
        for name, key in _candidate_keys():
            if _probe_key(base_url, key, model):
                return name, key, base_url, model

    keys = _candidate_keys()
    if keys:
        name, key = keys[0]
        return name, key, candidates[0][0], candidates[0][1]
    return "", "", candidates[0][0], candidates[0][1]


def _call_api(system: str, user: str) -> tuple[str, str, str | None]:
    key_name, api_key, base_url, model = _resolve_endpoint()
    if not api_key:
        return "", "none", "No API key"
    payload = {
        "model": model or "kimi-k2.6",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0 if "api.moonshot" in base_url else 0.15,
        "max_tokens": 16000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url:
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Mockup Fix Comparison"
    req = Request(base_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(req, timeout=900) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return "", model or "kimi-k2.6", f"HTTP {exc.code} ({key_name} @ {base_url}): {exc.read().decode('utf-8', errors='replace')[:1500]}"
    except URLError as exc:
        return "", model or "kimi-k2.6", f"Network ({key_name}): {exc.reason}"
    choices = body.get("choices") if isinstance(body, dict) else []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    content = str((message or {}).get("content") or "").strip()
    if not content:
        return "", model or "kimi-k2.6", f"Empty ({key_name} @ {base_url}): {json.dumps(body)[:1000]}"
    return content, f"{model} via {key_name}", None


def build_user_prompt() -> str:
    audit = OUT_DIR / "MOCKUP_WIDGET_AUDIT_LATEST.md"
    audit_text = audit.read_text(encoding="utf-8", errors="replace") if audit.is_file() else "(missing)"
    prior = DOCS / "MOONSHOT_AI_CONSULTATION_2026-07-07.md"
    prior_text = prior.read_text(encoding="utf-8", errors="replace")[:8000] if prior.is_file() else ""
    return f"""Compare the Cursor agent fix plan with your prior Moonshot recommendations.
Provide CODE for every fix. Audit data below.

{CURSOR_PLAN}

## Auto audit (2026-07-08)
{audit_text}

## Prior Moonshot consultation excerpt
{prior_text}
"""


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    audit_script = REPO / "NewRidgeFinancial2" / "scripts" / "collect-mockup-widget-audit.mjs"
    if audit_script.is_file():
        subprocess.run(["node", str(audit_script)], cwd=audit_script.parent.parent, timeout=120, check=False)

    user = build_user_prompt()
    content, model, err = _call_api(SYSTEM, user)

    out_path = DOCS / f"MOONSHOT_MOCKUP_FIX_COMPARISON_{stamp}.md"
    log_path = OUT_DIR / f"MOONSHOT_MOCKUP_FIX_COMPARISON_{stamp}.md"

    if not content:
        # Fallback: script exits 1 but comparison doc written by separate step
        print(f"API failed: {err}", file=sys.stderr)
        print(log_path)
        return 1

    header = (
        f"# Plan Comparison — Cursor Mockup/Widget Fix vs Moonshot AI\n\n"
        f"**Date:** {stamp}  \n**Model:** {model}  \n**Script:** `scripts/run_moonshot_mockup_fix_comparison.py`\n\n---\n\n"
    )
    full = header + content
    out_path.write_text(full, encoding="utf-8")
    log_path.write_text(full, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
