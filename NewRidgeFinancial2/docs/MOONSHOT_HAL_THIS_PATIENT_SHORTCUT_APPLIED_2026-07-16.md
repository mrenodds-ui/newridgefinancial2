# HAL “This Patient” Shortcut — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_OM_CLINICAL_MINI_2026-07-16.md`  
**Operator:** approve

## Shipped

| Item | Where |
|------|--------|
| Detect “this / current / about this patient” | `patient_dossier.query_refers_to_bound_patient` |
| Bound resolve via session TTL context | `format_hal_patient_summary_reply(..., session_id=)` |
| Unbound polite ask for OM Ask HAL or SoftDent id | intent `policy:patient-summary-unbound` |
| Pass `session_id` through HAL chat/gateway | `nr2_hal_gateway` + `nr2_http_server` chat/SSE |
| Early policy before money beams | so “copay for this patient” hits dossier path |
| Escape `{{fields}}` in AI prompt | `patient_dossier_prompts.py` (`.format` KeyError) |

## How to try

1. OM → Mon–Thu row → **Ask HAL** (binds context).  
2. In HAL chat: `What's the insurance for this patient?`  
3. Expect bound hash/initials header + SoftDent summary (empty ≠ $0).  
4. Without bind: HAL asks to use Ask HAL or give SoftDent id.
