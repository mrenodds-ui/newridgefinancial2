"""Moonshot AI — What's next after ERA remittance discovery (hal-10575).

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

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL (hal-10575).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes when OPS is blocked on missing real files.
Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.
empty != $0. Never invent SoftDent write-back or dollars.

JUST COMPLETED (7eec3ed / 10575):
- SoftDent ERA Remittance Discovery Scanner SHIPPED
- discover_era_candidates() read-only walk of SoftDent/export roots
- GET/POST /api/apex/hal/era-inbox/discover
- Gap tile "Scan for ERA Files" + HAL policy:era-discover
- LIVE SCAN on this machine: candidateCount=0 → chip
  "No local ERA files detected; procurement required"
- False-positive guards (DaySheet/manifests/UUID 835) PASS
- Prior: 10574 Refresh Inbox mutation-token + browser smoke PASS
- Prior OPS first-drop blocked multiple times; discovery now PROVES
  no local remittances exist on scanned roots

LIVE FACTS:
- BUILD_ID=hal-10575
- collectionsGapCode=ERA_835_REQUIRED, registerInsPlanZero=true
- ERA inbox empty; discovery found ZERO candidates
- Insurance gap cannot close without real payer 835 files

OPEN CANDIDATES (pick ONE highest leverage NOW):
1) OPS: Concrete payer-portal / clearinghouse 835 acquisition playbook
   — NOW evidence-backed (discovery=0). Prefer SPECIFIC steps for this
   practice (Delta Dental / MetLife / Availity / SoftDent ERA download
   menus if documented in repo) rather than vague "drop files" prose.
   Only recommend if you can cite REAL repo docs/paths for portals.
2) CODE: Expand discovery roots via SoftDent desktop/EDI path probes
   (read-only) if repo has known SoftDent install/EDI locations not yet
   scanned — only if new REAL paths exist beyond what 10575 already hits
3) CODE: Collections Summary Excel-temp reliability — only if NOT
   Register Ins Plan > 0 re-export
4) OPS: Real QuickBooks payroll/AP export drop — staff real files only
5) CODE: Browser smoke of 10575 Scan button — lower priority; unit+live
   discovery already PASS
6) CODE: Wire candidate "copy into inbox" helper AFTER staff confirm —
   premature while candidateCount=0

Since discovery proved zero local files, prefer either:
- OPS with a NEW concrete acquisition path grounded in repo evidence, OR
- the highest-ROI CODE package that is NOT another empty ERA loop
  (e.g. Collections Excel-temp or QB OPS if files can be produced).
Do NOT recommend repeating identical "drop 835" OPS without new specifics.
Do NOT invent dollars / Register re-export / synthetic 835 as production.

What NOT to redo: 10575 discovery, 10574 mutation wiring, 10573 inbox,
gap-tile/honesty, browser smokes already PASS, Register re-export.

REAL PATHS:
- NewRidgeFinancial2/apex_era835_pack.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- scripts/run_era_inbox_ingest_ops.py
- C:\\SoftDentFinancialExports
- C:\\SoftDentReportExports
- C:\\SoftDent
- NewRidgeFinancial2/docs/MOONSHOT_ERA_REMITTANCE_DISCOVERY_APPLIED_2026-07-12.md

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
        from apex_era835_pack import (  # noqa: E402
            discover_era_candidates,
            scan_era_inbox,
        )

        live["buildId"] = BUILD_ID
        live["prior"] = "7eec3ed 10575 discovery; live candidates=0"
        _r, bundle, _e = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        live["gap"] = {
            k: gap.get(k)
            for k in (
                "gapCode",
                "collectionsGapCode",
                "registerInsPlanZero",
                "insurance",
                "period",
            )
        }
        live["eraInbox"] = {
            k: scan_era_inbox(ensure_dirs=True).get(k)
            for k in ("empty", "fileCount", "chipStatus", "chipLabel")
        }
        disc = discover_era_candidates(limit=20, max_depth=4)
        live["discovery"] = {
            k: disc.get(k)
            for k in (
                "candidateCount",
                "chipStatus",
                "chipLabel",
                "scannedRoots",
                "missingRoots",
                "writeBack",
                "honesty",
            )
        }
        w = collections_gap_widget(bundle)
        live["widget"] = {
            "message": w.get("message"),
            "eraDiscoverLabel": w.get("eraDiscoverLabel"),
            "eraInboxIngestLabel": w.get("eraInboxIngestLabel"),
        }
        try:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(
                "https://127.0.0.1:8765/api/apex/hal/era-inbox/discover",
                timeout=20,
                context=ctx,
            ) as resp:
                live["liveDiscoverApi"] = {
                    k: json.loads(resp.read().decode("utf-8")).get(k)
                    for k in ("buildId", "candidateCount", "chipLabel", "ok")
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
        ("MOONSHOT_ERA_REMITTANCE_DISCOVERY_APPLIED_2026-07-12.md", 2400),
        ("MOONSHOT_WHATS_NEXT_AFTER_ERA_10574_SMOKE_2026-07-13.md", 1800),
        ("MOONSHOT_ERA_INBOX_MUTATION_TOKEN_BROWSER_SMOKE_2026-07-12.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "ERA discovery 10575 SHIPPED; live candidateCount=0. "
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
        headers["X-Title"] = "NR2 Whats Next After ERA 10575 Discovery"
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
    (OUT / f"moonshot_whats_next_after_era_10575_discovery_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10575"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After ERA Remittance Discovery (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** 10575 discovery live candidates=0 (`7eec3ed`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_era_10575_discovery_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_ERA_10575_DISCOVERY_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_ERA_10575_DISCOVERY_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:5000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
