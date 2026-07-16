# Trellis tomorrow HTTP probe — APPLIED

**Date:** 2026-07-16  
**Consult backlog #2:** `MOONSHOT_WHATS_NEXT_AFTER_OM_SCHEDULE_TRACK_2026-07-16.md`  
**Operator:** continue until all done

## Issue

Live `GET /api/trellis/tomorrow-insurance` returned **404** because the workstation NR2 process was still on pre-panel code. Route exists in `nr2_http_server.py`.

## Shipped

| Item | Where |
|------|--------|
| Desk smoke HTTP check `trellis_tomorrow_http` | `desk_smoke.py` (when `probe_http=True`) |
| Hint to restart server on miss | same |
| BUILD_ID bump | `nr2-build.json` → `nr2-12070-trellis-om-huddle` |

## Operator action

Restart NR2 browser/workstation server so `/api/trellis/tomorrow-insurance` loads, then open Office Manager → Tomorrow · Trellis insurance.
