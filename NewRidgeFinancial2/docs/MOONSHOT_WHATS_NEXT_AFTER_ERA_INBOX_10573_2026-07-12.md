# Moonshot AI — What's Next After ERA-835 Inbox Ingest (hal-10573) (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10573  
**Prior:** ERA inbox ingest (`426895a` / hal-10573)  
**Script:** `scripts/run_moonshot_whats_next_after_era_inbox_10573_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
OPS: Staff acquisition and drop of first real ERA-835 files into the wired inbox (`C:\SoftDentFinancialExports\era`) to validate the hal-10573 ingestion pipeline against production payer data and transition from scaffold/awaiting to live processing.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** OPS ERA-835 First Drop — Real File Ingestion Validation  
**Why now:** The hal-10573 ingest wiring is live, inbox directories exist and are healthy (`existingRoots` verified, `fileCount=0`, `chipStatus=awaiting`). The pipeline is code-complete but data-empty; no additional Apex/HAL wiring will change the `ERA_835_REQUIRED` gap state until real insurance payment data enters the system. This is the highest-ROI unblocker.  
**Effort:** Low (operational). Requires staff to download actual ERA 835 EDI/CSV files from payer portals (Delta Dental, MetLife, etc.) or extract from existing practice archives. No code deploy needed.  
**REAL files:** Genuine ERA 835 files (ANSI 5010 X12 835, CSV equivalents, or plain-text 835 remittances) from actual payers for the practice period. Explicitly do not invent dummy dollars or use synthetic test data as production truth.  
**Validation gate:** After drop, execute `ingest_era_inbox()` (local Python) or Sync; verify `fileCount>0`, `chipStatus` transitions from "awaiting" to "staged/processing", unified ledger shows insurance payment rows with `writeBack=false`, and no SoftDent re-export was required.

## 2. Runner-ups (2–3, why not now)
- **Browser smoke of hal-10573 ERA inbox chip:** Redundant prior to real data. The live snapshot confirms the chip renders "Awaiting first 835 drop" correctly; smoke testing the UI response to an empty inbox does not advance the business goal of closing the insurance gap.  
- **Wire mutation-token for UI ingest button:** Lower priority than data acquisition. The local `ingest_era_inbox()` function works immediately once files are dropped; the browser 403 on raw POST is expected and acceptable for internal staff who can run the local script. Polish the UI button after confirming the pipeline works with real files.  
- **Collections Summary Excel-temp reliability:** Blocked by `ERA_835_REQUIRED` gap. Improving Excel templates is premature when the underlying insurance payment data is still at `$0` awaiting the first 835 drop.

## 3. What NOT to redo
Do not re-apply hal-10573 inbox wiring, hal-10572 gap-tile labels, or hal-10571 honesty UX. Do not re-export July SoftDent Register hoping for `Ins Plan > 0` (explicitly violates `honesty=empty_not_zero`). Do not invent fake 835 content, synthetic insurance dollars, or SoftDent write-back mechanisms. Do not execute GitHub/PR workflows for this operational drop.

## 4. Acceptance criteria
- [ ] Staff obtains **real** ERA 835 remittance files from at least one payer portal (not synthetic).  
- [ ] Files are placed in `C:\SoftDentFinancialExports\era` (primary) or `C:\SoftDentReportExports\era` (fallback).  
- [ ] `scan_era_inbox()` detects `fileCount≥1` and `empty=false`.  
- [ ] `ingest_era_inbox()` processes files without error, returning `processedFiles≥1` and `rowsInserted≥1`.  
- [ ] `GET /api/apex/hal/era-inbox/status` reflects `chipStatus` no longer "awaiting" (e.g., "staged" or "ready").  
- [ ] Unified ledger aggregates show insurance payments derived **only** from dropped file contents (`writeBack=false`, no invented dollars).  
- [ ] Gap code remains `ERA_835_REQUIRED` until cumulative ERA volume clears the collections gap (do not force flip).

## 5. Executive Summary (5 bullets)
- **Code-complete, data-empty:** Hal-10573 ingest scaffolding is production-ready; the only remaining blocker is the absence of real payer files in the inbox.  
- **Honesty preserved:** The system correctly maintains `ERA_835_REQUIRED` and `empty_not_zero` until physical 835 files are detected, preventing false insurance reporting.  
- **Operational unblock:** Staff must source actual remittances from payer websites (e.g., dental benefit portals) or existing EDI archives; no development work required.  
- **Immediate validation:** Once dropped, the existing `ingest_era_inbox()` path will immediately parse and stage data for reconciliation without requiring a new deploy.  
- **Zero SoftDent mutation:** The pipeline operates read-only regarding SoftDent; no write-back or Register re-export is performed or expected.

## 6. Approval checklist
- [ ] Operator confirms staff can access real ERA 835 files from payers (not test data).  
- [ ] Target drop directory confirmed writable: `C:\SoftDentFinancialExports\era`.  
- [ ] Staff instructed NOT to re-export SoftDent Register reports seeking `Ins Plan > 0`.  
- [ ] Validation plan includes verifying `honesty` field transitions from `empty_not_zero` only after physical file presence confirmed.  
- [ ] Rollback plan: If files are corrupt, delete from inbox and re-drop; no database rollback needed (scaffold mode is non-destructive).
