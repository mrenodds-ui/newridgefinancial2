"""Moonshot AI — Consult on visual-ledger Decimal/audit hardening (CONSULT ONLY).

Operator: run what you just did through moonshot ai for a consult.
Prior commit: 8b2befa — Decimal cents + audit fingerprints.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
NR2 = REPO / "NewRidgeFinancial2"
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

OPERATOR_REQUEST_VERBATIM = (
    "run what you just did through moonshot ai for a consult"
)

SYSTEM = """You are Moonshot AI — principal financial engineer + compliance auditor
for NR2 Apex HAL SoftDent RCM.

CONSULT ONLY — do not claim you applied fixes. empty != $0.
No SoftDent write-back. Do not invent gold payment lines.

JUST SHIPPED (commit 8b2befa on fix/main-validate-ci, BUILD still hal-10593):
Financial compliance hardening of visual×ledger recon after an expert audit:
1) New money_cents.py — Decimal quantized to 0.01 ROUND_HALF_EVEN; to_money never
   coerces empty/null to 0; money_to_api for JSON floats after quantize
2) softdent_visual_ledger_recon.py — classify_variance uses Decimal equality for
   MATCH; carrier breakdown skips NULL amounts (no float(amt or 0)); ledger totals
   quantized via to_money; history insert uses BEGIN IMMEDIATE + busy_timeout,
   input_fingerprint (sha256 of period/visual/ledger/clamped/delta/result/build),
   money_scale='0.01' columns
3) Tests updated for cent-exact MATCH vs tolerance

Prior stack: HAL-10591 HON-001 empty≠$0; HAL-10592 visual×ledger; HAL-10593
carrier/clamp/history. Gold CSV still blocked (paymentLines=0).

Operator wants YOUR consult on THIS hardening: bugs remaining, whether Decimal
API float bridge is enough, audit trail gaps, what NEXT patch (if any) should be,
and what NOT to redo.

OUTPUT (strict markdown):
# Verdict (1–2 sentences: hardening adequate? top residual risk?)
## 0. Operator Intent (verbatim)
## 1. What the hardening got right
## 2. Residual bugs / risks (severity + file:symbol)
## 3. Compliance / audit-trail gaps still open
## 4. Recommended NEXT (one package only — or NONE if hold)
## 5. What NOT to redo
## 6. Acceptance checks if operator says proceed on your NEXT
## 7. Approval checklist
DO NOT APPLY CODE. Be concrete. Prefer one clear next over a laundry list.
"""


def _read(path: Path, lim: int = 10000) -> str:
    if not path.is_file():
        return f"(missing {path.name})"
    return path.read_text(encoding="utf-8")[:lim]


def _live() -> dict:
    live: dict = {"priorCommit": "8b2befa", "package": "hal-10593 money hardening"}
    try:
        sys.path.insert(0, str(NR2))
        from apex_backend import BUILD_ID  # noqa: E402
        from money_cents import to_money, money_to_api  # noqa: E402
        from softdent_visual_ledger_recon import (  # noqa: E402
            PACKAGE_BUILD_ID,
            classify_variance,
            reconcile_visual_vs_ledger,
        )

        live["buildId"] = BUILD_ID
        live["packageBuildId"] = PACKAGE_BUILD_ID
        live["decimalSmoke"] = {
            "to_money_100_001": str(to_money(100.001)),
            "null": to_money(None),
            "api": money_to_api(to_money(100.001)),
            "match_cent": classify_variance(100.0, 100.001).get("result"),
            "within": classify_variance(100.0, 98.0).get("result"),
            "null_visual": classify_variance(None, 0.0).get("result"),
        }
        live["reconSmoke"] = {
            k: reconcile_visual_vs_ledger().get(k)
            for k in (
                "ok",
                "result",
                "visualTotal",
                "ledgerTotal",
                "triggersGoldIngest",
                "gapCode",
                "paymentLines",
            )
        }
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return live


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

    excerpts = [
        ("money_cents.py", _read(NR2 / "money_cents.py", 5000)),
        (
            "softdent_visual_ledger_recon.py (money/history slices)",
            _read(NR2 / "softdent_visual_ledger_recon.py", 14000),
        ),
        (
            "MOONSHOT_APPLIED_HAL10593_VISUAL_LEDGER_FOLLOWONS_2026-07-13.md",
            _read(DOCS / "MOONSHOT_APPLIED_HAL10593_VISUAL_LEDGER_FOLLOWONS_2026-07-13.md", 2000),
        ),
    ]
    body = "\n\n".join(f"### FILE: {n}\n```\n{c}\n```" for n, c in excerpts)
    live = _live()

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Consult on the Decimal-cent + audit-fingerprint hardening just shipped "
        "(8b2befa). CONSULT ONLY — do not apply.\n\n"
        f"## LIVE SMOKE\n{json.dumps(live, indent=2, default=str)[:6000]}\n\n"
        f"## CODE UNDER CONSULT\n{body}"
    )
    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 8000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Money Hardening Consult"
    print("Calling Moonshot AI (money hardening consult — consult only)...")

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
    (OUT / f"moonshot_money_hardening_consult_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    header = (
        f"# Moonshot AI — Visual-Ledger Decimal/Audit Hardening Consult "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {live.get('buildId') or 'hal-10593'}  \n"
        f"**Prior:** money hardening (`8b2befa`) on HAL-10593  \n"
        f"**Script:** `scripts/run_moonshot_money_hardening_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_MONEY_HARDENING_CONSULT_{DATE}.md"
    out = OUT / f"MOONSHOT_MONEY_HARDENING_CONSULT_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
