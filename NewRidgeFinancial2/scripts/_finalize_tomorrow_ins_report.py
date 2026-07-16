import json
from datetime import datetime, timezone
from pathlib import Path

p = Path(r"C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\vyne_pulls\tomorrow_insurance_pull_2026-07-16.json")
d = json.loads(p.read_text(encoding="utf-8"))
for pt in d["patients"]:
    ins = pt.get("softdentInsurance") or {}
    name = ins.get("insurance_name")
    if isinstance(name, str) and (not name.strip() or "\ufffd" in name):
        ins.pop("insurance_name", None)
    if not ins:
        pt["gaps"] = ["No SoftDent sd_patient_insurance row"]
        pt["softdentInsurance"] = {}
d["pulledAt"] = datetime.now(timezone.utc).isoformat()
d["trellisEligibility"] = {
    "searched": True,
    "matchedInPatientList": 0,
    "note": (
        "Tomorrow SoftDent schedule patients are not present in Trellis Eligibility Patient List. "
        "SoftDent chart insurance pulled instead. Live ClearCoverage requires Add Patient + Verify "
        "(DOB not in current sd_patients extract)."
    ),
}
p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

lines = [
    "# Tomorrow insurance pull — 2026-07-16",
    "",
    f"Patients: {d['count']} · SoftDent insurance on file: {d['withSoftDentInsurance']}",
    "",
    "| Patient | SoftDent carrier | Member ID |",
    "|---|---|---|",
]
for pt in d["patients"]:
    ins = pt.get("softdentInsurance") or {}
    carrier = ins.get("insurance_name") or "—"
    member = ins.get("member_id") or "—"
    lines.append(f"| {pt['patientName']} | {carrier} | {member} |")
lines += [
    "",
    "## Trellis",
    d["trellisEligibility"]["note"],
    "",
    f"Saved: `{p}`",
]
md = Path(r"C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\vyne_pulls\tomorrow_insurance_pull_2026-07-16.md")
md.write_text("\n".join(lines), encoding="utf-8")
print(md)
