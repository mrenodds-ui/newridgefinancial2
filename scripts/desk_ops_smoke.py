#!/usr/bin/env python3
"""CLI wrapper: NR2 desk smoke confidence loop."""

from __future__ import annotations

import json
import sys
from pathlib import Path

NR2 = Path(__file__).resolve().parents[1] / "NewRidgeFinancial2"
if str(NR2) not in sys.path:
    sys.path.insert(0, str(NR2))

from desk_smoke import run_desk_smoke  # noqa: E402


def main() -> int:
    probe = "--no-http" not in sys.argv
    result = run_desk_smoke(probe_http=probe)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
