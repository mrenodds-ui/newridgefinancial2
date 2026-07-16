"""Build Trellis Add Patient worklist from Sensei Reference + SoftDent insurance.

Callable API: build_trellis_worklist(target_date="YYYY-MM-DD")
CLI: python _build_trellis_add_worklist.py [YYYY-MM-DD]
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DB = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
REF = Path(r"C:\ProgramData\Sensei Gateway Client\DataSync\0000950863\Reference")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "app_data" / "nr2" / "vyne_pulls"


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
    candidates = [REF / f"patient_{pid}.json"]
    for path in candidates:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        info = data.get("PATIENT") or data.get("PatientInfo") or data.get("patient") or data
        if not isinstance(info, dict):
            continue
        uid = str(info.get("UniqueID") or info.get("Id") or "").strip()
        file_id = path.stem.replace("patient_", "")
        if uid not in {pid, file_id} and str(info.get("Id") or "") not in {pid, file_id}:
            full = (
                f"{info.get('Firstname') or info.get('FirstName') or ''} "
                f"{info.get('Lastname') or info.get('LastName') or ''}"
            ).strip()
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


def build_trellis_worklist(
    *,
    target_date: str | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Build SoftDent→Trellis worklist for appt_date (ISO YYYY-MM-DD)."""
    if not target_date:
        target_date = (date.today() + timedelta(days=1)).isoformat()
    out_root = Path(out_dir) if out_dir else DEFAULT_OUT
    out_path = out_root / f"tomorrow_trellis_add_worklist_{target_date}.json"

    if not DB.is_file():
        raise FileNotFoundError(f"SoftDent analytics DB missing: {DB}")

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
        (target_date,),
    ).fetchall()

    rows: list[dict[str, Any]] = []
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
                        else (
                            "missing DOB/demo"
                            if not (demo and demo.get("dob"))
                            else "incomplete"
                        )
                    )
                ),
            }
        )
    conn.close()

    payload = {
        "date": target_date,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "ready": sum(1 for r in rows if r["ready"]),
        "patients": rows,
        "path": str(out_path),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else (date.today() + timedelta(days=1)).isoformat()
    payload = build_trellis_worklist(target_date=target)
    print(f"wrote {payload['path']}")
    print(f"ready {payload['ready']}/{payload['total']}")
    for r in payload["patients"]:
        d = r.get("demo") or {}
        flag = "READY" if r["ready"] else f"SKIP({r['skip_reason']})"
        print(
            f"{flag:22} {r['patient_name']:28} dob={d.get('dob','')} "
            f"sex={d.get('gender','')} carrier={r['insurance'].get('insurance_name','')} "
            f"id={r['insurance'].get('trellis_subscriber_id','')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
