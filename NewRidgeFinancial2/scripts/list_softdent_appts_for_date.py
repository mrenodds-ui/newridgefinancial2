"""List SoftDent appointments for a given date (default tomorrow)."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from softdent_odbc_extract import resolve_sd_sqlite_db

target = sys.argv[1] if len(sys.argv) > 1 else (date.today() + timedelta(days=1)).isoformat()
# also allow MM/DD/YYYY variants
parts = target.split("-")
mdy = f"{int(parts[1])}/{int(parts[2])}/{parts[0]}" if len(parts) == 3 else target
mdy0 = f"{parts[1]}/{parts[2]}/{parts[0]}" if len(parts) == 3 else target

db = resolve_sd_sqlite_db()
out = {"ok": False, "targetDate": target, "db": str(db) if db else None, "patients": []}
if not db or not Path(db).is_file():
    print(json.dumps(out))
    raise SystemExit(1)

conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
cur = conn.cursor()
# Find matching appointment dates
patterns = [target, mdy, mdy0, target.replace("-", "/"), f"%{parts[1]}/{parts[2]}/{parts[0]}%" if len(parts) == 3 else target]
rows = cur.execute(
    """
    SELECT a.appt_date, a.provider_code, a.status, a.patient_id,
           COALESCE(p.patient_name, '') AS patient_name
    FROM sd_appointments a
    LEFT JOIN sd_patients p ON p.patient_id = a.patient_id
    WHERE a.appt_date = ?
       OR a.appt_date = ?
       OR a.appt_date = ?
       OR a.appt_date LIKE ?
    ORDER BY a.patient_id
    """,
    (target, mdy, mdy0, f"%{int(parts[1])}/{int(parts[2])}/{parts[0]}%" if len(parts) == 3 else target),
).fetchall()

# If zero, try looser LIKE on month/day/year pieces
if not rows and len(parts) == 3:
    y, m, d = parts
    rows = cur.execute(
        """
        SELECT a.appt_date, a.provider_code, a.status, a.patient_id,
               COALESCE(p.patient_name, '') AS patient_name
        FROM sd_appointments a
        LEFT JOIN sd_patients p ON p.patient_id = a.patient_id
        WHERE a.appt_date LIKE ?
           OR a.appt_date LIKE ?
           OR a.appt_date LIKE ?
        ORDER BY a.patient_id
        """,
        (f"%{y}-{m}-{d}%", f"%{m}/{d}/{y}%", f"%{int(m)}/{int(d)}/{y}%"),
    ).fetchall()

seen = set()
for r in rows:
    pid = str(r["patient_id"] or "").strip()
    name = str(r["patient_name"] or "").strip()
    key = (pid, name)
    if key in seen:
        continue
    seen.add(key)
    out["patients"].append(
        {
            "patientId": pid,
            "patientName": name,
            "apptDate": r["appt_date"],
            "provider": r["provider_code"],
            "status": r["status"],
        }
    )

out["ok"] = True
out["count"] = len(out["patients"])
# recent date samples for debug if empty
if not out["patients"]:
    samples = cur.execute(
        "SELECT DISTINCT appt_date FROM sd_appointments ORDER BY appt_date DESC LIMIT 20"
    ).fetchall()
    out["recentDates"] = [s[0] for s in samples]
print(json.dumps(out, indent=2))
