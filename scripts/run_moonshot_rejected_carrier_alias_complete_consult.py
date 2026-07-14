"""Moonshot AI — Complete rejected carrier-alias list (CONSULT ONLY).

Operator: now use moonshot ai with all his powers and vast web resources and
his knowledge of other dental offices see if he can complete the list and consult
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
    "now use moonshot ai with all his powers and vast web resources and his "
    "knowledge of other dental offices see if he can complete the list and consult"
)

SYSTEM = """You are Moonshot AI — principal dental RCM / SoftDent financial engineer
with deep knowledge of US dental insurance payers as seen across many general
and specialty practices (Midwest / national). You know common SoftDent insurance-
company master naming quirks, TPA/ASO shells, rebrands, and claim-route aliases.

CONSULT ONLY — DO NOT claim you applied code or mutated the DB.
empty != $0. No SoftDent write-back. Do NOT invent InsCo×ADA settlement dollars.
An accepted alias only reuses EXISTING spine settlement $. Wrong alias = wrong $.

MISSION:
Complete as much of the REJECTED company-master list as honesty allows by mapping
each rejected master name → exactly one name from the SPINE LIST (SoftDent
settlement carriers already in this practice's ledger). Use:
- dental-office payer identity knowledge (rebrands, claim processors, common
  SoftDent abbreviations)
- industry truth (Assurant dental → Sun Life; MetLife variants → METLIFE DENTAL;
  UniCare → Anthem family when appropriate; Great-West → Empower/Great-West
  history; etc.)
- only when the target is IN THE SPINE LIST as written (exact string match)

HONESTY BANDS (required on every row):
- HIGH — industry identity clear; safe to accept as manual alias
- MEDIUM — plausible SoftDent/office alias; needs operator glance
- LOW — speculative; do NOT auto-apply
- NONE — no honest spine partner (TPA-only, employer self-funded unnamed,
  discontinued niche, or spine lacks that payer). Keep rejected.

HARD RULES:
1) spine_carrier_name MUST be copied EXACTLY from the SPINE LIST or left blank.
2) Never invent a spine name that is not in the list.
3) Prefer NONE over a wrong HIGH. Assurant≠Aflac. Bankers≠EBMS. Beauty First≠BCBS.
4) ASO / "Administrative Services Only" / Claim Management shells → NONE unless
   a named payer is inside the master string AND that payer is on spine.
5) Employer plans (Tyson Foods, Wichita Police, Haskell, Meyers Bakery) → NONE
   unless spine has that exact plan name.
6) Already-accepted weak manuals (First Health/Guardian→GUARDIAN; Preferred Plus
   Of Ks→PEQUOT; Kansas City Life→BCBS OF KANSAS CITY) are DONE — do not redo.
7) Met Life / Met Life/dental / Met Life/Pepsico → METLIFE DENTAL if on spine.
8) Do not recommend inventing gold or lowering InsCo×ADA floors.

ALSO recommend THE single best NEXT package after this consult (HAL-style),
knowing honesty CI (HAL-10603) already shipped and aliases are partially complete.

OUTPUT (strict markdown):
# Verdict (one sentence — can we complete the list? how many HIGH/MEDIUM?)
## 0. Operator Intent (verbatim)
## 1. Method (how you used dental-office / industry knowledge; limits of no live SoftDent)
## 2. Completed mapping table
For EVERY rejected master, one row:
| master | spine (exact or blank) | band (HIGH/MEDIUM/LOW/NONE) | rationale (1 short clause) |
## 3. Apply package proposal (HAL-10604?)
- Which bands to accept on `proceed` (recommend: HIGH only, or HIGH+MEDIUM)
- How to store (confidence=manual, review_status=accepted, match_method=moonshot_industry)
- Validation gate (TP probe sample; honesty CI still green; Excel refresh)
## 4. Still NONE / keep rejected (count + categories)
## 5. Recommended NEXT after apply (single package)
## 6. What NOT to redo
## 7. Acceptance criteria
## 8. Executive Summary (5 bullets)
## 9. Approval checklist
DO NOT APPLY CODE.
"""


def _payload_lists() -> tuple[list[dict], list[str], dict]:
    sys.path.insert(0, str(NR2))
    from softdent_carrier_alias import carrier_alias_status, list_spine_carriers
    from softdent_treatment_planning import resolve_analytics_db

    db = resolve_analytics_db()
    spine = list_spine_carriers(db_path=db)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rejected = [
            {"id": str(mid or ""), "name": str(name)}
            for name, mid in con.execute(
                """
                SELECT master_company_name, master_company_id
                FROM carrier_alias
                WHERE confidence='reject' OR review_status='rejected'
                ORDER BY master_company_name
                """
            ).fetchall()
        ]
        accepted_n = int(
            con.execute(
                "SELECT COUNT(*) FROM carrier_alias WHERE review_status='accepted'"
            ).fetchone()[0]
            or 0
        )
    finally:
        con.close()
    st = carrier_alias_status()
    meta = {
        "rejectedCount": len(rejected),
        "spineCount": len(spine),
        "acceptedCount": accepted_n,
        "status": {
            k: st.get(k)
            for k in (
                "autoAccepted",
                "manualPending",
                "rejected",
                "likelyActiveNotInSpine",
                "acceptanceGateMet",
                "totalRows",
            )
        },
        "alreadyAcceptedWeakManuals": [
            "First Health/Guardian → GUARDIAN LIFE INSURANCE CO.",
            "Preferred Plus Of Ks → PEQUOT PLUS HEALTH - 3620",
            "Kansas City Life Insurance → BCBS OF KANSAS CITY",
        ],
        "honestyNote": "Force token_set unblock of all 89 was attempted then REVERTED (unsafe).",
        "buildExpected": "hal-10603",
    }
    return rejected, spine, meta


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

    rejected, spine, meta = _payload_lists()
    rej_block = "\n".join(f"{r['id']}\t{r['name']}" for r in rejected)
    spine_block = "\n".join(spine)

    excerpts = []
    for name, lim in (
        ("MOONSHOT_APPLIED_HAL10600_CARRIER_ALIAS_2026-07-13.md", 2500),
        ("MOONSHOT_APPLIED_HAL10601_TP_CARRIER_ALIAS_2026-07-13.md", 2000),
        ("MOONSHOT_APPLIED_HAL10603_HONESTY_CI_2026-07-13.md", 1500),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Use your full dental-payer / multi-office SoftDent knowledge to complete "
        "the REJECTED alias list against THIS practice's SPINE only. CONSULT ONLY.\n\n"
        f"## META\n{json.dumps(meta, indent=2)}\n\n"
        f"## REJECTED MASTERS ({len(rejected)}) — map each\n{rej_block}\n\n"
        f"## SPINE LIST ({len(spine)}) — ONLY allowed targets\n{spine_block}\n\n"
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
        headers["X-Title"] = "NR2 Rejected Carrier Alias Complete Consult"
    print(
        f"Calling Moonshot AI (complete {len(rejected)} rejected aliases — consult only)..."
    )

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
    (OUT / f"moonshot_rejected_alias_complete_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    (OUT / f"moonshot_rejected_alias_complete_user_{stamp}.txt").write_text(
        user, encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — Complete Rejected Carrier Aliases "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Rejected in scope:** {len(rejected)}  \n"
        f"**Spine targets:** {len(spine)}  \n"
        f"**Script:** `scripts/run_moonshot_rejected_carrier_alias_complete_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_REJECTED_CARRIER_ALIAS_COMPLETE_{DATE}.md"
    out = OUT / f"MOONSHOT_REJECTED_CARRIER_ALIAS_COMPLETE_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
