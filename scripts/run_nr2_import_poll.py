#!/usr/bin/env python3
"""Phase T3 — poll SoftDent/QB import inboxes and ingest into nr2_unified.

Moonshot alternative to watchdog (Task Scheduler every 5 minutes):
  python scripts/run_nr2_import_poll.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))


def main() -> int:
    from apex_import_watcher_pack import poll_once, watcher_status

    state_path = REPO / "NewRidgeFinancial2" / "app_data" / "nr2" / "import_poll_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    since = 0.0
    if state_path.is_file():
        try:
            since = float(json.loads(state_path.read_text(encoding="utf-8")).get("newestMtime") or 0)
        except Exception:
            since = 0.0
    result = poll_once(since_mtime=since)
    state_path.write_text(
        json.dumps({"newestMtime": result.get("newestMtime"), "at": result.get("refreshedAt")}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"poll": result, "status": watcher_status()}, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
