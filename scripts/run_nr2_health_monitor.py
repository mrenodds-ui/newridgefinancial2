#!/usr/bin/env python3
"""CLI entry for Phase S2 proactive health monitor (Windows Task Scheduler).

Example:
  set NR2_AI_ORCHESTRATOR=1
  python scripts/run_nr2_health_monitor.py --classify-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))


def main() -> int:
    parser = argparse.ArgumentParser(description="NR2 proactive practice health audit")
    parser.add_argument(
        "--classify-only",
        action="store_true",
        help="Route/classify only — do not call Ollama",
    )
    args = parser.parse_args()
    from apex_health_monitor_pack import run_scheduled_health_audit

    result = run_scheduled_health_audit(classify_only=bool(args.classify_only))
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") or result.get("reason") == "orchestrator_disabled" else 1


if __name__ == "__main__":
    raise SystemExit(main())
