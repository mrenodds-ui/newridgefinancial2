#!/usr/bin/env python3
"""Import SoftDent insurance companies CSV → insurance_company_reference."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NR2 = REPO / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from softdent_insurance_company_reference import (  # noqa: E402
    ingest_insurance_companies_csv,
    insurance_company_reference_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load SoftDent insurance companies CSV into analytics DB"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to softdent_insurance_companies*.csv",
    )
    parser.add_argument("--db", type=Path, default=None, help="Analytics SQLite path")
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Do not copy CSV into SoftDentFinancialExports",
    )
    args = parser.parse_args()
    result = ingest_insurance_companies_csv(
        csv_path=args.csv,
        db_path=args.db,
        copy_to_exports=not args.no_copy,
    )
    status = insurance_company_reference_status(db_path=args.db)
    print(json.dumps({"ingest": result, "status": status}, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
