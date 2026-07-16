# HAL this-patient shortcut harden + OM print polish — APPLIED

**Date:** 2026-07-16  
**Consult backlog:** `MOONSHOT_WHATS_NEXT_AFTER_DESK_SMOKE_THIS_PATIENT_2026-07-16.md` items #3–#4  
**Operator:** continue with all

## Already shipped earlier in this wave

| # | Package | Commit |
|---|---------|--------|
| 1 | Sensei/ODBC `appt_time` extract + preserve | `17de5f9` / `3992284` |
| 2 | Trellis morning huddle OM panel | `3992284` / `137bc1a` |
| Desk smoke this-patient | `daa7ba2` |

Live desk smoke: `thisPatientShortcutCovered: true`, `monThuApptTimeOk: true` (~93% timed).

## This pass (#3–#4)

| Item | Where |
|------|--------|
| Clearer unbound when no HAL `session_id` | `patient_dossier.format_hal_patient_summary_reply` |
| Tests: no session + RBAC denied | `test_patient_dossier.py` |
| Print: provider group headers + avoid slot splits | `nr2-optical-theme.css` `@media print` |

## Honesty

- SoftDent READ-ONLY · empty ≠ $0 · board PHI = initials + hash  
- Missing times still `—` (never invent 09:00)
