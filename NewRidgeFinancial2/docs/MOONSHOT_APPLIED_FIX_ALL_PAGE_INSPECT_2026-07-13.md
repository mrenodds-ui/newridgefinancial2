# Moonshot AI — Fix-All Page Inspect (APPLIED)

**Date:** 2026-07-13  
**Build:** `hal-10608`  
**Consult:** `MOONSHOT_FIX_ALL_PAGE_INSPECT_2026-07-13.md`  
**Operator:** `proceed`  
**Prior:** page-smoke 429/warming repairs (`4aca8b2`)

## Summary

Applied the **verifiable** MUST/SHOULD pieces from Moonshot’s fix-all consult. Rejected fictional patch targets (`library_indexer.py`, `widget_resolver.py`, invented SoftDent SQL). Did **not** invent Gold CSV or ERA dollars.

## Shipped (code)

| Item | Path / change |
|------|----------------|
| MUST schema skew | `site/nr2-build.json` + `nr2-build.json` → `schemaVersion`/`BUILD_ID`/`assetVersion` = `hal-10608` |
| OPS-A/R (code path) | `import_sync` builds `softdent_ar_aging.csv` from newer of SoftDent `account_aging.csv` vs `account_aging.jsonl` (live buckets e.g. Current/$42,965.29) |
| Direct pipeline | `import_direct_pipeline.build_ar_pipeline_dataset` same CSV fallback |
| Patient context | `build_apex_widgets(..., patient_id=)` + `/api/apex/widgets/<page>?patient_id=` hydrates `selectedPatient` via `build_patient_dossier` |
| SoftDent dossier | `gapCode=NO_PATIENT_CONTEXT` when empty |
| OM dossier cards | Use `bundle.selectedPatient` for dossier/eligibility/TP/claims/notes |
| HAL actions | Recommend Gold CSV + ERA 835 when readiness gaps present |
| Library honesty | `lib-storage` empty → `gapCode=LIBRARY_NOT_INDEXED` |
| Tests | `test_fix_all_page_inspect_applied.py` |

## Live check

- Account aging CSV maps to AR rows (example Total **$49,111.03**) — empty ≠ $0  
- Pytest: `test_fix_all_page_inspect_applied` + SHOULD/cache coherence → **passed**  
- Restart NR2 required to serve new `nr2-build.json` / import path in the running process

## Continue (2026-07-13, post proceed)

| Item | Change |
|------|--------|
| NICE honest-empty | `denial-pareto` / `preauth-aging-lanes` / `payer-change-alerts` → `gapCode=ZERO_VOLUME` when empty |
| Library seed | `_library_widgets` calls real `hal_post_pull_setup.seed_document_library` (no invented indexer) — live library now **active** |
| Aging finder bug | `find_account_aging_export` skipped derived `softdent_ar_aging.csv`; prefers real SoftDent `account_aging.csv` that parses — bridge now `CLAIMS_AR_RECONCILE_MISMATCH` (honest SoftDent ins $0 vs claims) not false `AGING_EXPORT_MISSING` |

### Live re-inspect after continue

- schema/asset `hal-10608` · readiness **fresh** · A/R gaps **[]**
- **142 active / 22 faulty / 13 honest** (0 crashed)
- Library: active (seeded)
- SoftDent outstanding-claims bridge: honest reconcile mismatch (not missing export)

## Explicitly not done (still OPS / honest-empty)

| Issue | Why |
|-------|-----|
| Gold CSV (`GOLD_CSV_MISSING`) | Carestream ticket / real SoftDent line export — do not invent |
| ERA 835 | Clearinghouse enrollment + file drop |
| `CLAIMS_AR_RECONCILE_MISMATCH` | SoftDent Account Aging Outstanding Insurance = $0 vs sd_claims billed — flag only |
| OM patient cards empty | Need `?patient_id=` (or selected patient) — not invent |
| Financial empties (procedure-profitability, treatment-conversion, cash-flow-bridge) | No invented SoftDent SQL |
| Denial/preauth/payer ZERO_VOLUME | Honest until denial/preauth/payer-change feeds exist |

## Acceptance vs consult

1. app-info schema → `hal-10608` after restart  
2. SoftDent A/R can refresh from Account Aging CSV (not invent)  
3. `?patient_id=` can populate dossier widgets when SoftDent patient extract has that id  
4. HAL recommended actions no longer blank when Gold/ERA gaps exist  
5. Gold/ERA widgets remain honest gaps until OPS completes  

## Honesty

empty ≠ $0 · inventedGold=false · softDentWriteBack=false
