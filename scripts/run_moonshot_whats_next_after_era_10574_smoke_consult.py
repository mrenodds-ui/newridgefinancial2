"""Moonshot AI — What's next after ERA inbox mutation-token + browser smoke (hal-10574).

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

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL (hal-10574).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes when OPS is blocked on missing real files.
Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST COMPLETED (CODE + SMOKE — 5166a01 / hal-10574):
- ERA inbox Refresh Inbox mutation-token wiring SHIPPED
- X-NR2-Session-Token CSRF for POST /api/apex/hal/era-inbox/ingest
- Collections Gap tile Refresh Inbox button via apexFetch
- Browser smoke PASS: UI click → POST 200 with session header;
  empty=true, honesty=empty_not_zero, writeBack=false, chip awaiting
- Docs: MOONSHOT_ERA_INBOX_MUTATION_TOKEN_APPLIED + BROWSER_SMOKE

PRIOR (blocked OPS, healthy code):
- ERA inbox scaffold 10573; gap-tile 10572; honesty UX 10571
- First-drop OPS attempted twice — still NO real payer .835/.edi on machine
- SoftDent July Register Ins Plan $0 is SoftDent truth — do NOT re-export
- synthetic.835 NOT production truth

LIVE FACTS:
- collectionsGapCode=ERA_835_REQUIRED, registerInsPlanZero=true
- ERA inbox empty (fileCount=0), chip Awaiting first 835 drop
- UI ingest path unblocked; only real files missing for business ROI

OPEN CANDIDATES (pick ONE highest leverage NOW):
1) OPS: Staff procurement / drop of first REAL ERA-835 into
   C:\\SoftDentFinancialExports\\era — still highest business ROI, but
   blocked thrice on human/clearinghouse; only recommend as THE package
   if you believe repeating OPS guidance is still the best move AND
   you have a NEW concrete acquisition path (payer portal names, SoftDent
   ERA import location, clearinghouse download steps) — not identical
   "drop files" prose
2) CODE: SoftDent ERA/claim remittance discovery assist — help staff
   FIND where remittances already live (SoftDent print paths, EDI folders,
   clearinghouse export dirs) WITHOUT inventing dollars; scan known
   practice roots for 835-like files and surface candidates to HAL
3) CODE: Collections Summary Excel-temp reliability — only if it does NOT
   imply Register Ins Plan > 0 re-export
4) OPS: Real QuickBooks payroll/AP export drop — staff real files only
5) CODE: Wire HAL chip action to Refresh Inbox (one-click from HAL chat)
   — lower priority; UI button already works

Prefer highest ROI that advances insurance collections honesty without
inventing data. If OPS remains blocked, prefer a CODE package that helps
LOCATE real remittance files on disk / SoftDent export paths.
Do NOT redo: 10574 mutation wiring, 10573 inbox scaffold, gap-tile labels,
honesty UX, browser smokes already PASS, Register re-export, synthetic 835.

REAL PATHS:
- NewRidgeFinancial2/apex_era835_pack.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/site/apex-core.js
- scripts/run_era_inbox_ingest_ops.py
- C:\\SoftDentFinancialExports\\era
- C:\\SoftDentReportExports\\era
- C:\\SoftDentFinancialExports
- C:\\SoftDentReportExports
- NewRidgeFinancial2/docs/MOONSHOT_ERA_INBOX_MUTATION_TOKEN_BROWSER_SMOKE_2026-07-12.md

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
        from apex_era835_pack import scan_era_inbox, era_inbox_status  # noqa: E402

        live["buildId"] = BUILD_ID
        live["prior"] = "5166a01 + browser smoke 10574 Refresh Inbox PASS"
        _r, bundle, _e = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        live["gap"] = {
            k: gap.get(k)
            for k in (
                "gapCode",
                "collectionsGapCode",
                "registerInsPlanZero",
                "insurance",
                "eraAvailable",
                "period",
            )
        }
        live["eraInbox"] = {
            k: scan_era_inbox(ensure_dirs=True).get(k)
            for k in (
                "empty",
                "fileCount",
                "chipStatus",
                "chipLabel",
                "honesty",
                "existingRoots",
            )
        }
        st = era_inbox_status(ensure_dirs=False)
        live["statusContract"] = {
            k: st.get(k)
            for k in (
                "mutationAuthRequired",
                "mutationHeader",
                "ingestUrl",
                "chipStatus",
                "empty",
            )
        }
        w = collections_gap_widget(bundle)
        live["widget"] = {
            "message": w.get("message"),
            "eraInboxIngestLabel": w.get("eraInboxIngestLabel"),
            "eraInboxIngestUrl": w.get("eraInboxIngestUrl"),
            "chips": [c.get("label") for c in (w.get("halChips") or [])],
        }
        try:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(
                "https://127.0.0.1:8765/api/apex/hal/era-inbox/status",
                timeout=8,
                context=ctx,
            ) as resp:
                live["liveInboxApi"] = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            live["liveInboxApiError"] = f"{type(exc).__name__}:{exc}"
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:8000]


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
        ("MOONSHOT_ERA_INBOX_MUTATION_TOKEN_BROWSER_SMOKE_2026-07-12.md", 2400),
        ("MOONSHOT_ERA_INBOX_MUTATION_TOKEN_APPLIED_2026-07-13.md", 2000),
        ("MOONSHOT_WHATS_NEXT_AFTER_ERA_FIRST_DROP_OPS_2026-07-13.md", 1600),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "ERA mutation-token UI + browser smoke PASS on 10574; inbox still empty. "
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
        headers["X-Title"] = "NR2 Whats Next After ERA 10574 Smoke"
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
    (OUT / f"moonshot_whats_next_after_era_10574_smoke_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10574"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After ERA Inbox Mutation-Token Smoke (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** 10574 Refresh Inbox smoke PASS (`5166a01`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_era_10574_smoke_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_ERA_10574_SMOKE_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_ERA_10574_SMOKE_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
