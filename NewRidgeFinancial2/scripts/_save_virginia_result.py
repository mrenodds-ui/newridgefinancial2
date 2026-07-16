"""Append Virginia Lowe result and refresh pull summary."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

p = Path(
    r"C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\vyne_pulls"
    r"\tomorrow_trellis_verify_results_2026-07-16.json"
)
data = json.loads(p.read_text(encoding="utf-8"))
results = [r for r in data.get("results", []) if r.get("patient_name") != "Virginia Lowe"]
results.append(
    {
        "patient_name": "Virginia Lowe",
        "patient_id": "39702",
        "status": "Insurance Info Issue",
        "carrier": "Delta Dental of Indiana / MDWISE (Medicaid IN)",
        "carrierId": "DELTI",
        "memberId": "949065610",
        "dob": "01/31/1965",
        "verifiedAt": "2026-07-15",
        "notes": (
            "SoftDent DELTA DENTAL OF IN mapped to Trellis Medicaid IN variant; "
            "may need alternate Delta IN commercial carrier"
        ),
    }
)
data["results"] = results
data["updatedAt"] = datetime.now(timezone.utc).isoformat()
data["verifiedCount"] = len(results)
data["summary"] = {
    "readyWorklist": 28,
    "skippedNoInsurance": ["Steve Eberhart", "Jackie Conrady"],
    "verifiedSoFar": len(results),
    "eligible": sum(1 for r in results if r.get("status") == "Eligible"),
    "issues": sum(1 for r in results if r.get("status") != "Eligible"),
}
p.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(json.dumps(data["summary"], indent=2))

md = Path(
    r"C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\vyne_pulls"
    r"\tomorrow_insurance_pull_2026-07-16.md"
)
lines = [
    "# Tomorrow insurance pull (2026-07-16)",
    "",
    "SoftDent schedule: 30. Ready for Trellis Add+Verify: 28 (DOB from Sensei Reference). "
    "Skip: Eberhart, Conrady (no SoftDent insurance).",
    "",
    "## Trellis Add Patient + Verify so far",
    "",
]
for r in results:
    lines.append(
        f"- **{r['patient_name']}**: {r['status']} — {r.get('carrier', '')} "
        f"(id {r.get('memberId', '')})"
    )
lines += [
    "",
    "## Notes",
    "- DOBs from Sensei Reference `patient_*.json` (`Birthdate` / `Sex`).",
    "- SoftDent `DELTA DENTAL OF MO` → Trellis `Delta Dental of Missouri` worked "
    "(James Johnston Eligible).",
    "- SoftDent `DELTA DENTAL OF IN` → first Trellis hit was Medicaid MDWISE "
    "(Virginia Lowe Insurance Info Issue).",
    "",
]
md.write_text("\n".join(lines), encoding="utf-8")
print("updated", md)
