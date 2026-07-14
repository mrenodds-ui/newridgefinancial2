"""Moonshot AI — Expert SE program review + recommendations (CONSULT ONLY).

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
right now as an expert software enginger ask moonshot ai about this program and recommendations
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — principal engineer + product architect
reviewing NewRidge Financial 2.0 (NR2): a local HTTPS Apex “starship bridge” for a Kansas
dental S-corp. Stack: SoftDent + QuickBooks imports (direct-first), Bottle loopback TLS
server on 127.0.0.1:8765, Apex JS shell, local HAL via Ollama (single GPU-pinned 24B).

You are answering an EXPERT SOFTWARE ENGINEER peer review request. Be blunt, precise,
evidence-based. No fluff. No invented dollars / patients / claim IDs.

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: expert SE review of THIS program + recommendations.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE until operator explicitly approves.
3. Use LIVE FACTS + attached context as ground truth.
4. Separate: architecture strengths, active defects, coupling bugs, data/import blockers,
   HAL/UX honesty, reliability, and next recommendations ranked MUST / SHOULD / NICE.
5. Call out what is already shipped today so we do not re-litigate finished work.
6. Prefer additive Apex/HAL fixes over resurrecting retired mockups / legacy desktop.
7. Especially address the live coupling: GPU 24B is resident + /api/ollama/tags OK, but
   UI shows HAL Standby / empty telemetry because /api/apex/hal/* (and widgets) are under
   FINANCIAL_READ_PREFIXES and GET requires import readiness level "fresh". Missing
   SoftDent AR / QB revenue (etc.) → import_read_forbidden 403 → false “HAL off”.
8. Phased remediation with validation gates. State clearly: code only after approve.

OUTPUT FORMAT (strict markdown):
# Verdict (1–3 sentences, engineer-to-engineer)
## 0. Operator Intent (quote; confirm consult-only)
## 1. Program Snapshot (what NR2 is now at this build)
## 2. Architecture Strengths (keep)
## 3. Ranked Defects & Risks
Table: ID | Rank | Area | Defect | Evidence | Root cause | Effort (S/M/L)
## 4. HAL Offline Illusion — Specific Diagnosis & Fix Options
(A) data/import recovery  (B) gate policy split status vs money reads  (C) UI honesty copy
Pick a recommended path with rationale.
## 5. Recommendations — MUST / SHOULD / NICE
Table: ID | Rank | Recommendation | Why | Effort | Depends on
## 6. Suggested Fix Order (phases) + Validation Gates
## 7. Risks, PHI / honesty, Rollback
DO NOT APPLY until operator says proceed / approve.
"""

CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 40),
    ("NewRidgeFinancial2/site/data/hal-models.json", 80),
    ("NewRidgeFinancial2/nr2_browser_security.py", 120),
    ("NewRidgeFinancial2/docs/MOONSHOT_SOFTDENT_INSURANCE_EXTRACT_APPLIED_2026-07-11.md", 40),
    ("NewRidgeFinancial2/docs/MOONSHOT_SUBPAGES_EXPAND_APPLIED_2026-07-11.md", 40),
    ("NewRidgeFinancial2/docs/MOONSHOT_WHATS_WRONG_CONSULT_2026-07-10.md", 60),
    ("NewRidgeFinancial2/docs/MOONSHOT_PROGRAM_IMPROVE_CONSULT_2026-07-10.md", 60),
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

    # Focused extracts for the gate coupling
    sec = REPO / "NewRidgeFinancial2" / "nr2_browser_security.py"
    http = REPO / "NewRidgeFinancial2" / "nr2_http_server.py"
    if sec.is_file():
        text = sec.read_text(encoding="utf-8", errors="replace")
        for marker, label, n in (
            ("FINANCIAL_READ_PREFIXES", "FINANCIAL_READ_PREFIXES", 30),
            ("FINANCIAL_READ_EXEMPT", "FINANCIAL_READ_EXEMPT", 30),
            ("def financial_read_path", "financial_read_path", 20),
            ("def abort_import_read", "abort_import_read", 25),
        ):
            i = text.find(marker)
            chunk = text[i : i + 2500] if i >= 0 else f"(marker not found: {marker})"
            parts.append(f"### EXTRACT: nr2_browser_security.py — {label}\n```python\n{_truncate(chunk, n)}\n```")
    if http.is_file():
        text = http.read_text(encoding="utf-8", errors="replace")
        i = text.find("financial_read_path(bottle.request.path")
        chunk = text[max(0, i - 400) : i + 500] if i >= 0 else "(gate hook not found)"
        parts.append(
            f"### EXTRACT: nr2_http_server.py — before_request import readiness gate\n```python\n{_truncate(chunk, 35)}\n```"
        )

    parts.append(
        """### LIVE FACTS (operator session 2026-07-11 ~16:57 CT — ground truth)
- App: https://127.0.0.1:8765/ Apex Bridge, schema/build **hal-10498**, mode=financial,
  importMode=direct-first, TLS on loopback.
- HAL model policy: singleGpuLayout enabled; approvedModel=hal-local:24b (Q4_K_M,
  mistral-small3.1:24b), num_ctx=8192, keepAlive=-1, AMD Radeon AI PRO R9700 32GB.
  Lane id chat8b is legacy id mapped to 24B.
- GPU/Ollama: `hal-local:24b` IS resident — size_vram≈15.9GB, keep_alive pinned
  (expires year 2318). `/api/ollama/tags` ok=true, modelCount=12, includes hal-local:24b.
  Warmup ran on Start Program restart.
- UI symptom: sidebar shows **HAL Standby**, “Awaiting telemetry…”, Financial page empty /
  “TELEMETRY SYSTEM INITIALIZING…”. Operator perceived HAL as “off”.
- Root cause of UI “off” (verified): GET `/api/apex/hal/status` → **403 import_read_forbidden**.
  `/api/apex/hal` is under FINANCIAL_READ_PREFIXES; before_request requires import
  readiness level **fresh**. Chat path `/api/hal/evaluate-query` is EXEMPT — so chat may
  still work while status/widgets look dead.
- Import readiness (live at consult time): ok=False, level=degraded,
  completeness≈30% (min 85%), connected≈3/19, missing≈16.
  Blocking includes: softdent.dashboard, softdent.ar, quickbooks.revenue
  (also gaps: quickbooks.payroll, quickbooks.ap observed earlier same session).
  QB inbox has some CSVs (P&L, expenses, AR stub) but not revenue/payroll/AP datasets
  the readiness contract expects; SoftDent AR / dashboard missing.
- Recent shipped (2026-07-11): SoftDent insurance extract applied; subpages expand;
  OM Mon–Thu patients HAL; missing-widgets coding; voice/Availity niceties; many AI-PM
  phase packs earlier same day. Do not recommend redoing those.
- Hard rules: PHI stays local; never invent $; empty widgets stay honest; consult-only
  until operator approves coding.
- Expert SE ask: assess this program as it stands NOW and give ranked recommendations.
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
        "You are being consulted by an expert software engineer. Review THIS program "
        "as it exists at hal-10498 with the live facts below. Give blunt architecture "
        "assessment + ranked recommendations. CONSULT ONLY — do not apply code.\n\n"
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
        "max_tokens": 14000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Expert SE Program Recommendations Consult"

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
        f"# Moonshot AI — Expert SE Program Review & Recommendations (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10498  \n"
        f"**Script:** `scripts/run_moonshot_expert_se_program_recommendations_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_EXPERT_SE_PROGRAM_RECOMMENDATIONS_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_EXPERT_SE_PROGRAM_RECOMMENDATIONS_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
