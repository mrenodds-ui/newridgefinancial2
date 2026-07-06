"""SQLite backup on NR2 startup — retain last N timestamped copies."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RETAIN = int(os.environ.get("NR2_SQLITE_BACKUP_RETAIN", "5"))


def backup_sqlite(db_path: Path, *, retain: int = DEFAULT_RETAIN) -> dict[str, Any]:
    db_path = Path(db_path)
    if not db_path.is_file():
        return {"ok": False, "error": "database not found", "path": str(db_path)}
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = backup_dir / f"nr2-{ts}.sqlite3"
    shutil.copy2(db_path, dest)
    keep = max(1, int(retain or DEFAULT_RETAIN))
    existing = sorted(backup_dir.glob("nr2-*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed: list[str] = []
    for old in existing[keep:]:
        try:
            old.unlink()
            removed.append(old.name)
        except OSError:
            pass
    return {"ok": True, "path": str(dest), "retain": keep, "removed": removed}
