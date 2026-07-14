"""Moonshot AI — What's next after ERA-835 first drop OPS (attempt 2 blocked).

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

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL (hal-10573).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes when OPS is blocked on missing real files.
Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST COMPLETED (OPS — blocked twice):
- MOONSHOT_ERA835_FIRST_DROP_OPS_APPLIED (7f4c4f9) + ATTEMPT2 (e5a4fbd)
- Staff drop of real ERA-835 into C:\\SoftDentFinancialExports\\era attempted twice
- Inbox still EMPTY (fileCount=0, chipStatus=awaiting); no production .835/.edi on machine
- Empty-inbox honesty gates PASS; synthetic.835 test fixture NOT used as production
- Helper: scripts/run_era_inbox_ingest_ops.py works for staff after real drop

JUST SHIPPED CODE (426895a / hal-10573):
- scan_era_inbox / ingest_era_inbox / era_inbox_status
- GET /api/apex/hal/era-inbox/status; POST /api/apex/hal/era-inbox/ingest
  (POST needs mutation token — browser 403 without token is expected)
- Gap ERA_835_REQUIRED while inbox empty; chip "Awaiting first 835 drop"

PRIOR SHIPPED:
- Gap-tile honesty label hal-10572; Import Dataset Hygiene; ERA honesty UX hal-10571
- Browser smoke PASS; widgets NICE; TXN ledger; account-tx DB

LIVE FACTS:
- collectionsGapCode=ERA_835_REQUIRED, registerInsPlanZero=true, insurance=0
- ERA inbox roots EXIST and EMPTY; mode=scaffold; honesty=empty_not_zero
- SoftDent July Register Ins Plan $0 is SoftDent truth — do NOT re-export Register
- Unified DB has test-only rows (sourceFile t.835) — not production truth

OPEN CANDIDATES (pick ONE highest leverage NOW that OPS drop blocked twice):
1) CODE: Wire mutation-token / HAL chip so staff can trigger inbox ingest from UI
   without raw POST 403 — unblocks browser path while waiting for payer files
2) OPS: Staff procurement of real ERA-835 (still highest business ROI but blocked
   on human/clearinghouse action — only recommend if you believe repeating OPS
   guidance is still THE package; otherwise demote to runner-up)
3) Browser smoke of hal-10573 ERA inbox chip + gap tile regression after hard refresh
4) Collections Summary Excel-temp reliability — only if NOT Register re-export
5) Real QuickBooks payroll/AP OPS export drop — staff real files only
6) SoftDent non-Register report OPS only if on-screen Ins Plan > 0 (unlikely)

Since OPS first-drop failed twice for lack of files, prefer a CODE package that
advances the pipeline without inventing dollars — mutation-token UI ingest is
the strongest runner-up from prior consult. Do NOT recommend a third identical
OPS drop attempt as THE package unless you have new evidence files arrived.

Do NOT redo: ERA inbox scan/ingest wiring, gap-tile labels, Import Hygiene,
ERA honesty UX, browser smoke 10571/10572, widgets NICE, TXN ledger,
invent Ins/Patient split, Register re-export, synthetic 835 as production.

REAL PATHS:
- NewRidgeFinancial2/apex_era835_pack.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/nr2_browser_security.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/site/index.html
- scripts/run_era_inbox_ingest_ops.py
- NewRidgeFinancial2/docs/MOONSHOT_ERA835_FIRST_DROP_OPS_ATTEMPT2_2026-07-12.md
- C:\\SoftDentFinancialExports\\era
- C:\\SoftDentReportExports\\era

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
        from apex_era835_pack import scan_era_inbox, ingest_era_inbox  # noqa: E402

        live["buildId"] = BUILD_ID
        live["prior"] = "e5a4fbd ERA first drop OPS attempt 2 blocked"
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
        empty_ingest = ingest_era_inbox(ensure_dirs=True)
        live["emptyIngest"] = {
            k: empty_ingest.get(k)
            for k in ("empty", "chipStatus", "ingested", "honesty", "writeBack")
        }
        w = collections_gap_widget(bundle)
        live["widget"] = {
            "message": w.get("message"),
            "gapCode": w.get("gapCode"),
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
        ("MOONSHOT_ERA835_FIRST_DROP_OPS_ATTEMPT2_2026-07-12.md", 2400),
        ("MOONSHOT_ERA835_INBOX_SCAFFOLD_APPLIED_2026-07-12.md", 1800),
        ("MOONSHOT_WHATS_NEXT_AFTER_ERA_INBOX_10573_2026-07-12.md", 1600),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "ERA first drop OPS attempted twice — still blocked on real payer 835 files. "
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
        headers["X-Title"] = "NR2 Whats Next After ERA First Drop OPS"
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
    (OUT / f"moonshot_whats_next_after_era_first_drop_ops_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10573"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After ERA-835 First Drop OPS (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** ERA first drop OPS attempt 2 blocked (`e5a4fbd`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_era_first_drop_ops_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_ERA_FIRST_DROP_OPS_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_ERA_FIRST_DROP_OPS_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
