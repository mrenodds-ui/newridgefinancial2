"""CLI: SoftDent Collections-for-Period Excel export (safe wrapper).

Menu keys after Reports→Accounting default to 'c'. Override with
SOFTDENT_COLLECTIONS_MENU_KEYS if SoftDent version differs.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

from softdent_gui_export import export_collections_for_period  # noqa: E402


def main() -> int:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=f"{today.year:04d}-{today.month:02d}-01")
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--menu-keys", default=None, help="Keys after Accounting (default: c or env)")
    args = parser.parse_args()
    path = export_collections_for_period(
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        menu_keys=args.menu_keys,
    )
    print(f"OK wrote {path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
