"""Moonshot AI — What's next after SoftDent account-tx coverage chip.

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
If high-ROI local CODE is exhausted, recommend the single best OPS with
concrete SoftDent/portal steps grounded in REAL paths — not vague prose.
Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST SHIPPED (8096158 — account-tx coverage chip):
- SoftDent + Office Manager status chip: live db_total + 1996–2026 range
- SQL LIMIT/date filters on sd_account_transactions queries
- Prior: multi-year HAL (2906b0e), year-chunk ingest (6843a9c), 10576, 10575
  discovery candidates=0

Account-tx programming track is largely complete (pull → ingest → HAL → UI chip).

OPEN CANDIDATES (pick ONE highest leverage NOW):
1) OPS: July Register/Collections with Ins Plan Collections > 0 SoftDent export
   — DEF-001 ingest ready; cite REAL SoftDent menu path if known from docs
2) OPS: Concrete payer-portal / clearinghouse 835 acquisition — only with
   REAL repo evidence; discovery already proved local candidates=0
3) CODE: Browser smoke of SoftDent page coverage chip + HAL multi-year query
   — only if REAL smoke harness exists
4) CODE: Tiny HAL teach / policy line for coverage chip — only if missing
5) If no high-ROI CODE remains, verdict MUST be OPS and say programming
   on this track is done

What NOT to redo: coverage chip, multi-year HAL, year-chunk pull/ingest,
10575/10576, widgets MUST/SHOULD/NICE, invent Ins Plan/ERA dollars,
SoftDent write-back.

REAL PATHS:
- NewRidgeFinancial2/apex_better_backend_widgets_pack.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- C:\\SoftDentFinancialExports\\softdent_financial_analytics.db
- C:\\SoftDentReportExports
- NewRidgeFinancial2/docs/MOONSHOT_ACCOUNT_TX_COVERAGE_CHIP_APPLIED_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_WHATS_NEXT_AFTER_WIDGETS_NICE_2026-07-12.md

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
        from apex_softdent_hardening_pack import assess_collections_gap  # noqa: E402
        from apex_era835_pack import discover_era_candidates  # noqa: E402
        from apex_better_backend_widgets_pack import (  # noqa: E402
            build_account_tx_ledger_coverage_chip,
        )
        from softdent_transaction_extract import account_tx_ledger_coverage  # noqa: E402

        live["buildId"] = BUILD_ID
        live["prior"] = "8096158 coverage chip; 549564 rows; multi-year HAL live"
        live["coverage"] = account_tx_ledger_coverage()
        chip = build_account_tx_ledger_coverage_chip({}, page="softdent")
        live["chip"] = {
            k: chip.get(k)
            for k in (
                "id",
                "status",
                "message",
                "account_tx_multi_year_available",
                "dbTotal",
            )
        }
        _r, bundle, _e = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        live["gap"] = {
            k: gap.get(k)
            for k in (
                "collectionsGapCode",
                "registerInsPlanZero",
                "insurance",
                "period",
            )
        }
        disc = discover_era_candidates(limit=20, max_depth=4)
        live["discovery"] = {
            k: disc.get(k) for k in ("candidateCount", "chipStatus", "chipLabel")
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
                    for k in ("ok", "candidateCount", "buildId")
                }
        except Exception as exc:  # noqa: BLE001
            live["liveDiscoverApiError"] = f"{type(exc).__name__}:{exc}"
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
        ("MOONSHOT_ACCOUNT_TX_COVERAGE_CHIP_APPLIED_2026-07-13.md", 1800),
        ("MOONSHOT_ACCOUNT_TX_MULTI_YEAR_HAL_APPLIED_2026-07-13.md", 1200),
        ("MOONSHOT_WHATS_NEXT_AFTER_WIDGETS_NICE_2026-07-12.md", 1600),
        ("MOONSHOT_WHATS_NEXT_AFTER_ERA_10575_DISCOVERY_2026-07-13.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Coverage chip SHIPPED (8096158). Account-tx CODE track largely done. "
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
        headers["X-Title"] = "NR2 Whats Next After Coverage Chip"
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
    (OUT / f"moonshot_whats_next_after_coverage_chip_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After Account-TX Coverage Chip (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** coverage chip shipped (`8096158`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_coverage_chip_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_COVERAGE_CHIP_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_COVERAGE_CHIP_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
