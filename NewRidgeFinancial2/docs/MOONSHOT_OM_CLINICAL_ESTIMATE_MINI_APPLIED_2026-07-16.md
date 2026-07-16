# OM Mini-Dossier Clinical Notes + Treatment Estimates — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL_PATIENT_CONTEXT_2026-07-16.md`  
**Operator:** continue (deepen OM mini-dossier path)

## Shipped

| Item | Where |
|------|--------|
| Clinical note summaries (≤3, PHI-scrubbed) | `om_patient_dossier.get_patient_dossier_mini` via `load_clinical_context` |
| Treatment estimates (≤4 ADA × payer) | Same; `lookup_treatment_estimate` — null → `—` / empty ≠ $0 |
| OM panel sections | `nr2-optical-page-office-manager.js` Clinical notes + Treatment estimates |

## Honesty

- SoftDent READ-ONLY  
- No payer / insufficient sample → display `—` + reason (never invent $0)  
- Patient name scrubbed from note summary text on OM board  
- Estimates are historical payment-line aggregates, not benefit guarantees  

## How to try

1. Hard-refresh Office Manager.  
2. Click a Mon–Thu patient.  
3. Mini dossier shows Clinical notes + Treatment estimates above Claims.
