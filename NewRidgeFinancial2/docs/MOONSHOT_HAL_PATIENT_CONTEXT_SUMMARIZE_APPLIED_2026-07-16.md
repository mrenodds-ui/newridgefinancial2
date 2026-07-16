# HAL Patient Context + Dossier Summarize — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_OM_MON_THU_2026-07-16.md`  
**Operator:** approve

## Shipped

| Item | Where |
|------|--------|
| Session patient context (30 min TTL) | `hal_session_store.set_patient_context` / `active_patient_context` |
| `POST/GET /api/hal/patient-context` | `nr2_http_server.py` + audit `context_set` |
| Chat persona inject | `patient_context_persona_block` in `hal_chat_api` |
| `GET /api/hal/tools/patient-dossier-summary` | Thin SoftDent dossier + local summarize |
| OM Ask HAL handoff | `askHalAboutPatient` → sessionStorage + `?patientId=&autoSummarize=1` |
| HAL bind + banner + auto-summarize | `nr2-optical-page-hal.js` / `.html` / command CSS |

## Flow

1. OM Mon–Thu row → mini dossier  
2. **Ask HAL about this patient** → audit + navigate with SoftDent `patientId`  
3. HAL binds context via `POST /api/hal/patient-context`  
4. Banner shows initials · hash; auto-runs `Summarize patient {id}` via existing chat policy  

## Honesty

- SoftDent READ-ONLY; empty ≠ $0  
- Board still hash/initials; SoftDent id used only for bound summarize  
- No Classic Apex 2B restore (deferred)
