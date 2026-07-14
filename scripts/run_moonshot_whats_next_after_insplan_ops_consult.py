"""Moonshot AI — What's next after July Ins Plan OPS attempt + widgets NICE.

Operator: next. CONSULT ONLY — do not apply.
"""

from __future__ import annotations

import json
import os
import sqlite3
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
(hal-10570 + SoftDent Excel-temp export harden 05dfc1e).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST SHIPPED (05dfc1e OPS July Ins Plan proceed + Excel SaveCopyAs):
- SoftDent July Register Excel re-exported 07/01–07/12
- SoftDent BODY TRUTH: Ins Plan Collections = $0.00,
  Regular Collections = $30626.42
- collectionsFormatRequired remains true (honesty)
- Collections Summary Excel path did not yield a workbook this session
- softdent_gui_export SaveCopyAs fallback when Select File Name skipped

JUST SHIPPED PRIOR:
- Better Backend Widgets NICE (hal-10570 / 88fd003): pareto, tax-calendar,
  timeline-lanes
- Account-tx DB sd_account_transactions (4281a50)
- TXN ledger surface (hal-10569)

CRITICAL CONSTRAINT:
Do NOT recommend "re-export July Register hoping Ins Plan > 0" as THE next
if SoftDent already prints Ins Plan = $0 on Register — that is SoftDent truth,
not a missing file. Prefer a different Collections report that ON-SCREEN shows
Ins>0, OR a code package that advances practice value without inventing dollars,
OR browser smoke / ERA path honesty polish.

OPEN CANDIDATES (pick ONE):
1) SoftDent Collections Summary (or other report) ONLY if on-screen Ins Plan > 0
   before export — otherwise skip
2) Browser smoke of widgets NICE + TXN ledger + Donna DB after hard-refresh
3) ERA_835 / collections honesty UX when Register Ins Plan is truly $0
4) Wire Collections Summary Excel-temp path reliability (menu already opens OO)
5) HAL phrase polish for July collections when format-required
Prefer highest ROI. Prefer OPS only when SoftDent UI visibly shows Ins>0.

Do NOT redo: widgets MUST/SHOULD/NICE, account-tx DB, TXN ingest/ledger,
Register XLS parser, invent Ins/Patient split, invent GUI write-back.

REAL PATHS:
- NewRidgeFinancial2/softdent_gui_export.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/apex_better_backend_widgets_pack.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- C:\\SoftDentReportExports\\register_for_period_2026-07-01_2026-07-12.xls
- NewRidgeFinancial2/docs/MOONSHOT_OPS_SOFTDENT_2026_07_INSPLAN_PROCEED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_NICE_APPLIED_2026-07-12.md

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
    except Exception as exc:  # noqa: BLE001
        live["buildError"] = type(exc).__name__

    try:
        from softdent_practice_exports import summarize_daysheet_export  # noqa: E402

        reg = Path(r"C:\SoftDentReportExports\register_for_period_2026-07-01_2026-07-12.xls")
        if reg.is_file():
            s = summarize_daysheet_export(reg) or {}
            live["julyRegister"] = {
                "path": str(reg),
                "bytes": reg.stat().st_size,
                "period": s.get("period"),
                "production": s.get("production"),
                "collections": s.get("collections"),
                "insurance": s.get("insurance"),
                "patient": s.get("patient"),
                "collectionsFormatRequired": s.get("collectionsFormatRequired"),
            }
    except Exception as exc:  # noqa: BLE001
        live["julyRegisterError"] = type(exc).__name__

    try:
        from apex_softdent_hardening_pack import assess_collections_gap  # noqa: E402
        from apex_backend import _load_reports_and_bundle  # noqa: E402

        _r, bundle, _e = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        live["gap"] = {
            k: gap.get(k)
            for k in (
                "collectionsGapCode",
                "collectionsPending",
                "collectionsReported",
                "collectionsFormatRequired",
                "production",
                "collections",
                "period",
            )
        }
    except Exception as exc:  # noqa: BLE001
        live["gapError"] = type(exc).__name__

    db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
    if db.is_file():
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                if conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                    "AND name='sd_account_transactions'"
                ).fetchone()[0]:
                    live["sd_account_transactions_count"] = conn.execute(
                        "SELECT COUNT(*) FROM sd_account_transactions"
                    ).fetchone()[0]
            finally:
                conn.close()
        except Exception:
            pass
    return json.dumps(live, indent=2, default=str)[:6500]


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
        ("MOONSHOT_OPS_SOFTDENT_2026_07_INSPLAN_PROCEED_2026-07-12.md", 2400),
        ("MOONSHOT_BETTER_BACKEND_WIDGETS_NICE_APPLIED_2026-07-12.md", 1600),
        ("MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_DB_2026-07-12.md", 1200),
        ("MOONSHOT_ACCOUNT_TX_DB_APPLIED_2026-07-12.md", 1000),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "July Register Ins Plan OPS just attempted — SoftDent prints Ins Plan $0. "
        "Widgets NICE shipped. Pick THE next package. CONSULT ONLY.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After InsPlan OPS"
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
    (OUT / f"moonshot_whats_next_after_insplan_ops_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10570"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After July Ins Plan OPS + Widgets NICE "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** Ins Plan OPS proceed (05dfc1e); Widgets NICE (hal-10570)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_insplan_ops_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_INSPLAN_OPS_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_INSPLAN_OPS_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
