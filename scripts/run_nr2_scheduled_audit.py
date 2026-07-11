#!/usr/bin/env python3
"""Phase V0 — scheduled monthly deep audit (Windows Task Scheduler / cron).

Moonshot REAUDIT4: run on 1st of month (ops choice). Flag NR2_AUDIT_CRON default OFF.

Examples:
  set NR2_AUDIT_CRON=1
  python scripts/run_nr2_scheduled_audit.py --classify-only
  python scripts/run_nr2_scheduled_audit.py --force
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cron_enabled() -> bool:
    raw = str(os.getenv("NR2_AUDIT_CRON") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _log_path() -> Path:
    override = str(os.getenv("NR2_AUDIT_CRON_LOG") or "").strip()
    if override:
        return Path(override)
    return REPO / "NewRidgeFinancial2" / "app_data" / "nr2" / "audit_cron_log.jsonl"


def append_log(entry: dict) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="NR2 V0 scheduled deep audit")
    parser.add_argument("--classify-only", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when today is not the 1st (ops testing)",
    )
    parser.add_argument("--period", default=None)
    args = parser.parse_args()

    day = datetime.now().astimezone().day
    if not cron_enabled():
        entry = {
            "at": _utc_now(),
            "ok": False,
            "exit": 2,
            "reason": "audit_cron_disabled",
            "hint": "Set NR2_AUDIT_CRON=1 (default OFF until burn-in).",
        }
        append_log(entry)
        print(json.dumps(entry, indent=2))
        return 2

    if day != 1 and not args.force:
        entry = {
            "at": _utc_now(),
            "ok": True,
            "exit": 0,
            "skipped": True,
            "reason": "not_first_of_month",
            "day": day,
            "hint": "Use --force to run off-schedule.",
        }
        append_log(entry)
        print(json.dumps(entry, indent=2))
        return 0

    from apex_deep_audit_pack import generate_monthly_audit

    result = generate_monthly_audit(
        period=args.period,
        classify_only=bool(args.classify_only),
    )
    exit_code = 0 if result.get("ok") or result.get("reason") in {
        "orchestrator_disabled",
        "deep_audit_disabled",
    } else 1
    entry = {
        "at": _utc_now(),
        "ok": bool(result.get("ok")),
        "exit": exit_code,
        "classifyOnly": bool(args.classify_only),
        "forced": bool(args.force),
        "period": result.get("period"),
        "lane": result.get("lane"),
        "phase": "V0",
        # No dollar fields copied from result
        "reason": result.get("reason"),
    }
    append_log(entry)
    print(json.dumps({"log": entry, "result": result}, indent=2, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
