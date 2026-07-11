"""Moonshot AI — What is wrong with the NR2 program (CONSULT ONLY).

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
ask moonshot what us wrong with program
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect + HAL systems engineer
for NewRidge Financial 2.0 (NR2), a local HTTPS Apex starship-bridge app for a Kansas
dental S-corp (SoftDent + QuickBooks imports, local HAL).

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: what is wrong with the program — REPORT ONLY.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE until operator explicitly approves.
3. Use LIVE FACTS + attached context as ground truth. Never invent dollars, claim IDs,
   patients, ERA %, or clinical facts.
4. Diagnose ROOT CAUSES (not just symptoms). Separate: broken / slow / incomplete /
   confusing / already-fixed-today.
5. Rank defects MUST / SHOULD / NICE with evidence from live facts.
6. Prefer additive Apex/HAL fixes over resurrecting retired mockups.
7. Call out what is already working so the operator is not told to redo shipped work.
8. Phased remediation with validation gates. State clearly: code only after approve.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only)
## 1. What's Wrong — Ranked Defects
Table: ID | Rank | Area | What's wrong | Evidence | Likely root cause | Effort
## 2. Already Fixed / Working (do not re-diagnose as open)
## 3. Data / Import Blockers
## 4. HAL / UX Blockers
## 5. Performance / Reliability Blockers
## 6. Recommended Fix Order (phases) + Validation Gate
## 7. Risks & Rollback
DO NOT APPLY until operator says proceed / approve.
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 30),
    ("NewRidgeFinancial2/docs/MOONSHOT_FINANCIAL_PRO_PRESENTATION_CONSULT_2026-07-10.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_PROGRAM_IMPROVE_CONSULT_2026-07-10.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_IMPORT_HEALTH_CPA_TAX_CONSULT_2026-07-10.md", 50),
    ("NewRidgeFinancial2/site/apex-motion-helper.js", 90),
]


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


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

    parts.append(
        """### LIVE FACTS (hal-10441 / bridge — consult time 2026-07-10 evening)
- App: local HTTPS Apex Bridge at https://127.0.0.1:8765/ (TLS required; http:// fails).
- Schema/build: hal-10441. Financial page returns 12 widgets; 1 empty: revenue-composition
  (Collections/Daysheet gap — known).
- Operator pain today:
  1) Pages felt slow — widgets API was 6–8s; SoftDent/QB pipeline rebuilt N times per load.
     Mitigations shipped in-session: single pipeline assemble, daysheet memo, bundle TTL 90s,
     reports/bundle cache 20s, widgets response cache 15s. Warm page switches now ~10–500ms.
  2) HAL + pages “not coming on” — often wrong scheme (http vs https) and/or fetch during restart.
  3) HAL chat “not working” — decodeText scramble left gibberish on long replies; fixed to set
     plain text for chat / long strings (apex-core + apex-motion-helper, cache bust hal-10443).
  4) Auto-start at reboot registered: scheduled task “New Ridge NR2 Program” + Startup shortcut.
- Still open / likely wrong:
  - Collections/Daysheet export gap → revenue composition + collections vitals pending.
  - Cold first widget load still multi-second when caches empty (direct-first pipeline cost).
  - Bottle single-threaded: long HAL evaluate-query (~5s) can block concurrent page loads
    (“Loading bridge instruments…” stuck while Ollama thinks).
  - NewRidgeDashboardServersAutoStart still points at legacy “C:\\New folder\\…” and last
    result failed (-196608) — confusing parallel launcher vs NR2 Start Program.
  - Import honesty: never invent $; empty widgets must stay honest.
- Hard rules: PHI local; consult-only until operator approves coding.
- Operator: what is wrong with the program — REPORT; do not code until approval.
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
        "CONSULT ONLY — diagnose what is wrong. Do not apply code.\n"
        "Do not code until operator approval.\n\n"
        "## Context\n\n"
        + build_context()
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 12000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whats Wrong Consult"

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
        f"# Moonshot AI — What Is Wrong With the Program (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10441 / assets hal-10443  \n"
        f"**Script:** `scripts/run_moonshot_whats_wrong_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_WHATS_WRONG_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_WHATS_WRONG_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
