"""Force QuickBooks monthly export freshness for NR2 (read-only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NR2 = REPO / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from import_loader import quickbooks_import_dir  # noqa: E402
from quickbooks_monthly_sync import (  # noqa: E402
    ensure_quickbooks_fresh,
    sync_quickbooks_monthly_exports,
)


def main() -> int:
    dest = Path(quickbooks_import_dir())
    out = ensure_quickbooks_fresh(dest, max_age_minutes=30)
    if not out.get("refreshed"):
        sync = sync_quickbooks_monthly_exports(dest, force_sdk=True)
        out = {
            "stale": True,
            "refreshed": bool(sync.get("written")),
            "destination": str(dest),
            "sync": sync,
        }
    print(json.dumps(out, default=str))
    # Success if we refreshed OR destination exists with sync object (even empty warnings)
    sync = out.get("sync") if isinstance(out.get("sync"), dict) else {}
    if out.get("refreshed") or sync.get("months", 0) > 0 or sync.get("written"):
        return 0
    # Still ok if soft-fresh path said not stale
    if out.get("stale") is False:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
