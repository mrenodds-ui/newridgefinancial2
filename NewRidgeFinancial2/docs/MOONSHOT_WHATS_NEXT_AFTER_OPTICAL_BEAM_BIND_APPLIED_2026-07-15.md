# Moonshot AI — Period-Close SoftDent Morning Auto-Pull (APPLIED)

**Date:** 2026-07-15  
**Build:** `nr2-12029-period-close-softdent-pull`  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_OPTICAL_BEAM_BIND_2026-07-15.md`  
**Operator:** approve (every morning tick)

## What shipped

Morning period-close now pulls SoftDent aging automatically (consent-free):

1. **`nr2_scheduler.py`** — `run_period_close(..., auto=True, pull_softdent=True)` on morning tick (still skipped when human shift is active)
2. **`daily_closeout.py`** — after SoftDent Excel export succeeds → `heal_import_pipeline(force=True)` → re-check lasers → money-beam attest → JSONL with `pullSoftdent` / `importRefresh`
3. SoftDent write-back still **FORBIDDEN** (Excel / Print Preview only)

## Real paths

- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\nr2_scheduler.py`
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\daily_closeout.py`
- `C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\ops\daily_close_log.jsonl`

## Validation

- Unit: `test_period_close_softdent_pull` (mocked export + heal)
- Manual: `POST /api/period-close/run` with `{"auto":true,"pullSoftdent":true}` when SoftDent desktop is up
- Next morning tick (no active human shift): log row with `actor=scheduler`, `pullSoftdent=true`, beam totals

## Not done (runner-ups)

- SoftDent GUI Excel path hardening  
- HAL Force Close optical control  
- Formal beamHash desk proof across HAL + optical pages  
