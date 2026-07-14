# Moonshot AI — What's Next for InsCo×ADA Estimates / Reliability / Report (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** HAL-10582 probabilistic InsCo×ADA (`d028527`)  
**Script:** `scripts/run_moonshot_insco_ada_estimates_reliability_next_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot ai how to proceed with those estimates and relaiablity and report

---

# Verdict
Ship HAL board-action + widget surfacing only exact usable+ cells with explicit credibility badges, requiring staff opt-in to view inferred estimates; do not tighten credibility rules further while the gold path remains empty.

## 0. Operator Intent (verbatim)
> "ask moonshot ai how to proceed with those estimates and relaiablity and report"

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** HAL Board-Action + Credibility-Badge Widget (Candidate 1)  
**Why now:** The probabilistic engine is built and producing 124 published cells, but ops cannot safely consume them without UI guardrails. Only 2 cells are high credibility; the rest are usable exact (n≥10) or inferred (proportional splits). Without explicit badges, staff may treat inferred $ allocations as contractual truth. This is pure presentation-layer code on existing data—no new SoftDent dependencies, no GitHub PR required.  
**Effort:** Small (1–2 days). Local HAL widget + JSON inbox reader.  
**REAL files:**  
- Input: `app_data/nr2/document_inbox/softdent/softdent_insco_ada_probabilistic.json` (existing HAL-10582 output)  
- Output: HAL board action `insco_ada_estimate_lookup` + widget `InsCoAdaEstimateWidget`  
**Validation gate:**  
- Widget shows "exact usable" (n≥10) by default with green/amber badges  
- "Inferred" rows hidden behind "Show uncertain estimates" toggle with red warning banner  
- "Low" tier never displayed  
- Unit test: Query for Delta KS × D1110 returns $68/$18 with "high" badge; query for inferred cell returns `null` unless `?includeInferred=true`

## 2. Reliability posture (what 124 published / 2 high means; what to trust)
- **124 published / 2 high / 1,973 total = 6.3% coverage**, heavily concentrated in common prophys (D1110) and fillings (D2391).  
- **Exact usable (n≥10):** Trust directionally for fee negotiation; median paid is real but variance unmeasured. These are the 122 usable cells.  
- **Exact high (n≥30):** Trust for budgeting. Only **2 cells** qualify: Delta Dental KS × D1110 ($68 paid/$18 WO, n=32) and Cigna Dental × D2391 ($36 paid/$122 WO, n=30).  
- **Inferred (8,449 events):** Statistical fiction—proportional splits of lump payments across multi-ADA visits where ledger rows lack ADA tags. Never use for contractual quotes; only for "directional sense" with explicit warnings.  
- **Low (4,520 events):** Unpublished—too many ADAs (4+) to allocate meaningfully.  
- **Empty cells:** `empty != $0`; return "Insufficient data" rather than zero.

## 3. How to use the report in HAL/ops (display rules)
- **Default view:** Exact usable+ only (n≥10), sorted by carrier then ADA. Inferred and low tiers suppressed.  
- **Badge system:**  
  - "High" (n≥30, green) — reliable for budgeting  
  - "Usable" (n≥10–29, amber) — reliable for negotiation ballpark  
  - "Inferred" (red, hidden by default) — algorithmic estimate only, never quote to patient  
- **Interaction:** Staff must click "Show uncertain estimates" to see inferred cells, triggering logged audit entry: *"User viewed inferred InsCo×ADA estimate [Carrier×ADA]—invented proportional split warning acknowledged."*  
- **Hard stop:** Cells with n<10 or low tier return `{"status":"insufficient_data","n":0}` rather than `$0`.  
- **Use case:** Front-desk verifies "Delta typically pays $X for D1110" before patient checkout; do **not** use for treatment planning estimates (awaits hal-10400 gold path).

## 4. Runner-ups (2–3, why not now)
- **Candidate 2 (Reliability uplift):** Would sterilize the report. Tightening lookback to same-claim-day or requiring bootstrap CIs when only **702 exact events** exist risks publishing 0 cells. The 2 high-credibility cells are too precious to filter out. Defer until gold path provides line-item truth.  
- **Candidate 3 (SoftDent payment-line capture):** Excel unavailable per operator notes; gold path count=0. Do not chase ghost files or pretend Print Preview can be scraped reliably. Revisit only if Practice Manager confirms CSV export is actually written to disk and accessible.  
- **Candidate 4 (Fee schedule cross-validation):** Good sanity check but secondary. Fee schedules are often outdated; validating against them adds complexity before the base report is even surfaced to users. Defer until after widget is operational.

## 5. What NOT to redo
- Do not re-run HAL-10581 attribution (carrier names are set).  
- Do not rebuild HAL-10580 claims bridge (no new claim-to-payment linkage exists).  
- Do not invent ledger→ADA joins beyond exact/inferred (no new data vectors).  
- Do not claim empty cells equal $0 (`empty != $0`).  
- Do not write back to SoftDent Ins Plan Register (no invented dollars).  
- Do not pretend hal-10400 payment lines exist (count=0).

## 6. Acceptance criteria
- [ ] HAL widget renders 124 published cells with correct credibility badges (high/usable).  
- [ ] Default view excludes inferred (8,449 events) and low (4,520 events).  
- [ ] "Show uncertain" toggle reveals inferred with red warning banner and logs audit entry.  
- [ ] Query for non-published cell returns `{"error":"Insufficient data","n":0}` not `$0`.  
- [ ] Top 10 published list matches HAL-10582 output (Delta KS D1110 $68, Cigna D2391 $36, etc.).  
- [ ] No new SoftDent reads (uses existing JSON inbox only).

## 7. Executive Summary (5 bullets)
- HAL-10582 probabilistic report shipped with 124 usable InsCo×ADA cells (only 2 high credibility).  
- 95% of ledger events are "inferred" (proportional splits)—unsafe for contractual quotes without explicit warnings.  
- Gold path (payment lines) remains blocked by unavailable Excel exports; do not pursue Candidate 3.  
- Next: Productize existing data via HAL board widget with strict credibility badges and inferred opt-in only.  
- Outcome: Ops gains directional fee intelligence for top carriers/ADAs immediately without data hallucination.

## 8. Approval checklist
- [ ] Operator confirms HAL widget approach (no SoftDent changes).  
- [ ] Staff training drafted on "inferred" toggle meaning (invented splits, not contractual).  
- [ ] Confirm no Excel dependency for this package (uses existing JSON inbox).  
- [ ] Acknowledge 124 published cells is sufficient for pilot use (D1110, D2391 coverage).