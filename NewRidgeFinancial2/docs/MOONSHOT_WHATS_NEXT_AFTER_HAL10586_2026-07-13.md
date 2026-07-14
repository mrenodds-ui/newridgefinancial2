# Moonshot AI — What's Next After HAL-10586 Catalog Matrix (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** HAL-10586 full InsCo×ADA catalog (`3171bfe`)  
**Script:** `scripts/run_moonshot_whats_next_after_hal10586_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
Ship **SoftDent Treatment Plan / Estimate UX Surface** (HAL-10587) — wire the newly exposed 2274-cell catalog into staff-facing treatment planning chips, displaying pay$/WO$, variance % +/-, and credibility badges (exact/published/insufficient) without SoftDent write-back.

## 0. Operator Intent (verbatim)
> next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** Treatment Planning UX Surface — Catalog-Enriched Estimates (HAL-10587)  
**Why now:** HAL-10586 just exposed the full matrix breadth (2274 cells, 163 published, 46 exact usable). The immediate leverage is staff-facing treatment planning: the fallback spine already exists, but the UX currently lacks the rich catalog metadata (credibility tiers, variance ranges, carrier-specific vs. generic indicators). Surfacing this validates the catalog investment and gives schedulers/front-desk actionable confidence intervals before the gold payment-line path (still 0 rows) materializes.  
**Effort:** Medium (3–4 days). Additive wiring of existing `softdent_insco_ada_catalog_matrix.py` aggregates into the TP reply path; no new ETL or SoftDent export required.  
**REAL files:**  
- `softdent_treatment_planning.py` — enrich `lookup_treatment_estimate()` to return catalog-backed payload with `credibilityTier`, `payMedian`, `woMedian`, `payPct`, `varianceBand`  
- `softdent_hal_chips.py` — new `TpEstimateChip` component (badges: Exact / Published / Insufficient; pay vs WO delta; sample size n)  
- `softdent_treatment_planning_api.py` — `GET /api/apex/treatment-estimate/{patientId}?cdt=D####` returns catalog-enriched reply (falls back to spine gracefully)  
- `test_treatment_planning_hal10587.py` — unit tests for chip rendering logic and catalog fallback precedence  
- Export (debug): `C:\SoftDentFinancialExports\tp_estimate_audit_{date}.json`  
**Validation gate:**  
- Staff viewing a Treatment Plan in SoftDent sees a chip for D#### with:  
  - Exact usable: “$66 ±12% (n=35)” badge green  
  - Published (inferred): “$58 ±18% (n=8)” badge yellow  
  - Insufficient: “No credible data (n=2)” badge gray (empty ≠ $0)  
- Zero SoftDent write-back; empty insufficient cells never display $0.00.

## 2. Why this beats the other candidates now
- **Beats Catalog UX polish (#2):** Filters and searchable tables are internal-only visibility wins; TP surface directly impacts daily scheduling revenue decisions and proves the catalog’s business value to end users.  
- **Beats Spine reliability uplift (#3):** Bootstrap CI on borderline cells and secondary-ins exclusion are worthwhile, but the 46 exact usable cells are already credible; we should expose them to staff *before* refining the long tail of 2111 insufficient cells.  
- **Beats Gold path (#4) & ERA835 (#5):** Payment-line gold path remains 0 rows with no confirmed SoftDent export; pursuing these now requires infrastructure we don’t have. The catalog+spine fallback is live and actionable today.  
- **Beats Uncovered CDT ops (#6):** Ops playbook to diagnose the 47 missing CDTs is valuable parallel work, but it is research, not additive code; it doesn’t depend on HAL-10586 shipping and can follow the TP surface.

## 3. Runner-ups (2–3, why not now)
1. **Catalog UX polish (#2) — Drill-down filters & searchable matrix table:** Important for internal analysts, but the existing `/status` widget and JSON export suffice for immediate debugging. Defer until staff TP usage proves which filters matter (carrier vs. ADA vs. credibility).  
2. **Target uncovered 47 CDTs — Ops playbook (#6):** High analytical value to explain why D0171, D0240, etc. lack 2/51 pairings (timing, multi-visit, carrier miss), but this is an operational runbook, not a code deliverable. Schedule as parallel workstream while TP UX is being wired.  
3. **Reliability uplift on spine (#3) — Secondary-ins exclusion & same-day settlement:** Algorithmic improvements that reduce the 2111 insufficient count, but risky to tune before we see how staff interact with the current 46 exact usable cells in live TP workflows. Better to gather UX feedback first.

## 4. What NOT to redo
- **SoftDent write-back:** Never write estimated $ amounts back to SoftDent fee schedules or patient ledger.  
- **Invent $0:** Insufficient cells (2111) remain explicitly empty/null; never coerce to $0.00 in UI or API.  
- **Re-unify spine:** HAL-10585 spine logic is final; do not rebuild the 5yr episode join.  
- **Rebuild catalog:** HAL-10586 matrix is the source of truth; do not re-aggregate from raw ledger.  
- **Pretend gold path exists:** Do not mock SoftDent payment-line data; empty remains empty until real ERA/PL export arrives.  
- **Register re-export:** Do not attempt to pull Ins Plan Register dollars or carrier names from SoftDent if not already present.

## 5. Acceptance criteria
- [ ] API `/api/apex/treatment-estimate` returns catalog cell when `(carrier, ADA)` exists, else returns spine generic with `credibility: low`  
- [ ] Chip UI displays `payMedian` vs `woMedian` delta as percentage when `exactUsable` or `published`  
- [ ] Insufficient cells (n<10 or missing) display “Insufficient data” badge with no dollar value  
- [ ] Fallback chain documented: gold payment lines (0 rows) → catalog exact → catalog published → spine inferred → insufficient  
- [ ] No new SoftDent exports or database writes; read-only from existing `softdent_financial_analytics.db`  
- [ ] Unit tests cover all credibility tiers; integration test validates chip render in SoftDent widget container  

## 6. Executive Summary (5 bullets)
- **HAL-10586 breadth now usable:** 2274 cells analyzed, 46 exact usable, 163 published — ready for staff-facing display.  
- **Immediate staff impact:** Treatment planning chips show confidence intervals (pay$/WO$ ±%) instead of blind estimates.  
- **Zero gold-path dependency:** Works with existing ledger spine fallback; no blocked SoftDent payment-line export needed.  
- **Honest empty states:** Insufficient cells remain explicitly empty; no $0 coercion or write-back.  
- **Validation in days:** 3–4 day additive code effort; validation gate is visible credibility badges in live TP view.

## 7. Approval checklist
- [ ] Operator confirms `next` intent to proceed with TP UX surface (HAL-10587)  
- [ ] Confirm no SoftDent write-back requirement from practice stakeholders  
- [ ] Confirm fallback to spine acceptable until gold path (ERA/payment lines) arrives  
- [ ] Assign owner for parallel ops playbook on 47 uncovered CDTs (non-blocking)  
- [ ] Freeze scope: no secondary-ins exclusion or same-day settlement logic in this package