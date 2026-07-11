# Phase U2b Applied — Import Quarantine & Alerting (Moonshot REAUDIT3 SHOULD)

**Date:** 2026-07-11  
**Build:** hal-10485  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT3_2026-07-11.md`  
**Status:** U2b applied and validated

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_import_quarantine_pack.py` |
| Hook | `queue_import` → quarantine after persistent failure |
| Dir | `app_data/nr2/import_quarantine/` (+ `.reason.json` sidecar) |
| Threshold | **3** failures (`NR2_IMPORT_FAIL_THRESHOLD`) |
| Alert | Schema alert-banner → `save_last_insight` (SSE) |
| APIs | `import-quarantine-status`, `import-quarantine`, `import-quarantine-release` |
| Widget | `import-quarantine-status` on Financial |
| Flag | `NR2_IMPORT_QUARANTINE` default **ON** |

## Honesty

- Gap `IMPORT_QUARANTINED` — never invent dollars; alert `value=null`
- No SoftDent write-back; originals moved aside only

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_import_quarantine_u2b.py -q
```

## Rollback

```text
set NR2_IMPORT_QUARANTINE=0
```
