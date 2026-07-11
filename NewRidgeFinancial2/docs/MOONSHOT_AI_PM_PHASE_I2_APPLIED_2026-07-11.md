# Phase I2 Applied — SoftDent Collections/Daysheet Honesty (DEF-001)

**Date:** 2026-07-11  
**Build:** hal-10473  
**Plan:** AI Program Manager Upgrade  
**Prior:** I0 orchestrator · I1 structured insights  
**Status:** Phase I2 only — validated; **stop for I3 approval**

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_softdent_hardening_pack.py` — unified `assess_collections_gap` |
| Gap codes | `OK`, `COLLECTIONS_PENDING`, `COLLECTIONS_UNREPORTED`, `REGISTER_ONLY`, `COLLECTIONS_ZERO_ON_DAYSHEET`, `NO_PERIOD_ROW` |
| Widget | `softdent-collections-gap` on SoftDent page |
| Import health | DEF-001 warn alert when gap present |
| Revenue composition | Stamps `gapCode` / `def` when empty |
| SoftDent Collections KPI | Enriched with fix hint / gapCode when empty |
| HAL | “why are collections empty?” → gap reply + navigate SoftDent |
| API | `GET /api/apex/hal/collections-gap` |
| Tests | `test_apex_softdent_hardening_i2.py` |

## Honesty

- Empty Collections **≠ $0**
- Gap assessment never returns invented collections dollars when unhealthy
- Fix hint: daysheet / Register for a Period / Sync

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_softdent_hardening_i2.py -q
```

## Next

**I3** Additive unified SQLite (`nr2_unified.db`) for SoftDent×QB joins

Await: **approve I3**
