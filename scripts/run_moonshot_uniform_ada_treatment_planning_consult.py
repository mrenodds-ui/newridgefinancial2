"""Moonshot AI — Uniform ADA analysis + treatment-planning integration (CONSULT ONLY).

Operator: all ADA codes should be analyzed the same way; consult Moonshot for
reference/recommendation and for treatment planning with the program.
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

OPERATOR_REQUEST_VERBATIM = (
    "all ada codes should be analzyed the same way and consult with moonoshot ai "
    "for reference and recommendation and also for treatment planning with the program"
)

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL + SoftDent RCM.

Operator wants EVERY ADA/CDT analyzed THE SAME WAY, plus a clear reference +
recommendation for wiring that into TREATMENT PLANNING inside the program.

CONSULT ONLY — DO NOT claim you applied code. empty != $0.
No SoftDent write-back. Do not invent Ins Plan Register dollars or carrier names.
Do NOT redo HAL-10580/81/82/83/84 as greenfield — build ON them.

JUST SHIPPED (HAL-10584 on fix/main-validate-ci — 5f7fb56):
- softdent_insco_ada_pct_variance.py: 5yr history; SoftDent code 2=pay, 51=WO;
  episode pairing; pay%/WO% median +/- 1 SD; exact vs inferred
- Live: 13,320 episodes; 46 exact publishable cells; 365 incl. inferred
- APIs: /api/apex/insco-ada-pct-variance/status + lookup
- HAL intent policy:insco-ada-pct-variance

ALREADY PRESENT:
- HAL-10582/83: $ averages (default ~24mo), credibility badges, HAL widget,
  board-action prefers probabilistic when gold payment-lines empty
- softdent_treatment_planning.py: gold-path lookup_treatment_estimate from
  treatment_planning_estimates / sd_insurance_payment_lines — BOTH COUNT=0 today
- SoftDent ledger mixes CDT-like codes (1110,2391,2750) with SoftDent internal
  codes (12,61,8888) and decimals (11.93,50.9,1110.1) — normalize unevenly today:
  pct variance pads 3-digit→D0xxx; probabilistic uses normalize_ada_code only

OPERATOR PAIN (read carefully):
1) "all ADA codes analyzed the same way" — one uniform pipeline for every
   production CDT (not only high-volume fillings/prophys); same history window,
   same pairing rules, same % and $ outputs, same credibility labels
2) Moonshot reference + recommendation — pick THE next package
3) "also for treatment planning with the program" — staff treatment-plan /
   estimate UX should use this InsCo×ADA matrix when gold path is empty,
   with honesty badges (not silent invent)

Pick THE single best NEXT package. Prefer additive local CODE. Avoid GitHub/PR primary.

OPEN CANDIDATES (pick ONE):
1) CODE: Unify ADA analysis spine — one shared module (normalize SoftDent→CDT,
   same 5yr window, same episode 2/51 pairing) feeding BOTH $ table and %+/- table;
   every distinct production ADA gets a row (publishable OR honest insufficient);
   deprecate divergent lookback/normalize between 10582 and 10584
2) CODE: Treatment-planning program path — when treatment_planning_estimates empty,
   lookup_treatment_estimate / HAL treatment-plan replies fall through to unified
   InsCo×ADA ($ + pay%/WO% +/-) with source=ledger_episode, credibility badge,
   and empty≠$0; gold path still wins when payment lines land
3) CODE: Full CDT catalog matrix UI — show ALL ADAs seen in 5yr ledger per carrier
   (including insufficient) so "every code analyzed" is visible; rare codes labeled
   insufficient not omitted
4) OPS+CODE: SoftDent Insurance Payment Analysis → gold path (still 0 rows) —
   only if REAL export path exists; operator previously said Excel often unavailable
5) CODE: SoftDent-internal code map (12/61/8888/decimals) → CDT or explicit exclude
   list so internal non-CDTs do not pollute ADA matrix

What NOT to redo: SoftDent write-back; invent $0 for empty; claim contractual
fee schedule; Register re-export for Ins Plan>0; pretend gold path exists.

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 2. Uniform ADA analysis reference (how every code is treated identically)
## 3. Treatment planning integration (program path when gold empty)
## 4. Runner-ups (2–3, why not now)
## 5. What NOT to redo
## 6. Acceptance criteria
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
DO NOT APPLY CODE. Prefer one clear next over a laundry list.
If Candidates 1 and 2 are inseparable, name them as one package with ordered steps.
"""


