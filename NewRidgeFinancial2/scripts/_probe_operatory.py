#!/usr/bin/env python3
"""Probe sd_appointments and refresh operatory_schedule.json."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from import_loader import softdent_import_dir
from quickbooks_monthly_sync import resolve_analytics_db
from softdent_practice_exports import sync_practice_exports


def main() -> None:
    db = resolve_analytics_db()
    print("analytics_db", db)
    conn = sqlite3.connect(db, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    cur = conn.cursor()
    cur.execute(
        "SELECT provider_code, COUNT(*) c FROM sd_appointments "
        "GROUP BY provider_code ORDER BY c DESC LIMIT 15"
    )
    print("providers", cur.fetchall())
    cur.execute(
        "SELECT COUNT(*) FROM sd_appointments WHERE appt_date >= date('now', '-7 day')"
    )
    print("last7_days", cur.fetchone()[0])
    cur.execute(
        "SELECT appt_date, provider_code, status FROM sd_appointments "
        "WHERE appt_date >= date('now', '-14 day') ORDER BY appt_date DESC LIMIT 12"
    )
    print("recent", cur.fetchall())
    conn.close()

    result = sync_practice_exports()
    print("sync_practice_exports", json.dumps(result, indent=2, default=str))

    op_path = softdent_import_dir() / "operatory_schedule.json"
    if op_path.is_file():
        payload = json.loads(op_path.read_text(encoding="utf-8-sig"))
        chairs = payload.get("operatoryChairs") or []
        print("operatory_path", op_path)
        print("chair_count", len(chairs))
        if chairs:
            print("sample_chair", json.dumps(chairs[0], indent=2)[:600])


if __name__ == "__main__":
    main()
