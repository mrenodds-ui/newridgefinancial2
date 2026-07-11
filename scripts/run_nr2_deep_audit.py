#!/usr/bin/env python3
"""CLI entry for Phase U0 deep audit / forecast (Windows Task Scheduler).

Examples:
  python scripts/run_nr2_deep_audit.py --classify-only
  python scripts/run_nr2_deep_audit.py --forecast --classify-only
  python scripts/run_nr2_deep_audit.py --period 2026-06
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))


def main() -> int:
    parser = argparse.ArgumentParser(description="NR2 U0 deep practice health audit / forecast")
    parser.add_argument(
        "--classify-only",
        action="store_true",
        help="Route/classify only — do not call Ollama",
    )
    parser.add_argument(
        "--forecast",
        action="store_true",
        help="Run quarter forecast scaffold instead of monthly audit",
    )
    parser.add_argument("--period", default=None, help="YYYY-MM (default: current UTC month)")
    args = parser.parse_args()
    from apex_deep_audit_pack import forecast_next_quarter, generate_monthly_audit

    if args.forecast:
        result = forecast_next_quarter(
            period=args.period,
            classify_only=bool(args.classify_only),
        )
    else:
        result = generate_monthly_audit(
            period=args.period,
            classify_only=bool(args.classify_only),
        )
    print(json.dumps(result, indent=2, default=str))
    okish = bool(result.get("ok")) or result.get("reason") in {
        "orchestrator_disabled",
        "deep_audit_disabled",
    }
    return 0 if okish else 1


if __name__ == "__main__":
    raise SystemExit(main())
