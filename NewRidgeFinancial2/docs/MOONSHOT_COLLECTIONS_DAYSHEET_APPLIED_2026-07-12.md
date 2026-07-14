# Moonshot APPLIED — Collections/Daysheet DEF-001 (after Phase 5 GO)

**Date:** 2026-07-12  
**Build:** **hal-10564**  
**Consult:** `MOONSHOT_COLLECTIONS_DAYSHEET_AFTER_PHASE5_2026-07-12.md`  
**Status:** Applied (code + honesty gates). **Ops export still required** to populate live dollars.

## What shipped

| Area | Change |
|------|--------|
| Gap assess | `scan_collections_export_inbox()` + `exportInbox` on `assess_collections_gap`; keep `collectionsGapCode` before ERA enrich |
| Financial UI | Period-aware empty `revenue-composition` message (empty ≠ $0); insert `softdent-collections-gap` when revenue empty |
| HAL | Board actions for “revenue composition empty”; local policy `policy:def-001-collections` |
| Refresh | `refresh_softdent_period_imports` scans export inbox; DEF-001 `nextStep` |
| Build | **hal-10564** |
| Tests | `test_collections_daysheet_hal10564.py` + hardened I2 |

## Honesty (non-negotiable)

- Empty Collections / revenue-composition is **not** $0.
- No invented insurance/patient dollars from ERA or stubs.
- ERA may stamp `ERA_835_AVAILABLE` as a **proposal only** — staff post in SoftDent.

## Ops checklist (closes the live data loop)

1. SoftDent → **Reports → Accounting** → **Collections** or **Daysheet** (or **Register for a Period** for the open month).
2. Export CSV into `C:\SoftDentReportExports` (filename should include Collections / Daysheet / Register).
3. In NR2: **Sync** imports, or ask HAL: **Refresh SoftDent period**.
4. Confirm Financial → `revenue-composition` shows real ins/patient split **or** still-honest empty with inbox/period hint.

## Live note (this machine)

- `C:\SoftDentReportExports` exists; inbox scan found daysheet-like files (`daysheet.csv` / `daysheet.jsonl`) but dashboard period may still show `collectionsPending` / ERA proposal — re-run SoftDent period sync after a true Collections export for **2026-07**.

## Validation

```text
python -m unittest discover -s NewRidgeFinancial2 -p test_collections_daysheet_hal10564.py -v
python -m unittest discover -s NewRidgeFinancial2 -p test_apex_softdent_hardening_i2.py -v
→ OK (1 skip when live warming stub)
```

## Restart

Restart Start Program so staff UI picks up **hal-10564** (IDB BUILD_ID gate clears stale mosaics).
