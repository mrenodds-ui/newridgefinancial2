# Phase I3 Applied — Unified SQLite Data Plane

**Date:** 2026-07-11  
**Build:** hal-10474  
**Plan:** AI Program Manager Upgrade  
**Prior:** I0 orchestrator · I1 structured insights · I2 Collections honesty  
**Status:** Phase I3 validated — MUST closeout in `MOONSHOT_AI_PM_PHASE_I4_APPLIED_2026-07-11.md`

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_unified_db_pack.py` |
| DB | Additive `app_data/nr2/nr2_unified.db` (does not touch `nr2_local.sqlite3`) |
| Tables | `softdent_period_metrics`, `qb_expense_rows`, `import_health_log` |
| View | `practice_health_snapshot` (SoftDent×QB join) |
| Sync hook | `apex_sync_trigger` → `ingest_from_bundle` |
| Orchestrator | Deep lanes get unified period snapshot in system prompt (no PHI) |
| Widget | `unified-db-snapshot` on Financial + HAL |
| APIs | `GET /api/apex/unified/snapshot`, `POST /api/apex/unified/ingest` |
| Tests | `test_apex_unified_db_i3.py` |

## Honesty

- Collections pending periods store `collections=NULL` (not $0)
- Snapshot is a mirror of import bundle only
- Rollback: delete `nr2_unified.db`; bundles still work

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_unified_db_i3.py NewRidgeFinancial2/test_apex_softdent_hardening_i2.py NewRidgeFinancial2/test_apex_structured_insight_i1.py NewRidgeFinancial2/test_apex_orchestrator_i0.py -q
```

## Next

**I4** Integration gates + flag smoke — **done** (`MOONSHOT_AI_PM_PHASE_I4_APPLIED_2026-07-11.md`)
