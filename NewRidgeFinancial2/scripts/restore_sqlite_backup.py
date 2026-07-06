#!/usr/bin/env python3
"""Restore NR2 SQLite from latest backup — Moonshot operator drill."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "app_data" / "nr2"
DB = DATA / "nr2.sqlite3"
BACKUP_DIR = DATA / "backups"


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore nr2.sqlite3 from latest backup")
    parser.add_argument("--backup", type=Path, help="Specific backup file")
    args = parser.parse_args()
    if not BACKUP_DIR.is_dir():
        print("No backup directory", file=sys.stderr)
        return 1
    backup = args.backup
    if not backup:
        candidates = sorted(BACKUP_DIR.glob("*.sqlite3*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            print("No backups found", file=sys.stderr)
            return 1
        backup = candidates[0]
    if not backup.is_file():
        print(f"Backup missing: {backup}", file=sys.stderr)
        return 1
    if DB.is_file():
        shutil.copy2(DB, DB.with_suffix(".sqlite3.pre-restore-bak"))
    shutil.copy2(backup, DB)
    print(f"Restored {DB} from {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
