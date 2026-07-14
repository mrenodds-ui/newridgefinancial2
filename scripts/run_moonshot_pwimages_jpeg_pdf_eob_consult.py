"""Moonshot AI — Mine PWImages EOBs (JPEG/PDF focus) CONSULT ONLY.

Operator: have moonshot ai mine c:\\softdent\\pwimage for eob. most were either
jpeg or pdf files and consult
"""

from __future__ import annotations

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
PW = Path(r"C:\SoftDent\PWImages")
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
    "have moonshot ai mine c:\\softdent\\pwimage for eob. most were either "
    "jpeg or pdf files and consult"
)

SYSTEM = """You are Moonshot AI — principal dental RCM / SoftDent financial engineer
for NR2 Apex HAL (BUILD_ID=hal-10607).

CONSULT ONLY — DO NOT claim you applied code or mutated the DB.
empty ≠ $0. No SoftDent write-back. Do NOT invent InsCo×ADA / Gold / Register $.
Prefer NONE / insufficient over wrong $.

OPERATOR BELIEF: SoftDent PWImages EOBs are mostly JPEG or PDF.
LIVE FACTS (already inventoried + OCR-mined — do not ignore):
- Path is C:\\SoftDent\\PWImages (not pwimage).
- Extension census: ~91,004 .JPG · ~62,007 .mht · ~2,307 .HTM · ~201 .pdf
- ALL 201 PDFs are Check-In_Package_* forms — ZERO remittance EOB PDFs found.
- Remittance EOB lane that worked: NonPatient\\Account\\*.JPG (~2,641) + 5 Claim JPGs.
- Patient\\*\\Other\\*.JPG (~88k) are mixed clinical/scans — OCR of all is ROI-poor.
- MHTs are Carestream eForms (consent/history) — not remittance EOBs.
- HTMs are mostly portal Eligibility Benefits (plan design, not remittance).
- Prior mine (Tesseract on Account/Claim JPGs + HTM classify):
  REMITTANCE_EOB 8 + CANDIDATE 8 (=16 remittance hits), ELIGIBILITY 2276,
  INSURANCE_RELATED ~2.2k among classified rows.
- HAL-10607 ALREADY SHIPPED: eligibility staging + remittance path warehouse
  (no OCR $ into settlement/Gold). Fuzzy match ~93% on eligibility.

YOUR JOB (consult):
A) Correct the JPEG/PDF mental model with PWImages reality
B) Where true remittance EOBs actually live (JPEG Account lane vs PDF myth)
C) Whether to OCR more Patient JPGs / any PDF path — ROI vs honesty
D) THE ONE next package after HAL-10607 for JPEG/PDF EOB mining — or
   explicitly say STOP OCR expansion and stay on Gold/ERA
E) What NOT to do

OUTPUT (strict markdown):
# Verdict (one sentence)
## 0. Operator Intent (verbatim)
## 1. JPEG / PDF reality check vs operator expectation
## 2. Where remittance EOBs actually are in PWImages
## 3. Recommended NEXT (ONE package) — name, why, effort, files, gate
## 4. Relation to HAL-10607 / Gold CSV / ERA 835
## 5. Honesty rules for any further JPEG/PDF OCR $
## 6. Runner-ups (2–3)
## 7. What NOT to do
## 8. Acceptance criteria if proceed on §3
## 9. Executive Summary (7 bullets max)
## 10. Approval checklist
DO NOT APPLY CODE.
"""


def _inventory() -> dict:
    snap: dict = {"root": str(PW), "exists": PW.is_dir()}
    if not PW.is_dir():
        return snap
    ext: Counter[str] = Counter()
    pdf_names: list[str] = []
    for p in PW.rglob("*"):
        if not p.is_file():
            continue
        e = p.suffix.lower() or "(none)"
        ext[e] += 1
        if e == ".pdf":
            pdf_names.append(p.name)
    snap["extensions"] = dict(ext.most_common())
    snap["pdfCount"] = len(pdf_names)
    snap["pdfCheckInCount"] = sum(
        1 for n in pdf_names if "check-in" in n.lower() or "check_in" in n.lower()
    )
    snap["pdfNonCheckInSamples"] = [
        n for n in pdf_names if "check-in" not in n.lower() and "check_in" not in n.lower()
    ][:20]
    acct = PW / "NonPatient" / "Account"
    claim = PW / "NonPatient" / "Claim"
    snap["accountJpgs"] = sum(1 for _ in acct.rglob("*.JPG")) if acct.is_dir() else 0
    snap["claimJpgs"] = sum(1 for _ in claim.rglob("*.JPG")) if claim.is_dir() else 0
    return snap


def _mine_summary() -> dict:
    p = MINE / "eob_mine_summary.json"
    if not p.is_file():
        return {"missing": True}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _live() -> dict:
    live: dict = {"buildExpected": "hal-10607"}
    try:
        sys.path.insert(0, str(NR2))
        from apex_backend import BUILD_ID
        from softdent_treatment_planning import resolve_analytics_db

        live["buildId"] = BUILD_ID
        db = resolve_analytics_db()
        live["dbPath"] = str(db)
        if db and Path(db).is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                def _c(t: str) -> int | None:
                    try:
                        return int(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] or 0)
                    except Exception:
                        return None

                live["paymentLines"] = _c("sd_insurance_payment_lines")
                live["stagingEligibility"] = _c("staging_eligibility_parameters")
                live["warehouseRemittance"] = _c("warehouse_remittance_eobs")
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

    inventory = _inventory()
    mine = _mine_summary()
    live = _live()

    excerpts = []
    for name, lim in (
        ("MOONSHOT_APPLIED_HAL10607_PWIMAGES_ELIGIBILITY_PLAN_BRIDGE_2026-07-13.md", 3000),
        ("MOONSHOT_PWIMAGES_EOB_MINE_CONSULT_2026-07-13.md", 3500),
        ("MOONSHOT_DENTAL_INSURANCE_INDUSTRY_KNOWLEDGE_2026-07-13.md", 2000),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CONSULT ONLY. Operator thinks EOBs are mostly JPEG/PDF — validate against "
        "live PWImages inventory + prior OCR mine + HAL-10607 already applied. "
        "Pick THE one next package (or STOP further OCR).\n\n"
        f"## PWIMAGES INVENTORY\n{json.dumps(inventory, indent=2)[:12000]}\n\n"
        f"## PRIOR MINE SUMMARY\n{json.dumps(mine, indent=2)[:8000]}\n\n"
        f"## PROGRAM LIVE\n{json.dumps(live, indent=2)[:6000]}\n\n"
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
        headers["X-Title"] = "NR2 PWImages JPEG/PDF EOB Mine Consult"
    print("Calling Moonshot AI (PWImages JPEG/PDF EOB mine — consult only)...")

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
    (OUT / f"moonshot_pwimages_jpeg_pdf_eob_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — PWImages JPEG/PDF EOB Mine "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {live.get('buildId') or 'hal-10607'}  \n"
        f"**Script:** `scripts/run_moonshot_pwimages_jpeg_pdf_eob_consult.py`  \n"
        f"**PWImages:** `C:\\SoftDent\\PWImages`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_PWIMAGES_JPEG_PDF_EOB_CONSULT_{DATE}.md"
    out = OUT / f"MOONSHOT_PWIMAGES_JPEG_PDF_EOB_CONSULT_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
