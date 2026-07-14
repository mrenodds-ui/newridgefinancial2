# InsCo × ADA Probabilistic Report — APPLIED (HAL-10582)

**Date:** 2026-07-13  
**Operator:** build tiered high-probability report from ledger + coverage; state data needed for credibility  
**Status:** Applied (read-only analytics; no SoftDent write-back; empty ≠ $0)  
**Build stamp:** kept `hal-10576` (package HAL-10582)

## Verdict

Shipped a **tiered InsCo × ADA paid / write-off estimate report** from `sd_account_transactions` (`2` pay, `51`/`52` write-off) + `sd_patient_insurance`. Cells are labeled **exact / inferred** with credibility floors. This is **not** SoftDent contractual line truth (that still needs payment-analysis / ERA).

## Live run (this workstation)

| Metric | Value |
|--------|-------|
| History window | ~24 months (`2024-07-22` → `2026-07-12`) |
| Carrier-matched pay/WO events | **14,046** (miss **342**) |
| Event mix | exact **702** · inferred **8,449** · low **4,520** · none **375** |
| Stored cells | **1,973** |
| **Published** (credible) | **124** |
| High credibility (exact n≥30) | **2** |

Outputs:
- `C:\SoftDentFinancialExports\insco_ada_probabilistic_report_2026-07-12.json`
- `C:\SoftDentFinancialExports\insco_ada_probabilistic_report_2026-07-12.md`
- Inbox: `app_data/nr2/document_inbox/softdent/softdent_insco_ada_probabilistic.json`

Example published (exact): Delta KS × D1110 — paid med **$68**, WO med **$18**, n=32 (**high**).

## How much data pushes credibility

| Goal | Data needed |
|------|-------------|
| Publish one **exact usable** cell | ≥**10** single-ADA lookback events for that InsCo×ADA |
| **High** credibility exact | ≥**30** exact events |
| Publish **inferred** cell (2–3 ADAs) | ≥**30** events (always labeled inferred); stronger at ≥**75** |
| Useful practice matrix | ~**50** exact cells at n≥10 (or ~**20** at n≥30) |
| Coverage | Primary insurance on active accounts (`sd_patient_insurance`) |
| History | ~**24 months** account TX (already ingested) |
| “All ADAs, contractual” | Still need SoftDent payment lines / ERA — ledger cannot get there |

**Today:** 124 published cells with ~24 months TX + Sensei coverage. Exact high cells are scarce because most pay/write-off days sit behind **multi-ADA** visits (~95% inferred/low).

## What shipped

| Item | Path |
|------|------|
| Builder | `softdent_insco_ada_probabilistic.py` |
| Tables | `insco_ada_probabilistic_estimates`, `insco_ada_probabilistic_meta` |
| Sync hook | `import_sync.py` after treatment-planning ingest |
| Tests | `test_insco_ada_probabilistic_hal10582.py` |

## Honesty

- Code **51** = write-off, **2** = Ins pay — neither row carries ADA  
- Exact = one production ADA in 45-day lookback  
- Inferred = proportional split by billed $ (invented allocation)  
- Low (4+ ADAs) never published as credible  
- empty ≠ $0 · no SoftDent write-back · no invented Ins Plan Register $

## Validation

```text
cd NewRidgeFinancial2
python -m unittest test_insco_ada_probabilistic_hal10582 -v
python -c "from softdent_insco_ada_probabilistic import run_insco_ada_probabilistic_report; print(run_insco_ada_probabilistic_report()['export']['publishedCount'])"
```
