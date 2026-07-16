"""Discover SoftDent DOB / demographics needed for Trellis Add Patient."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from softdent_odbc_extract import resolve_sd_sqlite_db

db = resolve_sd_sqlite_db()
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("db", db)
print("sd_patients", [r[1] for r in cur.execute("PRAGMA table_info(sd_patients)").fetchall()])
print("sd_patient_insurance", [r[1] for r in cur.execute("PRAGMA table_info(sd_patient_insurance)").fetchall()])

dob_tables = []
for (t,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    hits = [c for c in cols if "dob" in c.lower() or "birth" in c.lower()]
    if hits:
        dob_tables.append({"table": t, "cols": hits, "all": cols})
print("dob_tables", json.dumps(dob_tables, indent=2))

# sample James Johnston
pid = "573301"
print("patient", dict(cur.execute("SELECT * FROM sd_patients WHERE patient_id=?", (pid,)).fetchone() or {}))
print("ins", [dict(r) for r in cur.execute("SELECT * FROM sd_patient_insurance WHERE patient_id=?", (pid,)).fetchall()])
