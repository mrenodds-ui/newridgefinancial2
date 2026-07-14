"""OPS helper — ingest ERA-835 files from the wired inbox (hal-10573).

Run after staff drop real 835/EDI/CSV into:
  C:\\SoftDentFinancialExports\\era
  C:\\SoftDentReportExports\\era

Does not invent dollars or write SoftDent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

from apex_era835_pack import ingest_era_inbox, scan_era_inbox  # noqa: E402


def main() -> int:
    scan = scan_era_inbox(ensure_dirs=True)
    print("=== SCAN ===")
    print(json.dumps(scan, indent=2, default=str))
    if scan.get("empty"):
        print("\nInbox empty — drop real ERA 835 files first. Empty != $0.")
        return 0
    result = ingest_era_inbox(ensure_dirs=True)
    print("\n=== INGEST ===")
    print(json.dumps(result, indent=2, default=str))
    ok = bool(result.get("ok"))
    ingested = result.get("ingested") or []
    any_rows = any(int(r.get("rowsInserted") or 0) > 0 for r in ingested if isinstance(r, dict))
    if not any_rows:
        print("\nWarning: files detected but no rows inserted — check file format.")
        return 1
    print("\nOK — ERA inbox ingested (proposal only; no SoftDent write-back).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
