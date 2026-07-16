"""Search Vyne Eligibility for SoftDent tomorrow patients — run while Trellis session open in browser is manual;
this script prepares the worklist and merges SoftDent schedule with prior pull templates.
Also used by agent to drive search names.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "app_data" / "nr2" / "vyne_pulls"
SCHEDULE = OUT / "softdent_appts_2026-07-16.json"


def last_first(name: str) -> str:
    parts = [p for p in str(name or "").split() if p]
    if len(parts) >= 2:
        return f"{parts[-1]}, {' '.join(parts[:-1])}"
    return name


def main() -> None:
    data = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    patients = data.get("patients") or []
    work = []
    for p in patients:
        name = str(p.get("patientName") or "").strip()
        work.append(
            {
                "patientId": p.get("patientId"),
                "patientName": name,
                "searchNames": [name, last_first(name), name.split()[-1] if name else ""],
                "provider": p.get("provider"),
                "status": p.get("status"),
            }
        )
    payload = {
        "targetDate": data.get("targetDate") or "2026-07-16",
        "count": len(work),
        "patients": work,
    }
    path = OUT / "tomorrow_insurance_worklist.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(path), "count": len(work)}, indent=2))


if __name__ == "__main__":
    main()
