# Moonshot AI — Page Smoke Analyze & Repairs (APPLIED)

**Date:** 2026-07-13  
**Build:** `hal-10608`  
**Consult:** `MOONSHOT_PAGE_SMOKE_ANALYZE_REPAIRS_2026-07-13.md`  
**Operator:** `proceed with moonshot recommendations and do not deviate then report`  
**Script:** `scripts/run_moonshot_page_smoke_analyze_repairs_consult.py`

## Summary

Applied Moonshot MUST patches A–C from the page-by-page smoke consult. No Gold/ERA invent. OPS Gold CSV / ERA 835 remain operator SoftDent work.

## Shipped (MUST)

| Patch | Path | Change |
|-------|------|--------|
| A | `nr2_rate_limit.py` | Exempt `/api/apex/widgets` (+ prefix) and `/api/apex/hal/orchestrate` from 429 |
| B | `site/apex-core.js` | BuildId skew reload; exponential warming backoff (cap 30s); 429 catch backoff |
| C | `apex_backend.py` | Warming stub `Cache-Control: no-store` + `X-NR2-Build-Id` |
| Coherence | `site/index.html`, `site/sw.js`, `ASSET_V` / `window.NR2_BUILD_ID` | Aligned chrome to `hal-10608` so skew guard converges (acceptance §5.3) |

## Tests

- `test_moonshot_sprint.py` — added `test_widgets_prefix_rate_limit_exempt`
- `test_cache_coherence_hal10563.py` — BUILD_ID asserts → `hal-10608`
- Ran: `pytest test_moonshot_sprint.py test_cache_coherence_hal10563.py test_expert_se_phase3.py` → **16 passed**

## Explicitly not done (per Moonshot)

- SHOULD Sync 503 semaphore (no full diff in consult §3; staging optional)
- OPS Gold CSV drop / ERA 835 import (data, not code)
- Inventing Gold/ERA dollars
- Disabling `NR2_WIDGETS_STUB_FASTPATH`

## Acceptance (consult §5)

1. Widget GETs under poll pressure must not 429 (prefix exempt)  
2. After Sync, mosaic should leave warming via backoff polls (not stuck forever from 429)  
3. UI build chip / `ASSET_V` / `BUILD_ID` = `hal-10608`  
4. Gold honesty unchanged (`GOLD_CSV_MISSING` until real CSV)

## Honesty

empty ≠ $0 · inventedGold=false · softDentWriteBack=false
