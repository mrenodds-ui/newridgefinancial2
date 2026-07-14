"""Moonshot AI — What's next after ERA-835 inbox ingest wiring (hal-10573).

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

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(hal-10573 ERA-835 inbox ingest wiring JUST SHIPPED as 426895a).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST SHIPPED (426895a / hal-10573):
- scan_era_inbox / ensure_era_inbox_dirs / era_inbox_status
- ingest_era_inbox: empty → awaiting (no invent $); files → ingest_era835_to_unified
- GET /api/apex/hal/era-inbox/status; POST /api/apex/hal/era-inbox/ingest
  (POST needs mutation token — browser 403 without token is expected)
- Gap stays ERA_835_REQUIRED while inbox empty; chip "Awaiting first 835 drop"
- Docs: MOONSHOT_ERA835_INBOX_SCAFFOLD_APPLIED_2026-07-12.md

JUST SHIPPED PRIOR:
- Gap-tile honesty label (157572e / hal-10572): visible ERA_835_REQUIRED
- Import Dataset Hygiene (5847920): optional QB payroll/AP empty-batch
- Watcher hotfix 2439197; ERA honesty UX 197efe8 / hal-10571
- Browser smoke; widgets NICE; TXN ledger

LIVE FACTS:
- collectionsGapCode=ERA_835_REQUIRED, registerInsPlanZero=true, insurance=0
- ERA inbox roots EXIST and are EMPTY (fileCount=0, chipStatus=awaiting)
- mode=scaffold; honesty=empty_not_zero
- SoftDent July Register Ins Plan $0 is SoftDent truth — do NOT re-export

OPEN CANDIDATES (pick ONE highest leverage):
1) OPS: Staff drop first real ERA-835 file(s) into
   C:\\SoftDentFinancialExports\\era (or ReportExports\\era), then run
   ingest_era_inbox / Sync — only if operator can obtain real 835/EDI/CSV;
   never invent sample dollars as production truth
2) Browser smoke of hal-10573 ERA inbox chip + gap tile after hard refresh
3) Wire mutation-token / HAL chip path so staff can trigger inbox ingest
   from the UI without raw POST 403 (if OPS drop is not yet available)
4) Collections Summary Excel-temp reliability — only if it does NOT imply
   Register Ins Plan > 0 re-export
5) SoftDent OPS only if a non-Register report on-screen shows Ins Plan > 0
6) Real QuickBooks payroll/AP OPS export drop — only if staff can produce
   real QB files; do not invent wages/AP balances

Prefer highest ROI. Prefer OPS when the code path is ready and only real
files are missing. Do NOT recommend re-export July Register for Ins Plan > 0.
Do NOT invent fake 835 content as live insurance truth.

Do NOT redo: ERA inbox scan/ingest wiring, gap-tile label polish,
Import Dataset Hygiene empty-batch markers, ERA honesty UX logic,
browser smoke of 10571/10572, widgets MUST/SHOULD/NICE, account-tx DB,
TXN ingest/ledger, invent Ins/Patient split, invent GUI write-back,
re-apply read_only watcher fix.

REAL PATHS:
- NewRidgeFinancial2/apex_era835_pack.py
- NewRidgeFinancial2/apex_softdent_era_pack.py
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/nr2_browser_security.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/docs/MOONSHOT_ERA835_INBOX_SCAFFOLD_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_GAP_TILE_ERA_REQUIRED_LABEL_APPLIED_2026-07-12.md
- C:\\SoftDentFinancialExports\\era
- C:\\SoftDentReportExports\\era
- C:\\SoftDentReportExports
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
        from apex_era835_pack import scan_era_inbox, ingest_era_inbox  # noqa: E402
        from softdent_practice_exports import stub_era835_ingestion_path  # noqa: E402

        live["buildId"] = BUILD_ID
        live["prior"] = "426895a ERA inbox ingest wiring hal-10573"
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
                "candidateRoots",
            )
        }
        live["eraStub"] = {
            k: stub_era835_ingestion_path().get(k)
            for k in ("mode", "chipStatus", "fileCount", "honesty", "empty")
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
        ("MOONSHOT_ERA835_INBOX_SCAFFOLD_APPLIED_2026-07-12.md", 2200),
        ("MOONSHOT_GAP_TILE_ERA_REQUIRED_LABEL_APPLIED_2026-07-12.md", 1400),
        ("MOONSHOT_WHATS_NEXT_AFTER_GAP_TILE_10572_2026-07-12.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "ERA-835 inbox ingest wiring (hal-10573) SHIPPED; inbox empty awaiting first drop. "
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
        headers["X-Title"] = "NR2 Whats Next After ERA Inbox 10573"
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
    (OUT / f"moonshot_whats_next_after_era_inbox_10573_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10573"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After ERA-835 Inbox Ingest (hal-10573) (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** ERA inbox ingest (`426895a` / hal-10573)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_era_inbox_10573_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_ERA_INBOX_10573_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_ERA_INBOX_10573_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
