# Moonshot AI — Import Cache KPIs Not Loading (APPLIED)

**Date:** 2026-07-13  
**Build:** `hal-10608`  
**Consult:** `MOONSHOT_IMPORT_CACHE_KPIS_2026-07-13.md`  
**Operator:** `proceed`  
**Script:** `scripts/run_moonshot_import_cache_kpis_consult.py`

## Summary

Applied Moonshot MUST + SHOULD for import-cache KPI warming hang. No Gold/ERA invent. Warming ≠ crash; empty ≠ $0.

## Shipped

| Priority | Change | Path |
|----------|--------|------|
| MUST | Per-page `_FILL_PROGRESS` registry + helpers | `apex_backend.py` |
| MUST | Single-flight `_load_reports_and_bundle` coalescing | `apex_backend.py` |
| MUST | Align `_REPORTS_BUNDLE_CACHE_TTL_SEC` **15.0** (was 20) | `apex_backend.py` |
| SHOULD | `Retry-After` + `retryAfter` on warming stub | `apex_backend.py` |
| SHOULD | Client backoff uses `retryAfter`, cap **8s** | `site/apex-core.js` |

## Tests

- Updated `test_crash_perf_hal10608.py` (per-page progress + TTL assert)
- Added `test_import_cache_kpis_hal10608.py` (4-thread single-flight)
- Ran: `pytest test_crash_perf_hal10608.py test_import_cache_kpis_hal10608.py` → **9 passed** 

## Explicitly not done

- Inventing Gold/ERA dollars
- Changing widget rate-limit exemption / Sync 423 (already shipped)
- HTTP 202 for warming (kept **200** + `Retry-After` so existing client fetch stays compatible)

## Acceptance (consult §6)

1. Concurrent page loads coalesce to one `_load_reports_and_bundle`  
2. Warming stubs expose per-page `fillProgress` ≥ 5 when queued  
3. `Retry-After` header on warming responses  
4. Client backoff respects `retryAfter` (cap 8s)  
5. empty ≠ $0 honesty unchanged  

## Honesty

empty ≠ $0 · inventedGold=false · softDentWriteBack=false · warming ≠ crash
