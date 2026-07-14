# Moonshot AI — What's Next After HAL-10599 Company-Master Catalog (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10599  
**Prior:** HAL-10598 (`6e5ba62`) · HAL-10599 (`cc76c70`)  
**Script:** `scripts/run_moonshot_whats_next_after_hal10599_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> now run what you did through moonshot ai for a consult

---

# Verdict
**HAL-10600 — Fuzzy alias reconciliation: spine carrier names ↔ company master (the 144 gap)**

## 0. Operator Intent (verbatim)
now run what you did through moonshot ai for a consult

## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
**HAL-10600 — Spine-to-Master Carrier Alias Reconciliation**

- **Why now**: HAL-10598 gave us 215 likely_active companies but HAL-10599 shows only 71 overlap with the settlement spine; 144 active names float without linked ledger history. These are likely aliases (e.g., "AETNA HEALTHCARE" vs "AETNA", "BLUE CROSS BLUE SHIELD OF ILLINOIS" vs "BCBS OF ILLINOIS"). Reconciling them unlocks existing settlement dollars already in the spine—**no new gold files required, no invented dollars, honest growth of exact_usable_cells from 46 upward**.

- **Effort**: Medium (2–3 dev days). Requires: (a) fuzzy matching module (Levenshtein/Jaro-Winkler/blocking on first 4 chars), (b) `carrier_alias` table schema, (c) reconciliation CLI with manual confirmation HAL for low-confidence matches (>0.85 auto-accept, 0.60–0.85 HAL chip, <0.60 reject), (d) backfill of matched master IDs into spine references.

- **REAL files/ops steps**: 
  1. Source: `C:\SoftDentFinancialExports\softdent_insurance_companies.csv` (HAL-10598 output) + existing spine carrier strings.
  2. No SoftDent write-back; read-only alias table.
  3. Output: `carrier_alias_mapping.csv` + updated catalog with `masterCompanyId` joined to spine settlements where aliases resolve.

- **Validation gate**: 
  - `likelyActiveNotInSpine` count drops from 144 toward 0 as aliases map.
  - `exactUsableCells` increases only from existing 2/51 ledger settlements (not from null→$0).
  - No regression: `emptyIsNotZero` remains true; `noSettlementPadCells` decreases only when real spine dollars attach.

## 2. Why this beats the other candidates now
- **vs Gold CSV drop (#7)**: Gold is still `GOLD_CSV_MISSING` / `paymentLines: 0`; manifest JSONs exist but no real 835/CSV content confirmed. Cannot proceed on wishful thinking.
- **vs Grow exact usable (#3)**: Without alias resolution, "growing" usable cells risks lowering credibility floors or inventing secondary-ins logic. Fix the identity layer first, then grow.
- **vs Uncovered CDT playbook (#4)**: 47 uncovered CDTs need gold line-item validation; blocked by same gold missing constraint.
- **vs Staff UX (#2)**: Filtering no_settlement is trivial Excel work; alias reconciliation is structural leverage that makes the UX actually useful (more green cells, less noise).
- **vs Honesty CI gate (#5)**: Defensive; do after reconciliation to protect the new joins.

## 3. Runner-ups (2–3, why not now)
1. **#4 Uncovered ledger CDT playbook** — 47 CDTs exist in treatment history but have no 2/51 settlement cells. *Why not now*: Without gold CSVs, we cannot validate if these are truly uncovered or just secondary/ bundled payments. Re-run after HAL-10600 alias fix to see if some "uncovered" CDTs were actually under aliased carriers.
2. **#5 Honesty CI gate** — Fail build if financial widgets regress `null→$0.00`. *Why not now*: Critical but defensive; wait until after HAL-10600 adds new joins to ensure the gate covers alias-mediated mappings.
3. **#2 Staff catalog UX** — Filter chips for "no_settlement" vs "usable". *Why not now*: Low code, high UI; defer 1 sprint until alias reconciliation populates more usable cells, making the filter meaningful.

## 4. What NOT to redo
- Do **not** re-import company CSV without new SoftDent export (HAL-10598 stable).
- Do **not** rebuild spine as greenfield (HAL-10596 shipped).
- Do **not** invent Ins Plan Register dollars or clear `no_settlement` without ledger 2/51 evidence.
- Do **not** write back to SoftDent (Insurance.xlsx still product-blocked).
- Do **not** pretend ERA-835 files exist (manifests ≠ content).

## 5. Acceptance criteria
- [ ] `carrier_alias` table exists with `spine_carrier_name`, `master_company_id`, `match_score`, `confidence` (auto|manual).
- [ ] CLI `reconcile_carrier_aliases.py` generates mapping for the 144 gap.
- [ ] Post-run: `likelyActiveNotInSpine` ≤ 20 (unmatched remnants flagged for manual review).
- [ ] `exactUsableCells` ≥ 46 (strictly from existing settlements now properly linked).
- [ ] Catalog CSV retains `emptyIsNotZero=true`; no `$0.00` invented for pad cells.
- [ ] Unit tests: alias match does not create synthetic payment lines.

## 6. Executive Summary (5 bullets)
- **Shipped**: 216 companies × 139 ADAs = 30,024 cells, but only 46 have real dollars; 144 active companies are orphaned due to name variants.
- **Constraint**: Gold CSV still missing; cannot ingest new payment lines.
- **Leverage**: Reconcile aliases to join existing spine settlements to master IDs—honest growth without new files.
- **Risk**: Fuzzy matching can over-match; implement confidence HAL gates and manual confirmation for borderline cases.
- **Outcome**: Staff sees which of the 215 "active" companies actually have payment history vs. true zero-volume carriers.

## 7. Approval checklist
- [ ] Operator confirms no real ERA-835/CSV files landed on disk (blocks #7).
- [ ] Operator accepts 144 alias reconciliations as priority over UX filtering.
- [ ] Dev confirms fuzzy match library approved (e.g., `rapidfuzz` or `jellyfish`).
- [ ] Compliance confirms: no SoftDent write-back, no invented dollars, null stays null.
- [ ] Build ID reserved: `hal-10600`.