#!/usr/bin/env python3
"""HAL-10593 — CLI visual-audit × ledger variance (+ carrier / history)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"
if str(NR2) not in sys.path:
    sys.path.insert(0, str(NR2))

from softdent_visual_ledger_recon import (  # noqa: E402
    format_visual_ledger_recon_reply,
    list_recon_variance_history,
    run_ops_10593_visual_ledger_recon,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Visual×ledger variance audit (HAL-10593)")
    parser.add_argument("period", nargs="?", default=None, help="Period e.g. 2026-06")
    parser.add_argument(
        "--carrier-breakdown",
        action="store_true",
        help="Force include carrier breakdown (default on)",
    )
    parser.add_argument(
        "--show-history-months",
        type=int,
        default=0,
        help="Also print variance history for N months",
    )
    parser.add_argument("--no-persist", action="store_true", help="Skip history append")
    args = parser.parse_args()

    result = run_ops_10593_visual_ledger_recon(
        period=args.period,
        persist_history=not args.no_persist,
        include_carrier_breakdown=True,
    )
    print(format_visual_ledger_recon_reply(result))
    if args.carrier_breakdown or result.get("carrierBreakdown"):
        print("carrierBreakdown=", json.dumps(result.get("carrierBreakdown") or [], indent=2))
    print(json.dumps(result, indent=2, default=str)[:9000])

    if args.show_history_months and args.show_history_months > 0:
        hist = list_recon_variance_history(months=args.show_history_months)
        print("history=", json.dumps(hist, indent=2, default=str)[:4000])

    cmp_ = result.get("comparison") if isinstance(result.get("comparison"), dict) else {}
    if cmp_.get("thresholdViolated"):
        return 2
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
