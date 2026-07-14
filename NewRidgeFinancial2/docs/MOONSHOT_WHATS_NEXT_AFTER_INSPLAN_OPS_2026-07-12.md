# Moonshot AI — What's Next After July Ins Plan OPS + Widgets NICE (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10570  
**Prior:** Ins Plan OPS proceed (05dfc1e); Widgets NICE (hal-10570)  
**Script:** `scripts/run_moonshot_whats_next_after_insplan_ops_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
**ERA-835 Collections Honesty UX Bridge** — code package that accepts SoftDent Register’s $0 Ins Plan as ground truth, surfaces ERA-835 as the alternative source of insurance collection truth, and updates HAL/dashboard gap language to explain the divergence without inventing dollars.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** ERA-835 Collections Honesty UX Bridge (hal-10571)  
**Why now:** SoftDent Register has spoken—July Ins Plan Collections = $0. Re-exporting cannot fabricate a split that does not exist in the SDWIN database. The practice still collected $30,626.42, and insurance payments likely arrived via ERA-835 rather than the Register’s “Ins Plan” bucket. This package closes the honesty gap: it stops the retry-loop on Collections Summary Excel (which failed to materialize and would likely show $0 anyway) and instead surfaces ERA-835 data as the authoritative insurance collection source when SoftDent Register reports $0. Highest ROI because it unblocks July financial truth without violating the “empty != $0” constraint.  
**Effort:** Small (½ day). Additive HAL phrases + backend gap-logic branch only; no SoftDent write-back.  
**REAL files:**  
- `NewRidgeFinancial2/apex_backend.py` — gap resolver: when `collectionsGapCode == "COLLECTIONS_EXPORT_REQUIRED"` and `julyRegister.insurance == 0`, branch to `ERA_835_LOOKUP` status instead of retry loop.  
- `NewRidgeFinancial2/nr2_hal_gateway.py` — HAL phrase pack for `COLLECTIONS_ERA_FALLBACK` context (e.g., “SoftDent Register shows Ins Plan $0; pulling ERA-835 for insurance allocation”).  
- `NewRidgeFinancial2/softdent_practice_exports.py` — stub ERA-835 ingestion path (read-only, idempotent).  
**Validation gate:**  
1. HAL returns message: “July Ins Plan Collections $0 per SoftDent Register; ERA-835 path active.”  
2. Dashboard gap tile shows `ERA_835_REQUIRED` (not `COLLECTIONS_EXPORT_REQUIRED`) when Register Ins Plan = $0.  
3. No `insurance` or `patient` dollars invented in DB; columns remain NULL until ERA ingest.  

## 2. Runner-ups (2–3, why not now)
- **Wire Collections Summary Excel-temp path reliability (Candidate 4):** Tactical hardening is sensible, but SoftDent Output Options already opened and failed to yield a workbook; even if fixed, the underlying data is $0 Ins Plan. Hardening would only automate the export of zeros. Defer until after honesty UX explains *why* zeros are expected.  
- **Browser smoke of widgets NICE + TXN ledger (Candidate 2):** Validation is valuable, yet the widgets (pareto, tax-calendar, timeline-lanes) are already shipped and the 1,716 TXN rows are confirmed live. Smoke testing does not unblock the July collections data gap that is currently breaking the financial close.  
- **SoftDent Collections Summary re-export (Candidate 1):** Skip—Operator constraint explicitly forbids OPS when SoftDent UI shows Ins Plan $0. Re-exporting violates the “honesty” principle; it implies we doubt the $0 truth.  

## 3. What NOT to redo
- Do **not** re-run `register_for_period` export expecting Ins Plan > 0.  
- Do **not** invent Ins/Patient split logic for the July $30,626.42 Regular Collections.  
- Do **not** write back to SoftDent (no GUI automation to “fix” the $0 line).  
- Do **not** rebuild widgets MUST/SHOULD/NICE (already hal-10570).  
- Do **not** re-ingest Account-Tx DB (already 4281a50).  

## 4. Acceptance criteria
- [ ] `apex_backend.py` returns `gap.collectionsGapCode = "ERA_835_REQUIRED"` when `julyRegister.insurance == 0` and `collectionsFormatRequired == true`.  
- [ ] `nr2_hal_gateway.py` emits contextual phrase: “SoftDent Register reports Ins Plan Collections $0.00; proceed with ERA-835 for insurance detail.”  
- [ ] No mutation of `julyRegister` JSON to fake `insurance > 0`.  
- [ ] Unit test: `test_era_fallback_when_register_zero_insurance` passes.  
- [ ] Manual validation: HAL response does not suggest “re-export July Register” as a fix.  

## 5. Executive Summary (5 bullets)
- **Ground Truth Accepted:** SoftDent Register July 2026 shows Ins Plan Collections $0.00; this is the system record, not a bug.  
- **ERA-835 Reality:** Insurance payments ($30k+ bucket) likely exist only in ERA-835 files, not the Register’s Ins Plan line.  
- **Honesty Over Hacks:** Package builds UX bridge explaining the divergence rather than fabricating a split.  
- **Unblocks July Close:** Allows financial summary to proceed with “Insurance TBD via ERA” instead of blocking on impossible SoftDent export.  
- **Zero Write-Back:** Read-only integration; SoftDent database remains untouched.  

## 6. Approval checklist
- [ ] Operator confirms SoftDent Register on-screen Ins Plan = $0 (truth).  
- [ ] ERA-835 file location/path confirmed accessible (or stubbed for next iteration).  
- [ ] HAL phrase tone approved (professional, not alarmist).  
- [ ] No dollars invented in acceptance test data.  
- [ ] Proceed to coding upon operator “apply.”
