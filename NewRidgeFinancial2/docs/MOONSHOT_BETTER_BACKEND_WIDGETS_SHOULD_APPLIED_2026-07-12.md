# Moonshot Better Backend Widgets SHOULD — APPLIED (hal-10568)

**Date:** 2026-07-12  
**Coding:** `MOONSHOT_BETTER_BACKEND_WIDGETS_SHOULD_CODING_2026-07-12.md`  
**Prior MUST:** `MOONSHOT_BETTER_BACKEND_WIDGETS_APPLIED_2026-07-12.md` (hal-10567)  
**Build:** **hal-10568**  
**Operator:** continue  

## What shipped (SHOULD gap-fill only)

| Widget | Type | Page | Id |
|--------|------|------|----|
| Recommended Actions | `action-list` | hal | `hal-recommended-actions` |
| Collections Workbench | `collection-task-list` | ar (main) | `ar-collection-task-list` |
| Narrative Insight | `ai-insight` | narratives | `narratives-ai-insight` |
| Patient Dossier | `patient-dossier-card` | softdent | `softdent-patient-dossier` |

## Already satisfied (not duplicated)

- OM `action-list` / patient-dossier via `apex_missing_widgets_pack`
- HAL `ai-insight` via `apex_structured_insight_pack`
- A/R collections **subpage** `collection-task-list` via `apex_subpages_pack`

## Files

| File | Change |
|------|--------|
| `apex_better_backend_widgets_pack.py` | Four SHOULD builders |
| `apex_backend.py` | Wire hal / ar / narratives / softdent; BUILD_ID **hal-10568** |
| Assets / tests | Cache-bust + SHOULD smoke tests |

## Live FE adaptations

- `collection-task-list`: `seeds`/`notes` on spec root (not nested in `data`)
- `ai-insight`: `insight` on spec root; `action_cta` = `{label, route}`
- SoftDent dossier empty: falsy `patientHash` so empty message renders

## Not done (NICE)

`pareto-chart`, `tax-calendar`, `timeline-lanes`

## Validation

```text
python -m unittest test_better_backend_widgets_should_hal10568 -v
```

Restart backend + hard-refresh browser.  
