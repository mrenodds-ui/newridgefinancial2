"""Ask Moonshot AI to review WORKSTATION_HAL_SIDENOTES_PLAN_REPORT vs prior Moonshot guidance."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PLAN_FILE = DOCS / "WORKSTATION_HAL_SIDENOTES_PLAN_REPORT_2026-07-08.md"
PRIOR_FILES = [
    DOCS / "MOONSHOT_WORKSTATION_SIDENOTES_2026-07-08.md",
    DOCS / "MOONSHOT_PHASE5_HUB_PROTOCOL.md",
    DOCS / "MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md",
    DOCS / "MOONSHOT_COMPREHENSIVE_CONSULT_2026-07-08.md",
]

SYSTEM = """You are Moonshot AI (kimi-k2.6 class) — independent reviewer for NewRidge Financial 2.0.
The operator's Cursor agent wrote a detailed Workstation + SideNotes + HAL Hub plan (hal-10095 baseline).
You previously consulted on this stack (Phase 5 hub protocol, QB/SoftDent/SideNotes review, comprehensive consult §8).

CRITIQUE the agent plan honestly: agree where it matches your prior guidance, disagree where wrong,
over-scoped, under-scoped, or mis-prioritized. Compare agent phases H1–H5 and hal-10096–10100 commits
to YOUR prior recommendations.

Do not invent files. Base review on the plan text and prior Moonshot reports provided.
Be specific to this solo dental practice — HAL on 8765 as hub, NR2 Workstation on 8766, SideNotesIM bridge.

Return markdown with EXACTLY these sections:
# Moonshot Verdict on Agent Workstation Plan
## Agreement (what the agent plan got right vs your prior guidance)
## Disagreements or Corrections (where agent plan is wrong, risky, or over-scoped)
## Missing Items (agent plan omitted — add these)
## Priority Reconciliation Table
| Rank | Agent plan item | Moonshot rank | Moonshot note |
## Moonshot Independent Roadmap (next 5 commits — your order, not agent's)
## Side-by-Side Phase Comparison (Agent H1–H5 vs Moonshot preferred order)
## Risk Flags Moonshot Would Escalate
## Final Recommendation (one paragraph for operator)
"""


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... [{len(text) - max_chars} chars truncated] ..."


def _resolve_api_key() -> str:
    for name in ("OPENROUTER_API_KEY", "KIMI_K2_API_KEY", "MOONSHOT_API_KEY"):
        val = str(os.getenv(name) or "").strip()
        if val:
            return val
    return ""


def _resolve_base_url() -> str:
    if os.getenv("OPENROUTER_API_KEY"):
        return "https://openrouter.ai/api/v1/chat/completions"
    explicit = str(os.getenv("MOONSHOT_API_BASE") or "").strip()
    if explicit:
        return explicit
    if os.getenv("MOONSHOT_API_KEY"):
        return "https://api.moonshot.ai/v1/chat/completions"
    return str(os.getenv("KIMI_K2_BASE_URL") or "https://openrouter.ai/api/v1/chat/completions").strip()


def _resolve_model() -> str:
    explicit = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "").strip()
    if explicit:
        return explicit
    base = _resolve_base_url().lower()
    if "openrouter" in base:
        return "moonshotai/kimi-k2"
    if "api.moonshot.ai" in base or "api.moonshot.cn" in base:
        return "kimi-k2.6"
    return "moonshotai/kimi-k2"


def _call_api(system: str, user: str) -> tuple[str, str, str | None]:
    api_key = _resolve_api_key()
    if not api_key:
        return "", "none", "No API key"

    payload = {
        "model": _resolve_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 10000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    referer = str(os.getenv("OPENROUTER_HTTP_REFERER") or "https://github.com/NewRidgeFamilyFinancial").strip()
    title = str(os.getenv("OPENROUTER_X_TITLE") or "NR2 Workstation Plan Comparison").strip()
    if "openrouter" in _resolve_base_url().lower():
        headers["HTTP-Referer"] = referer
        headers["X-Title"] = title

    req = Request(
        _resolve_base_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    model = _resolve_model()
    try:
        with urlopen(req, timeout=600) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return "", model, f"HTTP {exc.code}: {detail[:1500]}"
    except URLError as exc:
        return "", model, f"Network: {exc.reason}"

    choices = body.get("choices") if isinstance(body, dict) else []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    content = str((message or {}).get("content") or "").strip()
    if not content:
        return "", model, f"Empty response: {json.dumps(body)[:1500]}"
    return content, model, None


def build_user_prompt() -> str:
    if not PLAN_FILE.is_file():
        raise FileNotFoundError(PLAN_FILE)
    plan = _truncate(PLAN_FILE.read_text(encoding="utf-8", errors="replace"), 32000)
    prior_parts = []
    for path in PRIOR_FILES:
        if path.is_file():
            prior_parts.append(
                f"### Prior Moonshot report: {path.name}\n{_truncate(path.read_text(encoding='utf-8', errors='replace'), 8000)}"
            )
    prior = "\n\n".join(prior_parts)
    return f"""Review the Cursor agent's Workstation + SideNotes + HAL Hub plan below.
Compare it to YOUR prior Moonshot consultations on SideNotes, hub protocol (Phase 5), and HAL-as-hub.

