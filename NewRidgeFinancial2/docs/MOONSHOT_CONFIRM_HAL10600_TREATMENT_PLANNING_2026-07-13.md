# Moonshot AI — Confirm HAL-10600 + Treatment Planning (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10600  
**Prior apply:** HAL-10600 (`d784bdd`)  
**Script:** `scripts/run_moonshot_confirm_hal10600_treatment_planning_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> confirm with moonshot ai what you just did and for treatment planning - consult only

---

# Verdict
**HAL-10600 applied matches consult exactly; residual risk contained in 19 pending manuals and non-alias TP leakage. NEXT: Wire treatment planning payer resolution through accepted carrier_alias (Candidate #1) — unlock 107 carrier mappings without inventing dollars.**

## 0. Operator Intent (verbatim)
> "confirm with moonshot ai what you just did and for treatment planning - consult only"

## 1. Confirmation of HAL-10600 apply (pass/fail vs your consult; deviations; residual risks)

**PASS — Exact match to Moonshot consult specification.**

| Consult Requirement | Applied Reality | Status |
|---------------------|-----------------|--------|
| Fuzzy matching (Jaro-Winkler + token_set) with blocking | `rapidfuzz` implementation with first-4/distinctive-token blocking | ✓ |
| Confidence bands: >85 auto, 60–85 manual, <60 reject | 71 exact + 36 fuzzy auto = 107 accepted; 19 manual pending; 89 rejected | ✓ |
| No invented dollars / no synthetic gold | `no_settlement` pad reduced 28,653→27,838 only where real spine $ attached; no probabilistic rows invented | ✓ |
| Honest ≤20 gap gate | `acceptanceGateMet: false` correctly; 89 are true no-spine orphans (Assurant, Bankers, etc.), not safe to force-match | ✓ |
| CSV export + catalog join | `carrier_alias_mapping.csv` (21KB) exists; catalog includes `masterCompanyId` + `spineCarrierName` | ✓ |

**Residual Risks:**
1. **Pending manual band (19 rows) contains dubious proposals** — e.g., "Guardian Advantage"→"AETNA MEDICARE ADVANTAGE" (70.6 score), "Cigna Healthcare Service Center"→"UHC UNIVERSAL MEDICARE CLAIMS" (80.1 score). Auto-accepting these would over-match and attribute payments to wrong carriers.
2. **Treatment planning leakage** — Current `tpCodeUsesCarrierAlias: false` means TP lookup bypasses the 107 accepted aliases, missing existing spine settlements for mapped carriers and falling through to probabilistic guesses or nulls unnecessarily.
3. **Orphan attribution** — 89 rejected carriers remain in staff grid with `no_settlement`; operators must not manually pad these with synthetic estimates.

## 2. Recommended NEXT for treatment planning (name, why now, effort, REAL files, validation gate)

**Package:** **HAL-10601 — TP Payer Resolution via Accepted Carrier Alias** (Candidate #1)

**Why now:**
- Gold CSV remains blocked (`GOLD_CSV_MISSING`, 0 payment lines). The only credible data layer is the existing spine settlements (46 exact usable cells).
- 107 accepted aliases currently sit unused; treatment planning calls `_ledger_spine_treatment_fallback` directly without resolving master company names through the alias table, missing valid spine data for carriers like "Aetna Healthcare" (master) → "AETNA" (spine).
- Wiring this now prevents the TP chip from showing "insufficient" when actual spine dollars exist under a mapped alias, and prevents inappropriate probabilistic fallback when exact ledger history is available via alias resolution.

**Effort:** Low (1–2 dev days). Local refactor of `softdent_treatment_planning.py` only; no SoftDent write-back; no new dependencies.

**REAL files / ops steps:**
1. **Source:** `C:\SoftDentFinancialExports\carrier_alias_mapping.csv` (existing, 107 accepted rows)
2. **Code change:** Modify `lookup_treatment_estimate` in `softdent_treatment_planning.py`:
   - Step 1: Query `carrier_alias` where `master_company_id = ? AND confidence = 'auto' AND review_status = 'accepted'` (the 107)
   - Step 2: If alias found, use `spine_carrier_name` to query spine settlements (existing `insurance_company` + `ada_code` index)
   - Step 3: Only if no accepted alias AND no direct spine match, fall back to `_ledger_spine_treatment_fallback` / probabilistic lookup
   - Step 4: Return metadata `source: 'ledger_episode_5yr_via_alias'` when alias used
3. **Block:** Explicitly exclude `confidence = 'manual'` (the 19 pending) from auto-resolution; require HAL chip review.

**Validation gate:**
- `tpProbeAetnaHealthcare` (currently "No publishable ledger estimate") should flip to `found: true` with credible spine data if "Aetna Healthcare" maps to accepted alias with spine history.
- `tpCodeUsesCarrierAlias` flag becomes `true`.
- Pending aliases (19) never auto-resolve; TP returns `credibility: 'insufficient'` for these until HAL `--accept-pending` used.
- `emptyIsNotZero` remains true; no regression to $0.00 displays.

## 3. Why this beats other TP candidates now

- **vs #2 (Show metadata in chip):** Cosmetic only. Without #1, the chip has nothing honest to show; #1 provides the data foundation that makes #2 meaningful later.
- **vs #3 (Review 19 pending):** Operational task, not code. Can run in parallel via `scripts/reconcile_carrier_aliases.py --accept-pending`, but blocking TP on manual review of dubious matches (Guardian→Aetna) delays the 107 safe mappings already available.
- **vs #4 (Honesty CI):** Defensive; deploy after #1 to protect the new alias-resolution path from null→$0 regressions, but not the primary leverage point.
- **vs #5 (Gold CSV/ERA):** Blocked by reality—no 835/CSV files confirmed in manifest. Cannot proceed on wishful thinking.
- **vs #6 (Grow usable cells/secondary-ins):** Attempting to grow coverage before fixing identity layer risks attributing secondary payments to wrong primary carriers or inventing coverage for the 89 true orphans. Fix attribution first, then expand.

## 4. Runner-ups (2–3)

1. **#3 — Review/accept 19 pending manuals (OPS):** Required before those specific carriers become available in TP, but the 107 auto-accepted aliases provide immediate value without this. Schedule as parallel HAL task, not the primary code package.
2. **#4 — Honesty CI for TP chip null→$0 regressions:** Critical safety net after #1 is deployed, especially given 27,838 `no_settlement` cells remain. Prevents future builds from accidentally coercing null to 0.00 in the UI.
3. **#6 — Secondary insurance / usable cell growth:** High value, but only after #1 establishes clean attribution. Secondary payments currently mix into primary spine rows; without alias resolution, growing cells risks double-counting or misattribution.

## 5. What NOT to redo

- **SoftDent write-back:** Continue read-only policy; no updates to `insurance_company` table.
- **Invent gold from ledger:** Do not create synthetic `sd_insurance_payment_lines` or `treatment_planning_estimates` rows from spine aggregations.
- **Accept all 19 pending blindly:** Specifically reject auto-accepting the Guardian→Aetna Medicare (70.6) and Cigna→UHC (80.1) proposals without HAL review.
- **Force ≤20 gap gate with unsafe matches:** Do not lower threshold to absorb the 89 true orphans; they remain `no_settlement`.
- **Rebuild spine greenfield:** Existing 5-year episode spine (HAL-10582/84) remains valid; do not reprocess history.
- **GitHub/PR as primary next:** Focus on local `softdent_treatment_planning.py` wiring; repository hygiene is secondary to functional alias resolution.

## 6. Acceptance criteria

- [ ] `lookup_treatment_estimate` queries `carrier_alias` for `confidence = 'auto'` matches before spine direct query
- [ ] Pending aliases (`confidence = 'manual'`, 19 rows) are explicitly excluded from TP resolution; return `insufficient` for these carriers
- [ ] When alias resolves to spine data, TP returns `source: 'ledger_episode_5yr_via_alias'` and populates `estimated_pay` from actual settlements (not null→$0)
- [ ] When no alias and no spine data, falls back to probabilistic lookup with `credibility: 'probabilistic'` or `null` per existing logic
- [ ] `tpCodeUsesCarrierAlias` flag returns `true` in health checks
- [ ] `emptyIsNotZero` remains `true` across all TP probe tests (no $0.00 for empty result sets)

## 7. Executive Summary (5 bullets)

- **HAL-10600 applied correctly:** 107 safe aliases accepted, 19 held for HAL review, 89 honestly rejected; ≤20 gate unmet by design to prevent over-match.
- **TP identity gap exposed:** Treatment planning currently bypasses accepted aliases, missing valid spine data for 107 carriers and defaulting to insufficient/probabilistic unnecessarily.
- **Next leverage point:** Wire TP payer resolution through accepted aliases (HAL-10601) to unlock existing ledger dollars without inventing new data.
- **Risk containment:** Pending manual aliases (including Guardian→Aetna Medicare) remain blocked from auto-resolution until explicit HAL confirmation.
- **Gold still blocked:** No CSV/835 files available; spine + alias layer is the only credible data path for treatment estimates.

## 8. Approval checklist

- [ ] Operator confirms 19 pending aliases should remain blocked from TP auto-resolution until reviewed
- [ ] Dev confirms `softdent_treatment_planning.py` can query `carrier_alias` table without SoftDent write-back
- [ ] QA confirms `tpProbeAetnaHealthcare` and similar probes show `found: true` after alias wiring (if spine data exists)
- [ ] Compliance confirms `emptyIsNotZero` enforcement remains active in TP chip display layer
- [ ] HAL schedule set for manual review of 19 pending aliases (parallel track, not blocking code deploy)