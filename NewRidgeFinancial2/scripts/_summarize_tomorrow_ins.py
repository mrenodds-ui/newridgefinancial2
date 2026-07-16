import json
from pathlib import Path

raw = Path(r"C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\vyne_pulls\tomorrow_softdent_insurance_2026-07-16.json")
d = json.loads(raw.read_text(encoding="utf-8"))
summary = []
for pt in d["patients"]:
    spi_rows = (pt.get("insurance") or {}).get("sd_patient_insurance") or []
    spi = spi_rows[0] if spi_rows else {}
    keep = {}
    for k, v in (spi or {}).items():
        if v in (None, "", 0, "0"):
            continue
        kl = k.lower()
        if any(
            x in kl
            for x in (
                "carrier",
                "plan",
                "member",
                "subscri",
                "group",
                "payer",
                "ins",
                "relat",
                "dob",
                "birth",
                "first",
                "last",
                "id",
                "phone",
                "employer",
            )
        ):
            keep[k] = v
    summary.append(
        {
            "patientId": pt["patientId"],
            "patientName": pt["patientName"],
            "apptDate": pt["apptDate"],
            "softdentInsurance": keep,
            "vyneStatus": "not_in_trellis_eligibility_list",
        }
    )

out = {
    "ok": True,
    "targetDate": "2026-07-16",
    "source": "SoftDent sd_patient_insurance + Trellis Eligibility search",
    "trellisNote": "None of tomorrow SoftDent scheduled patients matched Trellis Eligibility Patient List search (No data). SoftDent chart insurance used as pull baseline; Add Patient+Verify needed in Trellis for live ClearCoverage.",
    "count": len(summary),
    "withSoftDentInsurance": sum(1 for s in summary if s["softdentInsurance"]),
    "patients": summary,
}
path = Path(r"C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\vyne_pulls\tomorrow_insurance_pull_2026-07-16.json")
path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
print(f"wrote {path}")
print(f"count={out['count']} withIns={out['withSoftDentInsurance']}")
for s in summary:
    ins = s["softdentInsurance"]
    carrier = (
        ins.get("carrier_name")
        or ins.get("insurance_name")
        or ins.get("payer_name")
        or ins.get("plan_name")
        or ins.get("carrier")
        or "—"
    )
    member = ins.get("member_id") or ins.get("subscriber_id") or ins.get("policy_id") or "—"
    print(f"{s['patientName'][:30]:30} | {str(carrier)[:32]:32} | {member}")
