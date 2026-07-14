#!/usr/bin/env python3
"""HAL-10591 — CLI UI honesty audit (empty ≠ $0)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"
if str(NR2) not in sys.path:
    sys.path.insert(0, str(NR2))

from ui_honesty_policy import audit_ui_honesty_surfaces, format_honesty_audit_reply  # noqa: E402


def main() -> int:
    result = audit_ui_honesty_surfaces()
    print(format_honesty_audit_reply(result))
    print(json.dumps(result, indent=2, default=str)[:8000])
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