def _live_snapshot() -> str:
    live: dict = {
        "priorPct": "5f7fb56 HAL-10584 InsCo×ADA % +/- variance",
        "priorDollar": "HAL-10582/83 probabilistic $ + HAL surface",
        "modules": [
            "NewRidgeFinancial2/softdent_insco_ada_pct_variance.py",
            "NewRidgeFinancial2/softdent_insco_ada_probabilistic.py",
            "NewRidgeFinancial2/softdent_treatment_planning.py",
        ],
        "appliedDoc": "MOONSHOT_APPLIED_HAL10584_INSCO_ADA_PCT_VARIANCE_2026-07-12.md",
        "operatorNotes": [
            "Want every ADA analyzed the same way",
            "Want Moonshot reference + recommendation",
            "Want treatment planning in the program to use this",
            "Gold path payment lines still 0",
        ],
    }
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402

        live["buildId"] = BUILD_ID
        from softdent_insco_ada_pct_variance import pct_variance_status  # noqa: E402
        from softdent_insco_ada_probabilistic import (  # noqa: E402
            CREDIBILITY,
            probabilistic_report_status,
        )
        from softdent_treatment_planning import treatment_planning_status  # noqa: E402

        live["pctVariance"] = pct_variance_status()
        live["probabilistic"] = probabilistic_report_status()
        live["treatmentPlanning"] = treatment_planning_status()
        live["probCredibilityRules"] = {
            k: CREDIBILITY[k] for k in CREDIBILITY if k != "honesty"
        }

        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                live["sd_insurance_payment_lines"] = int(
                    con.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
                    or 0
                )
                live["treatment_planning_estimates"] = int(
                    con.execute("SELECT COUNT(*) FROM treatment_planning_estimates").fetchone()[0]
                    or 0
                )
                live["pctExactCellsAdas"] = list(
                    con.execute(
                        """
                        SELECT COUNT(*), COUNT(DISTINCT ada_code)
                        FROM insco_ada_pct_variance
                        WHERE tier='exact' AND credibility IN ('high','usable')
                        """
                    ).fetchone()
                )
                live["pctAllPublishableAdas"] = list(
                    con.execute(
                        """
                        SELECT COUNT(*), COUNT(DISTINCT ada_code)
                        FROM insco_ada_pct_variance
                        WHERE credibility != 'insufficient'
                        """
                    ).fetchone()
                )
                live["probExactCellsAdas"] = list(
                    con.execute(
                        """
                        SELECT COUNT(*), COUNT(DISTINCT ada_code)
                        FROM insco_ada_probabilistic_estimates
                        WHERE tier='exact' AND credibility IN ('high','usable')
                        """
                    ).fetchone()
                )
                live["distinctProcedures5yr"] = int(
                    con.execute(
                        """
                        SELECT COUNT(DISTINCT procedure) FROM sd_account_transactions
                        WHERE service_date >= date('now','-5 years')
                        """
                    ).fetchone()[0]
                    or 0
                )
                live["topProcedures5yr"] = [
                    {"procedure": r[0], "n": r[1]}
                    for r in con.execute(
                        """
                        SELECT procedure, COUNT(*) n FROM sd_account_transactions
                        WHERE service_date >= date('now','-5 years')
                        GROUP BY procedure ORDER BY n DESC LIMIT 25
                        """
                    )
                ]
                live["topPctExact"] = [
                    {
                        "carrier": r[0],
                        "ada": r[1],
                        "n": r[2],
                        "payMed": r[3],
                        "paySd": r[4],
                        "woMed": r[5],
                        "woSd": r[6],
                        "cred": r[7],
                    }
                    for r in con.execute(
                        """
                        SELECT insurance_company, ada_code, sample_size,
                               paid_pct_median, paid_pct_stdev,
                               write_off_pct_median, write_off_pct_stdev, credibility
                        FROM insco_ada_pct_variance
                        WHERE tier='exact' AND credibility IN ('high','usable')
                        ORDER BY sample_size DESC LIMIT 12
                        """
                    )
                ]
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
        ("MOONSHOT_APPLIED_HAL10584_INSCO_ADA_PCT_VARIANCE_2026-07-12.md", 3200),
        ("MOONSHOT_WHATS_NEXT_INSCO_ADA_ESTIMATES_RELIABILITY_2026-07-13.md", 2400),
        ("MOONSHOT_INSCO_ADA_HOWTO_2026-07-13.md", 1800),
        ("MOONSHOT_INSCO_ADA_PROBABILISTIC_HAL10582_APPLIED_2026-07-13.md", 1600),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "HAL-10584 % +/- just shipped; gold treatment-planning path still empty. "
        "Operator wants uniform ADA analysis + treatment planning in the program. "
        "Pick THE next package. CONSULT ONLY.\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n"
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 8000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Uniform ADA + Treatment Planning Consult"
    print("Calling Moonshot AI (uniform ADA + treatment planning — consult only)...")

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
    (OUT / f"moonshot_uniform_ada_treatment_planning_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — Uniform ADA Analysis + Treatment Planning "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** HAL-10584 InsCo×ADA % +/- (`5f7fb56`)  \n"
        f"**Script:** `scripts/run_moonshot_uniform_ada_treatment_planning_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_UNIFORM_ADA_TREATMENT_PLANNING_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_UNIFORM_ADA_TREATMENT_PLANNING_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
