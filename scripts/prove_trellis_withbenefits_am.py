"""Prove Trellis ClearCoverage withBenefits > 0 after nightly scrape (AM check).

Usage (tomorrow AM after 10:10 PM verify):
  python scripts/prove_trellis_withbenefits_am.py
  python scripts/prove_trellis_withbenefits_am.py --date 2026-07-17

Exit 0 when withBenefits > 0; exit 2 when still status-only; exit 1 on hard error.
Counts only — never invent deductible / $0. SoftDent READ-ONLY.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NR2 = REPO / "NewRidgeFinancial2"
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
OUT.mkdir(parents=True, exist_ok=True)

if str(NR2) not in sys.path:
    sys.path.insert(0, str(NR2))


def _candidate_dates(explicit: str | None) -> list[str]:
    if explicit:
        return [explicit.strip()]
    today = date.today()
    days: list[date] = []
    for offset in range(0, 5):
        d = today + timedelta(days=offset)
        if d.weekday() < 5:
            days.append(d)
    # Prefer soonest weekday (often "tomorrow" Mon–Thu target)
    return [d.isoformat() for d in days]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="YYYY-MM-DD schedule date to prove")
    args = ap.parse_args()

    from nr2_trellis_nightly import eligibility_report_snapshot

    rows = []
    best = None
    for iso in _candidate_dates(args.date):
        snap = eligibility_report_snapshot(target_date=iso)
        row = {
            "targetDate": iso,
            "ok": bool(snap.get("ok")),
            "hasReport": bool(snap.get("hasReport")),
            "patients": snap.get("patients"),
            "withBenefits": snap.get("withBenefits"),
            "statusOnly": snap.get("statusOnly"),
            "reportUrl": snap.get("reportUrl"),
            "boardPhi": snap.get("boardPhi"),
            "emptyNotZero": True,
        }
        rows.append(row)
        wb = snap.get("withBenefits")
        if isinstance(wb, int) and wb > 0 and (best is None or wb > int(best.get("withBenefits") or 0)):
            best = row

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT / f"trellis_withbenefits_am_proof_{stamp}.json"
    payload = {
        "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "candidates": rows,
        "best": best,
        "passed": bool(best and int(best.get("withBenefits") or 0) > 0),
        "note": (
            "Counts only — no deductible/$ invent. Board stays initials+hash. "
            "Tonight 10:10 PM Trellis --verify raises withBenefits when ClearCoverage scrapes land."
        ),
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Wrote {out_path}", flush=True)

    if payload["passed"]:
        return 0
    if any(r.get("ok") for r in rows):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
