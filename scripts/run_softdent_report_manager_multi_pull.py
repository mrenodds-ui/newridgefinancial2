#!/usr/bin/env python3
"""Program SoftDent multi-report pull (Report Manager catalog + sequential Excel).

Uses SoftDent Report Manager group design (NR2 Money Widgets) when menus are
rights-enabled; otherwise pulls the same pack via desktop SoftDent Excel
automation (register, collections, transactions, daysheet, aging).
Never Printer. Never invent dollars.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

from softdent_report_manager_multi import (  # noqa: E402
    format_report_manager_multi_hal_reply,
    run_programmed_multi_report_pull,
    write_status,
)


def main() -> int:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=f"{today.year:04d}-{today.month:02d}-01")
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--skip-signon", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-report-manager", action="store_true")
    args = parser.parse_args()

    payload = run_programmed_multi_report_pull(
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        ensure_signon=not args.skip_signon,
        prefer_report_manager=not args.no_report_manager,
        dry_run=bool(args.dry_run),
    )
    path = write_status(payload)
    payload["statusPath"] = str(path)
    payload["halReply"] = format_report_manager_multi_hal_reply(payload)
    print(json.dumps(payload, indent=2, default=str))
    if payload.get("ok"):
        return 0
    if payload.get("partialOk"):
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
