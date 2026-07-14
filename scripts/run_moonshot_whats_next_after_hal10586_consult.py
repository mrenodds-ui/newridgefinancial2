"""Moonshot AI — What's next after HAL-10586 full InsCo×ADA catalog (CONSULT ONLY).

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

Operator said NEXT after HAL-10586 just shipped on fix/main-validate-ci (3171bfe).

CONSULT ONLY — DO NOT claim you applied code. empty != $0.
No SoftDent write-back. Do not invent Ins Plan Register dollars or carrier names.
Do NOT redo HAL-10580–10586 as greenfield — build ON them.

JUST SHIPPED (HAL-10586 — Full InsCo×ADA Catalog Matrix):
- softdent_insco_ada_catalog_matrix.py surfaces ALL spine cells including insufficient
- SoftDent widget softdent-insco-ada-catalog; APIs /api/apex/insco-ada-catalog(+ /status)
- HAL intent policy:insco-ada-catalog-matrix
- Live: 2274 cells; exact usable 46; published 163; insufficient 2111;
  spine ADAs 92; ledger CDT universe 139; uncovered (no 2/51) 47; episodes 13321
- Prior HAL-10585: unified 5yr spine + treatment-planning fallback (gold still 0)

Pick THE single best NEXT package. Prefer additive local CODE/OPS. Avoid GitHub/PR primary.

OPEN CANDIDATES (pick ONE):
1) CODE: SoftDent Treatment Plan / estimate UX surface — HAL chips + richer TP replies
   using catalog + spine (pay$/WO$ + % +/- + badges) for staff treatment planning;
   catalog now exists so UX has breadth
2) CODE: Catalog UX polish — filters (exact/insufficient/uncovered), searchable table
   widget, carrier×ADA drill-down in SoftDent page (beyond status widget)
3) CODE: Reliability uplift on spine — secondary-ins exclusion, same-day settlement,
   bootstrap CI on borderline n=10–15 cells only (catalog now identifies them)
4) OPS+CODE: SoftDent Insurance Payment Analysis → gold path (still 0 rows) —
   only if REAL export path exists
5) CODE: ERA835 / claims payment cross-check vs catalog cells for outliers
6) OPS: Target uncovered 47 ledger CDTs — ops playbook to find why no 2/51 pairing
   (timing, multi-visit, carrier miss) without inventing dollars

What NOT to redo: SoftDent write-back; invent $0; re-unify spine; rebuild catalog
from scratch; pretend gold path exists; Register re-export Ins Plan>0.

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
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
        "prior": "3171bfe HAL-10586 full InsCo×ADA catalog matrix",
        "appliedDoc": "MOONSHOT_APPLIED_HAL10586_INSCO_ADA_CATALOG_MATRIX_2026-07-12.md",
        "consultDoc": "MOONSHOT_WHATS_NEXT_AFTER_HAL10585_2026-07-13.md",
        "priorSpine": "9cacfa6 HAL-10585",
    }
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402
        from softdent_insco_ada_catalog_matrix import (  # noqa: E402
            catalog_matrix_status,
            uncovered_ledger_cdts,
        )
        from softdent_treatment_planning import (  # noqa: E402
            lookup_treatment_estimate,
            treatment_planning_status,
        )

        live["buildId"] = BUILD_ID
        live["catalog"] = catalog_matrix_status()
        live["uncoveredSample"] = uncovered_ledger_cdts()[:25]
        live["uncoveredCount"] = len(uncovered_ledger_cdts())
        live["tp"] = treatment_planning_status()
        sample = lookup_treatment_estimate(payer="DELTA DENTAL OF KS", ada_code="D1110")
        live["sampleTpD1110"] = {
            "source": sample.get("source"),
            "sufficient": sample.get("sufficient"),
            "credibility": sample.get("credibility"),
            "n": sample.get("sampleSize"),
            "paid": (sample.get("estimate") or {}).get("paidAmountAvg"),
        }
        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                live["payment_lines"] = int(
                    con.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
                    or 0
                )
                live["borderlineExact"] = int(
                    con.execute(
                        """
                        SELECT COUNT(*) FROM insco_ada_probabilistic_estimates
                        WHERE tier='exact' AND sample_size BETWEEN 10 AND 15
                          AND credibility IN ('high','usable')
                        """
                    ).fetchone()[0]
                    or 0
                )
            finally:
                con.close()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:14000]


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
        ("MOONSHOT_APPLIED_HAL10586_INSCO_ADA_CATALOG_MATRIX_2026-07-12.md", 2400),
        ("MOONSHOT_WHATS_NEXT_AFTER_HAL10585_2026-07-13.md", 2000),
        ("MOONSHOT_APPLIED_HAL10585_UNIFORM_ADA_SPINE_TP_2026-07-12.md", 1600),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "HAL-10586 full catalog just shipped. Pick THE next package. CONSULT ONLY.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After HAL-10586"
    print("Calling Moonshot AI (what's next after 10586 — consult only)...")

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
    (OUT / f"moonshot_whats_next_after_hal10586_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After HAL-10586 Catalog Matrix "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** HAL-10586 full InsCo×ADA catalog (`3171bfe`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_hal10586_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10586_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10586_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
