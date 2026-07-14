"""Moonshot AI — What's next after Import Dataset Hygiene (CONSULT ONLY).

Operator pattern: "next" → Moonshot consult; do not apply code.
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
(Import Dataset Hygiene JUST PASSED after ERA-835 honesty smoke).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST SHIPPED (Import Dataset Hygiene):
- Identified the 2 "missing" datasets as optional quickbooks.payroll + quickbooks.ap
- Wrote header-only empty-batch honesty markers (empty_not_zero) — no invented $
- Documented exclusions in IMPORT_DATASET_EXCLUSIONS_2026-07-12.md
- Purged leftover read_only TypeError quarantine; quarantineCount=0
- Live: importMissing=0, critical completeness 100%, ticker IMPORTS 17/19
  (partial=2 empty-batch), no "2 MISSING" alert
- Docs: MOONSHOT_IMPORT_DATASET_HYGIENE_APPLIED_2026-07-12.md

JUST SHIPPED PRIOR:
- Watcher hotfix 2439197 (dropped invalid read_only kwarg)
- ERA-835 honesty UX (197efe8 / hal-10571): collectionsGapCode=ERA_835_REQUIRED
  when Register Ins Plan <= 0; do not re-export Register hoping Ins Plan > 0
- Browser smoke PASS for honesty UX + widgets NICE + TXN ledger
- Widgets NICE (hal-10570), TXN ledger (hal-10569), account-tx DB

LIVE FACTS:
- collectionsGapCode=ERA_835_REQUIRED, registerInsPlanZero=true, insurance=0
- Gap strip message still shows outer gapCode ERA_835_AVAILABLE while nested
  collectionsGapCode is ERA_835_REQUIRED (cosmetic honesty UX note from smoke)
- eraStub.mode=stub; existingRoots=[] (ERA inbox dirs may be missing/empty)
- SoftDent July Register Ins Plan $0 is SoftDent truth — do NOT re-export

OPEN CANDIDATES (pick ONE highest leverage):
1) Gap-tile label polish: surface collectionsGapCode=ERA_835_REQUIRED in the
   visible message (not only nested), keep do-not-re-export hint legible —
   now that data hygiene is done, this cosmetic honesty fix is unblocked
2) Wire real ERA-835 inbox ingest / empty-inbox scaffolding beyond stub —
   ONLY if safe empty-inbox UX is explicit; never invent dollars; roots empty
3) SoftDent OPS only if a non-Register report on-screen shows Ins Plan > 0
4) Collections Summary Excel-temp reliability — only if it does NOT imply
   Register Ins Plan > 0 re-export
5) Real QuickBooks payroll/AP OPS export drop — only if staff can produce
   real QB files; do not invent wages/AP balances

Prefer highest ROI. Prefer OPS only when SoftDent UI visibly shows Ins>0
or real QB exports are available. Do NOT recommend re-export July Register
for Ins Plan > 0.

Do NOT redo: Import Dataset Hygiene empty-batch markers, ERA honesty UX logic,
browser smoke itself, widgets MUST/SHOULD/NICE, account-tx DB, TXN ingest/ledger,
invent Ins/Patient split, invent GUI write-back, re-apply read_only watcher fix,
re-purge quarantine already at 0.

REAL PATHS:
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/apex_softdent_era_pack.py
- NewRidgeFinancial2/apex_era835_pack.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/apex_qb_export_inbox_pack.py
- NewRidgeFinancial2/apex_qb_payroll_pack.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/docs/MOONSHOT_IMPORT_DATASET_HYGIENE_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/IMPORT_DATASET_EXCLUSIONS_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_ERA835_HONESTY_BROWSER_SMOKE_2026-07-12.md
- C:\\SoftDentReportExports
- C:\\SoftDentFinancialExports
- C:\\SoftDentFinancialExports\\era
- C:\\SoftDentReportExports\\era
- app_data/nr2/document_inbox/quickbooks/

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
        from softdent_practice_exports import stub_era835_ingestion_path  # noqa: E402
        from apex_qb_payroll_pack import assess_payroll_ap_gap  # noqa: E402
        from apex_qb_export_inbox_pack import batch_empty_status  # noqa: E402

        live["buildId"] = BUILD_ID
        live["prior"] = "import hygiene PASS + smoke + 2439197 + hal-10571 honesty"
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
                "fixHint",
            )
        }
        live["eraStub"] = stub_era835_ingestion_path()
        live["payrollApGap"] = {
            k: assess_payroll_ap_gap(bundle).get(k)
            for k in (
                "gapCode",
                "healthy",
                "payrollEmptyBatch",
                "apEmptyBatch",
                "honesty",
            )
        }
        live["batchEmpty"] = batch_empty_status()
        era_roots = []
        for root in (
            Path(r"C:\SoftDentFinancialExports\era"),
            Path(r"C:\SoftDentReportExports\era"),
            Path(r"C:\SoftDentFinancialExports"),
            Path(r"C:\SoftDentReportExports"),
        ):
            if root.is_dir():
                samples = sorted(root.glob("*"))[:12]
                era_roots.append(
                    {
                        "root": str(root),
                        "exists": True,
                        "sampleNames": [p.name for p in samples if p.is_file()][:12],
                    }
                )
            else:
                era_roots.append({"root": str(root), "exists": False})
        live["eraFilesystem"] = era_roots
        try:
            import urllib.request

            with urllib.request.urlopen(
                "https://127.0.0.1:8765/api/apex/hal/status", timeout=8, context=__import__(
                    "ssl"
                )._create_unverified_context()
            ) as resp:
                st = json.loads(resp.read().decode("utf-8"))
            live["halStatus"] = {
                "metrics": st.get("metrics"),
                "completeness": (st.get("readiness") or {}).get("completeness"),
                "summary": (st.get("readiness") or {}).get("summary"),
                "suggestion": st.get("suggestion"),
            }
        except Exception as exc:  # noqa: BLE001
            live["halStatusError"] = f"{type(exc).__name__}:{exc}"
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
        ("MOONSHOT_IMPORT_DATASET_HYGIENE_APPLIED_2026-07-12.md", 2200),
        ("IMPORT_DATASET_EXCLUSIONS_2026-07-12.md", 1600),
        ("MOONSHOT_ERA835_HONESTY_BROWSER_SMOKE_2026-07-12.md", 1600),
        ("MOONSHOT_WHATS_NEXT_AFTER_ERA835_SMOKE_2026-07-12.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Import Dataset Hygiene PASSED. Pick THE next package. CONSULT ONLY.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After Import Hygiene"
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
    (OUT / f"moonshot_whats_next_after_import_hygiene_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10571"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After Import Dataset Hygiene (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** import hygiene PASS / smoke PASS / watcher `2439197` / honesty UX `197efe8`  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_import_hygiene_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_IMPORT_HYGIENE_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_IMPORT_HYGIENE_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
