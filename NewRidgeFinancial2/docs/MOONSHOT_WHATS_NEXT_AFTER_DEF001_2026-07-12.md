# Moonshot AI — What's Next After DEF-001 Collections (CONSULT)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10564 + Phase 5 GO  
**Prior:** DEF-001 (`c645460`); Phase 5 GO (`7e46a70`)  
**Script:** `scripts/run_moonshot_whats_next_after_def001_consult.py`  
**Apply:** Operator already said proceed — apply THE recommended package after this consult lands.

## Operator request (verbatim)

> proceed

---

# Verdict
Close the NO_PERIOD_ROW gap by hardening `softdent_dashboard_period_sync.py` to ingest the existing daysheet exports (already present in `C:\SoftDentReportExports`) and create the period row, transforming the current "files exist but period null" state into either populated revenue-composition or an honest, specific prompt for the Collections-specific export format.

## 0. Operator Intent (verbatim: proceed)
Apply the next additive fix to complete the DEF-001 data loop now that Phase 5 safety gates are GO and export inbox scanning is live.

## 1. Recommended NEXT (name, why now, effort, REAL files, phases, validation gate)

**Name:** DEF-001 Period Sync Ingestion — Close NO_PERIOD_ROW Gap with Existing Exports

**Why now:** The LIVE SNAPSHOT shows `daysheet.csv` and `daysheet.jsonl` present in `C:\SoftDentReportExports` (mtime 2026-07-12), yet the gap assessment returns `NO_PERIOD_ROW` with `period: null`. The honesty gates shipped in hal-10564 prevent synthetic $0, but the dashboard remains blind because the sync logic has not ingested the existing files to establish the period row. This is the final code step to close the loop before declaring the issue OPS-only (staff export format).

**Effort:** Small (2–3 hours)

**REAL files:**
- `NewRidgeFinancial2/softdent_dashboard_period_sync.py` — add ingestion trigger for daysheet CSV/JSONL when `NO_PERIOD_ROW` detected but inbox files exist
- `NewRidgeFinancial2/apex_backend.py` — ensure `refresh_softdent_period_imports` calls the sync with `force_reimport=True` for the current open period (2026-07)
- `NewRidgeFinancial2/softdent_practice_exports.py` — validate daysheet schema detection (date range, practice ID) to auto-create period stub

**Phases:**
1. **Ingest:** Parse `daysheet.csv` for period metadata (date range, production) and create period row if absent
2. **Classify:** If file contains production data but lacks insurance/patient split, set `collectionsPending: true` with hint "Collections export required for split"
3. **Sync:** Wire `refresh_softdent_period_imports` to trigger the ingestion pipeline automatically when inbox scan finds unprocessed daysheets

**Validation gate:** Run `refresh_softdent_period_imports` → `assess_collections_gap` returns `healthy: true` (if daysheet contains sufficient data) OR `collectionsGapCode: COLLECTIONS_FORMAT_REQUIRED` with `collectionsPending: true` (clearly signalling staff to export the specific Collections report).

## 2. Runner-ups (2–3, why not now)

- **Browser smoke of density/cache/DEF-001 after hard-refresh:** UI verification is important, but the current blocker is data layer (NO_PERIOD_ROW), not presentation layer. Defer until period sync resolves the underlying gap.
- **SoftDent SQLite lock residual (WHY-ERRORS):** Connection timeouts were shipped in prior build; current snapshot shows no active timeout errors. Revisit only if sync ingestion reveals lock contention during import.
- **OPS-only: Staff Collections CSV export:** If the hardened sync determines that daysheet.csv lacks the required insurance/patient split columns, escalate to this checklist immediately after the code fix confirms the format mismatch.

## 3. What NOT to redo
DEF-001 honesty gates (empty ≠ $0, no invented dollars), Phase 1–5 190Q harness, KPI density widgets, cache coherence transactions, WHY-ERRORS connect timeout logic, CARC Phase 4 whitelisting, or inventing SoftDent write-back capabilities.

## 4. Acceptance criteria
- [ ] `refresh_softdent_period_imports` processes `C:\SoftDentReportExports\daysheet.csv` without error
- [ ] Period row created for 2026-07 (or current open month) if absent, linking to the ingested file
- [ ] Gap assess transitions from `NO_PERIOD_ROW` to either:
  - `healthy: true` with revenue-composition populated (if daysheet contains split), OR
  - `collectionsGapCode: COLLECTIONS_FORMAT_REQUIRED` with explicit next-step hint
- [ ] HAL local policy `policy:def-001-collections` reflects updated state (no false "pending" when data exists)

## 5. Executive Summary (5 bullets)
- **DEF-001 shipped:** Honesty gates active, inbox scanning operational, synthetic $0 prevented.
- **Data present, period missing:** `daysheet.csv` exists in export inbox but `NO_PERIOD_ROW` blocks financial console.
- **Root cause:** Period sync pipeline not auto-ingesting existing daysheet exports to bootstrap the period record.
- **Fix target:** Harden `softdent_dashboard_period_sync.py` to create period row from daysheet metadata when files exist but period is null.
- **Outcome:** Close the data loop or definitively escalate to staff for Collections-specific export format (honest, actionable state).

## 6. Approval checklist (operator already said proceed — list apply steps)
- [ ] **Pull:** `git pull origin main` (verify hal-10564 / c645460 at HEAD)
- [ ] **Edit:** `NewRidgeFinancial2/softdent_dashboard_period_sync.py` — add `ingest_daysheet_to_period()` handler
- [ ] **Edit:** `NewRidgeFinancial2/apex_backend.py` — call sync inside `refresh_softdent_period_imports` when `gap.gapCode == "NO_PERIOD_ROW"` and `exportInbox.matchCount > 0`
- [ ] **Test:** `python -m pytest NewRidgeFinancial2/test_softdent_period_sync.py -v` (validate daysheet → period row creation)
- [ ] **Live run:** Execute `refresh_softdent_period_imports` against production inbox
- [ ] **Verify:** Check HAL `assess_collections_gap` returns healthy or specific Collections format hint
- [ ] **Commit:** `git add -A && git commit -m "hal-10565: DEF-001 period sync ingestion for daysheet exports"` && `git push`
- [ ] **Tag:** `git tag -a hal-10565 -m "DEF-001 period sync closure"`
- [ ] **Notify:** If result is `COLLECTIONS_FORMAT_REQUIRED`, hand off to OPS checklist for staff export of SoftDent Collections report (CSV) to same inbox.