The operator uses HAL (8765 Start Program) as the main hub. They want NR2 Workstation comparable to SideNotes.

Produce honest agreement/disagreement, reorder priorities if needed, and give YOUR next-5-commits roadmap
for workstation/sidenotes/hub work specifically (may differ from agent hal-10096–10100).

---

## Agent plan to review

{plan}

---

## Your prior Moonshot context (what you said before)

{prior}
"""


def build_comparison_report(moonshot_body: str, model: str, api_note: str | None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# Workstation Plan Comparison — Cursor Agent vs Moonshot AI",
        "",
        f"**Date:** {stamp}  ",
        f"**Build:** hal-10095  ",
        f"**Agent plan:** `WORKSTATION_HAL_SIDENOTES_PLAN_REPORT_2026-07-08.md`  ",
        f"**Moonshot model:** {model}  ",
    ]
    if api_note:
        lines.append(f"**API note:** {api_note}  ")
    lines.extend(["", "---", ""])

    lines.extend([
        "## Executive synthesis",
        "",
        "This report compares the Cursor agent's Workstation + SideNotes + HAL Hub plan (Phases H1–H5, ",
        "builds hal-10096–10100) against Moonshot AI's prior guidance and independent review below.",
        "",
        "### Agent plan headline",
        "",
        "| Phase | Builds | Focus |",
        "|-------|--------|-------|",
        "| H1 | hal-10096 | Hub sign-off + token hardening |",
        "| H2 | hal-10097–98 | Popup + watcher reliability |",
        "| H3 | hal-10099 | History UX + send polish |",
        "| H4 | hal-10100 | Package deploy + desk rollout |",
        "| H5 | — | 14-day operator parity proof |",
        "",
        "### Moonshot prior guidance headline",
        "",
        "| Priority | Moonshot said |",
        "|----------|---------------|",
        "| P0 | Manual 8766→8765 broadcast test; popup on closed messenger |",
        "| P0 | Hub token + origin lock (hal-10094 implemented) |",
        "| P1 | Watcher health; SideNotes bridge reliability |",
        "| P1 | History merge; do NOT show IM text on 8765 |",
        "| P2 | HAL-initiated desk popups; office fallback on 8765 tabs |",
        "",
        "---",
        "",
        "## Moonshot AI independent review",
        "",
        moonshot_body,
        "",
        "---",
        "",
        "## Side-by-side: next 5 commits",
        "",
        "| # | Agent plan | Moonshot plan (see review above) |",
        "|---|------------|----------------------------------|",
        "| 1 | hal-10096 — hub sign-off | *Moonshot independent roadmap* |",
        "| 2 | hal-10097 — watcher health | *Moonshot independent roadmap* |",
        "| 3 | hal-10098 — popup stack | *Moonshot independent roadmap* |",
        "| 4 | hal-10099 — history UX | *Moonshot independent roadmap* |",
        "| 5 | hal-10100 — package deploy | *Moonshot independent roadmap* |",
        "",
        "---",
        "",
        "## Reconciliation guidance for operator",
        "",
        "1. **If Moonshot agrees H1 first** — run manual broadcast test before any code; record PASS.",
        "2. **If Moonshot elevates popup before history** — swap H2 ahead of H3 (agent already does).",
        "3. **If Moonshot deprioritizes full desk rollout** — pilot 3 desks before hal-10100 all-stations.",
        "4. **If Moonshot flags Ask HAL LAN routing** — add hub URL validation to Setup-Workstation.ps1.",
        "5. **Do not show SideNotes bodies on 8765** — both agent and Moonshot agree; non-negotiable.",
        "",
        "Full agent plan: `NewRidgeFinancial2/docs/WORKSTATION_HAL_SIDENOTES_PLAN_REPORT_2026-07-08.md`",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    moonshot_out = OUT_DIR / f"MOONSHOT_WORKSTATION_PLAN_REVIEW_{stamp}.md"
    compare_out = DOCS / f"MOONSHOT_WORKSTATION_PLAN_COMPARISON_{stamp}.md"
    compare_log = OUT_DIR / f"MOONSHOT_WORKSTATION_PLAN_COMPARISON_{stamp}.md"

    user = build_user_prompt()
    content, model, err = _call_api(SYSTEM, user)

    api_note = err
    if not content:
        content = ""
        model = model or "none"

    header = (
        f"# Moonshot AI Review of Agent Workstation Plan\n\n"
        f"**Date:** {stamp}  \n**Model:** {model}  \n"
        f"**Reviewed:** `WORKSTATION_HAL_SIDENOTES_PLAN_REPORT_2026-07-08.md`\n\n---\n\n"
    )

    if content:
        moonshot_full = header + content
    else:
        moonshot_full = header + f"*Live API failed: {err}*\n\nSee comparison report for synthesized reconciliation."

    moonshot_out.write_text(moonshot_full, encoding="utf-8")

    comparison = build_comparison_report(content or f"*API failed: {err}*", model, api_note)
    compare_out.write_text(comparison, encoding="utf-8")
    compare_log.write_text(comparison, encoding="utf-8")

    print(moonshot_out)
    print(compare_out)
    return 0 if content and not err else 1


if __name__ == "__main__":
    raise SystemExit(main())
