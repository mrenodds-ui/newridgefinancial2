# Moonshot AI — What's Next After Gap-Tile ERA_835_REQUIRED Label (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10572  
**Prior:** gap-tile polish (`157572e` / hal-10572)  
**Script:** `scripts/run_moonshot_whats_next_after_gap_tile_10572_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Wire the ERA-835 inbox ingest pipeline (empty-inbox safe) to move from scaffold mode to live file ingestion while preserving the empty≠$0 honesty contract and awaiting the first 835 drop.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** ERA-835 Inbox Ingest Wiring — Empty-Inbox Safe  
**Why now:** The gap-tile honesty label (hal-10572) is live showing `ERA_835_REQUIRED`, the ERA inbox directories exist and are confirmed empty (`existingRoots` valid, `fileCount=0`), and the system is in `mode=scaffold`. Wiring the ingest now ensures the first 835 file dropped by staff will process immediately without requiring an emergency deploy. This is the highest-leverage additive fix to close the loop between the visible gap message and actual processing capability.  
**Effort:** Small–Medium (additive wiring, empty-batch safety, no write-back)  
**REAL files:**  
- `NewRidgeFinancial2/apex_era835_pack.py` (`ingest_era835_to_unified`, `scan_era_inbox`)  
- `NewRidgeFinancial2/apex_softdent_era_pack.py` (`attach_era_to_ingest`, enrich hooks)  
- `NewRidgeFinancial2/softdent_practice_exports.py` (scaffold→live transition)  
- `C:\SoftDentFinancialExports\era` (real inbox root)  
- `C:\SoftDentReportExports\era` (real inbox root)  
**Validation gate:**  
- Unit `test_era835_empty_inbox_honesty` — empty dir returns `[]`, chipStatus stays `awaiting`, no invented dollars.  
- Unit `test_era835_single_file_ingest` — mock 835 EDI/CSV ingests to unified ledger, read-only, no SoftDent post.  
- Live drop test — place one 835 file → `scan_era_inbox` detects it → `ingest_era835_to_unified` creates ledger entries → widget chip transitions to `processing`/`ready` without re-exporting Register.

## 2. Runner-ups (2–3, why not now)
- **Browser smoke re-verify of hal-10572 gap-tile label:** Already completed per live snapshot (`widget.message="ERA_835_REQUIRED"`, `eraStub.mode=scaffold` verified post-hard-refresh in shipped docs). Re-smoking would duplicate verified work.  
- **Collections Summary Excel-temp reliability:** Deferred; any export logic risks implying a need to re-export SoftDent Register Ins Plan to make the summary non-zero, which violates the `$0 is truth` policy.  
- **Real QuickBooks payroll/AP OPS export drop:** Deferred; no evidence staff have produced real QB files (prior hygiene applied empty-batch markers only). Candidate #1 unblocks ERA processing first.

## 3. What NOT to redo
- Gap-tile label polish / `ERA_835_REQUIRED` visibility (hal-10572 just shipped).  
- Import Dataset Hygiene empty-batch markers (applied).  
- ERA honesty UX logic / do-not-re-export hints (hal-10571 applied).  
- Browser smoke of 10571/10572 (completed).  
- Re-export July Register for Ins Plan > 0 (prohibited; `$0` is SoftDent truth).  
- Inventing QB payroll/AP rows or wages (no files available).  
- SoftDent write-back or GUI posting (never permitted).

## 4. Acceptance criteria
- [ ] `apex_era835_pack.scan_era_inbox()` returns empty list without error when `C:\SoftDentFinancialExports\era` is empty; never returns invented `$0` or dummy transactions.  
- [ ] `apex_era835_pack.ingest_era835_to_unified()` correctly parses a real 835 EDI/CSV when dropped, creating unified ledger entries (insurance payments, adjustments) with full traceability.  
- [ ] `apex_softdent_era_pack.attach_era_to_ingest()` links ERA data to existing SoftDent Register collections rows by patient/account without modifying SoftDent source data.  
- [ ] Widget `chipStatus` remains `awaiting` when inbox empty; updates to `processing` only when files are present, then `ready` after successful ingest.  
- [ ] Gap code remains `ERA_835_REQUIRED` if inbox empty or if ingested ERA sums to $0; transitions to `ERA_835_AVAILABLE` or `OK` only based on actual ERA content, never on re-exported Register data.

## 5. Executive Summary (5 bullets)
- **Hal-10572 gap-tile label is live:** Surface now correctly shows `ERA_835_REQUIRED` when Register Ins Plan is $0, with explicit do-not-re-export hint.  
- **ERA inbox is scaffolded but empty:** Directories `C:\SoftDentFinancialExports\era` and `C:\SoftDentReportExports\era` exist and are confirmed empty (`fileCount=0`, `empty_not_zero`).  
- **Next critical path:** Wire real ingest so the first 835 drop processes automatically; maintains empty-inbox honesty (no invented dollars).  
- **Import hygiene complete:** 100% critical completeness with 17/19 partial empty-batch markers; no blockers for ERA file processing.  
- **Strict read-only contract:** Apex ingests ERA for insurance detail and unified ledger only; never posts back to SoftDent, never re-exports Register to force Ins Plan > 0.

## 6. Approval checklist
- [ ] Operator confirms no real QB payroll/AP files available yet (defer Candidate #5).  
- [ ] Operator confirms no SoftDent non-Register reports show Ins Plan > 0 (defer Candidate #4).  
- [ ] Operator approves wiring ERA-835 ingest with empty-inbox safety (Candidate #1).  
- [ ] I have not invented file trees beyond the two `C:\...\era` roots listed in REAL PATHS.  
- [ ] I have not claimed code is applied; this is consult-only pending operator approval.
