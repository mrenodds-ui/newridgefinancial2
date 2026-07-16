"""Pull SoftDent insurance fields for patients scheduled on a date."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from softdent_odbc_extract import resolve_sd_sqlite_db

target = sys.argv[1] if len(sys.argv) > 1 else "2026-07-16"
OUT = Path(__file__).resolve().parents[2] / "app_data" / "nr2" / "vyne_pulls"
OUT.mkdir(parents=True, exist_ok=True)

db = resolve_sd_sqlite_db()
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
cur = conn.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

# appointments for date
appts = cur.execute(
    """
    SELECT a.patient_id, a.appt_date, a.provider_code, a.status,
           COALESCE(p.patient_name,'') AS patient_name
    FROM sd_appointments a
    LEFT JOIN sd_patients p ON p.patient_id = a.patient_id
    WHERE a.appt_date = ? OR a.appt_date LIKE ?
    ORDER BY a.patient_id
    """,
    (target, f"%{target}%"),
).fetchall()

# discover useful columns across tables
schema = {}
for t in tables:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    schema[t] = cols

# Prefer explicit insurance tables if present
candidates = [
    t
    for t in tables
    if any(k in t.lower() for k in ("insur", "eligib", "plan", "carrier", "subscriber", "policy"))
]

rows_out = []
seen = set()
for a in appts:
    pid = str(a["patient_id"] or "").strip()
    if not pid or pid in seen:
        continue
    seen.add(pid)
    entry = {
        "patientId": pid,
        "patientName": a["patient_name"],
        "apptDate": a["appt_date"],
        "provider": a["provider_code"],
        "status": a["status"],
        "insurance": {},
        "gaps": [],
    }
    # patient demographics
    if "sd_patients" in tables:
        prow = cur.execute("SELECT * FROM sd_patients WHERE patient_id=? LIMIT 1", (pid,)).fetchone()
        if prow:
            entry["demographics"] = {
                k: prow[k]
                for k in prow.keys()
                if k
                in {
                    "patient_name",
                    "first_visit_date",
                    "last_visit_date",
                    "practice_id",
                    "dob",
                    "birth_date",
                    "date_of_birth",
                }
                or "dob" in k.lower()
                or "birth" in k.lower()
            }

    # scan related tables for this patient_id
    for t in tables:
        cols = schema.get(t) or []
        if "patient_id" not in cols:
            continue
        interesting = [
            c
            for c in cols
            if any(
                x in c.lower()
                for x in (
                    "ins",
                    "plan",
                    "carrier",
                    "member",
                    "subscriber",
                    "group",
                    "payer",
                    "policy",
                    "elig",
                )
            )
        ]
        if not interesting and t not in candidates:
            continue
        try:
            qcols = ", ".join(interesting) if interesting else "*"
            r = cur.execute(
                f"SELECT {qcols} FROM {t} WHERE patient_id=? LIMIT 3",
                (pid,),
            ).fetchall()
        except Exception:
            continue
        if not r:
            continue
        entry["insurance"][t] = [dict(x) for x in r]

    if not entry["insurance"]:
        entry["gaps"].append("no SoftDent insurance rows found for patient_id")
    rows_out.append(entry)

payload = {
    "ok": True,
    "targetDate": target,
    "count": len(rows_out),
    "tablesSeen": tables,
    "insuranceCandidateTables": candidates,
    "patients": rows_out,
}
path = OUT / f"tomorrow_softdent_insurance_{target}.json"
path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
print(json.dumps({"ok": True, "path": str(path), "count": len(rows_out), "withInsurance": sum(1 for p in rows_out if p['insurance']), "candidateTables": candidates}, indent=2))
