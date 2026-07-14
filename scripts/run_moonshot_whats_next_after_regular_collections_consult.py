"""Moonshot AI — What's next after DEF-001 Regular Collections ingest (hal-10577).

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
Do NOT recommend re-exporting SoftDent Register hoping Ins Plan > 0 —
July OPS confirmed Ins Plan Collections = $0.00 is SoftDent ground truth.
Do NOT recommend re-ingesting Regular Collections — that just shipped (fc2f5aa).

JUST COMPLETED (fc2f5aa — DEF-001 Regular Collections ingest / package hal-10577):
- SoftDent Regular Collections $30,626.42 → July patient / regularCollections
- Ins Plan stays $0.00; collectionsGapCode=ERA_835_REQUIRED; healthy=False
- Widget: Regular Collections: Complete ($30,626.42) · Insurance ERA Required
- Stale CSV can no longer clobber Register XLS Regular; REG\\d{6} inbox match
- Doc: MOONSHOT_REGULAR_COLLECTIONS_DEF001_APPLIED_2026-07-13.md
- Prior OPS: Ins Plan $0 confirmed; account-tx track done; ERA discovery=0
- Collections Excel-temp 10576; ERA honesty UX 10571; discovery 10575 live

OPEN CANDIDATES (pick ONE highest leverage NOW):
1) OPS: Concrete payer-portal / clearinghouse 835 acquisition playbook —
   NOW evidence-backed (Regular complete; Ins Plan=$0; discovery=0). Prefer
   SPECIFIC steps citing REAL repo docs/paths for Delta/MetLife/Availity/
   SoftDent ERA menus if present; otherwise say evidence is insufficient and
   pick the next CODE package that unblocks operators while procurement waits.
2) CODE: Browser smoke for Regular-complete + ERA-required gap tile / HAL —
   only if a REAL smoke harness exists in-repo.
3) CODE: Align July production max-merge honesty if live production drifted
   above Register (optional hygiene) — only if live snapshot shows a real
   distortion vs Register production.
4) OPS: Real QuickBooks payroll/AP export drop — staff real files only
5) CODE: Small HAL phrase polish for "Regular Complete · ERA Required" —
   only if live HAL/policy still pushes Register re-export (it should NOT)

What NOT to redo: Regular Collections ingest, July Register re-export for Ins
Plan, invent Ins/Patient split, account-tx year chunks/HAL/chip, 10571/10575/
10576, SoftDent write-back, synthetic 835s.

REAL PATHS:
- C:\\SoftDentReportExports\\REG202607.XLS
- app_data/nr2/document_inbox/softdent/softdent_dashboard_data.json
- NewRidgeFinancial2/docs/MOONSHOT_REGULAR_COLLECTIONS_DEF001_APPLIED_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_JULY_REGISTER_INSPLAN_OPS_RESULT_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_ERA_REMITTANCE_DISCOVERY_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_ERA835_FIRST_DROP_OPS_APPLIED_2026-07-12.md
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/apex_era835_pack.py
- scripts/run_era_inbox_ingest_ops.py
- C:\\SoftDentFinancialExports
- C:\\NR2\\ERA_INBOX (or whatever live discovery roots report)

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
        from apex_backend import BUILD_ID, _load_reports_and_bundle  # noqa: E402
        from apex_softdent_hardening_pack import (  # noqa: E402
            assess_collections_gap,
            collections_gap_widget,
        )
        from apex_era835_pack import discover_era_candidates, scan_era_inbox  # noqa: E402

        live["buildId"] = BUILD_ID
        live["prior"] = (
            "fc2f5aa Regular Collections DEF-001: patient=$30626.42 Ins Plan=$0; "
            "widget Regular Complete · ERA Required; discovery candidates=0"
        )
        _r, bundle, _e = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        live["gap"] = {
            k: gap.get(k)
            for k in (
                "gapCode",
                "collectionsGapCode",
                "registerInsPlanZero",
                "insurance",
                "patient",
                "regularCollections",
                "collections",
                "production",
                "period",
                "collectionsFormatRequired",
                "healthy",
            )
        }
        w = collections_gap_widget(bundle)
        live["widget"] = {
            k: w.get(k)
            for k in ("message", "eraDiscoverLabel", "eraInboxIngestLabel", "status")
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
        dash = (
            REPO
            / "app_data"
            / "nr2"
            / "document_inbox"
            / "softdent"
            / "softdent_dashboard_data.json"
        )
        if dash.is_file():
            rows = json.loads(dash.read_text(encoding="utf-8-sig"))
            jul = next((r for r in rows if str(r.get("period") or "")[:7] == "2026-07"), None)
            live["julyDashboardRow"] = {
                k: (jul or {}).get(k)
                for k in (
                    "period",
                    "production",
                    "collections",
                    "insurance",
                    "patient",
                    "regularCollections",
                    "registerInsPlanZero",
                )
            }
        reg = Path(r"C:\SoftDentReportExports\REG202607.XLS")
        live["reg202607"] = {
            "exists": reg.is_file(),
            "bytes": reg.stat().st_size if reg.is_file() else 0,
        }
        try:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(
                "https://127.0.0.1:8765/api/apex/hal/era-inbox/discover",
                timeout=15,
                context=ctx,
            ) as resp:
                live["liveDiscoverApi"] = {
                    k: json.loads(resp.read().decode("utf-8")).get(k)
                    for k in ("ok", "candidateCount", "chipLabel", "buildId")
                }
        except Exception as exc:  # noqa: BLE001
            live["liveDiscoverApiError"] = f"{type(exc).__name__}:{exc}"
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
        ("MOONSHOT_REGULAR_COLLECTIONS_DEF001_APPLIED_2026-07-13.md", 2400),
        ("MOONSHOT_JULY_REGISTER_INSPLAN_OPS_RESULT_2026-07-13.md", 1800),
        ("MOONSHOT_ERA_REMITTANCE_DISCOVERY_APPLIED_2026-07-12.md", 1400),
        ("MOONSHOT_ERA835_FIRST_DROP_OPS_APPLIED_2026-07-12.md", 1400),
        ("MOONSHOT_WHATS_NEXT_AFTER_JULY_INSPLAN_OPS_2026-07-13.md", 1600),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Regular Collections DEF-001 just shipped (patient=$30626.42). "
        "Ins Plan=$0 truth stands. ERA discovery still 0. "
        "Do NOT re-ingest Regular or re-export Register. Pick THE next package. "
        "CONSULT ONLY.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After Regular Collections DEF001"
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
    (OUT / f"moonshot_whats_next_after_regular_collections_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After Regular Collections DEF-001 (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** Regular Collections DEF-001 applied (`fc2f5aa`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_regular_collections_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_REGULAR_COLLECTIONS_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_REGULAR_COLLECTIONS_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
