"""Moonshot AI — How to build a database for SoftDent account transactions.

Operator asked how to place account txs in a DB now that Excel pull is known.
CONSULT ONLY — do not apply code.
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

OPERATOR_REQUEST_VERBATIM = (
    "ask moonshot how to make a database to place account transactions "
    "now that we know how to get them. then report"
)

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(hal-10569 + SoftDent TXN Excel ingest + HAL ledger + SoftDentFinancialExports).

Operator asks: HOW to make a DATABASE to store SoftDent ACCOUNT TRANSACTIONS
now that the Excel pull path is proven (Trans for a Period → Excel →
C:\\SoftDentReportExports\\TXN*.xls → parse → tx_parsed JSONL).

CONSULT ONLY — DO NOT claim you applied code. Design the single best local
database package. Prefer additive reuse of real paths over inventing new DBs.
empty != $0. Never invent SoftDent write-back. Never invent dollars.
Desktop SoftDent Excel remains source of truth for these txs (not ODBC fiction).

KNOWN FACTS (use LIVE SNAPSHOT when present):
- Pull path validated: Reports → Accounting → Trans for a Period → Excel Format 1
- Live file: C:\\SoftDentReportExports\\TXN260201.xls (1736 sheet rows)
- Parsed JSONL: C:\\SoftDentFinancialExports\\tx_parsed\\TXN260201.jsonl
- Typed fields: date, account_num, patient_name, provider, procedure, amount,
  note_flag (+ prod/charges/prod_adj/cash/check/credit/pay_adj)
- HAL: query_account_transactions + SoftDent/OM ledger widgets (hal-10569)
- Existing analytics DB path often:
  C:\\SoftDentFinancialExports\\softdent_financial_analytics.db
- Existing table sd_transactions_full already exists for older JSONL
  transactions_for_period.jsonl shape (patient_id, ada_code, amount, …)
- Honesty: null amounts stay null; never coerce empty to $0

YOUR JOB — produce a concrete DB design + load plan:
1) Prefer extend softdent_financial_analytics.db vs new DB file (justify)
2) Exact table DDL (columns, types, PK/indexes) for TXN Excel rows
3) How it maps from parse_account_transactions_xls / JSONL
4) Upsert / idempotency key (stable_id) so re-ingest is safe
5) How HAL / widgets / analytics should read it after load
6) Validation gates (Donna 27002 = 5 Feb rows; rowCount honesty)
7) What NOT to do (ODBC write-back, invent claim links, invent $0)

REAL PATHS ONLY:
- NewRidgeFinancial2/softdent_transaction_extract.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/apex_better_backend_widgets_pack.py
- NewRidgeFinancial2/apex_backend.py
- C:\\SoftDentReportExports
- C:\\SoftDentFinancialExports\\tx_parsed
- C:\\SoftDentFinancialExports\\softdent_financial_analytics.db
- NewRidgeFinancial2/docs/MOONSHOT_SOFTDENT_TXN_XLS_INGEST_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_TXN_LEDGER_SURFACE_APPLIED_2026-07-12.md

OUTPUT (strict markdown):
# Verdict (one sentence — THE recommended DB approach)
## 0. Operator Intent (verbatim)
## 1. Recommended design (DB file, table name, why now, effort)
## 2. DDL (CREATE TABLE + indexes) — exact SQL
## 3. Load / upsert plan (REAL functions/files, idempotency key)
## 4. Read path (HAL, widgets, analytics)
## 5. Runner-ups (2–3, why not)
## 6. What NOT to do
## 7. Acceptance criteria
## 8. Executive Summary (5 bullets)
## 9. Approval checklist
DO NOT APPLY CODE. Prefer one clear design over a laundry list.
"""


