# Moonshot AI — What's Next After DEF-001 + Phase 5 GO (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10564 + Phase 5 GO  
**Prior:** DEF-001 (`c645460`); Phase 5 GO (`7e46a70` / `32214ac`)  
**Script:** `scripts/run_moonshot_whats_next_after_def001_shipped_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Close the NO_PERIOD_ROW gap by hardening `softdent_dashboard_period_sync.py` to auto-ingest existing daysheet exports from `C:\SoftDentReportExports` when files exist but the period row is null, transforming the current stalemate into either a populated revenue-composition or an honest, specific prompt for the Collections-specific export.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)

**Name:** DEF-001 Period Sync Ingestion — Close NO_PERIOD_ROW Gap with Existing Daysheet Exports

**Why now:** The live snapshot shows `daysheet.csv` and `daysheet.jsonl` present in `C:\SoftDentReportExports` (mtime 2026-07-12), yet `assess_collections_gap` returns `NO_PERIOD_ROW` with `period: null`. The honesty gates shipped in hal-10564 prevent synthetic $0, but the dashboard remains blind because the sync logic has not ingested the existing files to establish the period row. This is the final code step to close the data loop before the issue becomes purely OPS (staff export format guidance).

**Effort:** Small (2–3 hours)

**REAL files:**
- `NewRidgeFinancial2/softdent_dashboard_period_sync.py` — add `ingest_daysheet_to_period()` trigger when inbox scan finds unprocessed daysheet CSV/JSONL but `period` is null; create period stub from daysheet metadata (date range, practice ID)
- `NewRidgeFinancial2/softdent_practice_exports.py` — validate daysheet schema detection; distinguish between "daysheet with production only" (sets `collectionsPending: true`) vs "daysheet with insurance/patient split" (populates revenue-composition)
- `NewRidgeFinancial2/apex_backend.py` — ensure `refresh_softdent_period_imports` calls the sync with `force_reimport=True` for the current open period (2026-07) when unprocessed inbox files detected
- `NewRidgeFinancial2/apex_financial_console_pack.py` — update `assess_collections_gap` to recognize new period row status `DAYSHEET_WITHOUT_SPLIT` (honest empty with actionable hint)

**Validation gate:** Run `refresh_softdent_period_imports` → `assess_collections_gap` returns `period` populated (not null) and either `healthy: true` (if split data present) or `collectionsGapCode: "COLLECTIONS_EXPORT_REQUIRED"` with specific next-step hint; zero `NO_PERIOD_ROW` when valid daysheet files exist in inbox.

## 2. Runner-ups (2–3, why not now)

- **Ops-only SoftDent Collections CSV for 2026-07:** Defer until after period sync ingestion proves the code loop can create the period row from existing exports; otherwise staff exports into a blind dashboard with no period anchor.
- **Browser smoke of density/cache/DEF-001 after hard-refresh:** Important validation but secondary to unblocking the data pipeline; perform after this package to confirm the full loop renders correctly in the financial widgets.
- **QB payroll/AP inbox refinements:** Lower ROI than closing the active SoftDent revenue recognition gap that blocks month-end close.

## 3. What NOT to redo

- DEF-001 honesty gates (empty ≠ $0, no invented insurance/patient dollars, ERA as proposal only)
- Phase 1–5 190Q safety/latency work (100% success, 98.4% quality, ≤15s latency)
- Cache coherence hal-10563 (IDB BUILD_ID invalidation, stub survivability)
- KPI density hal-10562 or WHY-ERRORS SQLite timeout fixes
- CARC Phase 4 logic
- Any SoftDent write-back operations (remain read-only)

## 4. Acceptance criteria

- [ ] `softdent_dashboard_period_sync.py` detects daysheet CSV/JSONL in inbox when `NO_PERIOD_ROW` active
- [ ] Period row created with correct date range from daysheet metadata (2026-07)
- [ ] If daysheet lacks insurance/patient split: `collectionsPending: true`, `collectionsGapCode: "DAYSHEET_WITHOUT_SPLIT"`, honest empty revenue-composition with hint "Collections export required for split"
- [ ] If daysheet contains split: `revenue-composition` populated with real ins/patient dollars, `collectionsGapCode: null`
- [ ] `refresh_softdent_period_imports` triggers ingestion automatically on inbox scan without manual file moves
- [ ] `assess_collections_gap` never returns `period: null` when valid daysheet files exist in `C:\SoftDentReportExports`
- [ ] No SoftDent write-back; empty revenue remains ≠ $0; no PHI leakage in error messages

## 5. Executive Summary (5 bullets)

- **Gap:** Daysheet files exist in export inbox but dashboard shows `NO_PERIOD_ROW` (period: null), leaving the honesty gates with no data to display and staff unable to proceed.
- **Fix:** Harden period sync to ingest existing daysheet exports and create the period row, distinguishing between "period missing" (fixable by code ingestion) and "Collections export needed" (specific OPS action).
- **Impact:** Closes the DEF-001 data loop; staff either see real revenue split or a specific prompt to export Collections format, enabling month-end reconciliation.
- **Risk:** Low; additive read-only ingestion of existing files, no SoftDent write-back, preserves empty ≠ $0 policy.
- **Build:** hal-10565 (proposed next tag)

## 6. Approval checklist

- [ ] Confirm daysheet files exist in `C:\SoftDentReportExports` (already verified in live snapshot)
- [ ] Review `softdent_dashboard_period_sync.py` for null-period ingestion logic and date-range parsing
- [ ] Verify no SoftDent write-back in proposed changes (remain read-only)
- [ ] Validate acceptance criteria cover both split-present and split-absent daysheet scenarios
- [ ] Confirm effort estimate (2–3 hours) fits current sprint window before 2026-07 month-end close