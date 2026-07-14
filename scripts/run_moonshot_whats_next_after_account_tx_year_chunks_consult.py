"""Moonshot AI — What's next after SoftDent account-tx year-chunk Excel pulls.

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

JUST COMPLETED (desktop SoftDent Trans-for-a-Period year chunks):
- Full-history pull TXNALL260712 truncated at mid-2017 (~385k rows).
- Year chunks VERIFIED on disk under C:\\SoftDentReportExports:
  TXN2017H2, TXN2018..TXN2025, TXN2026YTD (10/10 ok).
- Scripts: scripts/_pull_account_tx_year_chunks.py,
  scripts/_pull_account_tx_remaining_years.py
- Commit f80b58d hardens remaining-year puller (SameFileError + year verify).
- Summary JSON: C:\\SoftDentFinancialExports\\softdent_account_tx_year_chunks.json

ALSO IN FLIGHT / PRIOR:
- ERA discovery 10575 SHIPPED; live candidateCount=0 (procurement still required).
- Collections Excel-temp reliability (hal-10576) APPLIED locally in working tree
  but may still be uncommitted — do NOT redo that package; if still uncommitted,
  prefer "commit+ship 10576" only if that is higher leverage than ingesting the
  NEW year-chunk TX Excel into the account-tx DB/HAL path.
- Register Ins Plan zero / ERA_835_REQUIRED still open; do NOT invent Ins Plan
  dollars or synthetic 835s.

OPEN CANDIDATES (pick ONE highest leverage NOW):
1) CODE: Ingest year-chunk TX Excel (TXN2017H2..TXN2026YTD + TXNALL) into the
   existing SoftDent account-tx SQLite/JSONL + HAL ledger path — only if REAL
   ingest scripts/modules already exist (cite paths). Prefer extending proven
   TXN XLS ingest over inventing a new pipeline.
2) OPS: Commit/ship leftover local 10576 Excel-temp work if still uncommitted
   and tests already PASS — only if ingest is blocked or already done.
3) CODE/OPS: Wire HAL answers for multi-year account-tx coverage using the new
   files — only with existing format_softdent_account_tx_* / DB helpers.
4) OPS: Concrete payer-portal 835 acquisition — only with REAL repo evidence;
   discovery already proved local candidates=0.
5) OPS: July Register/Collections with Ins Plan Collections > 0 — only if still
   the month-end blocker AND code already ingests Register XLS (DEF-001).

What NOT to redo: year-chunk GUI pulls already verified, 10575 discovery,
10574 mutation smoke, widgets MUST/SHOULD/NICE, invent Register Ins Plan > 0,
synthetic ERA, SoftDent write-back.

REAL PATHS:
- C:\\SoftDentReportExports\\TXNALL260712.csv
- C:\\SoftDentReportExports\\TXN2017H2.XLS … TXN2025.XLS, TXN2026YTD.XLS
- C:\\SoftDentFinancialExports\\softdent_account_tx_year_chunks.json
- scripts/_pull_account_tx_remaining_years.py
- scripts/continue_softdent_txn_excel.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/softdent_excel_temp.py (10576 local)
- NewRidgeFinancial2/nr2_hal_gateway.py

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


def _year_chunk_snapshot() -> str:
    dest = Path(r"C:\SoftDentReportExports")
    summary = Path(r"C:\SoftDentFinancialExports\softdent_account_tx_year_chunks.json")
    files = []
    for pat in (
        "TXNALL*",
        "TXN2017H2*",
        "TXN2018*",
        "TXN2019*",
        "TXN2020*",
        "TXN2021*",
        "TXN2022*",
        "TXN2023*",
        "TXN2024*",
        "TXN2025*",
        "TXN2026YTD*",
    ):
        for p in sorted(dest.glob(pat)):
            if p.suffix.lower() in {".xls", ".csv"}:
                files.append({"name": p.name, "bytes": p.stat().st_size})
    payload: dict = {"files": files[:40]}
    if summary.is_file():
        try:
            payload["summary"] = json.loads(summary.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            payload["summaryError"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(payload, indent=2, default=str)[:6000]


def _live_snapshot() -> str:
    live: dict = {}
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID, _load_reports_and_bundle  # noqa: E402
        from apex_softdent_hardening_pack import assess_collections_gap  # noqa: E402
        from apex_era835_pack import discover_era_candidates, scan_era_inbox  # noqa: E402

        live["buildId"] = BUILD_ID
        live["prior"] = "f80b58d year-chunk TX puller; 10/10 chunks verified on disk"
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
            for k in ("candidateCount", "chipStatus", "chipLabel", "scannedRoots")
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
        excel_temp = REPO / "NewRidgeFinancial2" / "softdent_excel_temp.py"
        live["hal10576Local"] = {
            "softdent_excel_temp_exists": excel_temp.is_file(),
            "appliedDocExists": (
                DOCS / "MOONSHOT_COLLECTIONS_EXCEL_TEMP_RELIABILITY_APPLIED_2026-07-12.md"
            ).is_file(),
        }
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
        ("MOONSHOT_WHATS_NEXT_AFTER_ERA_10575_DISCOVERY_2026-07-13.md", 1800),
        ("MOONSHOT_COLLECTIONS_EXCEL_TEMP_RELIABILITY_APPLIED_2026-07-12.md", 1600),
        ("MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_DB_2026-07-12.md", 1400),
        ("MOONSHOT_WHATS_NEXT_AFTER_TXN_XLS_INGEST_2026-07-12.md", 1400),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    years = _year_chunk_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "SoftDent account-tx year chunks VERIFIED on disk (10/10). "
        "Pick THE next package. CONSULT ONLY.\n\n"
        f"## YEAR CHUNK SNAPSHOT\n{years}\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After Account TX Year Chunks"
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
    (OUT / f"moonshot_whats_next_after_account_tx_year_chunks_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After Account-TX Year Chunks (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** year-chunk TX 10/10 verified (`f80b58d`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_account_tx_year_chunks_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_YEAR_CHUNKS_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_YEAR_CHUNKS_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
