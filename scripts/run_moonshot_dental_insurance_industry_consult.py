"""Moonshot AI — Industry-wide dental insurance knowledge for NR2 (CONSULT ONLY).

Operator: ask moonshot ai about his full knowledge of dental insurance industry
wide and anything that can help us with this program consult.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
NR2 = REPO / "NewRidgeFinancial2"
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
    "ask moonshot ai about his full knowledge of dental insurance industry wide "
    "and anything that can help us with this program consult."
)

SYSTEM = """You are Moonshot AI — principal dental RCM / SoftDent financial engineer
with deep, cross-practice knowledge of the US dental insurance industry (national
carriers, Blues, Delta Dental networks, Medicare Advantage dental, Medicaid/DentaQuest,
federal programs FEP/GEHA/UCCI, TPAs/ASOs, union/employer plans, discount networks,
claim routing, rebrands/acquisitions, and how SoftDent offices typically name payers).

CONSULT ONLY — DO NOT claim you applied code or mutated the DB.
empty != $0. No SoftDent write-back. Do NOT invent InsCo×ADA settlement dollars,
gold payment lines, or Register collections. Prefer NONE / insufficient over wrong $.

PROGRAM CONTEXT (NR2 Apex HAL SoftDent RCM, BUILD_ID=hal-10604, branch fix/main-validate-ci):
Already shipped (do not redo as greenfield):
- Ledger InsCo×ADA spine + probabilistic estimates + staff catalog expand
- SoftDent insurance company master CSV → insurance_company_reference
- Carrier alias reconcile (HAL-10600) + TP via accepted alias (HAL-10601)
- Honesty CI null↛$0 (HAL-10603)
- HAL-10604 Moonshot industry HIGH aliases applied (Assurant→Sun Life,
  Connecticut General→CIGNA, MetLife variants, UniCare→Anthem);
  Coventry→Aetna still MEDIUM pending; 77 rejected honest NONEs remain
- Gold CSV still missing (sd_insurance_payment_lines=0)
- Exact usable InsCo×ADA cells still thin (~46); most catalog is no_settlement null

OPERATOR ASK:
Share your FULL useful dental-insurance industry knowledge that can help THIS
program — not a generic textbook dump. Focus on what changes staff TP estimates,
payer identity, SoftDent ops, gold/ERA, and honesty.

YOUR JOB (consult):
A) Industry map that matters for SoftDent GP practices (especially Midwest/KS-adjacent)
B) Payer identity / rebrand / acquisition table still relevant to leftover masters
C) SoftDent naming quirks offices hit constantly
D) What TP / fee estimation can and cannot honestly do without gold/ERA
E) Practical ops playbooks (desktop SoftDent Excel/Print Preview vs inventing $)
F) THE single best NEXT package for NR2 now (HAL-style), given 10604 just shipped
G) What NOT to do (over-match aliases, fake usable cells, SoftDent write-back)

OUTPUT (strict markdown):
# Verdict (one sentence — biggest industry lever for this program now)
## 0. Operator Intent (verbatim)
## 1. Industry map for SoftDent RCM (carriers / Blues / Delta / MA / Medicaid /
    federal / TPA-ASO / employer-union / discount — what each means for TP $)
## 2. SoftDent office realities (company master pollution, claim address names,
    plan-year junk rows, ASO shells, how other offices keep masters clean)
## 3. Rebrand / acquisition cheat sheet (still actionable vs this spine)
## 4. Leftover 77 rejected — industry triage categories + any NEW HIGH you dare
    (only if spine target exists; else NONE). Do not force-match.
## 5. Gold / ERA / Register — industry truth of what files unlock what estimates
## 6. Treatment-planning honesty doctrine (empty≠$0; when % vs $; secondary ins)
## 7. Recommended NEXT package (ONE) — name, why now, effort, validation gate
## 8. Runner-ups (2–3)
## 9. What NOT to redo
## 10. Acceptance criteria if operator says proceed on §7
## 11. Executive Summary (7 bullets max)
## 12. Approval checklist
DO NOT APPLY CODE.
"""


def _live_snapshot() -> str:
    sys.path.insert(0, str(NR2))
    live: dict = {"buildExpected": "hal-10604", "operatorAsk": OPERATOR_REQUEST_VERBATIM}
    try:
        from apex_backend import BUILD_ID
        from softdent_carrier_alias import carrier_alias_status, list_spine_carriers
        from softdent_treatment_planning import resolve_analytics_db

        live["buildId"] = BUILD_ID
        st = carrier_alias_status()
        live["aliasStatus"] = {
            k: st.get(k)
            for k in (
                "autoAccepted",
                "manualPending",
                "rejected",
                "totalRows",
                "acceptanceGateMet",
                "likelyActiveNotInSpine",
                "spineCarriers",
            )
        }
        db = resolve_analytics_db()
        live["dbPath"] = str(db)
        spine = list_spine_carriers(db_path=db)
        live["spine"] = spine
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            live["rejected"] = [
                r[0]
                for r in con.execute(
                    """
                    SELECT master_company_name FROM carrier_alias
                    WHERE confidence='reject' OR review_status='rejected'
                    ORDER BY master_company_name
                    """
                )
            ]
            live["pending"] = [
                r[0]
                for r in con.execute(
                    """
                    SELECT master_company_name FROM carrier_alias
                    WHERE confidence='manual' AND review_status='pending'
                    ORDER BY master_company_name
                    """
                )
            ]
            live["industryHigh"] = [
                {"master": a, "spine": b}
                for a, b in con.execute(
                    """
                    SELECT master_company_name, spine_carrier_name FROM carrier_alias
                    WHERE match_method='moonshot_industry' AND review_status='accepted'
                    ORDER BY master_company_name
                    """
                )
            ]
            live["paymentLines"] = int(
                con.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
                or 0
            )
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:22000]


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
        ("MOONSHOT_APPLIED_HAL10604_MOONSHOT_INDUSTRY_ALIAS_2026-07-13.md", 2500),
        ("MOONSHOT_REJECTED_CARRIER_ALIAS_COMPLETE_2026-07-13.md", 3500),
        ("MOONSHOT_APPLIED_HAL10603_HONESTY_CI_2026-07-13.md", 1500),
        ("MOONSHOT_APPLIED_HAL10601_TP_CARRIER_ALIAS_2026-07-13.md", 1500),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Unload your full dental-insurance industry knowledge that helps THIS SoftDent "
        "NR2 program. CONSULT ONLY — pick ONE next package after the industry dump.\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n"
        + "\n\n".join(excerpts)
    )

    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 16000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Dental Insurance Industry Knowledge Consult"
    print("Calling Moonshot AI (dental insurance industry knowledge — consult only)...")

    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=1200) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(raw)
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        content = str(exc)
        status = "error"
        raw = {"error": content}
        try:
            if isinstance(exc, urllib.error.HTTPError) and exc.fp is not None:
                body = exc.read().decode("utf-8", errors="replace")
                raw = {"error": content, "body": body}
                content = f"{content}\n{body}"
        except Exception:
            pass

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (OUT / f"moonshot_dental_insurance_industry_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — Dental Insurance Industry Knowledge "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10604  \n"
        f"**Script:** `scripts/run_moonshot_dental_insurance_industry_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_DENTAL_INSURANCE_INDUSTRY_KNOWLEDGE_{DATE}.md"
    out = OUT / f"MOONSHOT_DENTAL_INSURANCE_INDUSTRY_KNOWLEDGE_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
