#!/usr/bin/env python3
"""Sync SoftDent InsCo + Office Insurance contacts → payer_reference.json.

Default: write STAGING file for operator diff review.
Pass --apply to promote staging → production and broadcast alerts.

Reuses merge logic from feed_hal_dental_insurances.py (Moonshot HAL-said 2.1).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))
sys.path.insert(0, str(ROOT / "scripts"))

from feed_hal_dental_insurances import (  # noqa: E402
    PAYER_PATH,
    load_insco_from_sensei,
    load_office_contacts,
    merge_into_payer_reference,
)

STAGING_PATH = PAYER_PATH.with_suffix(".staging.json")


def _snapshot_ids_phones() -> dict[str, str]:
    if not PAYER_PATH.is_file():
        return {}
    data = json.loads(PAYER_PATH.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for p in data.get("payers") or []:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        out[str(p["id"])] = str(p.get("eligibilityNotes") or p.get("narrativeNotes") or "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync Office Insurance / SoftDent InsCo → payer_reference")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Promote staging to production and broadcast payer alerts",
    )
    ap.add_argument(
        "--staging-only",
        action="store_true",
        help="Only write staging (default behavior without --apply)",
    )
    args = ap.parse_args()

    before = _snapshot_ids_phones()
    insco = load_insco_from_sensei()
    office = load_office_contacts()
    print(f"SoftDent InsCo rows: {len(insco)}")
    print(f"Office Insurance contacts: {len(office)}")

    # merge_into_payer_reference writes production — for staging we copy first
    backup = None
    if not args.apply:
        if PAYER_PATH.is_file():
            backup = PAYER_PATH.read_text(encoding="utf-8")
        added, updated = merge_into_payer_reference(insco, office)
        staging_body = PAYER_PATH.read_text(encoding="utf-8")
        STAGING_PATH.write_text(staging_body, encoding="utf-8")
        if backup is not None:
            PAYER_PATH.write_text(backup, encoding="utf-8")
            try:
                from payer_reference_store import load_payer_reference

                load_payer_reference.cache_clear()
            except Exception:
                pass
        print(f"STAGING written: {STAGING_PATH}")
        print(f"merge preview: added={added} updated={updated}")
        print("Review staging diff, then re-run with --apply to promote.")
        return 0

    # --apply: merge to production (or promote existing staging)
    if STAGING_PATH.is_file() and args.apply and not insco and not office:
        PAYER_PATH.write_text(STAGING_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        added, updated = 0, 0
        print(f"Promoted staging → {PAYER_PATH}")
    else:
        added, updated = merge_into_payer_reference(insco, office)
        if STAGING_PATH.is_file():
            STAGING_PATH.write_text(PAYER_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Applied to production: added={added} updated={updated}")

    after = _snapshot_ids_phones()
    changed = [pid for pid, notes in after.items() if before.get(pid) != notes]
    new_ids = [pid for pid in after if pid not in before]
    print(f"Changed payers: {len(changed)} · new: {len(new_ids)}")

    try:
        from apex_hal_said_improve_pack import broadcast_payer_change

        for pid in (changed + new_ids)[:40]:
            broadcast_payer_change(
                pid,
                f"Payer reference sync {datetime.now(timezone.utc).strftime('%Y-%m-%d')}: "
                f"{'new' if pid in new_ids else 'updated'} contact/notes",
                notify_steve=("eligibility" in (after.get(pid) or "").lower()),
            )
        print(f"Broadcast alerts for {min(40, len(changed) + len(new_ids))} payer(s)")
    except Exception as exc:
        print(f"(alerts skipped: {exc})")

    try:
        from payer_reference_store import load_payer_reference

        load_payer_reference.cache_clear()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
