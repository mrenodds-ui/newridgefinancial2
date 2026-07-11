# Phase W2 Applied — Quarantine Review UI (Moonshot REAUDIT5 SHOULD)

**Date:** 2026-07-11  
**Build:** hal-10492  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT5_2026-07-11.md`  
**Status:** W2 applied and validated

## Shipped

| Item | Detail |
|------|--------|
| Panel widget | `quarantine-panel` → `import-quarantine-panel` |
| Actions | `retry_quarantine` (release + queue ingest), `purge_quarantine` |
| API | `POST /import-quarantine-retry`, `POST /import-quarantine-purge` |
| Frontend | `site/apex-quarantine-panel.js` + table render in `apex-core.js` |
| Tests | `test_apex_phase_w2_quarantine_ui.py` |

## Flags

```text
set NR2_QUARANTINE_UI=1
```

Default **ON**. Set `0` to hide the interactive panel.

## Honesty

- Purge deletes **local** quarantine copies only — no SoftDent write-back
- Retry re-queues through DQ-gated ingest; empty ≠ $0
- Panel shows filename / error code / attempts — no patient PHI

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_phase_w2_quarantine_ui.py NewRidgeFinancial2/test_apex_import_quarantine_u2b.py -q
```
