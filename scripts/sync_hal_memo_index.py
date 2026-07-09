#!/usr/bin/env python3
"""Sync browser HalMemoIndex from governed + corpus + learned memory stores."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from knowledge_memory_store import write_browser_memo_index_js  # noqa: E402


def main() -> int:
    target = write_browser_memo_index_js()
    from knowledge_memory_store import load_approved_memories

    count = len(load_approved_memories())
    print(f"Wrote {target} ({count} approved indexable memories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
