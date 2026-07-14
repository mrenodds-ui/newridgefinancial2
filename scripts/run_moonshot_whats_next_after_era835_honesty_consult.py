"""Moonshot AI — What's next after ERA-835 honesty UX (hal-10571). CONSULT ONLY."""

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
(hal-10571 + ERA-835 Collections Honesty UX just shipped as 197efe8).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST SHIPPED (197efe8 / hal-10571 ERA-835 honesty UX):
- collectionsGapCode=ERA_835_REQUIRED when Register collections reported
  + collectionsFormatRequired + Ins Plan <= 0
- HAL: SoftDent Register Ins Plan $0.00 → proceed with ERA-835
- Do not re-export Register hoping Ins Plan > 0
- stub_era835_ingestion_path (read-only)

JUST SHIPPED PRIOR:
- July Register OPS (Ins Plan $0 SoftDent truth) + Excel SaveCopyAs (05dfc1e)
- Widgets NICE (hal-10570): pareto, tax-calendar, timeline-lanes
- Account-tx DB + TXN ledger (hal-10569 / 4281a50)

OPEN CANDIDATES (pick ONE highest leverage):
1) Wire real ERA-835 inbox ingest into the honesty path (beyond stub) —
   only if real ERA files/paths exist; do not invent dollars
2) Browser smoke: widgets NICE + TXN ledger + ERA_835_REQUIRED gap tile
   after hard-refresh (hal-10571)
3) Collections Summary Excel-temp reliability (menu opens OO; workbook flaky)
4) HAL phrase polish / dashboard tile for ERA_835_REQUIRED
5) SoftDent OPS only if on-screen Ins Plan > 0 on a non-Register report
Prefer highest ROI. Prefer OPS only when SoftDent UI visibly shows Ins>0.
Do NOT recommend re-export July Register for Ins Plan > 0.

Do NOT redo: ERA honesty UX, widgets MUST/SHOULD/NICE, account-tx DB,
TXN ingest/ledger, invent Ins/Patient split, invent GUI write-back.

REAL PATHS:
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/apex_softdent_era_pack.py
- NewRidgeFinancial2/apex_era835_pack.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/apex_better_backend_widgets_pack.py
- NewRidgeFinancial2/docs/MOONSHOT_ERA835_HONESTY_UX_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_NICE_APPLIED_2026-07-12.md
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
        from apex_backend import BUILD_ID  # noqa: E402
        from apex_softdent_hardening_pack import assess_collections_gap  # noqa: E402
        from apex_backend import _load_reports_and_bundle  # noqa: E402
        from softdent_practice_exports import stub_era835_ingestion_path  # noqa: E402

        live["buildId"] = BUILD_ID
        _r, bundle, _e = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        live["gap"] = {
            k: gap.get(k)
            for k in (
                "gapCode",
                "collectionsGapCode",
                "registerInsPlanZero",
                "collectionsFormatRequired",
                "collectionsExportRequired",
                "period",
                "production",
                "insurance",
                "eraAvailable",
            )
        }
        live["eraStub"] = stub_era835_ingestion_path()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
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
        ("MOONSHOT_ERA835_HONESTY_UX_APPLIED_2026-07-12.md", 2200),
        ("MOONSHOT_WHATS_NEXT_AFTER_INSPLAN_OPS_2026-07-12.md", 1400),
        ("MOONSHOT_BETTER_BACKEND_WIDGETS_NICE_APPLIED_2026-07-12.md", 1200),
        ("MOONSHOT_OPS_SOFTDENT_2026_07_INSPLAN_PROCEED_2026-07-12.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "ERA-835 honesty UX JUST SHIPPED (197efe8 / hal-10571). "
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
        headers["X-Title"] = "NR2 Whats Next After ERA835 Honesty"
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
    (OUT / f"moonshot_whats_next_after_era835_honesty_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10571"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After ERA-835 Honesty UX (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** ERA-835 honesty UX (`197efe8` / hal-10571)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_era835_honesty_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_ERA835_HONESTY_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_ERA835_HONESTY_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
