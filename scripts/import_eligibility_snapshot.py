#!/usr/bin/env python3
"""Import one or more PHI-redacted eligibility snapshots into NR2 cache."""

from __future__ import annotations

import json
import sys
from pathlib import Path

NR2 = Path(__file__).resolve().parents[1] / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from eligibility_cache_store import upsert_eligibility_entry  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_eligibility_snapshot.py <snapshot.json>")
        return 1
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}")
        return 1
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw if isinstance(raw, list) else [raw.get("entry", raw)]
    ok = 0
    for item in entries:
        if not isinstance(item, dict):
            continue
        result = upsert_eligibility_entry(item)
        if result.get("ok"):
            ok += 1
            print(f"Cached: {result['entry'].get('payerName')} ({result['entry'].get('id')})")
    print(f"Imported {ok}/{len(entries)} entries")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
