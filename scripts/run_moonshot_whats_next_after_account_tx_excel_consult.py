"""Moonshot AI — What's next after SoftDent account-tx Excel + HAL teach (CONSULT ONLY).

Operator pattern: "next" / "next program" → Moonshot consult; do not apply code.
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

OPERATOR_REQUEST_VERBATIM = "next program"

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(hal-10567 + SoftDent desktop Excel doctrine + Phase 5 190Q GO +
hal-local:32b / qwen3:32b Q4_K_M on R9700).

Operator said "next program" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.

JUST SHIPPED (SoftDent account transactions Excel — c4d2331 / a008f1c):
- Validated Carestream path: Reports → Accounting → Trans for a Period →
  Output Options → Excel → Format 1 (List Each Transaction Separately)
- SoftDent often opens Excel on temp %LOCALAPPDATA%\\Temp\\SDWIN*.csv
  (window SDWIN3 - Excel); SaveCopyAs into C:\\SoftDentReportExports
- Live file: C:\\SoftDentReportExports\\TXN260201.xls (~286KB, 1736 rows)
  Donna Nickel (27002) present (Feb 2026 lines validated)
- HAL taught: format_softdent_account_tx_excel_hal_reply + local policy +
  compile_softdent_signon_guidance; docs/SOFTDENT_ACCOUNT_TX_EXCEL_WEB_VALIDATE_*
- softdent_gui_export: Toolhelp PID lookup + Cursor-focus retry
- Sign On: COMPUTE/computer; never Printer; never Esc on SoftDent main

JUST SHIPPED PRIOR (hal-10567 Better Backend Widgets MUST):
- Tax planning data-table, collections radial-gauge, system health status-matrix

JUST SHIPPED PRIOR:
- SoftDent safe GUI export / daily master GUI pull / July Register automation
- DEF-001 Register XLS ingest (hal-10566), period sync, Phase 5 GO

LIVE FACTS (from LIVE SNAPSHOT when present):
- TXN260201.xls exists; account-tx Excel path proven
- July Register/Collections Ins/Patient split may still be incomplete for DEF-001
- Prefer OPS SoftDent Excel when dollars missing; empty ≠ $0; no SoftDent write-back

OPEN CANDIDATES (pick ONE highest leverage):
- Wire Trans-for-Period Excel auto-save (temp SDWIN*.csv → inbox) into
  softdent_gui_export.export_transactions_for_period so catalog exports don't
  hang waiting for Select File Name
- Ingest/parse TXN*.xls into SoftDent analytics / HAL patient-ledger tools
  (Donna-style account tx query) without inventing dollars
- OPS July Register/Collections with Ins Plan > 0 if gap still open
- Better Backend Widgets SHOULD follow-ups if MUST left gaps
- Browser smoke density/cache after hard-refresh only if lower ROI than above

Do NOT redo: account-tx Excel validation docs already shipped, HAL teach already
shipped, invent SoftDent write-back, invent dollars, Phase 1–5 190Q, KPI density,
cache coherence, DEF-001 honesty gates, Register XLS parser fiction.

REAL PATHS:
- NewRidgeFinancial2/softdent_gui_export.py
- NewRidgeFinancial2/softdent_signon.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/softdent_transaction_extract.py
- NewRidgeFinancial2/softdent_master_reports.json
- NewRidgeFinancial2/docs/SOFTDENT_ACCOUNT_TX_EXCEL_WEB_VALIDATE_2026-07-12.md
- scripts/continue_softdent_txn_excel.py, scripts/validate_softdent_account_tx_excel.py
- C:\\SoftDentReportExports\\TXN260201.xls
- NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_APPLIED_2026-07-12.md

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim: next program)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 2. Runner-ups (2–3, why not now)
## 3. What NOT to redo
## 4. Acceptance criteria
## 5. Executive Summary (5 bullets)
## 6. Approval checklist
DO NOT APPLY CODE. Prefer one clear next over a laundry list.
"""


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    if "moonshot" not in (base_url or "").lower():
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")

    excerpts = []
    for name, lim in (
        ("SOFTDENT_ACCOUNT_TX_EXCEL_WEB_VALIDATE_2026-07-12.md", 2800),
        ("MOONSHOT_BETTER_BACKEND_WIDGETS_APPLIED_2026-07-12.md", 1600),
        ("MOONSHOT_SOFTDENT_SAFE_GUI_EXPORT_APPLIED_2026-07-12.md", 1400),
        ("MOONSHOT_WHATS_NEXT_AFTER_REGISTER_XLS_10566_2026-07-12.md", 1400),
        ("MOONSHOT_DEF001_REGISTER_XLS_INGEST_APPLIED_2026-07-12.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live: dict = {"buildId": None, "txnExport": None, "gap": None}
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402
        from apex_softdent_hardening_pack import assess_collections_gap  # noqa: E402
        from apex_backend import _load_reports_and_bundle  # noqa: E402

        live["buildId"] = BUILD_ID
        _reports, bundle, _err = _load_reports_and_bundle()
        live["gap"] = assess_collections_gap(bundle)
    except Exception as exc:  # noqa: BLE001
        live["gapError"] = f"{type(exc).__name__}:{exc}"

    txn = Path(r"C:\SoftDentReportExports\TXN260201.xls")
    if txn.is_file():
        live["txnExport"] = {
            "path": str(txn),
            "bytes": txn.stat().st_size,
            "mtime": datetime.fromtimestamp(txn.stat().st_mtime, timezone.utc).isoformat(),
        }
    val = Path(r"C:\SoftDentFinancialExports\softdent_account_tx_excel_validation.json")
    if val.is_file():
        try:
            live["validation"] = json.loads(val.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            live["validationError"] = type(exc).__name__

    user = (
        f"Operator request (verbatim): {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE SNAPSHOT:\n{json.dumps(live, indent=2, default=str)[:6000]}\n\n"
        + "\n\n".join(excerpts)
    )

    import urllib.request

    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 7000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whats Next After Account Tx Excel"
    print("Calling Moonshot AI (consult only — will not apply)...")
    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:  # noqa: S310
            raw = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(raw)
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        content = str(exc)
        status = "error"
        raw = {"error": content}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_whats_next_after_account_tx_excel_{stamp}.json"
    raw_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    header = (
        f"# Moonshot AI — What's Next After SoftDent Account-Tx Excel + HAL Teach "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {live.get('buildId') or 'hal-10567'}  \n"
        f"**Prior:** SoftDent Trans Excel validated + HAL playbook (c4d2331); "
        f"Better Backend Widgets MUST (hal-10567)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_account_tx_excel_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_EXCEL_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_EXCEL_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    if status == "ok":
        print(content or "")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
