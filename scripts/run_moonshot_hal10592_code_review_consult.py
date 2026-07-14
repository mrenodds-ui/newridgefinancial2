"""Moonshot AI — Code review of HAL-10592 visual×ledger recon (CONSULT ONLY).

Operator asked: review this code for bugs, optimization, and edge cases.
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
    "Please review this code for bugs, optimization, and edge cases."
)

SYSTEM = """You are Moonshot AI — principal engineer reviewing NR2 SoftDent/Apex code.

CONSULT ONLY — do not claim you applied fixes. empty != $0. No SoftDent write-back.
Do not invent gold payment lines. Prefer concrete findings with severity and file:symbol.

Review HAL-10592 / HON-002 visual-audit × ledger reconciliation just shipped
(commit 2ababd5, BUILD_ID=hal-10592). Focus on:
1) Bugs / correctness
2) Optimization / performance
3) Edge cases / honesty regressions (null→$0.00, visual conflated with gold)
4) What is fine to leave alone

Context constraints that MUST stay true:
- Print Preview visual totals are NOT gold CSV / sd_insurance_payment_lines
- Ledger side is SoftDent code-2 payment sum from sd_account_transactions
- Variance is flag-only (never auto-correct / invent lines)
- HON-001: null/missing never treated as $0.00 in compare math
- SoftDent Insurance Income Print Preview may not match ledger code-2 1:1
  (scope mismatch risk is a design finding if real)

OUTPUT (strict markdown):
# Verdict (1–2 sentences: ship-worthy? top risk?)
## 1. Critical / High bugs
## 2. Medium bugs & edge cases
## 3. Optimization opportunities
## 4. Honesty / policy risks (empty≠$0, visual≠gold)
## 5. What looks solid
## 6. Recommended fix order (if proceed) — small concrete patches, no greenfield redo
## 7. Acceptance checks before merge-to-main confidence
DO NOT APPLY CODE. Be specific (line-level / function-level). Skip fluff.
"""


def _read(path: Path, lim: int = 12000) -> str:
    if not path.is_file():
        return f"(missing {path.name})"
    return path.read_text(encoding="utf-8")[:lim]


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
        ("softdent_visual_ledger_recon.py", _read(NR2 / "softdent_visual_ledger_recon.py", 14000)),
        (
            "test_hal10592_visual_ledger_recon.py",
            _read(NR2 / "test_hal10592_visual_ledger_recon.py", 8000),
        ),
        (
            "MOONSHOT_APPLIED_HAL10592_VISUAL_LEDGER_RECON_2026-07-13.md",
            _read(DOCS / "MOONSHOT_APPLIED_HAL10592_VISUAL_LEDGER_RECON_2026-07-13.md", 2500),
        ),
        (
            "ui_honesty_policy.py (enforce helpers)",
            _read(NR2 / "ui_honesty_policy.py", 4500),
        ),
    ]
    body = "\n\n".join(f"### FILE: {n}\n```\n{c}\n```" for n, c in excerpts)

    # Live smoke of classify + parse
    live = {}
    try:
        sys.path.insert(0, str(NR2))
        from softdent_visual_ledger_recon import (  # noqa: E402
            classify_variance,
            parse_date_range,
            reconcile_visual_vs_ledger,
        )

        live["parse_june"] = parse_date_range("2026-06")
        live["within"] = classify_variance(100.0, 98.0)
        live["exceeds"] = classify_variance(100.0, 50.0)
        live["null_visual"] = classify_variance(None, 0.0)
        live["explicit_zero_vs_zero"] = classify_variance(0.0, 0.0)
        live["recon_smoke"] = {
            k: reconcile_visual_vs_ledger().get(k)
            for k in (
                "ok",
                "result",
                "period",
                "visualTotal",
                "ledgerTotal",
                "gapCode",
                "paymentLines",
                "triggersGoldIngest",
            )
        }
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Review HAL-10592 visual×ledger reconciliation code. CONSULT ONLY.\n\n"
        f"## LIVE SMOKE\n{json.dumps(live, indent=2, default=str)[:6000]}\n\n"
        f"## CODE UNDER REVIEW\n{body}"
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
        headers["X-Title"] = "NR2 HAL-10592 Code Review"
    print("Calling Moonshot AI (HAL-10592 code review — consult only)...")

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
    (OUT / f"moonshot_hal10592_code_review_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    header = (
        f"# Moonshot AI — HAL-10592 Visual×Ledger Recon Code Review (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10592  \n"
        f"**Prior:** HAL-10592 (`2ababd5`)  \n"
        f"**Script:** `scripts/run_moonshot_hal10592_code_review_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_HAL10592_CODE_REVIEW_{DATE}.md"
    out = OUT / f"MOONSHOT_HAL10592_CODE_REVIEW_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
