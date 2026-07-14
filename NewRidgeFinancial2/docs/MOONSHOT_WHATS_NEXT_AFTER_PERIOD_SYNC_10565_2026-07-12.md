# Moonshot AI — What's Next After Period Sync Honesty (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10565 + Phase 5 GO  
**Prior:** period sync ingestion (`b018d0d`); format honesty (`ebfad88`); DEF-001 (`c645460`); Phase 5 GO  
**Script:** `scripts/run_moonshot_whats_next_after_period_sync_10565_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Close the 2026-07 collections gap by executing the SoftDent Register for Period CSV export (OPS-only), feeding the existing hal-10565 CSV ingestion pipeline to populate Ins/Patient splits without inventing parsers or dollars.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)

**Name:** SoftDent Register for Period CSV Export — July 2026 Collections (OPS-only)

**Why now:** The live inbox at `C:\SoftDentReportExports` already contains `RegisterForPeriodReportFor07012026.xls`, but hal-10565 ships CSV-only register parsing (quoted money, Ins/Patient column detection). July production ($45.6k) is live; collections attribution is blocked solely by file format. Exporting the same report as CSV engages existing ingestion logic—zero code latency, zero parser risk, immediate population of the revenue-composition split.

**Effort:** Zero code; 15 minutes staff time.

**REAL files:**
- `C:\SoftDentReportExports` (target directory; existing hal-10565 inbox scanner watches here)

**Validation gate:**
1. File appears: `register_for_period_2026-07-01_2026-07-31.csv` (or similar date-range pattern) in `C:\SoftDentReportExports`
2. `refresh_softdent_period_imports` or automated scan ingests the CSV
3. Dashboard 2026-07 row updates: `collectionsPending` → false, `insurance` and `patient` populated with non-zero dollars (sum equals total collections), `collectionsGapCode` cleared

## 2. Runner-ups (2–3, why not now)

- **Parse existing July XLS programmatically**: Writing an XLS/XLSX parser (binary or OOXML) introduces fragility (schema variance, formatting layers) and violates the directive to avoid greenfield parsers when OPS export is the real blocker. CSV is a native SoftDent export option; use it.
- **Browser smoke of density/cache/DEF-001**: Lower ROI than closing the $45.6k collections attribution gap; defer until after July data is honest.
- **SQLite lock residual investigation**: Informational-only at this stage; not blocking ingestion path.

## 3. What NOT to redo
- DEF-001 honesty gates (shipped hal-10564)
- Period-sync ingestion/format-required logic (shipped hal-10565)
- WHY-ERRORS timeout handling (shipped prior)
- Invent SoftDentImportParser fiction or write-back
- Invent dollars (empty ≠ $0)
- Phase 1–5 190Q (GO status achieved)

## 4. Acceptance criteria
- [ ] SoftDent → **Reports → Accounting → Register for a Period** (or **Collections** with Ins/Patient detail)
- [ ] Date range: 07/01/2026 – 07/31/2026 (open month)
- [ ] Export format: **CSV** (comma-delimited, not XLS)
- [ ] Columns required: `Ins Plan Collections`, `Patient Collections` (or equivalent quoted money fields)
- [ ] File saved to `C:\SoftDentReportExports` with filename containing `register_for_period` and date range (e.g., `register_for_period_2026-07-01_2026-07-31.csv`)
- [ ] Dashboard refresh ingests file; 2026-07 row shows non-null `insurance` and `patient` values; gap code `COLLECTIONS_EXPORT_REQUIRED` clears

## 5. Executive Summary (5 bullets)
- **Live blocker**: July register XLS is present but hal-10565 only auto-ingests CSV register formats for Ins/Patient split detection.
- **Zero-code fix**: SoftDent natively exports the same Register for Period report as CSV; this engages existing `softdent_dashboard_period_sync.py` logic without new parsers.
- **Immediate value**: Populates the $45.6k July production’s collections attribution (insurance vs. patient) using honest SoftDent dollars.
- **Risk avoidance**: Avoids XLS parsing complexity (binary formats, schema drift) and maintains read-only SoftDent policy.
- **Validation**: CSV ingestion verified by existing test suite (`test_period_sync_format_hal10565`); no new build required.

## 6. Approval checklist
- [ ] Operator confirms SoftDent workstation access to export “Register for a Period” (July 2026)
- [ ] Staff instructed to select CSV (not XLS) format per acceptance criteria
- [ ] File landing confirmed in `C:\SoftDentReportExports`
- [ ] Dashboard refresh executed and July collections populated
- [ ] If CSV export fails or format is unavailable, escalate to “Parse July XLS” code package (runner-up)