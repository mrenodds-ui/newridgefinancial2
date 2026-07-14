"""Moonshot AI — What to do with PWImages dental insurance EOB mine (CONSULT ONLY).

Operator: we just mined c:\\softdent\\pwimages for all insurance eobs, ask moonshot
ai what he wants to do with these in the program and consult.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
NR2 = REPO / "NewRidgeFinancial2"
MINE = DOCS / "_pwimages_eob_mine"
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
    "we just mined c:\\softdent\\pwimages for all insurance eobs, ask moonshot ai "
    "what he wants to do with these in the program and consult"
)

SYSTEM = """You are Moonshot AI — principal dental RCM / SoftDent financial engineer
for NR2 Apex HAL (BUILD_ID=hal-10606).

CONSULT ONLY — DO NOT claim you applied code or mutated the DB.
empty ≠ $0. No SoftDent write-back. Do NOT invent InsCo×ADA settlement dollars,
gold payment lines, or Register collections. Prefer NONE / insufficient over wrong $.

CONTEXT — JUST COMPLETED (operator):
Mined C:\\SoftDent\\PWImages for dental insurance documents via Tesseract OCR +
heuristic classify. Script:
  NewRidgeFinancial2/scripts/mine_pwimages_dental_eobs.py
Outputs:
  NewRidgeFinancial2/docs/_pwimages_eob_mine/
    eob_mine_summary.json, eob_mine_all.json/csv,
    remittance_eobs.csv, remittance_eobs/ (copied hits)

PWImages shape (facts):
- ~155k Patient files: almost all under category folder Other
- ~62k MHT = Carestream eForms (consent/history/privacy) — EXCLUDED from OCR
- ~2.3k HTM = mostly portal Eligibility/Benefits dumps (NOT remittance EOBs)
- ~2.6k NonPatient/Account JPGs = scanned insurance lane (PRIMARY OCR corpus)
- 5 Claim JPGs
- Categories used: REMITTANCE_EOB, REMITTANCE_EOB_CANDIDATE,
  ELIGIBILITY_BENEFITS, INSURANCE_CARD, CLAIM_OR_LEDGER, INSURANCE_RELATED, OTHER

PROGRAM STATE (do not redo as greenfield):
- Ledger InsCo×ADA spine + TP estimates + carrier alias (HAL-10600/10601/10604)
- Gold CSV still missing: sd_insurance_payment_lines=0
- Exact usable InsCo×ADA cells still thin (~46)
- ERA/835 ingest + EOB match backlog widgets already exist (paper EOBs ≠ ERA)
- Moonshot industry consult already said: prefer Gold CSV / 835 over OCR EOB
  pipelines as the primary settlement truth path
- document_classifier already has EOB_ERA heuristic + vision path

OPERATOR ASK:
What do YOU want to do with these mined PWImages insurance EOBs / related docs
INSIDE this program? Consult — pick THE single best next package that uses this
mine (or honestly says: warehouse only / do not over-invest in OCR).

YOUR JOB (consult):
A) Triage what the mine actually produced (remittance vs eligibility vs cards)
B) What value each class has for NR2 (TP estimates, alias, posting backlog, ERA)
C) THE ONE next package (HAL-style name) that should consume this mine — or
   explicitly recommend NOT wiring OCR into settlement yet
D) How this intersects Gold CSV / ERA 835 (complement vs substitute)
E) Honesty doctrine for any OCR-derived $ (empty≠$0; OCR≠posted truth)
F) Runner-ups and what NOT to do

