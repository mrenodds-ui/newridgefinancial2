# Moonshot AI — What's Next After ERA-835 Honesty Browser Smoke (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10571  
**Prior:** smoke PASS + watcher fix (`2439197`) / honesty UX (`197efe8` / hal-10571)  
**Script:** `scripts/run_moonshot_whats_next_after_era835_smoke_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Quarantine hygiene completion—identify and restore the 2 remaining missing import datasets following the watcher hotfix (2439197), restoring Apex to 100% completeness without inventing data or triggering SoftDent Register re-export.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** Import Dataset Hygiene—Quarantine Clearance & Inbox Restoration (post-2439197)  
**Why now:** The watcher hotfix shipped 2439197 released 50 mass-quarantined items but left 2 datasets still missing, leaving Apex below 100% completeness. Before wiring real ERA-835 ingest or polishing gap-tile UX, we must audit the quarantine log to identify these stragglers (likely SoftDent financial exports or account-tx bundles) and restore them cleanly to the inbox. This is pure data hygiene that unblocks downstream features without violating the honesty policy or requiring SoftDent re-export.  
**Effort:** Low-Medium (audit quarantine registry, identify 2 specific missing datasets, validate bundle integrity, restore to active inbox, verify ledger visibility).  
**REAL files:**  
- `NewRidgeFinancial2/apex_import_quarantine_pack.py` (audit quarantine registry, identify the 2 items)  
- `NewRidgeFinancial2/apex_import_watcher_pack.py` (verify watcher no longer blocks with read_only TypeError)  
- `NewRidgeFinancial2/apex_backend.py` (confirm restored datasets surface in TXN ledger/account-tx views)  
**Validation gate:** Import completeness returns to 100% (dashboard metric), zero items remain quarantined for "read_only" or "import_read_forbidden" reasons, the 2 missing datasets are visible in the data lake (account-tx or SoftDent exports), and no manual SoftDent Register re-export was performed.

## 2. Runner-ups (2–3, why not now)
1. **Gap-tile label polish** (surface `collectionsGapCode=ERA_835_REQUIRED` in outer message vs. nested only): Cosmetic improvement noted in smoke ("Gap strip message shows outer gapCode ERA_835_AVAILABLE while nested collectionsGapCode is ERA_835_REQUIRED"). Honesty logic is functionally correct; defer until data completeness is restored so the tile reflects real data state.  
2. **Wire real ERA-835 inbox ingest** (beyond stub): Blocked because `C:\SoftDentFinancialExports\era` and `C:\SoftDentReportExports\era` do not exist (`exists: false`) and `existingRoots=[]` (no 835 files present). Premature to wire ingest until directories exist or explicit empty-inbox UX is designed.  
3. **Collections Summary Excel-temp reliability**: Not critical path while `insurance=0` and `ERA_835_REQUIRED` state is active; risk of implying Register Ins Plan > 0 re-export if not careful. Defer until ERA-835 provides insurance detail or non-Register report shows Ins Plan > 0.

## 3. What NOT to redo
- ERA honesty UX logic (already shipped hal-10571/197efe8)
- Browser smoke test itself (already passed)
- Widgets MUST/SHOULD/NICE (already validated)
- Account-tx DB schema (already exists at 4281a50)
- TXN ingest/ledger (hal-10569, working)
- Invent Ins/Patient split or GUI write-back
- Re-export July Register for Ins Plan > 0 (forbidden by honesty policy; Ins Plan $0 is SoftDent truth)
- Re-apply the read_only watcher fix (already shipped as 2439197)

## 4. Acceptance criteria
- [ ] Identify the specific 2 missing datasets by name/source from `apex_import_quarantine_pack.py` registry
- [ ] Restore both datasets to active inbox without data invention or dollar fabrication
- [ ] Import completeness metric returns to 100% (or pre-quarantine baseline)
- [ ] Quarantine count for "read_only" TypeError = 0 (confirm 2439197 durability)
- [ ] No manual SoftDent Register re-export triggered (honesty policy maintained)
- [ ] Restored datasets appear in TXN ledger or account-tx views within 30 seconds of warm

## 5. Executive Summary (5 bullets)
- Watcher hotfix 2439197 resolved the mass quarantine but left 2 datasets orphaned in limbo
- Data completeness is the blocking foundation issue before any ERA wiring or UI polish can ship safely
- Task is strictly hygiene: audit quarantine registry, identify the 2 stragglers, restore to inbox—no invention, no SoftDent ops
- Uses real quarantine/watcher packs already in codebase; no GitHub PR required
- Unblocks downstream work (ERA-835 ingest, gap-tile polish, Excel reliability) once the data lake is whole

## 6. Approval checklist
- [ ] Operator confirms "next" targets data hygiene completion, not ERA wiring
- [ ] Verify `eraStub.existingRoots=[]` still true (no ERA files yet to ingest)
- [ ] Verify SoftDent Register still shows `registerInsPlanZero=true` (no re-export trigger)
- [ ] `apex_import_quarantine_pack.py` audit log accessible to identify the 2 missing items
- [ ] Confirm no new GitHub PR required (local Apex pack fixes only)
