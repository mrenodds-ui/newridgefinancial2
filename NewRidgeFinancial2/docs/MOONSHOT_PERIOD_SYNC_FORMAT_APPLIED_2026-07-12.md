# Moonshot APPLIED — DEF-001 Period Sync Honesty (hal-10565)

**Date:** 2026-07-12  
**Build:** **hal-10565**  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_DEF001_2026-07-12.md`  
**Prior:** DEF-001 honesty gates (`hal-10564` / `c645460`); Phase 5 GO  
**Status:** Applied. Live July still needs SoftDent **Register/Collections for 2026-07** (ops).

## Verdict vs consult

Moonshot’s consult framed `NO_PERIOD_ROW` from `assess_collections_gap(None)`. Live bundle shows **period rows exist**; July is `collectionsPending`. Inbox `daysheet.csv` is a **May 28 DaySheet**, not July Collections.

Applied the **real** package: stop invented patient dumps + stamp `COLLECTIONS_FORMAT_REQUIRED` when inbox files don’t cover the open month / lack Ins–Patient split.

## What shipped

| Area | Change |
|------|--------|
| Period sync | `_aggregate_daysheet` / `_build_period_row` — no `patient=collections` when insurance=0; `collectionsFormatRequired` |
| Gap assess | `GAP_COLLECTIONS_FORMAT_REQUIRED` + `classify_daysheet_inbox_periods()` |
| Refresh | `nextStep` / `collectionsGap` reflect format-required vs pending |
| Build | **hal-10565** |
| Tests | `test_period_sync_format_hal10565.py` + period sync / I2 updates |

## Live after sync (this machine)

- **2026-07:** production present, `collectionsPending=true`, insurance/patient 0  
- **2026-06:** collections total kept; false all-patient dump cleared; `collectionsFormatRequired=true`  
- Inbox classified periods: **`['2026-05']`** → does **not** cover open month → format required  

## Ops (closes live dollars)

1. SoftDent → Reports → Accounting → **Register for a Period** (`07/01/2026` → today) **or** Collections/Daysheet with real Ins/Patient split  
2. CSV → `C:\SoftDentReportExports`  
3. Sync / HAL: Refresh SoftDent period  
4. Restart Start Program for **hal-10565**

## Validation

```text
python -m unittest discover -s NewRidgeFinancial2 -p test_period_sync_format_hal10565.py -v
python -m unittest discover -s NewRidgeFinancial2 -p test_softdent_dashboard_period_sync.py -v
→ OK
```

## Honesty

Empty ≠ $0. No invented insurance/patient dollars. May DaySheet ≠ July Collections.
