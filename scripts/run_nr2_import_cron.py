#!/usr/bin/env python3
"""Phase W1 — import cron (Task Scheduler / cron). Flag NR2_IMPORT_CRON default OFF.

Examples:
  set NR2_IMPORT_CRON=1
  python scripts/run_nr2_import_cron.py
  python scripts/run_nr2_import_cron.py --force
  python scripts/run_nr2_import_cron.py --loop --max-ticks 2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))


def main() -> int:
    parser = argparse.ArgumentParser(description="NR2 W1 import cron (DQ-gated poll)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when NR2_IMPORT_CRON is unset (ops testing)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Long-running loop (prefer Task Scheduler one-shots)",
    )
    parser.add_argument("--max-ticks", type=int, default=None)
    args = parser.parse_args()

    from apex_import_scheduler_pack import run_import_cron_once, run_scheduler_loop

    if args.loop:
        result = run_scheduler_loop(max_ticks=args.max_ticks)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 2

    result = run_import_cron_once(force=bool(args.force))
    print(json.dumps(result, indent=2, default=str))
    log = result.get("log") if isinstance(result.get("log"), dict) else result
    return int(log.get("exit") if isinstance(log, dict) and "exit" in log else (0 if result.get("ok") else 1))


if __name__ == "__main__":
    raise SystemExit(main())
