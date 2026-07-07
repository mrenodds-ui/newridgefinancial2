#!/usr/bin/env python3
"""Phase 3 cutover readiness — extends Moonshot batch5 validator + 30-day shadow criteria."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from nr2_pilot import cutover_readiness_checks

    report = cutover_readiness_checks()
    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        print("\nPhase 3 cutover: NOT READY", file=sys.stderr)
        print("NR2 remains assistant-only — keep daily SoftDent reconciliation.", file=sys.stderr)
        return 1
    print("\nPhase 3 cutover: READY — NR2 may operate as system of record on this workstation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
