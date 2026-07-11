# Moonshot AI — HAL Voice + Report Programming (APPLIED)

**Date:** 2026-07-11  
**Source consult:** `MOONSHOT_HAL_VOICE_REPORT_CONSULT_2026-07-11.md`  
**Directive:** Operator said proceed — implement without deviation.  
**Status:** Applied (MUST + SHOULD + NICE Phase 5)

## What shipped

| Phase | Item | Files |
|-------|------|-------|
| 1 MUST | `parse_voice_report_command` + board `run_tool` | `apex_backend.py`, `apex-core.js` |
| 1 MUST | Spoken excerpts on handoff / readiness / briefing tools | `site/hal-agent.js` |
| 2 MUST | PHI-safe TTS guards (`containsPhi`) | `site/hal-voice.js` |
| 3 SHOULD | Hold-to-talk PTT (`data-hal-voice-ptt="hold"`) | `site/app.js`, `site/hal-page-canvas.js` |
| 4 SHOULD | `daily_ops_briefing` + read-only APIs | `hal-agent.js`, `nr2_http_server.py` |
| 5 NICE | Voice calibration persistence | `site/hal-voice.js` |

## Feature flags

- Client: `window.NR2_CONFIG.voiceReportsEnabled` (default **true** after proceed)
- Server: `NR2_VOICE_REPORTS=0` disables board voice→report routing

## Voice grammar (deterministic)

- handoff / shift report / end of shift / clock out → `clock_out_shift`
- readiness / system check / health check / smoke test → `readiness_diagnostics`
- briefing / morning brief / daily ops / status update → `daily_ops_briefing`

## Read-only briefing endpoints

- `GET /api/softdent/today-schedule` (alias of appointments-today)
- `GET /api/claims/aging-summary` (counts + over30; no invented dollars)
- `GET /api/employee/on-duty` (active shift employee ids)

## Validation

- Unit: `python -m unittest test_hal_voice_report`
- Manual: say/type "handoff report", "readiness check", "morning briefing"
- PHI: speaking text containing `123-45-6789` should skip TTS and warn

## SoftDent / PHI

- SoftDent remains READ-ONLY
- Spoken excerpts use counts/ids only
- Browser TTS blocked when PHI patterns match unless `allowPhi:true`
