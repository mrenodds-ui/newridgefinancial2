#!/usr/bin/env python3
"""CLI: build next clinical day Trellis worklist (+ optional headed Verify).

Usage:
  python scripts/run_trellis_nightly_verify.py
  python scripts/run_trellis_nightly_verify.py --force --verify
  set NR2_TRELLIS_VERIFY=1 && python scripts/run_trellis_nightly_verify.py --force
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NR2 = REPO / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))


def main() -> int:
    parser = argparse.ArgumentParser(description="HAL nightly Trellis insurance verify")
    parser.add_argument("--force", action="store_true", help="Ignore Mon–Thu / already-ran gates")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Drive Trellis Playwright Verify (needs .env.vyne.local + interactive desktop)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    store = None
    try:
        from local_store import LocalStore

        store = LocalStore(REPO / "app_data" / "nr2")
    except Exception:
        store = None

    from nr2_trellis_nightly import insurance_verify_tick

    result = insurance_verify_tick(
        store,
        force=args.force,
        run_verify=True if args.verify else None,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(
            f"ok={result.get('ok')} skipped={result.get('skipped')} "
            f"target={result.get('targetDate')} ready={result.get('worklistReady')}/"
            f"{result.get('worklistTotal')} verifyRan={result.get('verifyRan')}"
        )
        if result.get("results"):
            print("results", result["results"])
        report = result.get("report") or {}
        if report.get("path"):
            print("report", report.get("path"), "withBenefits", report.get("withBenefits"))
        if result.get("error"):
            print("error", result.get("error"), result.get("detail") or "")
            return 1
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
