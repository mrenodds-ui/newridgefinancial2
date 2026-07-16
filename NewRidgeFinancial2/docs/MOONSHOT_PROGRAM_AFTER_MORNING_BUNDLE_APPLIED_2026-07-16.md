# Moonshot AI — Desk Smoke Package (APPLIED)

**Date:** 2026-07-16  
**Build:** `nr2-12038-desk-smoke`  
**Consult:** `MOONSHOT_PROGRAM_AFTER_MORNING_BUNDLE_2026-07-16.md`  
**Operator:** approve

## What shipped

1. **`desk_smoke.py`** — confidence loop: period-close status, money beams + `dataBeamHash`, Force Close availability vs lasers/stalled, in-process VERIFY BEAM, optional HTTP probe of `/api/hal/tools/beam-verify`
2. **`GET /api/health/desk-smoke`** (+ `/api/desk-smoke`) — `?run=1` executes; `?run=0` returns last state
3. **Hub / Office Manager** — DESK SMOKE card + RUN SMOKE button
4. **`scripts/desk_ops_smoke.py`** — CLI wrapper (`--no-http` skips live probe)

## Ops note

Live 8765 returned **404** for `/api/hal/tools/beam-verify` because the running Python process predated the route (static `nr2-build.json` can update without route reload). **Restart NR2 browser/workstation** so beam-verify and desk-smoke HTTP routes load. In-process smoke still validates desk proof without HTTP.

## SoftDent doctrine

- Write-back **FORBIDDEN**
- Excel / Print Preview only
- empty ≠ $0

## Validation

- Unit: green path MATCH; force-close availability mismatch → RED
- CLI: `python scripts/desk_ops_smoke.py --no-http`
- After restart: `python scripts/desk_ops_smoke.py` should be GREEN including HTTP beam-verify