OUTPUT (strict markdown):
# Verdict (one sentence — what Moonshot wants done with this mine NOW)
## 0. Operator Intent (verbatim)
## 1. Mine triage (what we actually have vs what staff call "EOBs")
## 2. Program value by document class (remittance / eligibility / card / other)
## 3. Recommended NEXT package (ONE) — name, why now, effort, real files, gate
## 4. How this relates to Gold CSV and ERA/835 (complement vs substitute)
## 5. Honesty / safety rules if any OCR $ ever surfaces in UI
## 6. Runner-ups (2–3)
## 7. What NOT to do
## 8. Acceptance criteria if operator says proceed on §3
## 9. Executive Summary (7 bullets max)
## 10. Approval checklist
DO NOT APPLY CODE.
"""


def _mine_snapshot() -> dict:
    snap: dict = {"mineDir": str(MINE)}
    summary_path = MINE / "eob_mine_summary.json"
    if summary_path.is_file():
        try:
            snap["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            snap["summaryError"] = str(exc)

    all_path = MINE / "eob_mine_all.json"
    if all_path.is_file():
        try:
            rows = json.loads(all_path.read_text(encoding="utf-8"))
            snap["totalRows"] = len(rows)
            snap["byLane"] = dict(Counter(r.get("lane") for r in rows))
            acct = Counter()
            carriers = Counter()
            for r in rows:
                if r.get("lane") in ("account", "claim"):
                    acct[r.get("category") or "?"] += 1
                for c in r.get("carriers") or []:
                    carriers[str(c).lower()] += 1
            snap["accountClaimByCategory"] = dict(acct.most_common())
            snap["topCarriers"] = dict(carriers.most_common(20))
        except Exception as exc:  # noqa: BLE001
            snap["allError"] = str(exc)

    remit_csv = MINE / "remittance_eobs.csv"
    samples: list[dict] = []
    if remit_csv.is_file():
        with remit_csv.open(encoding="utf-8", newline="") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if i >= 20:
                    break
                samples.append(
                    {
                        "category": row.get("category"),
                        "confidence": row.get("confidence"),
                        "account_or_claim_id": row.get("account_or_claim_id"),
                        "carriers": row.get("carriers"),
                        "markers": row.get("markers"),
                        "preview": (row.get("ocr_preview") or "")[:220],
                        "path": row.get("path"),
                    }
                )
    snap["remittanceSamples"] = samples
    return snap


def _live_program_snapshot() -> dict:
    live: dict = {"buildExpected": "hal-10606"}
    try:
        sys.path.insert(0, str(NR2))
        from apex_backend import BUILD_ID
        from softdent_treatment_planning import resolve_analytics_db

        live["buildId"] = BUILD_ID
        db = resolve_analytics_db()
        live["dbPath"] = str(db)
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            def _count(table: str) -> int | None:
                try:
                    return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
                except Exception:
                    return None

            live["paymentLines"] = _count("sd_insurance_payment_lines")
            live["settlementMatrix"] = _count("settlement_matrix")
            live["carrierAlias"] = _count("carrier_alias")
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return live


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

    mine = _mine_snapshot()
    live = _live_program_snapshot()

    excerpts = []
    for name, lim in (
        ("MOONSHOT_DENTAL_INSURANCE_INDUSTRY_KNOWLEDGE_2026-07-13.md", 3500),
        ("MOONSHOT_SOFTDENT_COMPREHENSIVE_INGEST_HAL_2026-07-13.md", 2500),
        ("MOONSHOT_HAL_SAID_IMPROVE_FIX_CONSULT_2026-07-11.md", 2000),
        ("MOONSHOT_EXPERT_SE_FIRST_CLASS_PROGRAM_2026-07-13.md", 2000),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CONSULT ONLY — tell us what YOU want done with this PWImages EOB mine "
        "in the NR2 program. Pick ONE next package.\n\n"
        f"## MINE SNAPSHOT\n{json.dumps(mine, indent=2)[:18000]}\n\n"
        f"## PROGRAM LIVE SNAPSHOT\n{json.dumps(live, indent=2)[:8000]}\n\n"
        + "\n\n".join(excerpts)
    )

    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 12000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 PWImages EOB Mine Consult"
    print("Calling Moonshot AI (PWImages EOB mine — consult only)...")

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
    (OUT / f"moonshot_pwimages_eob_mine_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — PWImages Dental Insurance EOB Mine "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {live.get('buildId') or 'hal-10604+'}  \n"
        f"**Script:** `scripts/run_moonshot_pwimages_eob_mine_consult.py`  \n"
        f"**Mine:** `NewRidgeFinancial2/docs/_pwimages_eob_mine/`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_PWIMAGES_EOB_MINE_CONSULT_{DATE}.md"
    out = OUT / f"MOONSHOT_PWIMAGES_EOB_MINE_CONSULT_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
