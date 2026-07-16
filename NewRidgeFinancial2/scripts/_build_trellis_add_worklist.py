"""Build tomorrow Trellis Add Patient worklist from Sensei Reference + SoftDent insurance."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATE = "2026-07-16"
DB = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
REF = Path(r"C:\ProgramData\Sensei Gateway Client\DataSync\0000950863\Reference")
OUT = Path(
    r"C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\vyne_pulls"
    f"\\tomorrow_trellis_add_worklist_{DATE}.json"
)


def _norm_dob(raw: str) -> str:
    text = str(raw or "").strip().replace("-", "/")
    if not text or text.startswith("0001") or text.lower() in {"none", "null"}:
        return ""
    parts = text.split("T")[0].split(" ")[0].split("/")
    if len(parts) != 3:
        return ""
    y, m, d = parts
    try:
        return f"{int(m):02d}/{int(d):02d}/{int(y):04d}"  # MM/DD/YYYY for Trellis
    except ValueError:
        return ""


def _load_patient(pid: str, name: str) -> dict | None:
    # Prefer UniqueID filename, then scan Id match if needed
    candidates = [REF / f"patient_{pid}.json"]
    for path in candidates:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        info = data.get("PATIENT") or data.get("PatientInfo") or data.get("patient") or data
        if not isinstance(info, dict):
            continue
        # Some files keyed by UniqueID while Id differs
        uid = str(info.get("UniqueID") or info.get("Id") or "").strip()
        file_id = path.stem.replace("patient_", "")
        if uid not in {pid, file_id} and str(info.get("Id") or "") not in {pid, file_id}:
            # still accept if name matches
            full = f"{info.get('Firstname') or info.get('FirstName') or ''} {info.get('Lastname') or info.get('LastName') or ''}".strip()
            if full.lower() != name.lower():
                continue
        dob = _norm_dob(
            str(info.get("Birthdate") or info.get("BirthDate") or info.get("DOB") or "")
        )
        sex = str(info.get("Sex") or info.get("Gender") or "").strip().upper()
        gender = {"M": "Male", "F": "Female", "MALE": "Male", "FEMALE": "Female"}.get(sex, sex)
        first = str(info.get("Firstname") or info.get("FirstName") or "").strip()
        last = str(info.get("Lastname") or info.get("LastName") or "").strip()
        middle = str(info.get("Middlename") or info.get("MiddleName") or "").strip()
        rel = str(info.get("Relationship0") or "").strip()
        # SoftDent: 01 = self typically
        is_subscriber = rel in {"01", "1", "SELF", "Self", ""}
        return {
            "patient_id": pid,
            "first": first,
            "last": last,
            "middle": middle,
            "dob": dob,
            "gender": gender,
            "is_subscriber": is_subscriber,
            "relationship0": rel,
            "insured0_ins_id": str(info.get("Insured0_InsId") or "").strip(),
            "src": str(path),
        }
    return None


conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
appts = conn.execute(
    """
    SELECT a.patient_id, p.patient_name
    FROM sd_appointments a
    LEFT JOIN sd_patients p ON p.patient_id = a.patient_id
    WHERE a.appt_date = ?
    ORDER BY p.patient_name
    """,
    (DATE,),
).fetchall()

rows = []
for appt in appts:
    pid = str(appt["patient_id"])
    name = str(appt["patient_name"] or "")
    demo = _load_patient(pid, name)
    ins = conn.execute(
        """
        SELECT * FROM sd_patient_insurance
        WHERE patient_id = ?
        ORDER BY priority
        LIMIT 1
        """,
        (pid,),
    ).fetchone()
    ins_d = dict(ins) if ins else {}
    rel_code = str(ins_d.get("relationship_code") or "").upper()
    is_self = rel_code in {"", "SELF", "01", "1"}
    if demo:
        demo["is_subscriber"] = is_self
    subscriber_id = str(ins_d.get("subscriber_id") or ins_d.get("member_id") or "").strip()
    member_id = str(ins_d.get("member_id") or "").strip()
    # Trellis Subscriber ID field usually wants member/subscriber id used for eligibility
    trellis_sub_id = member_id or subscriber_id
    rows.append(
        {
            "patient_id": pid,
            "patient_name": name,
            "demo": demo,
            "insurance": {
                "insurance_name": str(ins_d.get("insurance_name") or "").strip(),
                "carrier_code": str(ins_d.get("carrier_code") or "").strip(),
                "member_id": member_id,
                "subscriber_id": subscriber_id,
                "group_number": str(ins_d.get("group_number") or "").strip(),
                "relationship_code": rel_code,
                "trellis_subscriber_id": trellis_sub_id,
            },
            "ready": bool(
                demo
                and demo.get("dob")
                and demo.get("first")
                and demo.get("last")
                and (member_id or subscriber_id)
                and ins_d.get("insurance_name")
            ),
            "skip_reason": (
                None
                if (
                    demo
                    and demo.get("dob")
                    and (member_id or subscriber_id)
                    and ins_d.get("insurance_name")
                )
                else (
                    "missing SoftDent insurance"
                    if not ins_d
                    else ("missing DOB/demo" if not (demo and demo.get("dob")) else "incomplete")
                )
            ),
        }
    )

payload = {
    "date": DATE,
    "builtAt": datetime.now(timezone.utc).isoformat(),
    "total": len(rows),
    "ready": sum(1 for r in rows if r["ready"]),
    "patients": rows,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"wrote {OUT}")
print(f"ready {payload['ready']}/{payload['total']}")
for r in rows:
    d = r.get("demo") or {}
    flag = "READY" if r["ready"] else f"SKIP({r['skip_reason']})"
    print(
        f"{flag:22} {r['patient_name']:28} dob={d.get('dob','')} "
        f"sex={d.get('gender','')} carrier={r['insurance'].get('insurance_name','')} "
        f"id={r['insurance'].get('trellis_subscriber_id','')}"
    )
