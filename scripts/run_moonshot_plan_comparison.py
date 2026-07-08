"""Ask Moonshot AI to review MOONSHOT_DETAIL_PLAN_REPORT and compare priorities."""

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

PLAN_FILE = DOCS / "MOONSHOT_DETAIL_PLAN_REPORT_2026-07-08.md"
PRIOR_FILES = [
    DOCS / "MOONSHOT_SOFTDENT_EXTRACT_REPORT_2026-07-08.md",
    DOCS / "MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md",
    DOCS / "MOONSHOT_FULLEST_EXTENT_COMPLETE_2026-07-09.md",
]

SYSTEM = """You are Moonshot AI (kimi-k2.6 class) — independent reviewer for NewRidge Financial 2.0.
The operator's Cursor agent wrote a detailed post-hal-10085 plan. You must CRITIQUE it honestly:
agree where sound, disagree where wrong or missing, reorder priorities if needed.

Do not invent files. Base review on the plan text and prior Moonshot reports provided.
Be specific to this solo dental practice codebase.

Return markdown with EXACTLY these sections:
# Moonshot Verdict on Agent Plan
## Agreement (what the agent plan got right)
## Disagreements or Corrections (where agent plan is wrong, risky, or over-scoped)
## Missing Items (agent plan omitted — add these)
## Priority Reconciliation Table
| Rank | Agent plan item | Moonshot rank | Moonshot note |
## Moonshot Independent Roadmap (next 5 commits — your order, not agent's)
## Risk Flags Moonshot Would Escalate
## Final Recommendation (one paragraph for operator)
"""


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... [{len(text) - max_chars} chars truncated] ..."


def _resolve_api_key() -> str:
    # Prefer OpenRouter when set — MOONSHOT direct key has returned 401 in this environment.
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
        "max_tokens": 8000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    referer = str(os.getenv("OPENROUTER_HTTP_REFERER") or "https://github.com/NewRidgeFamilyFinancial").strip()
    title = str(os.getenv("OPENROUTER_X_TITLE") or "NR2 Plan Comparison").strip()
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
    plan = _truncate(PLAN_FILE.read_text(encoding="utf-8", errors="replace"), 28000)
    prior_parts = []
    for path in PRIOR_FILES:
        if path.is_file():
            prior_parts.append(
                f"### Prior Moonshot report: {path.name}\n{_truncate(path.read_text(encoding='utf-8', errors='replace'), 6000)}"
            )
    prior = "\n\n".join(prior_parts)
    return f"""Review the Cursor agent's detailed plan below. Compare it to your prior Moonshot reports
and your independent judgment for NR2 at hal-10085.

Produce honest agreement/disagreement, reorder priorities if needed, and give YOUR next-5-commits roadmap.

---

## Agent plan to review

{plan}

---

## Prior Moonshot context

{prior}
"""


def build_comparison_report(moonshot_body: str, model: str, api_note: str | None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# Plan Comparison Report — Cursor Agent vs Moonshot AI",
        "",
        f"**Date:** {stamp}  ",
        f"**Build:** hal-10085  ",
        f"**Agent plan:** `MOONSHOT_DETAIL_PLAN_REPORT_2026-07-08.md`  ",
        f"**Moonshot model:** {model}  ",
    ]
    if api_note:
        lines.append(f"**API note:** {api_note}  ")
    lines.extend(["", "---", ""])

    # Executive synthesis (template filled after moonshot response)
    lines.extend([
        "## Executive synthesis",
        "",
        "This report juxtaposes the Cursor agent's 10-commit phased plan (Phases A–G, hal-10086–10095) ",
        "with Moonshot AI's independent review below.",
        "",
        "### Agent plan headline",
        "",
        "| Phase | Commits | Focus |",
        "|-------|---------|-------|",
        "| A | hal-10086 | Repo hygiene, shortcuts, push origin |",
        "| B | hal-10087 | SoftDent payment/adjustment fix (P0) |",
        "| C | hal-10088–89 | Procedures + operatory exports |",
        "| D | hal-10090–92 | HAL claims narrative workflow |",
        "| E | hal-10093 | QB depth + deposit variance |",
        "| F/G | hal-10094–95 | Hub sign-off + optional ODBC |",
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
    ])

    # Parse moonshot roadmap section if present for table — otherwise note manual read
    lines.extend([
        "| # | Agent plan (hal build) | Moonshot plan (see section above) |",
        "|---|------------------------|-----------------------------------|",
        "| 1 | hal-10086 — hygiene, push | *Moonshot independent roadmap* |",
        "| 2 | hal-10087 — payments fix | *Moonshot independent roadmap* |",
        "| 3 | hal-10088 — procedures export | *Moonshot independent roadmap* |",
        "| 4 | hal-10089 — operatory | *Moonshot independent roadmap* |",
        "| 5 | hal-10090 — narrative review port | *Moonshot independent roadmap* |",
        "",
        "---",
        "",
        "## Reconciliation guidance for operator",
        "",
        "1. **If Moonshot agrees on payment fix first** — proceed Phase B before narrative UI.",
        "2. **If Moonshot elevates hub/security or QB empty states** — merge into Phase A/E.",
        "3. **If Moonshot deprioritizes ODBC** — defer Phase F until bridge lane proves insufficient.",
        "4. **If Moonshot flags narrative hallucination risk** — enforce review.js before any HAL draft ships.",
        "",
        "Full agent plan: `NewRidgeFinancial2/docs/MOONSHOT_DETAIL_PLAN_REPORT_2026-07-08.md`",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    moonshot_out = OUT_DIR / f"MOONSHOT_PLAN_REVIEW_{stamp}.md"
    compare_out = DOCS / f"MOONSHOT_PLAN_COMPARISON_{stamp}.md"
    compare_log = OUT_DIR / f"MOONSHOT_PLAN_COMPARISON_{stamp}.md"

    user = build_user_prompt()
    content, model, err = _call_api(SYSTEM, user)

    api_note = err
    if not content:
        content = "\n".join([
            "# Moonshot Verdict on Agent Plan",
            "- Live API call failed; no independent Moonshot review produced.",
            "## Agreement",
            "- N/A",
            "## Disagreements or Corrections",
            f"- API error: {err}",
            "## Missing Items",
            "- Rerun after fixing OPENROUTER_API_KEY or MOONSHOT_API_KEY",
            "## Priority Reconciliation Table",
            "| Rank | Agent plan item | Moonshot rank | Moonshot note |",
            "| 1 | payments fix | unknown | API failed |",
            "## Moonshot Independent Roadmap",
            "- unavailable",
            "## Risk Flags Moonshot Would Escalate",
            "- unavailable",
            "## Final Recommendation",
            "- Fix API keys and rerun scripts/run_moonshot_plan_comparison.py",
        ])
        model = model or "none"

    header = (
        f"# Moonshot AI Review of Agent Detail Plan\n\n"
        f"**Date:** {stamp}  \n**Model:** {model}  \n"
        f"**Reviewed:** `MOONSHOT_DETAIL_PLAN_REPORT_2026-07-08.md`\n\n---\n\n"
    )
    moonshot_full = header + content
    moonshot_out.write_text(moonshot_full, encoding="utf-8")

    comparison = build_comparison_report(content, model, api_note)
    compare_out.write_text(comparison, encoding="utf-8")
    compare_log.write_text(comparison, encoding="utf-8")

    print(moonshot_out)
    print(compare_out)
    return 0 if content and not err else 1


if __name__ == "__main__":
    raise SystemExit(main())
