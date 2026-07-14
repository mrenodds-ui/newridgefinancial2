#!/usr/bin/env python3
"""HAL-10595 — Backfill recon_variance_history exact cents from source Decimal.

Never copies lossy REAL float columns. Recomputes ledger from
sd_account_transactions; visual from Print Preview audits when matched.
Uses BEGIN IMMEDIATE + busy_timeout. Flag only — no SoftDent/gold writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NR2 = REPO / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from softdent_visual_ledger_recon import migrate_history_to_exact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate recon_variance_history to exact integer cents (HAL-10595)"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Analytics SQLite path (default: resolve_analytics_db)",
    )
    parser.add_argument(
        "--exports",
        type=Path,
        default=None,
        help="Exports dir for Print Preview visual audits",
    )
    args = parser.parse_args()
    result = migrate_history_to_exact(db_path=args.db, dest=args.exports)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
