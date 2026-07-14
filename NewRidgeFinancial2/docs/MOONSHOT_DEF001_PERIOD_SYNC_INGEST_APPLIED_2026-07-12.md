# Moonshot DEF-001 Period Sync Ingestion — APPLIED (hal-10565)

**Date:** 2026-07-12  
**Build:** hal-10565  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_DEF001_SHIPPED_2026-07-12.md`  
**Status:** Applied (operator `proceed`)

## What shipped

| Item | Detail |
| --- | --- |
| Inbox → period stub | `ingest_daysheet_to_period()` in `softdent_dashboard_period_sync.py` |
| Inbox JSONL bootstrap | `_aggregate_inbox_daysheet()` when analytics DB has no daysheet row |
| Schema detect / summarize | `detect_daysheet_export_schema` + `summarize_daysheet_export` in `softdent_practice_exports.py` |
| Refresh force reimport | `refresh_softdent_period_imports` sets `force_reimport=True` when inbox has matches |
| Gap codes | `DAYSHEET_WITHOUT_SPLIT`, `COLLECTIONS_EXPORT_REQUIRED` (ops synonym), existing `COLLECTIONS_FORMAT_REQUIRED` / `COLLECTIONS_PENDING` |
| Honesty | Empty ≠ $0; no invented Ins/Patient dump; SoftDent read-only |

## Behavior

1. SoftDent export inbox (`daysheet.csv` / `.jsonl` / `register_for_period*.csv`) is scanned.
2. Schema detection distinguishes production-only daysheet vs register with Ins Plan split.
3. Period stub is written to `softdent_dashboard_data.json` from file metadata (never invent open-month dollars).
4. Production-only daysheet → `collectionsPending` + `daysheetWithoutSplit` + hint “Collections export required for split”.
5. Register with `Ins Plan Collections > 0` → real insurance/patient split populates revenue-composition.
6. `assess_collections_gap` never returns `NO_PERIOD_ROW` when a valid daysheet/register stub created a period row.

## Validation

```text
python -m unittest test_collections_daysheet_hal10564 test_period_sync_format_hal10565 test_softdent_dashboard_period_sync -v
```

- Inbox daysheet CSV → period stub + not `NO_PERIOD_ROW`
- `daysheetWithoutSplit` + pending → `DAYSHEET_WITHOUT_SPLIT` / `COLLECTIONS_EXPORT_REQUIRED`
- Register Ins Plan split → insurance/patient populated (no invent)
- Prior format-required + no all-patient dump tests remain green

## Not done (OPS)

- July open-month Collections / Register MTD with positive Ins Plan side still required for full revenue-composition on `2026-07` when inbox only has production-only daysheet.
