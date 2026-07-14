"""Moonshot AI — What's next after Outstanding Claims by Carrier Bridge (HAL-10580).

CONSULT ONLY. Operator: next.
"""

from __future__ import annotations

import json
import os
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

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL + SoftDent.

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes when OPS is blocked on missing real files.
Avoid GitHub/PR as the primary package.
Do not invent fictional paths — only REAL paths below.
empty != $0. Never invent SoftDent write-back, Ins Plan dollars, or carrier names.
Do NOT redo HAL-10580 bridge, Regular Collections ingest, production max-merge,
or Register re-export for Ins Plan > 0.

JUST COMPLETED (33d6917 — Outstanding Claims by Carrier Bridge / HAL-10580):
- Account Aging ↔ sd_claims by payer bridge live
- Live: AR $49,111.03; aging outstanding insurance $0.00; sd_claims ~61
  (mostly unnamed "Insurance"); gapCode=CLAIMS_PAYER_ATTRIBUTION_REQUIRED
- HAL policy + SoftDent widget + outstanding_claims_by_co promoted
- Prior: Regular Collections DEF-001; no-reexport 10578; production honesty 10579
- ERA discovery still typically 0; Ins Plan $0 truth stands

OPEN CANDIDATES (pick ONE highest leverage NOW):
1) CODE/OPS: Refresh SoftDent ODBC claims with NAMED payers +/or populate
   sd_patient_insurance so CLAIMS_PAYER_ATTRIBUTION_REQUIRED can clear —
   only if REAL extract path / env queries exist and live snapshot shows
   sd_patient_insurance empty or claims mostly unnamed (it does).
2) CODE: Phase-2 production_by_provider Excel ingest + Register reconcile
   (hal-10579 production authority already shipped).
3) OPS: ERA-835 procurement playbook — ONLY if REAL in-repo portal SOPs exist;
   else say evidence insufficient.
4) CODE: Deposit slip / collection_reconciliation Phase-2 wiring — lower than
   named-payer unblock if attribution is the active gap.
5) CODE: Small HAL report composition that stitches Register + Aging + Claims
   bridge into one "practice brief" — only if REAL HAL compose helpers exist
   and would not invent missing ERA dollars.

What NOT to redo: 10580 bridge itself, invent carriers, invent Ins Plan $,
Register re-export, account-tx year chunks, 10571/10575/10576, SoftDent write-back.

REAL PATHS:
- NewRidgeFinancial2/softdent_outstanding_claims_bridge.py
- NewRidgeFinancial2/softdent_odbc_extract.py
- NewRidgeFinancial2/softdent_master_reports.json
- NewRidgeFinancial2/nr2_hal_gateway.py
- C:\\SoftDentReportExports\\account_aging.csv
- C:\\SoftDentFinancialExports\\softdent_financial_analytics.db
- app_data/nr2/document_inbox/softdent/softdent_outstanding_claims_by_carrier.json
- NewRidgeFinancial2/docs/MOONSHOT_OUTSTANDING_CLAIMS_BRIDGE_HAL10580_APPLIED_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_SOFTDENT_COMPREHENSIVE_INGEST_HAL_2026-07-13.md

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
        from apex_backend import BUILD_ID  # noqa: E402

        live["buildId"] = BUILD_ID
        live["prior"] = "33d6917 HAL-10580 outstanding claims by carrier bridge"
        from softdent_outstanding_claims_bridge import (  # noqa: E402
            build_outstanding_claims_by_carrier_bridge,
        )

        bridge = build_outstanding_claims_by_carrier_bridge(write_inbox=False)
        live["bridge"] = {
            "gapCode": bridge.get("gapCode"),
            "suggestedAction": bridge.get("suggestedAction"),
            "aging": {
                k: (bridge.get("aging") or {}).get(k)
                for k in (
                    "trueReceivablesTotal",
                    "outstandingInsuranceTotal",
                    "accountCount",
                    "ok",
                )
            },
            "claims": {
                k: (bridge.get("claims") or {}).get(k)
                for k in (
                    "claimCount",
                    "namedPayerClaimCount",
                    "unnamedPayerClaimCount",
                    "billedTotal",
                    "ok",
                )
            },
            "reconcileIssues": ((bridge.get("reconcile") or {}).get("issues") or [])[:4],
        }
        import sqlite3

        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                live["sd_patient_insurance_count"] = con.execute(
                    "SELECT COUNT(*) FROM sd_patient_insurance"
                ).fetchone()[0]
                live["sd_claims_count"] = con.execute(
                    "SELECT COUNT(*) FROM sd_claims"
                ).fetchone()[0]
            except Exception as exc:  # noqa: BLE001
                live["dbError"] = f"{type(exc).__name__}:{exc}"
            finally:
                con.close()
        try:
            from apex_era835_pack import discover_era_candidates, scan_era_inbox

            live["eraInbox"] = {
                k: scan_era_inbox(ensure_dirs=True).get(k)
                for k in ("empty", "fileCount", "chipLabel")
            }
            disc = discover_era_candidates(limit=8, max_depth=3)
            live["eraDiscovery"] = {
                k: disc.get(k) for k in ("candidateCount", "chipLabel")
            }
        except Exception as exc:  # noqa: BLE001
            live["eraError"] = f"{type(exc).__name__}:{exc}"
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:9000]


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
        ("MOONSHOT_OUTSTANDING_CLAIMS_BRIDGE_HAL10580_APPLIED_2026-07-13.md", 2400),
        ("MOONSHOT_SOFTDENT_COMPREHENSIVE_INGEST_HAL_2026-07-13.md", 2000),
        ("MOONSHOT_SOFTDENT_INSURANCE_EXTRACT_APPLIED_2026-07-11.md", 1400),
        ("MOONSHOT_PRODUCTION_MAX_MERGE_HONESTY_HAL10579_APPLIED_2026-07-13.md", 1000),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "HAL-10580 just shipped; live gap is CLAIMS_PAYER_ATTRIBUTION_REQUIRED "
        "(sd_patient_insurance empty; claims mostly unnamed). "
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
        headers["X-Title"] = "NR2 Whats Next After Outstanding Claims Bridge 10580"
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
    (OUT / f"moonshot_whats_next_after_claims_bridge_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After Outstanding Claims Bridge (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** Outstanding Claims by Carrier Bridge (`33d6917` / HAL-10580)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_claims_bridge_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_CLAIMS_BRIDGE_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_CLAIMS_BRIDGE_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
