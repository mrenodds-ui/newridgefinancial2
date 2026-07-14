# Moonshot REC-007 HAL Cache Warm / Keep-Alive — APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_REC005_2026-07-12.md`  
**Operator:** proceed (typo: proveed)  

## Goal

Keep `hal-local:32b` GPU-resident and prime common CARC/payer explain prompts after Apex startup and ERA ingest. Complements (does not replace) Phase 3 widget stub fast-path.

## Applied (real paths)

| Piece | Where |
|-------|--------|
| Warm pack + selective ERA warm | `apex_hal_cache_warm_pack.py` |
| `keep_alive` on all Ollama chat calls (default `-1`) | `nr2_hal_gateway.call_ollama_chat` |
| Startup background warm | `browser_app.py` |
| ERA ingest → selective warm | `apex_program_improve_pack.ingest_era_835` |
| Status / trigger APIs | `GET/POST /api/apex/hal/cache-warm-status`, `POST .../cache-warm` |
| Telemetry gate (connected, not fresh) | `nr2_browser_security.SYSTEM_STATUS_PREFIXES` |
| Tests | `test_rec007_hal_cache_warm.py` |

## Flags

- `NR2_HAL_CACHE_WARM` — default ON  
- `NR2_OLLAMA_KEEP_ALIVE` — default `-1` (forever)

## Honesty

- Warm prompts never invent dollars or PHI  
- Background warm does not block ERA ingest or page load  
- Widget `warming-bridge` stub path unchanged  

## Validate

1. `python -m pytest test_rec007_hal_cache_warm.py -q`  
2. Restart NR2 → stderr shows `NR2 HAL model warm: … background=True`  
3. `GET /api/apex/hal/cache-warm-status` after warm completes → `warmed: true`  
4. ERA ingest with CAS → response includes `halCacheWarm`  
