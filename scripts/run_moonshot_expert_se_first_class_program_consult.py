"""Moonshot AI — Expert SE program review: issues, structure, 1st-class bar (CONSULT ONLY).

Operator asked (verbatim intent): as an expert software engineer, ask Moonshot what
you need to know about this program's issues, recommendations, structure, and
anything else that would make it a first-class highly proficient professional program.
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
    "as an expert software enginer ask moonshot ai what you need to know about this "
    "programs issues, recommendations and structure and anything else that woul make "
    "this a 1st class highly profienct profesional program"
)

SYSTEM = """You are Moonshot AI — principal engineer reviewing NewRidge Financial 2.0 (NR2).

A peer EXPERT SOFTWARE ENGINEER is asking what YOU need to know / what matters about:
- this program's ISSUES
- RECOMMENDATIONS
- STRUCTURE / architecture
- anything else to make it a FIRST-CLASS, highly proficient PROFESSIONAL program

CONSULT ONLY — DO NOT claim you applied code. empty != $0. No SoftDent write-back.
No invented Ins Plan $, patients, claim IDs, or contractual fee schedules.

PROGRAM FACTS (ground truth — do not contradict without evidence):
- Local Apex HAL bridge for a Kansas dental S-corp: SoftDent + QuickBooks, Bottle TLS
  loopback, Apex JS shell, local HAL.
- Branch fix/main-validate-ci recently shipped InsCo×ADA stack:
  HAL-10580 claims bridge → 10581 Sensei coverage → 10582/83 probabilistic $ →
  10584 % +/- → 10585 unified 5yr spine + TP fallback → 10586 full catalog
  (incl. insufficient) → 10587 TP estimate chips UX.
- Live analytics (~): ~550k account TX; ~5.4k patient insurance; 61 claims;
  gold sd_insurance_payment_lines=0; treatment_planning_estimates=0;
  InsCo×ADA spine cells ~2274 (46 exact usable); BUILD_ID often still labeled hal-10576
  while package IDs advanced to 10587 — versioning drift is a real issue.
- ~276 Python modules, ~122 tests, ~266 Moonshot docs under NewRidgeFinancial2.
- Hard rules: SoftDent period $ via desktop Excel/Print Preview not ODBC; never Printer;
  empty != $0; no SoftDent write-back; no Register re-export hoping Ins Plan > 0.

Be blunt and professional. Separate:
1) What you NEED TO KNOW (information gaps / unknowns that block a true 1st-class bar)
2) Structural diagnosis (architecture, coupling, data planes, honesty gates)
3) Ranked issues (MUST/SHOULD/NICE)
4) Concrete recommendations to reach first-class professional quality
5) One recommended NEXT package if operator says proceed (single package)

Do NOT re-litigate finished InsCo×ADA spine/catalog/TP-chip work as greenfield.
Do NOT recommend GitHub/PR as the primary next step unless truly blocked.

OUTPUT (strict markdown):
# Verdict (2–4 sentences — engineer-to-engineer)
## 0. Operator Intent (verbatim)
## 1. What Moonshot Needs To Know (discovery checklist — unknowns that matter)
## 2. Program Structure Diagnosis (data planes, HAL, SoftDent/QB, honesty)
## 3. Ranked Issues
Table: ID | Severity | Area | Issue | Evidence | Why it blocks 1st-class
## 4. Recommendations to Reach First-Class
Table: ID | Rank (MUST/SHOULD/NICE) | Recommendation | Why | Effort | Depends on
## 5. Target Architecture Sketch (what “professional” looks like for NR2)
## 6. Suggested NEXT package (ONE) if operator says proceed
## 7. Acceptance criteria for “1st-class”
## 8. Executive Summary (7 bullets)
## 9. Approval checklist
DO NOT APPLY CODE.
"""


def _live_snapshot() -> str:
    live: dict = {
        "branch": "fix/main-validate-ci",
        "headHint": "6cf8913 HAL-10587 TP estimate chips",
        "recentPackages": [
            "HAL-10587 TP estimate UX chips",
            "HAL-10586 full catalog matrix",
            "HAL-10585 unified spine + TP fallback",
            "HAL-10584 % +/- variance",
            "HAL-10582/83 probabilistic $ + HAL surface",
            "HAL-10581 Sensei insurance",
            "HAL-10580 outstanding claims bridge",
        ],
        "operatorAsk": "expert SE: issues, recommendations, structure, 1st-class bar",
    }
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402

        live["buildId"] = BUILD_ID
        nr2 = REPO / "NewRidgeFinancial2"
        live["pyModules"] = len(list(nr2.glob("*.py")))
        live["testModules"] = len(list(nr2.glob("test_*.py")))
        docs = nr2 / "docs"
        live["moonshotDocs"] = len(list(docs.glob("MOONSHOT*.md"))) if docs.is_dir() else 0

        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                for table in (
                    "sd_account_transactions",
                    "sd_patient_insurance",
                    "sd_claims",
                    "sd_insurance_payment_lines",
                    "treatment_planning_estimates",
                    "insco_ada_probabilistic_estimates",
                    "insco_ada_pct_variance",
                ):
                    try:
                        live[table] = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
                    except Exception:
                        live[table] = "missing"
                live["exactUsable"] = int(
                    con.execute(
                        """
                        SELECT COUNT(*) FROM insco_ada_probabilistic_estimates
                        WHERE tier='exact' AND credibility IN ('high','usable')
                        """
                    ).fetchone()[0]
                    or 0
                )
            finally:
                con.close()
        try:
            from softdent_treatment_planning import treatment_planning_status  # noqa: E402
            from softdent_insco_ada_catalog_matrix import catalog_matrix_status  # noqa: E402

            live["tpStatus"] = treatment_planning_status()
            live["catalogStatus"] = {
                k: catalog_matrix_status().get(k)
                for k in (
                    "totalCells",
                    "exactUsableCells",
                    "insufficientCells",
                    "ledgerCdtUniverse",
                )
            }
        except Exception as exc:  # noqa: BLE001
            live["statusError"] = f"{type(exc).__name__}:{exc}"
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
        ("MOONSHOT_EXPERT_SE_PROGRAM_RECOMMENDATIONS_CONSULT_2026-07-11.md", 2200),
        ("MOONSHOT_APPLIED_HAL10587_TP_ESTIMATE_UX_2026-07-12.md", 1600),
        ("MOONSHOT_APPLIED_HAL10585_UNIFORM_ADA_SPINE_TP_2026-07-12.md", 1400),
        ("MOONSHOT_WHATS_NEXT_AFTER_HAL10586_2026-07-13.md", 1200),
        ("MOONSHOT_WHATS_WRONG_CONSULT_2026-07-10.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Peer expert SE wants: issues, recommendations, structure, and what makes NR2 "
        "first-class professional. CONSULT ONLY. Be blunt.\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n"
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 9000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Expert SE First-Class Program Review"
    print("Calling Moonshot AI (expert SE 1st-class program review — consult only)...")

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
    (OUT / f"moonshot_expert_se_first_class_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — Expert SE: Issues, Structure, First-Class Bar "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** HAL-10587 TP estimate chips (`6cf8913`)  \n"
        f"**Script:** `scripts/run_moonshot_expert_se_first_class_program_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_EXPERT_SE_FIRST_CLASS_PROGRAM_{DATE}.md"
    out = OUT / f"MOONSHOT_EXPERT_SE_FIRST_CLASS_PROGRAM_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
