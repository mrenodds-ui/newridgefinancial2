"""Moonshot AI — What's next after Better Backend Widgets NICE (hal-10570).

Operator pattern: "next" → Moonshot consult; do not apply code.
"""

from __future__ import annotations

import json
import os
import sys
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

OPERATOR_REQUEST_VERBATIM = "next"

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(build **hal-10570**).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.

JUST SHIPPED (hal-10570 Better Backend Widgets NICE — 88fd003):
- A/R aging pareto (ar + financial)
- Tax calendar on taxes MAIN
- Claim status timeline-lanes (claims + documents)
- Completes Better Backend Widgets trail:
  MUST 10567 → SHOULD 10568 → TXN ledger 10569 → NICE 10570

JUST SHIPPED PRIOR:
- SoftDent TXN XLS ingest + HAL ledger (9cbf8c7)
- SoftDent account-transactions SQLite upsert (4281a50) if present in history
- TXN ledger surface widgets (001a927 / hal-10569)
- DEF-001 Register XLS ingest (hal-10566); July Ins/Patient still OPS-blocked

OPEN CANDIDATES (pick ONE as THE next):
1) OPS SoftDent July Register/Collections with Ins Plan Collections > 0
2) Wire SoftDent account-tx SQLite into Apex/HAL (if 4281a50 landed but UI/HAL
   still Excel-JSONL-only — close the gap without inventing dollars)
3) Browser smoke / hard-refresh validation of hal-10567..10570 widgets
4) Trans-for-Period Excel auto-save (only if real scripts exist; no invent)
5) Small HAL phrase polish for ledger + new widget focus_rules
Prefer highest ROI that unblocks practice truth.
Prefer OPS when the only missing input is a SoftDent export with Ins>0.
empty ≠ $0. Never invent SoftDent write-back or dollars.

Do NOT redo: Better Backend Widgets MUST/SHOULD/NICE, TXN XLS ingest,
TXN ledger surface, DEF-001 honesty, Register XLS ingest, Phase 1–5 190Q,
KPI density, invent GUI bots.

REAL PATHS:
- NewRidgeFinancial2/apex_better_backend_widgets_pack.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/softdent_transaction_extract.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/nr2_local_db.py (if SoftDent tx SQLite lives there)
- C:\\SoftDentReportExports
- C:\\SoftDentFinancialExports\\tx_parsed
- NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_NICE_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_TXN_LEDGER_SURFACE_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_SOFTDENT_TXN_XLS_INGEST_APPLIED_2026-07-12.md

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim: next)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 2. Runner-ups (2–3, why not now)
## 3. What NOT to redo
## 4. Acceptance criteria
## 5. Executive Summary (5 bullets)
## 6. Approval checklist
DO NOT APPLY CODE. Prefer one clear next over a laundry list.
If the best next is OPS-only, say so with exact SoftDent export steps.
"""


def _live_snapshot() -> str:
    parts: list[str] = []
    for folder in (
        Path(r"C:\SoftDentReportExports"),
        Path(r"C:\SoftDentFinancialExports\tx_parsed"),
    ):
        if not folder.is_dir():
            parts.append(f"### {folder}\n(missing)")
            continue
        files = sorted(folder.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:15]
        lines = [f"- {p.name} ({p.stat().st_size} bytes)" for p in files if p.is_file()]
        parts.append(f"### {folder}\n" + ("\n".join(lines) if lines else "(empty)"))
    return "\n\n".join(parts)


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")

    excerpts = []
    for rel in (
        "NewRidgeFinancial2/nr2-build.json",
        "NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_NICE_APPLIED_2026-07-12.md",
        "NewRidgeFinancial2/docs/MOONSHOT_TXN_LEDGER_SURFACE_APPLIED_2026-07-12.md",
        "NewRidgeFinancial2/docs/MOONSHOT_SOFTDENT_TXN_XLS_INGEST_APPLIED_2026-07-12.md",
    ):
        path = REPO / rel
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            excerpts.append(f"### FILE: {rel}\n```\n{text[:3000]}\n```")

    # Note recent SoftDent tx SQLite if present
    for needle, rel in (
        ("account_transaction", "NewRidgeFinancial2/nr2_local_db.py"),
        ("account_transaction", "NewRidgeFinancial2/softdent_transaction_extract.py"),
    ):
        path = REPO / rel
        if path.is_file() and needle in path.read_text(encoding="utf-8", errors="replace"):
            excerpts.append(f"### NOTE: `{needle}` referenced in `{rel}`")

    user = (
        "OPERATOR REQUEST (VERBATIM):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Produce THE single best NEXT package after Widgets NICE (hal-10570).\n"
        "CONSULT ONLY.\n\n"
        "## LIVE SNAPSHOT\n\n"
        + _live_snapshot()
        + "\n\n## DOCS\n\n"
        + "\n\n".join(excerpts)
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 8000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whats Next After Widgets NICE"

    print("Calling Moonshot AI (what's next — consult only)...")
    import urllib.error
    import urllib.request

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
        f"# Moonshot AI — What's Next After Widgets NICE (hal-10570)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10570  \n"
        f"**Prior:** Widgets NICE (88fd003); TXN ledger (hal-10569)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_widgets_nice_consult.py`  \n"
        f"**Operator:** next  \n"
        f"**Apply:** DO NOT APPLY until operator validates.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_WIDGETS_NICE_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_WIDGETS_NICE_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
