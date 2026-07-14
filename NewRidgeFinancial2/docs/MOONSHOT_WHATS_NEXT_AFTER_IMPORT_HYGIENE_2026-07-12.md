# Moonshot AI — What's Next After Import Dataset Hygiene (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10571  
**Prior:** import hygiene PASS / smoke PASS / watcher `2439197` / honesty UX `197efe8`  
**Script:** `scripts/run_moonshot_whats_next_after_import_hygiene_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Surface the nested `collectionsGapCode=ERA_835_REQUIRED` in the visible gap-tile label while preserving the "do-not-re-export Register" honesty hint, completing the cosmetic honesty UX fix unblocked by the import hygiene PASS.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** Gap-Tile Honesty Label Polish — Surface ERA_835_REQUIRED  
**Why now:** Import hygiene is clean (100% completeness, 0 missing), unblocking the final cosmetic fix noted in smoke: the gap strip currently shows outer `gapCode=ERA_835_AVAILABLE` while hiding the actionable `collectionsGapCode=ERA_835_REQUIRED` in nested JSON. Staff need the visible message to state explicitly that ERA-835 is required (not merely available) and to retain the legible "SoftDent Register Ins Plan $0 is truth — do not re-export" hint. This is the highest ROI additive fix before wiring real ERA ingest or requiring staff to produce QB files that don't yet exist.  
**Effort:** Low — local string/template refactor in HAL gap formatter; no new external dependencies.  
**REAL files:**  
- `NewRidgeFinancial2/apex_softdent_era_pack.py` (gap code resolution logic)  
- `NewRidgeFinancial2/nr2_hal_gateway.py` (gap tile message rendering / API response construction)  
- `NewRidgeFinancial2/apex_backend.py` (gap serialization for frontend)  
**Validation gate:** Browser smoke showing gap tile text contains "ERA-835 Required" (or equivalent) and retains the "do not re-export July Register" sub-hint; no "ERA-835 Available" ambiguity in the primary label.

## 2. Runner-ups (2–3, why not now)
**A) Wire real ERA-835 inbox ingest / empty-inbox scaffolding** — Premature: `existingRoots=[]` (ERA inbox dirs do not exist). Without staff dropping real 835 files, we would only be building empty-inbox scaffolding; better to first clarify via the gap-tile that 835 is *required*, prompting staff to create the inbox and drop files.  
**B) Collections Summary Excel-temp reliability** — Lower priority: the Collections Summary is functional; reliability tweaks can follow once the primary ERA-835 messaging is unambiguous. Risk of implying Register re-export must be audited first.  
**C) Real QuickBooks payroll/AP OPS export drop** — Blocked: no real QB payroll or AP exports found in `app_data/nr2/document_inbox/quickbooks/`; staff have not produced source files. Empty-batch honesty markers are correct for now; do not invent wages/AP balances.

## 3. What NOT to redo
- Import Dataset Hygiene empty-batch markers (already applied; quarantineCount=0)  
- ERA honesty UX logic `collectionsGapCode=ERA_835_REQUIRED` (already live in API response; only the visible label needs polish)  
- Browser smoke itself (passed)  
- Watcher hotfix 2439197 (already shipped)  
- Re-export July Register for Ins Plan > 0 (forbidden by honesty UX; Register $0 is truth)  
- Invent SoftDent write-back or dollar amounts  

## 4. Acceptance criteria
- [ ] Gap tile primary message surfaces `ERA_835_REQUIRED` (not `ERA_835_AVAILABLE`) when `registerInsPlanZero=true` and `collectionsGapCode=ERA_835_REQUIRED`  
- [ ] Hint text explicitly states "SoftDent Register Ins Plan Collections $0.00 is SoftDent truth — proceed with ERA-835 for insurance detail"  
- [ ] No "Re-export Register" call-to-action appears in the gap remediation chips  
- [ ] HAL `/api/apex/hal/collections-gap` response unchanged (already correct); only presentation layer updated  
- [ ] Empty-batch honesty for QB payroll/AP remains untouched (header-only markers retained)  

## 5. Executive Summary (5 bullets)
- Import hygiene PASS leaves only a cosmetic gap-tile mismatch: outer code says "Available," inner code says "Required."  
- Staff confusion risk: seeing "ERA-835 Available" may suggest waiting, whereas "ERA-835 Required" prompts action to drop 835 files into the inbox.  
- Fix is localized to HAL/Apex message formatting; no SoftDent re-export, no invented dollars, no new file system dependencies.  
- Unblocks future ERA inbox wiring by clearly communicating to staff that 835 ingest is the expected next step.  
- Preserve the "do-not-re-export Register" honesty hint to prevent accidental SoftDent OPS hoping for Ins Plan > 0.

## 6. Approval checklist
- [ ] Operator confirms `existingRoots=[]` (no ERA files yet) — do not build ingest scaffolding prematurely  
- [ ] Operator confirms SoftDent Register still shows Ins Plan $0 (no re-export)  
- [ ] Staff confirm no real QB payroll/AP exports available yet (keep empty-batch markers)  
- [ ] Dev confirms gap-tile template can distinguish `gapCode` vs `collectionsGapCode` for rendering  
- [ ] Smoke test plan drafted for post-polish browser verification
