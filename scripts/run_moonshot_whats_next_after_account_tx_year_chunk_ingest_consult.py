"""Moonshot AI — What's next after SoftDent account-tx year-chunk INGEST.

CONSULT ONLY. Operator: next.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
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

OPERATOR_REQUEST_VERBATIM = "next"

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL.

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes when OPS is blocked on missing real files.
Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST SHIPPED (6843a9c — year-chunk account-tx INGEST):
- TXNALL260712 + TXN2017H2..TXN2026YTD ingested into sd_account_transactions
- Live: dbTotal=549564, service years 1996→2026, multi_year_available=true
- TXNALL max service_date=2017-06-28; no overlap with TXN2017H2
- TXN260201 purged after TXN2026YTD; Donna 27002 Feb=5 from DB
- CLI: scripts/continue_softdent_txn_excel.py --ingest-year-chunks
- CSV-as-.xls parse + manifest parity in softdent_transaction_extract.py
- Applied doc: MOONSHOT_ACCOUNT_TX_YEAR_CHUNKS_INGEST_APPLIED_2026-07-13.md

PRIOR (do not redo):
- Year-chunk SoftDent GUI pulls (verified on disk)
- ERA discovery 10575 (live candidateCount=0; procurement still required)
- Collections Excel-temp 10576 (shipped 82aef29)
- Widgets MUST/SHOULD/NICE; Register Ins Plan invent dollars; synthetic 835

OPEN CANDIDATES (pick ONE highest leverage NOW):
1) CODE: Wire HAL / policy surface so multi-year account-tx answers use
   sd_account_transactions (query_account_transactions + format_* helpers) —
   expose account_tx_multi_year_available / date-span honesty in HAL replies
   without inventing dollars. Cite REAL gateway/policy files.
2) CODE: Browser/HAL smoke that a multi-year account query (e.g. Donna or
   range 2018–2026) returns from DB source — only if hooks already exist.
3) OPS: Concrete payer-portal / clearinghouse 835 acquisition — only with
   REAL repo evidence; discovery already proved local candidates=0.
4) OPS: July Register/Collections with Ins Plan Collections > 0 — only if
   DEF-001 ingest is ready and this is still the month-end blocker.
5) CODE: Small ledger UX/widget showing multi-year coverage chip from ingest
   log — only if REAL widget surfaces exist; keep empty≠$0.

Prefer the highest-ROI CODE that unlocks the NEW 549k-row ledger for HAL
operators now that ingest is done. Do NOT recommend re-pulling year chunks
or re-ingesting. Do NOT invent ERA/Ins Plan dollars.

REAL PATHS:
- C:\\SoftDentFinancialExports\\softdent_financial_analytics.db
- C:\\SoftDentFinancialExports\\softdent_account_tx_year_chunks_ingest.json
- NewRidgeFinancial2/softdent_transaction_extract.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- scripts/continue_softdent_txn_excel.py
- NewRidgeFinancial2/docs/MOONSHOT_ACCOUNT_TX_YEAR_CHUNKS_INGEST_APPLIED_2026-07-13.md

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
"""


def _live_snapshot() -> str:
    live: dict = {}
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID, _load_reports_and_bundle  # noqa: E402
        from apex_softdent_hardening_pack import assess_collections_gap  # noqa: E402
        from apex_era835_pack import discover_era_candidates, scan_era_inbox  # noqa: E402
        from softdent_transaction_extract import (  # noqa: E402
            query_account_transactions,
            resolve_analytics_db,
        )

        live["buildId"] = BUILD_ID
        live["prior"] = "6843a9c year-chunk ingest; dbTotal=549564; 1996-2026"
        ingest_log = Path(r"C:\SoftDentFinancialExports\softdent_account_tx_year_chunks_ingest.json")
        if ingest_log.is_file():
            raw = json.loads(ingest_log.read_text(encoding="utf-8"))
            live["ingest"] = {
                k: raw.get(k)
                for k in (
                    "ok",
                    "dbTotal",
                    "okCount",
                    "failCount",
                    "serviceYearMin",
                    "serviceYearMax",
                    "account_tx_multi_year_available",
                    "purgedSupersededRows",
                )
            }
        db = resolve_analytics_db()
        live["dbPath"] = str(db) if db else None
        q = query_account_transactions(
            account_num="27002", date_range="2026-02", prefer_db=True, limit=10
        )
        live["donnaFeb"] = {
            k: q.get(k) for k in ("ok", "matchCount", "source", "reason")
        }
        q2 = query_account_transactions(
            date_range="2018-01-01:2018-01-31", prefer_db=True, limit=3
        )
        live["jan2018"] = {
            k: q2.get(k) for k in ("ok", "matchCount", "source")
        }
        _r, bundle, _e = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        live["gap"] = {
            k: gap.get(k)
            for k in (
                "gapCode",
                "collectionsGapCode",
                "registerInsPlanZero",
                "insurance",
                "period",
            )
        }
        live["eraInbox"] = {
            k: scan_era_inbox(ensure_dirs=True).get(k)
            for k in ("empty", "fileCount", "chipStatus", "chipLabel")
        }
        disc = discover_era_candidates(limit=20, max_depth=4)
        live["discovery"] = {
            k: disc.get(k)
            for k in ("candidateCount", "chipStatus", "chipLabel")
        }
        try:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(
                "https://127.0.0.1:8765/api/apex/hal/era-inbox/discover",
                timeout=20,
                context=ctx,
            ) as resp:
                live["liveDiscoverApi"] = {
                    k: json.loads(resp.read().decode("utf-8")).get(k)
                    for k in ("buildId", "candidateCount", "chipLabel", "ok")
                }
        except Exception as exc:  # noqa: BLE001
            live["liveDiscoverApiError"] = f"{type(exc).__name__}:{exc}"
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
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
        ("MOONSHOT_ACCOUNT_TX_YEAR_CHUNKS_INGEST_APPLIED_2026-07-13.md", 2200),
        ("MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_YEAR_CHUNKS_2026-07-13.md", 1600),
        ("MOONSHOT_WHATS_NEXT_AFTER_ERA_10575_DISCOVERY_2026-07-13.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Year-chunk account-tx INGEST SHIPPED (6843a9c; 549564 rows; 1996-2026). "
        "Pick THE next package. CONSULT ONLY.\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After Account TX Year Chunk Ingest"
    print("Calling Moonshot AI (consult only — will not apply)...")

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
    (OUT / f"moonshot_whats_next_after_account_tx_year_chunk_ingest_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After Account-TX Year-Chunk Ingest (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** year-chunk ingest shipped (`6843a9c`; 549564 rows)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_account_tx_year_chunk_ingest_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_YEAR_CHUNK_INGEST_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_YEAR_CHUNK_INGEST_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