def _live_snapshot() -> str:
    live: dict = {}
    txn = Path(r"C:\SoftDentReportExports\TXN260201.xls")
    jsonl = Path(r"C:\SoftDentFinancialExports\tx_parsed\TXN260201.jsonl")
    db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
    if txn.is_file():
        live["txnXls"] = {"path": str(txn), "bytes": txn.stat().st_size}
    if jsonl.is_file():
        live["txnJsonl"] = {"path": str(jsonl), "bytes": jsonl.stat().st_size}
        try:
            lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
            meta = json.loads(lines[0]) if lines else {}
            sample = json.loads(lines[1]) if len(lines) > 1 else {}
            live["txnJsonlMeta"] = {
                k: meta.get(k) for k in ("rowCount", "recordCount", "periodHint", "sourcePath")
            }
            live["txnJsonlSampleKeys"] = sorted(sample.keys()) if isinstance(sample, dict) else []
            donna = 0
            for ln in lines[1:]:
                obj = json.loads(ln)
                if str(obj.get("account_num") or "") == "27002":
                    donna += 1
            live["donna27002Lines"] = donna
        except Exception as exc:  # noqa: BLE001
            live["txnJsonlError"] = type(exc).__name__
    if db.is_file():
        live["analyticsDb"] = {"path": str(db), "bytes": db.stat().st_size}
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                tables = [
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1"
                    ).fetchall()
                ]
                live["analyticsTables"] = tables
                if "sd_transactions_full" in tables:
                    live["sd_transactions_full"] = dict(
                        zip(
                            ("count", "minDate", "maxDate"),
                            conn.execute(
                                "SELECT COUNT(*), MIN(service_date), MAX(service_date) "
                                "FROM sd_transactions_full"
                            ).fetchone(),
                        )
                    )
                    cols = [
                        r[1]
                        for r in conn.execute("PRAGMA table_info(sd_transactions_full)").fetchall()
                    ]
                    live["sd_transactions_full_columns"] = cols
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001
            live["analyticsDbError"] = f"{type(exc).__name__}:{exc}"
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402

        live["buildId"] = BUILD_ID
    except Exception as exc:  # noqa: BLE001
        live["buildError"] = type(exc).__name__
    return json.dumps(live, indent=2, default=str)[:8000]


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
        ("MOONSHOT_SOFTDENT_TXN_XLS_INGEST_APPLIED_2026-07-12.md", 2200),
        ("MOONSHOT_TXN_LEDGER_SURFACE_APPLIED_2026-07-12.md", 1800),
        ("MOONSHOT_SOFTDENT_FULL_EXTRACT_APPLIED_2026-07-10.md", 1600),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    # Schema excerpt from extract module
    extract = REPO / "NewRidgeFinancial2" / "softdent_transaction_extract.py"
    if extract.is_file():
        text = extract.read_text(encoding="utf-8")
        start = text.find("def ensure_transactions_schema")
        excerpts.append(
            "--- softdent_transaction_extract.ensure_transactions_schema ---\n"
            + text[start : start + 2200]
        )
        start2 = text.find("def parse_account_transactions_xls")
        excerpts.append(
            "--- softdent_transaction_extract.parse_account_transactions_xls ---\n"
            + text[start2 : start2 + 1800]
        )

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Design THE database package for SoftDent account transactions.\n"
        "CONSULT ONLY — do not apply.\n\n"
        f"## LIVE SNAPSHOT\n{_live_snapshot()}\n\n"
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
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 SoftDent Account Tx Database Design"
    print("Calling Moonshot AI (account-tx DB design — consult only)...")
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
    (OUT / f"moonshot_account_tx_db_design_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — SoftDent Account Transactions Database Design (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10569  \n"
        f"**Prior:** TXN XLS ingest + ledger surface (001a927)  \n"
        f"**Script:** `scripts/run_moonshot_account_tx_db_design_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_ACCOUNT_TX_DB_DESIGN_CONSULT_{DATE}.md"
    out = OUT / f"MOONSHOT_ACCOUNT_TX_DB_DESIGN_CONSULT_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    # Avoid Windows console UnicodeEncodeError on special chars
    sys.stdout.buffer.write(((content or "")[:6000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
