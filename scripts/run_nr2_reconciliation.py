#!/usr/bin/env python3
"""CLI entry for Phase U2 SoftDent×QB reconciliation (Task Scheduler friendly).

Examples:
  python scripts/run_nr2_reconciliation.py --classify-only
  python scripts/run_nr2_reconciliation.py --period 2026-06 --classify-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))


def main() -> int:
    parser = argparse.ArgumentParser(description="NR2 U2 SoftDent×QB reconciliation scan")
    parser.add_argument("--classify-only", action="store_true", help="Do not call Ollama for explainer")
    parser.add_argument("--period", default=None, help="YYYY-MM")
    parser.add_argument("--no-explain", action="store_true", help="Skip 30B explainer entirely")
    args = parser.parse_args()
    from apex_reconciliation_pack import run_reconciliation

    result = run_reconciliation(
        period=args.period,
        classify_only=bool(args.classify_only),
        explain=not bool(args.no_explain),
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") or result.get("reason") == "reconciliation_disabled" else 1


if __name__ == "__main__":
    raise SystemExit(main())
