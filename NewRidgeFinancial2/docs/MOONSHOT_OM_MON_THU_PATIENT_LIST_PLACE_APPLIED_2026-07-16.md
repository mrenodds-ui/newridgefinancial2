# OM Mon–Thu Patient List — APPLIED (Optical 2A)

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_OM_MON_THU_PATIENT_LIST_PLACE_2026-07-16.md`  
**Operator:** approve → 2A; **continue** → SHOULD/NICE; **continue** → claims + HAL handoff

## Shipped

| Item | Where |
|------|--------|
| Mon–Thu schedule section | `site/nr2-optical-page-office-manager.html` |
| Fetch + render (PHI initials/hash) | `GET /api/softdent/appointments-range?days=4` |
| Grid + today highlight + print | `site/nr2-optical-theme.css` |
| Provider filter | `#wk-provider` → `?provider=` |
| Click → mini dossier | `#wk-dossier` + `GET /api/apex/patient-dossier-mini/{id}` |
| Claims sample on click | mini API embeds `get_claims_review_detail` (limit 5) |
| Ask HAL handoff | link → `nr2-optical-page-hal.html?patientHash=` (compose prefill) |

## Honesty

- SoftDent read-only; board = initials + hash only
- Time = `—`; empty ≠ $0; claim amounts null → `—` not `$0`
- Mini dossier account balance stays `unavailable` when schema has no AR column

## How to try

1. Hard-refresh Office Manager.
2. Click a Mon–Thu row → mini dossier + claims list.
3. **Ask HAL about this patient →** opens HAL with draft prompt.
