# HAL-10588 — Gold Data Pipeline Audit & Repair (applied)

**Date:** 2026-07-12  
**Prior consult:** `MOONSHOT_EXPERT_SE_FIRST_CLASS_PROGRAM_2026-07-13.md`  
**Operator:** `proceed` (exactly, without deviation)  
**BUILD_ID:** `hal-10588` (coupled to package — FIX-002)

## Moonshot MUST items addressed

| ID | Action | Result |
|----|--------|--------|
| **FIX-001** | Audit + repair gold insurance payment-line ETL | Root cause: `GOLD_CSV_MISSING` — no SoftDent Insurance Payment Analysis CSV on disk. ETL + candidate ingest ready; auto-ingest on Sync when file lands. Does **not** invent gold from ledger spine. |
| **FIX-002** | BUILD_ID / package coupling | `apex_backend.BUILD_ID` = `nr2-build.json` = `PACKAGE_BUILD_ID` = `hal-10588` |
| **FIX-003** | >80% line coverage on financial modules | Measured **84%** total (`softdent_insco_ada_*.py` + `softdent_treatment_planning.py` + gold pipeline); each module ≥80% |

## What shipped

| Piece | Location |
|-------|----------|
| Gold audit / repair module | `softdent_gold_payment_pipeline.py` |
| Recursive payment CSV hunt | `find_newest_csv` + `find_gold_payment_candidates` |
| Sync hook | `import_sync.py` → `run_gold_payment_pipeline_repair` |
| SoftDent widget | `softdent-gold-payment-pipeline` |
| API | `GET /api/apex/gold-payment-pipeline/status`, `POST .../repair` |
| HAL intent | `policy:gold-payment-pipeline` |
| Tests | `test_gold_payment_pipeline_hal10588.py`, `test_financial_coverage_hal10588.py` |
| Live report | `C:\SoftDentFinancialExports\gold_payment_pipeline_report_*.{json,md}` |

## Live audit (honest)

- **gapCode:** `GOLD_CSV_MISSING`
- **paymentLines:** `0` (empty ≠ $0)
- **Root cause:** SoftDent export never dropped; DaySheet/`sd_payments` are not ADA×InsCo gold lines
- **Exact usable spine validation:** **46** cells checked · **46** pass · **0** flag (spine consistency; remittance compare deferred until gold/ERA lines exist)
- **Playbook:** SoftDent **Reports → Insurance → Insurance Payment Analysis** → save `C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv` → Sync

## Fixture proof

Unit tests prove: missing CSV → `GOLD_CSV_MISSING`; valid fixture CSV → ingest → `GOLD_OK` with `sd_insurance_payment_lines ≥ 3`; candidate-token file (non-glob name) still ingested; negative spine medians flagged.

## Honesty

No SoftDent write-back. Missing gold is not `$0.00`. Probabilistic spine remains ledger-derived until Insurance Payment Analysis lands.

## Coverage snapshot (FIX-003)

```
softdent_gold_payment_pipeline.py     86%
softdent_insco_ada_catalog_matrix.py  89%
softdent_insco_ada_pct_variance.py    88%
softdent_insco_ada_probabilistic.py   85%
softdent_insco_ada_spine.py           81%
softdent_treatment_planning.py        82%
TOTAL                                 84%
```

## Acceptance vs Moonshot 1st-class bar

- [x] BUILD_ID matches package (`hal-10588`)
- [x] Line coverage >80% on named financial modules
- [x] Root cause of `sd_insurance_payment_lines=0` diagnosed + repair path shipped
- [ ] `sd_insurance_payment_lines > 0` in live DB — **blocked on SoftDent CSV drop** (operator playbook above)
- [ ] Exact usable cells remittance-validated — deferred until gold lines flow (spine consistency only for now)
