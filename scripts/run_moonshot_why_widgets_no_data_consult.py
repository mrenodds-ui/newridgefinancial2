"""Moonshot AI — Why do these widgets not have data? (CONSULT ONLY).

Operator: ask moonshot why these widgets do not have data
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
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

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")

OPERATOR_REQUEST_VERBATIM = "ask moonshot why these widgets do not have data"

LIVE_EMPTY_CENSUS = """
LIVE @ https://127.0.0.1:8765/ build **hal-10612** (demote-to-Ops applied).
empty ≠ $0 is intentional policy. Honesty: do not invent SoftDent dollars.

### Overview empties (still visible on first viewport)
CLAIMS (3 empty of 7):
- claims-era-gauge — emptyMessage: "ERA match % appears when ERA status is on the SoftDent import (or after NR2 ERA ingest)"
  Code: apex_claims_narratives_pack.claims_era_gauge_widget — needs meta.eraMatchRate
- denial-pareto — "No denials recorded"
  Code: apex_missing_widgets_pack denial builder — needs denial rows in SoftDent claims import
- verification-matrix — "Verification tracking disabled"
  Code: apex_missing_widgets_pack — needs elig/ben/breakdown fields on schedule/appt rows

SOFTDENT:
- softdent-gold-csv-drop-ops — "v19: Print Preview only for Insurance Income - visual audit does not create gold lines (gapCode=GOLD_CSV_MISSING; empty != $0)"
- sd-prod-trend — blank status; hint SoftDent dashboard periods (may lack multi-period spark series)

A/R:
- ar-aging-chart — blank status; hint "Buckets from SoftDent A/R import"
  App-info softGap: softdent.ar STALE (271+ min old; max 120) — critical soft gap even though completeness scorePct=100

OFFICE-MANAGER:
- import-health-monitor — "DEF-001 ERA_835_REQUIRED: SoftDent collections/daysheet gap (2026-07)"

### Demoted Ops empties (not on overview; still empty)
financial/ops: import-cache-kpi (warming), reconciliation-status (unavailable), gold-csv-ticket-ops (awaiting Carestream case # / no line-item file)
claims/ops: import-health-monitor (DEF-001), ins-patient-split (no real split), preauth-aging-lanes (no pending pre-auths)
hal/ops: import-cache-kpi warming, reconciliation-status unavailable, payer-change-alerts none, mosaics ar/claims blank status

### OK on overview (for contrast — DO have import-backed data)
financial: bridge-errors, financial-command-strip, collections-gauge, financial-dual-trend, provider-hbar
taxes: period scrubber, tax-core-strip, tax-bridge-waterfall all ok
claims: claims-executive-strip, claims-aging-exposure, claims-open-kanban ok
"""

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(BUILD **hal-10612**: zero-scroll demote surplus widgets to #{page}/ops).

Operator asks WHY widgets do not have data.

CONSULT ONLY — DO NOT claim you applied code. empty ≠ $0. Never invent SoftDent dollars.

RULES:
- SoftDent desktop money truth = Excel or Print Preview only (never Printer) when OPS needed
- Distinguish: (A) intentional honest empty / not wired, (B) missing import field, (C) stale softGap, (D) DEF-001 product gap, (E) wrong page / demoted to Ops so overview looks sparse
- Prefer real file/function names when citing causes
- Give operator OPS actions vs code actions separately

OUTPUT (strict markdown):
# Verdict (one blunt sentence: why the blanks)
## 0. Operator Intent (verbatim; consult-only)
## 1. Per-widget root cause table (widget id | why empty | data source expected | OPS vs CODE)
## 2. Top 5 root causes ranked by impact
## 3. What is healthy / already filled (so we don't chase ghosts)
## 4. Fix order (OPS first, then CODE) — no SoftDent dollar invention
## 5. Coding package IF approved later (MUST/SHOULD, real paths)
## 6. Acceptance criteria to prove empties are honest vs broken
## 7. Executive Summary (5 bullets)
"""


def fetch_json(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=30, context=CTX) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def live_snippet() -> str:
    bits = [LIVE_EMPTY_CENSUS]
    try:
        info = fetch_json("/api/app-info")
        soft = (info.get("importReadiness") or {}).get("completeness") or {}
        gaps = (info.get("importReadiness") or {}).get("datasetGaps") or []
        bits.append(
            "\nLIVE app-info softGaps/datasetGaps JSON excerpt:\n"
            + json.dumps({"completeness": soft, "datasetGaps": gaps[:6]}, indent=2)[:2500]
        )
    except Exception as exc:  # noqa: BLE001
        bits.append(f"\n(app-info fetch failed: {exc})")
    return "\n".join(bits)


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

    user = (
        f"Operator request (verbatim):\n> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"{live_snippet()}\n\n"
        "Explain WHY these widgets lack data. Consult only."
    )
    payload = {
        "model": model,
        "temperature": 1.0 if "moonshot" in base_url.lower() else 0.2,
        "max_tokens": 9000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://newridgefamilyfinancial.local",
            "X-Title": "NR2 Moonshot Why Widgets No Data Consult",
        },
        method="POST",
    )
    print(f"key={key_name} model={model} base={base_url}", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=700) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read()[:800]}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    content = extract_message_content(body) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw = OUT / f"moonshot_why_widgets_no_data_raw_{stamp}.json"
    raw.write_text(
        json.dumps(
            {"model": model, "key": key_name, "operator": OPERATOR_REQUEST_VERBATIM, "content": content},
            indent=2,
        ),
        encoding="utf-8",
    )
    doc = DOCS / f"MOONSHOT_WHY_WIDGETS_NO_DATA_CONSULT_{DATE}.md"
    header = (
        f"# Moonshot AI — Why widgets do not have data (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Build:** hali-10612\n"
        f"**Script:** `scripts/run_moonshot_why_widgets_no_data_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    ).replace("hali-10612", "hal-10612")
    doc.write_text(header + content + "\n", encoding="utf-8")
    print(f"wrote {doc}", flush=True)
    print(f"wrote {raw}", flush=True)
    print("--- PREVIEW ---", flush=True)
    print(re.sub(r"[^\x00-\x7F]+", "?", content)[:6000], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
