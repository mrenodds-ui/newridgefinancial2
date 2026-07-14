# Moonshot why-no-data recommendations — APPLIED (hal-10613)

**Date:** 2026-07-13  
**Build:** `hal-10613`  
**Source consult:** `MOONSHOT_WHY_WIDGETS_NO_DATA_CONSULT_2026-07-13.md`

## OPS (done)
1. SoftDent **Account Aging → Excel** via `scripts/run_softdent_money_widget_pull.py --reports aging` (not Insurance Income — that was a Moonshot mislabel for A/R).
2. Files landed under `C:\SoftDentReportExports` (`account_aging.csv` / `AGE260713.XLS`).
3. Sync + AR pipe refresh.

## CODE (done — real paths only)
1. `import_sync._sync_softdent_pipeline_exports`: when SoftDent aging OPS export is newer than `softdent_ar_aging.csv` but bucket bytes are unchanged, **retouch mtime** so `softdent.ar` softGap clears (empty ≠ $0; dollars not invented).
2. Honest empty messages:
   - `apex_claims_narratives_pack.claims_era_gauge_widget`
   - `apex_missing_widgets_pack` denial-pareto + verification-matrix

## Honest residual (not invented)
- **Gold CSV** remains `GOLD_CSV_MISSING` — SoftDent v19 Insurance Income is Print Preview only; visual audit ≠ gold lines.
- **ERA / denials / elig fields** stay empty until SoftDent exports include those fields or a real `.835` is dropped under `C:\SoftDentFinancialExports\era`.
- Did **not** invent Moonshot paths `src/defects/DEF-001/era_835_ingest.py` or `softdent_ar_poll.py` — ERA ingest already lives in `apex_era835_pack.py` / `era835_parser.py`.

## Gate
- `app-info` softGaps for `softdent.ar` → **cleared** after freshness retouch.
