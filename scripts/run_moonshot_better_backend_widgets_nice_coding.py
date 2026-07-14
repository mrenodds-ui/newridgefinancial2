"""Moonshot AI — CODING for better backend widgets NICE wave.

Operator: continue (typo cpntinue). After MUST/SHOULD/TXN ledger shipped.
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

OPERATOR_REQUEST_VERBATIM = "cpntinue"

SYSTEM = """You are Moonshot AI — Apex instrumentation engineer for NR2 (build **hal-10569**).

Operator CONTINUE after MUST + SHOULD + TXN ledger. Deliver APPLY-READY CODING for
NICE items ONLY from MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT:

1. Aging Pareto Chart (pareto-chart) on ar + financial — A/R aging buckets 80/20
2. Tax Calendar (tax-calendar) on taxes MAIN — quarterly filing deadlines
3. Claim Timeline Lanes (timeline-lanes) on claims + documents — claim status swimlanes

CRITICAL:
- DO NOT redo MUST/SHOULD/TXN ledger.
- DO NOT duplicate denial-pareto (claims) or preauth-aging-lanes already in
  apex_missing_widgets_pack — those are DIFFERENT. NICE needs AGING bucket pareto
  and CLAIM STATUS timeline lanes (or documents workflow lanes).
- tax-calendar already exists on #taxes/calendar subpage — gap is taxes MAIN page.
- LIVE FE contracts:
  - pareto-chart: data.bars[{code,amount,count,pct}], data.cumulative[], data.threshold
  - tax-calendar: items[{label,amount,due,logged}] on spec root
  - timeline-lanes: data.lanes[{code,total,segments[{bucket,count,color}]}]
- Prefer apex_better_backend_widgets_pack.py + thin apex_backend wiring.
- Never invent dollars. empty ≠ $0. BUILD_ID → hal-10570.

OUTPUT:
# Verdict
## 0. Operator Intent
## 1. Gap vs Already-Shipped
## 2. Files to Touch
## 3. Paste-ready Code
## 4. Validation Gate
## 5. Apply Order
## 6. What NOT to redo
"""


def _truncate(text: str, n: int) -> str:
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "\n".join(lines[:n]) + f"\n... [{len(lines)-n} truncated]"


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    if "moonshot" not in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2").strip()
    print(f"Using {key_name} @ {base_url} model={model}")

    parts = []
    for rel, max_lines in (
        ("NewRidgeFinancial2/nr2-build.json", 15),
        ("NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12.md", 55),
        ("NewRidgeFinancial2/docs/MOONSHOT_TXN_LEDGER_SURFACE_APPLIED_2026-07-12.md", 40),
        ("NewRidgeFinancial2/apex_better_backend_widgets_pack.py", 30),
    ):
        path = REPO / rel
        if path.is_file():
            parts.append(f"### {rel}\n```\n{_truncate(path.read_text(encoding='utf-8', errors='replace'), max_lines)}\n```")

    for rel, needles in (
        ("NewRidgeFinancial2/apex_missing_widgets_pack.py", ("def build_denial_pareto", "def build_preauth_lanes")),
        ("NewRidgeFinancial2/apex_subpages_wave5_pack.py", ("def build_tax_calendar",)),
    ):
        t = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        for n in needles:
            i = t.find(n)
            if i >= 0:
                parts.append(f"### {rel}::{n}\n```python\n" + "\n".join(t[i:].splitlines()[:45]) + "\n```")

    core = (REPO / "NewRidgeFinancial2/site/apex-core.js").read_text(encoding="utf-8", errors="replace")
    for label, needle in (
        ("pareto", 'if (this.type === "pareto-chart")'),
        ("tax-cal", 'if (this.type === "tax-calendar")'),
        ("lanes", 'if (this.type === "timeline-lanes")'),
    ):
        i = core.find(needle)
        if i >= 0:
            parts.append(f"### FE {label}\n```javascript\n" + "\n".join(core[i:].splitlines()[:40]) + "\n```")

    user = (
        f"OPERATOR (VERBATIM): {OPERATOR_REQUEST_VERBATIM}\n\n"
        "NICE wave coding only. Apply-ready. Match live FE contracts.\n\n"
        + "\n\n".join(parts)
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
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    print("Calling Moonshot AI (NICE coding)...")
    req = urllib.request.Request(base_url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            body = json.loads(resp.read().decode())
        content = extract_message_content(body)
        status = "ok"
    except urllib.error.HTTPError as exc:
        content = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}"
        status = f"HTTP {exc.code}"
    except Exception as exc:
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — Better Backend Widgets NICE CODING\n\n"
        f"**Date:** {DATE}  \n**Model:** {model}  \n**Key:** {key_name}  \n"
        f"**Status:** {status}  \n**Build base:** hal-10569  \n"
        f"**Script:** `scripts/run_moonshot_better_backend_widgets_nice_coding.py`  \n"
        f"**Operator:** continue  \n\n"
        f"## Operator request\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_BETTER_BACKEND_WIDGETS_NICE_CODING_{DATE}.md"
    doc = DOCS / f"MOONSHOT_BETTER_BACKEND_WIDGETS_NICE_CODING_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
