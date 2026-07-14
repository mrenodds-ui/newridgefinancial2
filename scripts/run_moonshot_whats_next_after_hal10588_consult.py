"""Moonshot AI — What's next after HAL-10588 gold payment pipeline (CONSULT ONLY).

Operator said: next
"""

from __future__ import annotations

import json
import os
import sqlite3
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

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL + SoftDent RCM.

Operator said NEXT after HAL-10588 just shipped on fix/main-validate-ci (b6f561b).

CONSULT ONLY — DO NOT claim you applied code. empty != $0.
No SoftDent write-back. Do not invent Ins Plan Register dollars or carrier names.
Do NOT redo HAL-10580–10588 as greenfield — build ON them.

JUST SHIPPED (HAL-10588 — Gold Data Pipeline Audit & Repair):
- softdent_gold_payment_pipeline.py: audit gapCodes (GOLD_CSV_MISSING /
  GOLD_FILE_PRESENT_NOT_INGESTED / GOLD_OK), candidate hunt, repair ingest,
  exact usable spine consistency validation, SoftDent widget + API + HAL intent
- BUILD_ID coupled to package: hal-10588 (FIX-002 done)
- Financial module line coverage ~84% (FIX-003 done; each target ≥80%)
- Live still: sd_insurance_payment_lines=0, gapCode=GOLD_CSV_MISSING —
  SoftDent Insurance Payment Analysis CSV never dropped; ETL ready; empty != $0
- Exact usable spine: 46 checked / 46 pass / 0 flag (consistency only; no remittance)
- Playbook documented: Reports → Insurance → Insurance Payment Analysis →
  C:\\SoftDentFinancialExports\\insurance_payments_YYYYMMDD.csv → Sync
- Prior stack: 10580–10587 InsCo×ADA spine/catalog/TP chips all live on ledger fallback

Pick THE single best NEXT package. Prefer additive local CODE/OPS. Avoid GitHub/PR primary.

OPEN CANDIDATES (pick ONE — argue from current blockers):
1) OPS: Operator SoftDent Insurance Payment Analysis CSV drop + Sync —
   unblock live gold (paymentLines>0). Package may be OPS playbook + light
   verification checklist / ingest smoke, NOT inventing gold from ledger.
2) CODE: Remittance validation of the 46 exact usable cells once gold OR ERA
   lines exist — cross-check paid$/WO$ vs remittance; until gold, this is blocked.
3) CODE: Empty≠$0 programmatic UI enforcement audit — prove no null renders as
   $0.00 across Apex/SoftDent widgets (HON-001 from expert SE).
4) CODE: Async HAL invocation / request queue (ASGI) — ENH-001; latency under load.
5) CODE: Catalog cell growth / spine reliability — secondary-ins exclusion,
   same-day settlement, borderline n bootstrap — grow beyond 46 exact usable.
6) CODE: ERA835 first-drop / payment cross-check vs InsCo×ADA cells (if ERA inbox
   has real files; do not invent).
7) OPS+CODE: Uncovered ledger CDT playbook (47 CDTs with no 2/51 pairing).

What NOT to redo: SoftDent write-back; invent gold lines from spine; pretend
CSV exists; BUILD_ID drift (already fixed); redo TP chips/catalog/spine;
Register re-export Ins Plan>0; GitHub/PR as primary next.

CRITICAL JUDGMENT: Expert SE said do not proceed with additional UX surfaces
until gold data flows. If the highest-leverage next step is still OPS CSV drop,
say so clearly — even if it is OPS-heavy rather than code-heavy. If a CODE
package unblocks value WHILE gold is waiting, justify why it is not another
UX surface that depends on gold fiction.

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
## 2. Why this beats the other candidates now
## 3. Runner-ups (2–3, why not now)
## 4. What NOT to redo
## 5. Acceptance criteria
## 6. Executive Summary (5 bullets)
## 7. Approval checklist
DO NOT APPLY CODE. Prefer one clear next over a laundry list.
"""


def _live_snapshot() -> str:
    live: dict = {
        "prior": "b6f561b HAL-10588 gold payment pipeline audit/repair",
        "appliedDoc": "MOONSHOT_APPLIED_HAL10588_GOLD_PAYMENT_PIPELINE_2026-07-12.md",
        "consultDoc": "MOONSHOT_EXPERT_SE_FIRST_CLASS_PROGRAM_2026-07-13.md",
        "operatorAsk": "next",
    }
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402
        from softdent_gold_payment_pipeline import (  # noqa: E402
            PACKAGE_BUILD_ID,
            audit_gold_payment_pipeline,
        )
        from softdent_insco_ada_catalog_matrix import catalog_matrix_status  # noqa: E402
        from softdent_treatment_planning import treatment_planning_status  # noqa: E402

        live["buildId"] = BUILD_ID
        live["packageBuildId"] = PACKAGE_BUILD_ID
        live["buildIdCoupled"] = BUILD_ID == PACKAGE_BUILD_ID == "hal-10588"
        live["goldAudit"] = audit_gold_payment_pipeline()
        live["catalog"] = {
            k: catalog_matrix_status().get(k)
            for k in (
                "ok",
                "totalCells",
                "exactUsableCells",
                "publishedCells",
                "insufficientCells",
                "ledgerCdtUniverse",
                "spineEpisodes",
            )
        }
        live["tp"] = treatment_planning_status()
        # ERA / export root presence (no invent)
        exports = Path(r"C:\SoftDentFinancialExports")
        era_hits = []
        if exports.is_dir():
            for pat in ("*835*", "*era*", "*ERA*", "*remit*"):
                era_hits.extend([str(p.name) for p in exports.glob(pat)][:10])
        live["eraLikeFilesSample"] = sorted(set(era_hits))[:20]
        live["insurancePaymentCsvSample"] = sorted(
            p.name for p in exports.glob("insurance_payment*")
        )[:10] if exports.is_dir() else []
        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                for table, key in (
                    ("sd_insurance_payment_lines", "paymentLines"),
                    ("treatment_planning_estimates", "tpEstimates"),
                    ("era_835_payments", "era835"),
                    ("sd_payments", "sdPayments"),
                ):
                    try:
                        live[key] = int(
                            con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0
                        )
                    except sqlite3.Error:
                        live[key] = None
            finally:
                con.close()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:16000]


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
        ("MOONSHOT_APPLIED_HAL10588_GOLD_PAYMENT_PIPELINE_2026-07-12.md", 3200),
        ("MOONSHOT_EXPERT_SE_FIRST_CLASS_PROGRAM_2026-07-13.md", 2800),
        ("MOONSHOT_APPLIED_HAL10587_TP_ESTIMATE_UX_2026-07-12.md", 1600),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "HAL-10588 gold pipeline audit/repair just shipped (BUILD_ID coupled, "
        "coverage ≥80%, live still GOLD_CSV_MISSING / paymentLines=0). "
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
        headers["X-Title"] = "NR2 Whats Next After HAL-10588"
    print("Calling Moonshot AI (what's next after 10588 — consult only)...")

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
    (OUT / f"moonshot_whats_next_after_hal10588_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10588"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After HAL-10588 Gold Pipeline "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** HAL-10588 gold payment pipeline (`b6f561b`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_hal10588_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10588_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10588_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
