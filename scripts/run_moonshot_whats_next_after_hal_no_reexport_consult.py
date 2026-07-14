"""Moonshot AI — What's next after HAL no-reexport hardening (hal-10578).

CONSULT ONLY. Operator: next (typed as nect).
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

Operator said "next" (typed "nect") — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes when OPS is blocked on missing real files.
Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.
Do NOT recommend re-exporting SoftDent Register hoping Ins Plan > 0.
Do NOT redo Regular Collections ingest (fc2f5aa) or HAL no-reexport (12451bb).

JUST COMPLETED (12451bb — HAL Policy Hardening no Register re-export / hal-10578):
- suggestedAction=era_835_procure when Ins Plan $0 + Regular complete
- Forbid suggestedAction=re_export_register; HAL refuse policy:forbid-register-reexport
- Gap tile still: Regular Collections: Complete ($30,626.42) · Insurance ERA Required
- Doc: MOONSHOT_HAL_HARDENING_NO_REEXPORT_HAL10578.md
- Prior: Regular Collections DEF-001 (fc2f5aa); Ins Plan OPS $0; ERA discovery=0
- 10571/10575/10576 already live

OPEN CANDIDATES (pick ONE highest leverage NOW):
1) OPS: Concrete payer-portal / clearinghouse 835 acquisition playbook —
   ONLY if you can cite REAL repo docs/paths for Delta/MetLife/Availity/SoftDent
   ERA download menus. If evidence insufficient, say so and pick a CODE package.
2) CODE: July production max-merge honesty — live julyDashboardRow may show
   production above Register (Register=44735) if max-merge drifted; fix only if
   LIVE SNAPSHOT shows a real distortion operators would misread.
3) CODE: Wire suggestedAction into gap-tile UI / HAL chips display (if UI
   ignores the new field) — only if REAL site JS/widget path exists and does
   not already surface ERA procure.
4) OPS: Real QuickBooks payroll/AP export drop — staff real files only
5) CODE: Small unit/integration harden around policy:forbid-register-reexport
   edge queries — only if 10578 left a clear hole (prefer not; package just shipped)

What NOT to redo: 10578 hardening, Regular Collections ingest, Register re-export
for Ins Plan, invent Ins/Patient split, account-tx track, 10571/10575/10576,
SoftDent write-back, synthetic 835s.

REAL PATHS:
- NewRidgeFinancial2/docs/MOONSHOT_HAL_HARDENING_NO_REEXPORT_HAL10578.md
- NewRidgeFinancial2/docs/MOONSHOT_REGULAR_COLLECTIONS_DEF001_APPLIED_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_ERA835_FIRST_DROP_OPS_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_ERA_REMITTANCE_DISCOVERY_APPLIED_2026-07-12.md
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/site/index.html
- NewRidgeFinancial2/site/hal-agent.js
- scripts/run_era_inbox_ingest_ops.py
- app_data/nr2/document_inbox/softdent/softdent_dashboard_data.json
- C:\\SoftDentReportExports\\REG202607.XLS
- C:\\SoftDentFinancialExports

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
            "12451bb HAL no-reexport: suggestedAction=era_835_procure; "
            "Regular Complete · ERA Required; discovery=0"
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
                "suggestedAction",
                "forbidRegisterReexport",
                "healthy",
            )
        }
        w = collections_gap_widget(bundle)
        live["widget"] = {
            k: w.get(k)
            for k in (
                "message",
                "suggestedAction",
                "forbidRegisterReexport",
                "eraDiscoverLabel",
                "status",
            )
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
        live["registerProductionTruth"] = 44735.0
        # UI surface check — does site JS mention suggestedAction?
        for rel in (
            "NewRidgeFinancial2/site/hal-agent.js",
            "NewRidgeFinancial2/site/index.html",
        ):
            p = REPO / rel
            if p.is_file():
                blob = p.read_text(encoding="utf-8", errors="ignore")
                live[f"uiMentions_{p.name}"] = {
                    "suggestedAction": "suggestedAction" in blob,
                    "era_835_procure": "era_835_procure" in blob,
                    "forbidRegisterReexport": "forbidRegisterReexport" in blob,
                    "bytes": p.stat().st_size,
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
    return json.dumps(live, indent=2, default=str)[:9500]


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
        ("MOONSHOT_HAL_HARDENING_NO_REEXPORT_HAL10578.md", 2400),
        ("MOONSHOT_REGULAR_COLLECTIONS_DEF001_APPLIED_2026-07-13.md", 1800),
        ("MOONSHOT_ERA_REMITTANCE_DISCOVERY_APPLIED_2026-07-12.md", 1200),
        ("MOONSHOT_ERA835_FIRST_DROP_OPS_APPLIED_2026-07-12.md", 1200),
        ("MOONSHOT_WHATS_NEXT_AFTER_REGULAR_COLLECTIONS_2026-07-13.md", 1400),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "HAL no-reexport (hal-10578 / 12451bb) just shipped. "
        "Regular Collections complete; Ins Plan=$0; ERA discovery still 0. "
        "Do NOT redo 10578 or Regular ingest. Pick THE next package. CONSULT ONLY.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After HAL No Reexport 10578"
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
    (OUT / f"moonshot_whats_next_after_hal_no_reexport_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After HAL No-Reexport Hardening (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** HAL no-reexport hardening applied (`12451bb` / hal-10578)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_hal_no_reexport_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_HAL_NO_REEXPORT_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_HAL_NO_REEXPORT_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
