# Moonshot / Operator — HAL Completely Autonomous (APPLIED)

**Date:** 2026-07-16  
**Build:** `nr2-12040-hal-autonomous`  
**Operator:** “i want hal completely autonomous - fix it”

## What “completely autonomous” means here

HAL runs the **full read-only office loop without operator clicks**. SoftDent write-back, QB posting, payer submit, and outbound email stay consent-gated (doctrine).

## What was broken

1. `HalAutonomousOps.start` existed but was **never called**
2. QB sync + optical navigate still required Approve modals
3. HAL Level-7 continuous shift was treated as `human_shift_active` and **blocked morning/EOD autonomy**
4. No always-on **server** tick when the browser page was closed

## What shipped

| Area | Change |
|------|--------|
| `hal_brain_tools.py` | SoftDent export, QB sync, navigate (+ memo/web/desk smoke) = read-autonomous |
| Optical HAL | Auto-exec those actions; start `HalAutonomousOps` on boot |
| Workstation | Boot starts autonomous ops |
| `nr2_scheduler.py` | HAL shift no longer blocks morning; morning adds QB sync + desk smoke; `hal_autonomous_ops_tick` |
| `browser_app.py` | Background tick every 15 minutes |
| `POST /api/hal/autonomous/tick` | Heal + desk smoke + Force Close when lasers red |
| Doctrine | Session system prompt updated |

## Still gated (intentional)

- SoftDent write-back
- QuickBooks post / IIF outbound
- Payer portal submit
- Staff email send

## Ops note

Restart NR2 so the new `/api/hal/autonomous/tick` route and 15m scheduler job load. SoftDent desktop must be running for GUI Excel pulls.
