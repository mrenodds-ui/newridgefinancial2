# Moonshot HAL Voice NICE + Availity live-ready — Applied

**Date:** 2026-07-11  
**Build:** **hal-10496**  
**Status:** Applied (operator “do all”)

## Voice NICE (from voice+report consult)

| Item | Status | Where |
|------|--------|-------|
| Report “Read Summary” re-speak | Done | `site/hal-reports.js` + chat meta button + hero chip |
| Barge-in “HAL, stop” | Done | `site/hal-voice.js` (`startBargeInListener`) |
| Scripts on Apex + workstation | Done | `site/index.html`, `site/workstation/index.html` |

## Availity live path

| Item | Status |
|------|--------|
| Prefer live when `AVAILITY_USE_DEMO=0` | Done |
| Auto demo fallback if live scope unauthorized | Done (`AVAILITY_LIVE_FALLBACK_DEMO=1` default) |
| Clear HAL message when fallback used | Done |

**Note:** Real patient 271s still require Availity **Standard Plan**. Until approved, HAL continues on demo coverages with an explicit fallback message.

## Try

- `morning briefing` / `handoff report` → then **Read Summary**
- While HAL speaks: say **“HAL, stop”**
- Availity: keep demo until Standard Plan; then set User env `AVAILITY_USE_DEMO=0`
