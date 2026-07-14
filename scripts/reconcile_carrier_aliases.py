#!/usr/bin/env python3
"""HAL-10600 — Reconcile SoftDent company master ↔ InsCo spine carrier aliases.

CONSULT recommendation applied. empty != $0. No SoftDent write-back.
Does not invent payment lines.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NR2 = REPO / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from softdent_carrier_alias import (  # noqa: E402
    PACKAGE_BUILD_ID,
    accept_pending_alias,
    carrier_alias_status,
    reconcile_carrier_aliases,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="HAL-10600 carrier alias reconcile")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--dest", type=Path, default=None, help="CSV export directory")
    parser.add_argument(
        "--accept-pending",
        type=str,
        default=None,
        help="Accept a pending manual master company name",
    )
    parser.add_argument(
        "--reject-pending",
        type=str,
        default=None,
        help="Reject a pending manual master company name",
    )
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    if args.status_only:
        print(json.dumps(carrier_alias_status(db_path=args.db), indent=2, default=str))
        return 0
    if args.accept_pending:
        print(
            json.dumps(
                accept_pending_alias(args.accept_pending, db_path=args.db, accept=True),
                indent=2,
                default=str,
            )
        )
        return 0
    if args.reject_pending:
        print(
            json.dumps(
                accept_pending_alias(args.reject_pending, db_path=args.db, accept=False),
                indent=2,
                default=str,
            )
        )
        return 0

    result = reconcile_carrier_aliases(db_path=args.db, dest=args.dest)
    result["packageBuildId"] = PACKAGE_BUILD_ID
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
