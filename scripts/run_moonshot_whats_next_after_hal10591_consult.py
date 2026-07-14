"""Moonshot AI — What's next after HAL-10591 UI honesty (CONSULT ONLY).

Operator said: next
"""

from __future__ import annotations

import json
import os
import sqlite3
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

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL + SoftDent RCM.

Operator said NEXT after HAL-10591 just shipped on fix/main-validate-ci (1c1d431).

CONSULT ONLY — DO NOT claim you applied code. empty != $0.
No SoftDent write-back. Do not invent Ins Plan Register dollars or carrier names.
Do NOT redo HAL-10580–10591 as greenfield — build ON them.

JUST SHIPPED (HAL-10591 / HON-001 — Empty≠$0 Programmatic UI Enforcement):
- ui_honesty_policy.py: HonestyPolicy enum, enforce_empty_not_zero(value, source_tag),
  audit_ui_honesty_surfaces(), widget softdent-ui-honesty, CLI scripts/audit_ui_honesty.py
- BUILD_ID=hal-10591 coupled
- Wire-ins: Print Preview [visual] badge ≠ gold; gold paymentLines=0 → display —;
  TP chips/_fmt_money; Apex _money_kpi; HAL policy:empty-not-zero; API /api/apex/ui-honesty/status
- Null/missing never renders as $0.00; explicit float 0.0 still allowed as $0.00
- Prior: 10590 Print Preview visual audit (PHI-safe JSONL, triggersGoldIngest=false);
  10588–10589 gold ETL ready but product-blocked; 10580–10587 InsCo×ADA spine/catalog/TP
  (46 exact usable / 46 pass) on ledger fallback

GROUND TRUTH: Gold CSV path remains product-blocked (gapCode=GOLD_CSV_MISSING,
paymentLines=0). UI honesty layer now guards against empty→$0.00 lies beside visual
audit dollars. Pick THE single best NEXT that advances honesty/RCM without inventing
gold lines.

OPEN CANDIDATES (pick ONE — HON-001 is DONE, do not re-recommend it):
1) CODE: Visual-audit × ledger spine reconciliation — compare Print Preview last-page
   Insurance Income aggregates to ledger/probabilistic period sums (PHI-safe); flag
   variance without inventing InsCo×ADA gold lines. HON-001 now makes this safe.
2) CODE/OPS: ERA835 first-drop — only if real 835 content exists (not just manifests);
   cross-check vs 46 exact usable cells and/or visual audit totals
3) CODE: Catalog/spine reliability — secondary-ins exclusion, same-day settlement,
   borderline-n bootstrap (grow beyond 46 carefully without gold fiction)
4) OPS+CODE: Uncovered ledger CDT playbook (CDTs with no 2/51 pairing)
5) CODE: Async HAL / ASGI queue (ENH-001) — latency; not data-plane unblock
6) CODE: Staff Print Preview audit UX polish — carrier breakdown helper, month-close
   checklist tying visual_audit_last_page_total into SoftDent page close workflow
7) CODE: Honesty CI gate hardening — fail CI if any financial widget regresses to
   null→$0.00 (screenshot/contract tests beyond unit matrix)

What NOT to redo: SoftDent write-back; invent gold from ledger/DaySheet; pretend
Excel/CSV exists for Insurance Income; BUILD_ID drift; redo TP chips/catalog/spine
or 10588–10591 discovery; Register re-export Ins Plan>0; re-do HON-001; GitHub/PR
as primary next.

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
## 2. Why this beats the other candidates now
## 3. Runner-ups (2–3, why not now)
## 4. What NOT to redo
## 5. Acceptance criteria
## 6. Executive Summary (5 bullets)
## 7. Approval checklist
DO NOT APPLY CODE. Prefer one clear next over a laundry list.
"""


def _live_snapshot() -> str:
    live: dict = {
        "prior": "1c1d431 HAL-10591 empty≠$0 UI honesty enforcement",
        "appliedDoc": "MOONSHOT_APPLIED_HAL10591_UI_HONESTY_2026-07-13.md",
        "consultDoc": "MOONSHOT_WHATS_NEXT_AFTER_HAL10590_2026-07-13.md",
        "operatorAsk": "next",
    }
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402
        from softdent_gold_payment_pipeline import audit_gold_payment_pipeline  # noqa: E402
        from softdent_insco_ada_catalog_matrix import catalog_matrix_status  # noqa: E402
        from softdent_print_preview_audit import list_print_preview_audits  # noqa: E402
        from ui_honesty_policy import (  # noqa: E402
            PACKAGE_BUILD_ID,
            audit_ui_honesty_surfaces,
        )

        live["buildId"] = BUILD_ID
        live["packageBuildId"] = PACKAGE_BUILD_ID
        live["buildIdCoupled"] = BUILD_ID == PACKAGE_BUILD_ID == "hal-10591"
        gold = audit_gold_payment_pipeline()
        live["gold"] = {
            "gapCode": gold.get("gapCode"),
            "paymentLines": gold.get("paymentLines"),
            "treatmentEstimates": gold.get("treatmentEstimates"),
        }
        live["printPreviewAudit"] = list_print_preview_audits(limit=5)
        hon = audit_ui_honesty_surfaces()
        live["uiHonesty"] = {
            "ok": hon.get("ok"),
            "passCount": hon.get("passCount"),
            "failCount": hon.get("failCount"),
            "def": hon.get("def"),
        }
        live["catalog"] = {
            k: catalog_matrix_status().get(k)
            for k in (
                "ok",
                "totalCells",
                "exactUsableCells",
                "publishedCells",
                "insufficientCells",
            )
        }
        exports = Path(r"C:\SoftDentFinancialExports")
        if exports.is_dir():
            live["eraLikeFilesSample"] = sorted(
                {
                    p.name
                    for pat in ("*835*", "*era*", "*ERA*", "*remit*")
                    for p in exports.glob(pat)
                }
            )[:20]
            live["auditLogExists"] = (exports / "print_preview_audit_log.jsonl").is_file()
        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                for table, key in (
                    ("sd_insurance_payment_lines", "paymentLines"),
                    ("era_835_payments", "era835"),
                ):
                    try:
                        live[key] = int(
                            con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0
                        )
                    except sqlite3.Error:
                        live[key] = None
            finally:
                con.close()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:16000]


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
        ("MOONSHOT_APPLIED_HAL10591_UI_HONESTY_2026-07-13.md", 2800),
        ("MOONSHOT_WHATS_NEXT_AFTER_HAL10590_2026-07-13.md", 2400),
        ("MOONSHOT_APPLIED_HAL10590_PRINT_PREVIEW_AUDIT_2026-07-13.md", 1800),
        ("MOONSHOT_EXPERT_SE_FIRST_CLASS_PROGRAM_2026-07-13.md", 1600),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "HAL-10591 empty≠$0 UI honesty just shipped. Gold CSV still blocked. "
        "HON-001 is DONE — do not re-recommend it. Pick THE next package. CONSULT ONLY.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After HAL-10591"
    print("Calling Moonshot AI (what's next after 10591 — consult only)...")

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
    (OUT / f"moonshot_whats_next_after_hal10591_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10591"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After HAL-10591 UI Honesty (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** HAL-10591 empty≠$0 UI honesty (`1c1d431`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_hal10591_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10591_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10591_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
