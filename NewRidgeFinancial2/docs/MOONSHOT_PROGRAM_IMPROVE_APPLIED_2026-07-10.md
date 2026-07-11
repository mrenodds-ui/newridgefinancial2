# Program Improve Pack IMP-001..010 — Applied

**Date:** 2026-07-10  
**Build:** **hal-10390**  
**Consult:** `MOONSHOT_PROGRAM_IMPROVE_CONSULT_2026-07-10.md`  
**Status:** All ranked items applied after operator “proceed with all”

## Shipped

| ID | Item | Where |
|---|---|---|
| IMP-001 | Kanban card actions: Narrative / Note / Callback (NR2 audit only) | Claims Workbench |
| IMP-002 | SoftDent weekly period export task doc + HAL period-gap alerts | `docs/SOFTDENT_WEEKLY_PERIOD_EXPORT_TASK.md` + import health |
| IMP-003 | Proactive Import Health Monitor widget + HAL | Claims / Office Manager |
| IMP-004 | ERA 835 ingest → match → promote ERA Matched column | Documents upload + Claims |
| IMP-005 | A/R Aging Forecast (illustrative) | A/R page |
| IMP-006 | Claim attachment bridge (upload by claim ID) | Documents |
| IMP-007 | Daily Huddle dashboard | Office Manager |
| IMP-008 | Batch narratives (check Batch on cards → Narratives seed) | Claims → Narratives |
| IMP-009 | Voice/context carry (`nr2-apex-focused-claim` + HAL “draft appeal for this claim”) | HAL + Narratives |
| IMP-010 | EBITDA Trend chart (rolling snapshots) | Financial |

## Honesty

- No SoftDent write-back from kanban actions
- ERA/forecast never invent dollars; forecast labeled illustrative
- Attachments stored under `app_data/nr2/claim_attachments`

## Files

- `apex_program_improve_pack.py` (new)
- `apex_backend.py`, `nr2_browser_security.py`
- `site/apex-core.js`, `site/apex-bridge.css`, `site/index.html`
- `nr2-build.json` → **hal-10390**
- `docs/SOFTDENT_WEEKLY_PERIOD_EXPORT_TASK.md`
- `docs/MOONSHOT_PROGRAM_IMPROVE_APPLIED_2026-07-10.md`
