# Moonshot AI — What's Next After HAL-10585 Unified Spine (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** HAL-10585 unified spine + TP fallback (`9cacfa6`)  
**Script:** `scripts/run_moonshot_whats_next_after_hal10585_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
Ship the **Full CDT Catalog Matrix** to expose all 2,274 InsCo×ADA cells including honest insufficient/empty states, expanding visibility from the current narrow ~21 distinct CDTs to the complete procedure catalog so "every code analyzed" is provable in the UI.

## 0. Operator Intent (verbatim)
> next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** Full CDT Catalog Matrix (Honest Empty Exposure)  
**Why now:** HAL-10585 unified the spine but revealed only **21 distinct CDTs** are publishable against 13,321 episodes and 2,274 total matrix cells. The immediate gap is not treatment-planning UX wiring—it is that 95%+ of codes appear "missing" without proof the system analyzed them. Exposing the full matrix with tier badges (exact/inferred/low/insufficient) proves comprehensive analysis and identifies specific gaps for future data collection.  
**Effort:** Low-Medium (2–3 days). Read-only aggregation of existing `softdent_insco_ada_spine.py`; no new ETL or SoftDent export dependencies.  
**REAL files:**  
- `softdent_insco_ada_catalog_matrix.py` (full outer join of Sensei carriers × normalized CDT universe against spine aggregates)  
- `nr2_hal_gateway.py` — new intent `policy:insco-ada-catalog-matrix`  
- `softdent_hal_chips.py` — Catalog Viewer widget (table with filters: exact only, show insufficient)  
- API: `GET /api/apex/insco-ada-catalog` (returns all 2,274 cells with credibility tier, n count, pay$/WO$, ±%)  
- Report: `C:\SoftDentFinancialExports\insco_ada_catalog_matrix_{date}.json`  
**Validation gate:** UI lists >150 distinct CDTs (full ledger spectrum) with 46 exact, 163 published, and ~2,100 honestly marked "insufficient (n<10)"; zero regression on existing exact cells; query performance <2s for full matrix.

## 2. Why this beats the other candidates now
- **Treatment Plan UX Surface (1):** Premature. Building a UI widget when only 21 CDTs have data means 90% of lookups return empty. Catalog first ensures the subsequent UX has substantive breadth to display.  
- **Reliability Uplift (3):** Dangerous at this moment. Secondary-insurance exclusion or same-day settlement preference would likely collapse the fragile 46 exact cells toward zero given current episode concentration (13k episodes → only 46 exact). Defer until catalog identifies borderline cells (n=10–15) for targeted bootstrap.  
- **Gold Path Capture (4):** Historically blocked. SoftDent Excel exports for payment lines are often unavailable; chasing unavailable data wastes cycles when the spine fallback is already functional and honest.  
- **ERA835 Cross-check (5):** No evidence of 835 file availability in the live snapshot (`payment_lines: 0`). Defer until files confirmed present.  
- **Sensei Expansion (6):** Redundant. Coverage map is already 5,221; the issue is CDT distribution within existing episodes, not patient coverage geography.

## 3. Runner-ups (2–3, why not now)
1. **SoftDent Treatment Plan / Estimate UX Surface (Candidate 1):** High value, but sequence after catalog. The widget needs >50 usable CDTs to avoid frustrating "no data" states. Build on top of the catalog matrix once it proves the breadth of available estimates.  
2. **Reliability Uplift — Secondary Ins Exclusion (Candidate 3):** Necessary eventually for precision, but risks destroying the current 46 exact usable cells. Wait until catalog matrix exposes which cells are borderline (n=10–15), then apply bootstrap CI only to those specific cells rather than blanket exclusion.  
3. **OPS: Expand Sensei Coverage (Candidate 6):** The 5-year TX chunks and 5,221 insurance map entries suggest coverage is already deep; the bottleneck is procedure code diversity in the ledger, not patient geography. Address CDT breadth first.

## 4. What NOT to redo
- Do **not** rebuild the unified spine (already converged on 5-year window, same episodes for $ and %).  
- Do **not** attempt SoftDent write-back or claim contractual fee schedule authority.  
- Do **not** invent gold-path payment-line data (remains empty).  
- Do **not** exclude inferred tiers from publication (they are already honest and flagged).  
- Do **not** treat empty as $0 (maintain `empty != $0` discipline).

## 5. Acceptance criteria
- [ ] Matrix API returns all 2,274 InsCo×ADA combinations defined by the spine (carrier × CDT).  
- [ ] Each cell exposes: credibility tier (exact/inferred/low/insufficient), sample size `n`, median pay $, median WO $, pay % with ±1 SD, and `last_updated`.  
- [ ] HAL Catalog Viewer lists the full CDT universe with visual badges (green exact, yellow inferred, red insufficient).  
- [ ] "Insufficient" cells (n<10) are explicitly labeled and visible, not hidden or defaulted to $0.  
- [ ] Regression: existing 46 exact usable cells remain exact with identical values.  
- [ ] Performance: full matrix query completes in <2 seconds against `softdent_financial_analytics.db`.

## 6. Executive Summary (5 bullets)
- HAL-10585 unified the spine but exposed severe CDT concentration: only ~21 codes publishable vs. thousands of ledger possibilities.  
- Full catalog matrix exposes honest data boundaries across all 2,274 InsCo×ADA cells, proving "every code analyzed" to the user.  
- Read-only aggregation of existing 5-year ledger spine; zero risk to current credible cells.  
- Unblocks future Treatment Planning UX work by defining the complete surface area of available estimates.  
- Preserves `empty != $0` honesty; gold path (payment lines) remains optional future enhancement.

## 7. Approval checklist
- [ ] Operator confirms "next" prioritizes catalog visibility over UI wiring.  
- [ ] Confirm SoftDent integration remains read-only (no write-back to patient records).  
- [ ] Verify `exact_usable=46` is preserved as a floor (must not decrease with this change).  
- [ ] Acknowledge gold path (`sd_insurance_payment_lines`) remains empty; spine fallback stays the primary data source for treatment planning.  
- [ ] Commit to subsequent package (post-catalog) being Treatment Plan UX Surface once CDT breadth exceeds 50 usable codes.