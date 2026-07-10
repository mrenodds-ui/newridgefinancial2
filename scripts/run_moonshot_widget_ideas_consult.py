"""Moonshot AI — Personal/fintech widget ideas vs NR2-Apex schema (CONSULT ONLY).

Operator request is passed VERBATIM where possible. Do not rewrite operator intent.
Does NOT apply any code.
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
ask moonshot ai about these widget ideas - Personal Finance & Mobile Home Screen WidgetsThese smartphone widgets leverage deep AI connections to link directly to your bank accounts and forecast cash flow.Origin: Best for full-context financial reasoning across spending, taxes, and retirement tracking. Its interactive UI functions like a true financial command center. Check out the platform directly at Origin.Copilot Money: Features advanced lock screen spending summaries and automated transactional categorization. Built seamlessly with local AI processing on Apple devices. Find download options on Copilot Money.Monarch Money: Provides real-time budget progress metrics directly on your home screen. It utilizes predictive algorithms to alert you of upcoming bills before they happen. Learn more at Monarch Money.PocketGuard: Employs an automated “In My Pocket” algorithmic summary. It instantly factors in recurring bills to show disposable daily cash. Get started with PocketGuard.2. Embeddable Web & Fintech WidgetsIf you are looking to install high-tech widgets onto a website, blog, or application dashboard, these tools deploy with single-line JavaScript code.TradingView Widgets: High-velocity interactive charting tools that allow web visitors to map technical indicators instantly. Explore configurations via TradingView Widgets.Investing.com Tools: Offers an auto-refresh economic calendar widget that updates within one second of global events. Grab the raw embed code at Investing.com Webmaster Tools.theFinancials Custom Widgets: High-frequency streaming data modules covering Treasuries, Swaps, SOFR, and indices. They update up to every 7 minutes. Review documentation at theFinancials.Chimney Widgets: Highly interactive, responsive lead-generation calculators built to run natively inside bank-grade apps. View deployment templates at Chimney.io.How to Choose Your SetupFeature FocusSuggested TechnologyDeployment TypePersonal Wealth AutopilotOrigin / Copilot MoneyiOS / Android App WidgetLive Multi-Asset StreamingTradingView / theFinancialsHTML / JS SnippetInstant Real-Time CalendarsInvesting.comWeb Component and can he use any of these in the current schema with a pages to boost visual information.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect for NewRidge Financial 2.0 (NR2),
a solo dental practice financial cockpit on Windows (SoftDent + QuickBooks imports, local HAL/Ollama).

CRITICAL:
1. Answer the operator's question: can ANY of these widget products/ideas be used in the CURRENT NR2-Apex schema/pages to boost visual information?
2. Do not rewrite what the operator wants — treat their list as the source of truth for products to evaluate.
3. CONSULT ONLY — DO NOT APPLY. No code changes to the live app.
4. Be honest about fit: NR2 is a PRACTICE financial bridge (production, collections, A/R, claims, taxes, narratives), NOT a consumer bank-linking wealth app and NOT a public multi-asset trading terminal — unless a specific embed clearly helps practice ops without inventing dollars or leaking PHI.
5. Hard rules for NR2: never invent financial dollar amounts; prefer SoftDent/QB/import-backed data; HTTPS localhost Apex bridge (hal-10240) with fixed mosaic instruments, sidebar, ticker, interactive narratives.
6. For each named product (Origin, Copilot Money, Monarch Money, PocketGuard, TradingView, Investing.com, theFinancials, Chimney), give: Fit (YES / PARTIAL / NO), why, risk (privacy, CSP, PHI, licensing, offline), and if PARTIAL/YES what NR2 page + instrument pattern could borrow the IDEA (not necessarily embed the vendor).
7. Prefer "borrow UX patterns into Apex instruments" over "drop third-party JS embeds" when embeds conflict with CSP, offline, or practice data rules.
8. Provide a short recommended page map: which current Apex pages could gain which visual boosts (inspired by which product).
9. If useful, sketch 3–5 NEW Apex instrument types (names + payload shape) that capture the best ideas WITHOUT requiring bank OAuth or market-data subscriptions.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only)
## 1. Product-by-Product Fit Matrix
## 2. What Can Be Used In Current Schema (concrete)
## 3. What Must NOT Be Embedded (and why)
## 4. Recommended Visual Boosts Per Apex Page
## 5. New Instrument Ideas (Apex-native, import-backed)
## 6. Implementation Phases (optional; DO NOT APPLY until operator validates)
## 7. Risks & Alternatives
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("NewRidgeFinancial2/site/index.html", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_APEX_P6_SIGNOFF_2026-07-10.md", 80),
    ("NewRidgeFinancial2/docs/_consult_scratch/apex_current_snapshot.json", 120),
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
        """### LIVE NR2 FACTS
- Build: hal-10240 NR2-Apex starship bridge
- Pages: financial, taxes, softdent, quickbooks, ar, claims, narratives, documents, library, office-manager, hal
- Layout: left sidebar + top ticker + fixed mosaic instruments (not stretchy cards)
- Data: SoftDent/QB imports via apex_backend.py — honest empty KPIs; no invented dollars
- Stack: Bottle HTTPS 8765, vanilla JS, local HAL; CSP/browser security on mutations
- Not a consumer Plaid/bank-link app; not a public trading site
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
        "Evaluate these widget products/ideas against CURRENT NR2-Apex schema/pages.\n"
        "CONSULT ONLY — do not apply.\n\n"
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
        "max_tokens": 12000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Widget Ideas Consult"

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
        f"# Moonshot AI — Widget Ideas vs NR2-Apex Schema (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10240  \n"
        f"**Script:** `scripts/run_moonshot_widget_ideas_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator validates.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_WIDGET_IDEAS_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_WIDGET_IDEAS_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
