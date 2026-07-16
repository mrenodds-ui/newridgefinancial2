# PushEngage Flash-Risk Consult — APPLIED (hygiene only)

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_PUSHENGAGE_FLASH_RISK_2026-07-15.md`  
**Operator:** continue until all done  
**Moonshot follow-on:** `MOONSHOT_WHATS_NEXT_AFTER_OM_SCHEDULE_TRACK_2026-07-16.md` #1

## What this is

Consult-only risk review of a PushEngage blog article about free live-chat widgets.  
**Verdict: AVOID** embedding PushEngage / Tawk.to / Tidio / similar consumer chat or push scripts on NR2 SoftDent / optical / financial pages.

## What we did NOT build

Moonshot later invented paths (`integrations/push_risk/`, `optical/hal_push_bridge.js`, etc.) — **those do not exist and were not implemented.** There is no PushEngage integration in NR2.

## Shipped (repo hygiene)

| Item | Path |
|------|------|
| Consult report | `docs/MOONSHOT_PUSHENGAGE_FLASH_RISK_2026-07-15.md` |
| Consult runner | `scripts/run_moonshot_pushengage_flash_risk_consult.py` |
| HAL flash rings | remain disabled (`hal-live-widget-bridge.js` `flashElement` no-op) |

## Policy

- Do not paste third-party chat / web-push embeds into NR2 production pages.
- Visiting the PushEngage URL in a browser does not inject code into NR2.
- Adobe Flash / .swf risk: none for the listed widgets (HTML5).
