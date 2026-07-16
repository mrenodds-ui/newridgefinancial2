"""Match tomorrow SoftDent appts to Sensei patient BirthDate/Gender."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
appts = conn.execute(
    """
  SELECT a.patient_id, p.patient_name
  FROM sd_appointments a
  LEFT JOIN sd_patients p ON p.patient_id = a.patient_id
  WHERE a.appt_date = '2026-07-16'
  ORDER BY p.patient_name
"""
).fetchall()
print(f"tomorrow appts: {len(appts)}")

roots = [
    Path(r"C:\SoftDent\DataSync\SDInjector_JSON\ImportedFiles\0000950863\patient"),
    Path(r"C:\ProgramData\Sensei Gateway Client\DataSync"),
    Path(r"C:\SoftDent\DataSync\SDExtractor_JSON"),
]


def index_patients(pat_dirs: list[Path]) -> tuple[dict, dict]:
    by_id: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for pat_dir in pat_dirs:
        if not pat_dir.is_dir():
            continue
        files = list(pat_dir.glob("patient_*.json"))
        if not files and pat_dir.name != "patient":
            files = list(pat_dir.rglob("patient_*.json"))
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            info = data.get("PatientInfo") or data.get("patient") or data
            if not isinstance(info, dict):
                continue
            lid = str(info.get("LegacyKey") or info.get("Id") or info.get("Code") or "").strip()
            fn = str(info.get("FirstName") or info.get("Firstname") or "").strip()
            ln = str(info.get("LastName") or info.get("Lastname") or "").strip()
            dob = str(info.get("BirthDate") or info.get("Birthdate") or info.get("DOB") or "")
            if "T" in dob:
                dob = dob.split("T")[0]
            rec = {
                "path": str(path),
                "id": lid,
                "first": fn,
                "last": ln,
                "dob": dob[:10],
                "gender": str(info.get("Gender") or info.get("Sex") or ""),
            }
            if not rec["dob"]:
                continue
            if lid:
                by_id[lid] = rec
            if fn and ln:
                by_name[f"{fn} {ln}".lower()] = rec
                by_name[f"{ln}, {fn}".lower()] = rec
    return by_id, by_name


pat_dirs = []
for root in roots:
    print("root", root, "exists", root.exists())
    if root.name == "patient" and root.is_dir():
        pat_dirs.append(root)
    elif root.is_dir():
        for p in root.rglob("patient"):
            if p.is_dir():
                pat_dirs.append(p)
                print("  patient dir", p)

by_id, by_name = index_patients(pat_dirs)
print(f"indexed with DOB: by_id={len(by_id)} by_name={len(by_name)}")

found = 0
missing = []
for row in appts:
    pid = str(row["patient_id"] or "")
    name = str(row["patient_name"] or "")
    rec = by_id.get(pid) or by_name.get(name.lower())
    if rec:
        found += 1
        print(f"OK  {name:30} id={pid} dob={rec['dob']} sex={rec['gender']}")
    else:
        missing.append((pid, name))
        print(f"MISS {name:30} id={pid}")
print(f"found={found} missing={len(missing)} of {len(appts)}")
