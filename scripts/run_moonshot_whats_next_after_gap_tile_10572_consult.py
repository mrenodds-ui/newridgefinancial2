"""Moonshot AI — What's next after gap-tile ERA_835_REQUIRED label (hal-10572).

CONSULT ONLY. Operator: next.
"""

from __future__ import annotations

import json
import os
import sys
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
(hal-10572 gap-tile honesty label polish JUST SHIPPED as 157572e).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST SHIPPED (157572e / hal-10572):
- Gap tile visible message surfaces ERA_835_REQUIRED (not ERA_835_AVAILABLE)
  when Register Ins Plan $0
- enrich keeps gapCode=ERA_835_REQUIRED; ERA presence on eraGapCode=AVAILABLE
- Do-not-re-export hint + ERA-835 path HAL chips
- Docs: MOONSHOT_GAP_TILE_ERA_REQUIRED_LABEL_APPLIED_2026-07-12.md

JUST SHIPPED PRIOR:
- Import Dataset Hygiene (5847920): optional QB payroll/AP empty-batch markers
- Watcher hotfix 2439197; ERA honesty UX 197efe8 / hal-10571
- Browser smoke PASS; widgets NICE; TXN ledger

LIVE FACTS:
- collectionsGapCode=ERA_835_REQUIRED, registerInsPlanZero=true, insurance=0
- eraStub.mode=stub; existingRoots=[] (no 835 files in ERA inbox yet)
- Import completeness critical 100%; ticker IMPORTS 17/19 partial empty-batch OK
- SoftDent July Register Ins Plan $0 is SoftDent truth — do NOT re-export

OPEN CANDIDATES (pick ONE highest leverage):
1) Wire real ERA-835 inbox ingest / empty-inbox scaffolding beyond stub —
   ONLY with safe empty-inbox UX; never invent dollars; roots may be empty
2) Browser smoke re-verify of hal-10572 gap-tile label after hard refresh
3) Collections Summary Excel-temp reliability — only if it does NOT imply
   Register Ins Plan > 0 re-export
4) SoftDent OPS only if a non-Register report on-screen shows Ins Plan > 0
5) Real QuickBooks payroll/AP OPS export drop — only if staff can produce
   real QB files; do not invent wages/AP balances

Prefer highest ROI. Prefer OPS only when SoftDent UI visibly shows Ins>0
or real QB/ERA files are available. Do NOT recommend re-export July Register
for Ins Plan > 0.

Do NOT redo: gap-tile label polish, Import Dataset Hygiene empty-batch markers,
ERA honesty UX logic, browser smoke of 10571, widgets MUST/SHOULD/NICE,
account-tx DB, TXN ingest/ledger, invent Ins/Patient split, invent GUI write-back,
re-apply read_only watcher fix.

REAL PATHS:
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/apex_softdent_era_pack.py
- NewRidgeFinancial2/apex_era835_pack.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/apex_qb_export_inbox_pack.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/docs/MOONSHOT_GAP_TILE_ERA_REQUIRED_LABEL_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_IMPORT_DATASET_HYGIENE_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_ERA835_HONESTY_UX_APPLIED_2026-07-12.md
- C:\\SoftDentReportExports
- C:\\SoftDentFinancialExports
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
        from apex_backend import BUILD_ID  # noqa: E402
        from apex_softdent_hardening_pack import (  # noqa: E402
            assess_collections_gap,
            collections_gap_widget,
        )
        from apex_backend import _load_reports_and_bundle  # noqa: E402
        from softdent_practice_exports import stub_era835_ingestion_path  # noqa: E402

        live["buildId"] = BUILD_ID
        live["gitTipHint"] = "157572e / hal-10572"
        _r, bundle, _e = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        w = collections_gap_widget(bundle)
        live["gap"] = {
            k: gap.get(k)
            for k in (
                "gapCode",
                "collectionsGapCode",
                "eraGapCode",
                "registerInsPlanZero",
                "period",
                "insurance",
                "eraAvailable",
            )
        }
        live["widget"] = {
            "message": w.get("message"),
            "emptyMessage": w.get("emptyMessage"),
            "gapCode": w.get("gapCode"),
            "chips": [c.get("label") for c in (w.get("halChips") or [])],
        }
        live["eraStub"] = stub_era835_ingestion_path()
        era_roots = []
        for root in (
            Path(r"C:\SoftDentFinancialExports\era"),
            Path(r"C:\SoftDentReportExports\era"),
        ):
            era_roots.append(
                {
                    "root": str(root),
                    "exists": root.is_dir(),
                    "sampleNames": (
                        [p.name for p in sorted(root.glob("*"))[:8] if p.is_file()]
                        if root.is_dir()
                        else []
                    ),
                }
            )
        live["eraFilesystem"] = era_roots
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:7500]


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
        ("MOONSHOT_GAP_TILE_ERA_REQUIRED_LABEL_APPLIED_2026-07-12.md", 2200),
        ("MOONSHOT_WHATS_NEXT_AFTER_IMPORT_HYGIENE_2026-07-12.md", 1400),
        ("MOONSHOT_IMPORT_DATASET_HYGIENE_APPLIED_2026-07-12.md", 1200),
        ("MOONSHOT_ERA835_HONESTY_UX_APPLIED_2026-07-12.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Gap-tile ERA_835_REQUIRED label JUST SHIPPED (157572e / hal-10572). "
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
        headers["X-Title"] = "NR2 Whats Next After Gap Tile 10572"
    print("Calling Moonshot AI (consult only — will not apply)...")
    import urllib.request

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
    (OUT / f"moonshot_whats_next_after_gap_tile_10572_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10572"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After Gap-Tile ERA_835_REQUIRED Label (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** gap-tile polish (`157572e` / hal-10572)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_gap_tile_10572_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_GAP_TILE_10572_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_GAP_TILE_10572_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
