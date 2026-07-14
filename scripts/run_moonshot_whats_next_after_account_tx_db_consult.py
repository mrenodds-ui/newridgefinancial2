"""Moonshot AI — What's next after SoftDent account-tx DB (CONSULT ONLY).

Operator pattern: "next" → Moonshot consult; do not apply code.
"""

from __future__ import annotations

import json
import os
import sqlite3
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
(hal-10569 + SoftDent account-tx DB just shipped as 4281a50).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST SHIPPED (4281a50 SoftDent account-tx DB):
- Table sd_account_transactions in softdent_financial_analytics.db
- upsert_account_transactions_jsonl (purge-by-source_file; stable_id)
- ingest Excel→JSONL→DB; query_account_transactions prefers DB
- Live: 1716 rows, Donna 27002 = 5, null amounts preserved

JUST SHIPPED PRIOR:
- TXN ledger surface widgets + /api/apex/softdent/ledger (hal-10569 / 001a927)
- TXN XLS parse + HAL ledger (9cbf8c7)
- Better Backend Widgets MUST/SHOULD (hal-10567/10568)
- DEF-001 Register XLS ingest; July Ins/Patient still often OPS-blocked

OPEN CANDIDATES (pick ONE highest leverage):
1) Better Backend Widgets NICE: pareto-chart, tax-calendar, timeline-lanes
   (coding consult already drafted locally — only if still highest ROI)
2) OPS SoftDent July Register/Collections with Ins Plan Collections > 0
3) Wire Trans-for-Period Excel auto-save (only if real scripts exist)
4) Join/analytics polish on sd_account_transactions (indexes already exist;
   only if a clear HAL/widget gap remains after DB ship)
5) Browser smoke of ledger + Donna DB path after hard-refresh
Prefer highest ROI that unblocks practice truth or closes a clear code gap.
Prefer OPS when the only missing input is a SoftDent export with Ins>0.

Do NOT redo: account-tx DB, TXN XLS ingest, ledger surface, widgets MUST/SHOULD,
DEF-001 honesty, Register XLS parser, Phase 1–5 190Q, invent GUI bots.

REAL PATHS:
- NewRidgeFinancial2/softdent_transaction_extract.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/apex_better_backend_widgets_pack.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/site/apex-core.js
- C:\\SoftDentReportExports
- C:\\SoftDentFinancialExports\\tx_parsed
- C:\\SoftDentFinancialExports\\softdent_financial_analytics.db
- NewRidgeFinancial2/docs/MOONSHOT_ACCOUNT_TX_DB_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_TXN_LEDGER_SURFACE_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_SHOULD_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12.md

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
    live: dict = {}
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402

        live["buildId"] = BUILD_ID
    except Exception as exc:  # noqa: BLE001
        live["buildError"] = type(exc).__name__

    db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
    if db.is_file():
        live["analyticsDb"] = {"path": str(db), "bytes": db.stat().st_size}
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                if conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                    "AND name='sd_account_transactions'"
                ).fetchone()[0]:
                    live["sd_account_transactions"] = {
                        "count": conn.execute(
                            "SELECT COUNT(*) FROM sd_account_transactions"
                        ).fetchone()[0],
                        "donna27002": conn.execute(
                            "SELECT COUNT(*) FROM sd_account_transactions "
                            "WHERE account_num='27002'"
                        ).fetchone()[0],
                        "nullAmounts": conn.execute(
                            "SELECT COUNT(*) FROM sd_account_transactions "
                            "WHERE amount IS NULL"
                        ).fetchone()[0],
                    }
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001
            live["dbError"] = f"{type(exc).__name__}:{exc}"

    jsonl = Path(r"C:\SoftDentFinancialExports\tx_parsed\TXN260201.jsonl")
    if jsonl.is_file():
        live["txnJsonlBytes"] = jsonl.stat().st_size
    return json.dumps(live, indent=2, default=str)[:6000]


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
    for name, lim in (
        ("MOONSHOT_ACCOUNT_TX_DB_APPLIED_2026-07-12.md", 2200),
        ("MOONSHOT_TXN_LEDGER_SURFACE_APPLIED_2026-07-12.md", 1400),
        ("MOONSHOT_BETTER_BACKEND_WIDGETS_SHOULD_APPLIED_2026-07-12.md", 1200),
        ("MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12.md", 1600),
        ("MOONSHOT_WHATS_NEXT_AFTER_TXN_XLS_INGEST_2026-07-12.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Account-tx DB JUST SHIPPED (4281a50). Pick THE next package. CONSULT ONLY.\n\n"
        f"## LIVE SNAPSHOT\n{_live_snapshot()}\n\n"
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 7000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whats Next After Account Tx DB"
    print("Calling Moonshot AI (consult only — will not apply)...")
    import urllib.request

    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(raw)
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        content = str(exc)
        status = "error"
        raw = {"error": content}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (OUT / f"moonshot_whats_next_after_account_tx_db_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — What's Next After SoftDent Account-Tx DB (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {json.loads(_live_snapshot()).get('buildId') or 'hal-10569'}  \n"
        f"**Prior:** Account-tx DB (`4281a50`); TXN ledger surface (hal-10569)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_account_tx_db_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_DB_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_DB_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
