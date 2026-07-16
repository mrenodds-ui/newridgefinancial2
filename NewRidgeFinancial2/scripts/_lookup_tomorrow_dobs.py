"""Lookup tomorrow patients in Sensei Reference for BirthDate."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
appts = [
    (str(r["patient_id"]), str(r["patient_name"] or ""))
    for r in conn.execute(
        """
        SELECT a.patient_id, p.patient_name
        FROM sd_appointments a
        LEFT JOIN sd_patients p ON p.patient_id = a.patient_id
        WHERE a.appt_date = '2026-07-16'
        """
    )
]
want_ids = {pid for pid, _ in appts}
print("want", len(want_ids))

ref = Path(r"C:\ProgramData\Sensei Gateway Client\DataSync\0000950863\Reference")
# Count patient files
patient_files = list(ref.glob("patient_*.json"))
print("Reference patient_*.json", len(patient_files))

found = {}
# Prefer exact id files first
for pid, name in appts:
    for cand in [
        ref / f"patient_{pid}.json",
        Path(r"C:\SoftDent\DataSync\SDInjector_JSON\ImportedFiles\0000950863\patient")
        / f"patient_{pid}.json",
    ]:
        if cand.is_file():
            data = json.loads(cand.read_text(encoding="utf-8"))
            info = data.get("PatientInfo") or data.get("patient") or data
            dob = str(info.get("BirthDate") or info.get("Birthdate") or "")
            if "T" in dob:
                dob = dob.split("T")[0]
            found[pid] = {
                "name": name,
                "dob": dob[:10],
                "gender": str(info.get("Gender") or ""),
                "first": str(info.get("FirstName") or info.get("Firstname") or ""),
                "last": str(info.get("LastName") or info.get("Lastname") or ""),
                "src": str(cand),
            }
            break

print("direct id hits", len(found))
missing = [(pid, name) for pid, name in appts if pid not in found]
print("missing after direct", len(missing))

# Scan Reference patient files for remaining ids / names
if missing:
    miss_ids = {p for p, _ in missing}
    miss_names = {n.lower(): p for p, n in missing}
    scanned = 0
    for path in patient_files:
        scanned += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        info = data.get("PatientInfo") or data.get("patient") or data
        if not isinstance(info, dict):
            continue
        lid = str(info.get("LegacyKey") or info.get("Id") or "").strip()
        fn = str(info.get("FirstName") or info.get("Firstname") or "").strip()
        ln = str(info.get("LastName") or info.get("Lastname") or "").strip()
        full = f"{fn} {ln}".lower()
        hit_pid = None
        if lid in miss_ids:
            hit_pid = lid
        elif full in miss_names:
            hit_pid = miss_names[full]
        if not hit_pid:
            continue
        dob = str(info.get("BirthDate") or info.get("Birthdate") or "")
        if "T" in dob:
            dob = dob.split("T")[0]
        name = next(n for p, n in appts if p == hit_pid)
        found[hit_pid] = {
            "name": name,
            "dob": dob[:10],
            "gender": str(info.get("Gender") or ""),
            "first": fn,
            "last": ln,
            "src": str(path),
        }
        miss_ids.discard(hit_pid)
        if full in miss_names:
            miss_names.pop(full, None)
        if not miss_ids:
            break
    print("scanned", scanned, "found total", len(found), "still missing", len(miss_ids))

out = Path(r"C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\vyne_pulls\tomorrow_dobs_2026-07-16.json")
out.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "date": "2026-07-16",
    "found": found,
    "missing": [{"patient_id": p, "patient_name": n} for p, n in appts if p not in found],
}
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("wrote", out)
for pid, name in appts:
    rec = found.get(pid)
    if rec:
        print(f"OK  {name:30} dob={rec['dob']} sex={rec['gender']}")
    else:
        print(f"MISS {name:30} id={pid}")
