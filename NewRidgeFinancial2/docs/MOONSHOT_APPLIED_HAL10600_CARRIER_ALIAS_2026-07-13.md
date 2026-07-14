# HAL-10600 — Spine ↔ company-master carrier alias reconcile (applied)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10599_2026-07-13.md`  
**Operator:** proceed (exact Moonshot recommendation)  
**BUILD_ID:** `hal-10600`

## Verdict applied

Fuzzy alias reconciliation between SoftDent company master (`insurance_company_reference`) and InsCo settlement spine carriers — join existing ledger dollars by identity, do **not** invent payments.

## What shipped

| Piece | Location |
|-------|----------|
| Module | `softdent_carrier_alias.py` |
| Schema | `carrier_alias` (`spine_carrier_name`, `master_company_id`, `match_score`, `confidence` auto\|manual, `review_status`) |
| Fuzzy | `rapidfuzz` Jaro-Winkler + token_set; first-4 / distinctive-token blocking; state + plan-code guards |
| Bands | `>85` auto-accept · `60–85` manual pending (HAL chip) · `<60` reject |
| CLI | `scripts/reconcile_carrier_aliases.py` |
| CSV | `C:\SoftDentFinancialExports\carrier_alias_mapping.csv` |
| Catalog | staff CSV adds `masterCompanyId`, `spineCarrierName`; alias rows `source=alias_spine_settlement` |
| Dependency | `rapidfuzz==3.14.5` in `requirements.txt` |

## Honesty

- No SoftDent write-back  
- No synthetic `insco_ada_probabilistic_estimates` / gold payment lines  
- `no_settlement` stays null $ (empty ≠ $0)  
- Manual band requires HAL `--accept-pending` / `--reject-pending`

## Live result (2026-07-13)

| Metric | Value |
|--------|------:|
| Alias rows | 215 |
| Exact identity | 71 |
| Fuzzy auto-accepted | 36 |
| Auto total | 107 |
| Manual pending (HAL) | 19 |
| Rejected / no candidate | 89 |
| likelyActiveNotInSpineExact | 144 |
| likelyActiveNotInSpine (after accepted aliases) | **108** |
| acceptanceGateMet (≤20) | **false** (89 are true no-spine orphans — not safe to force-match) |
| exactUsableCells | **46** (≥46 gate met; no invented $) |
| Staff no_settlement pad | 27,838 (was 28,653; dropped where aliases attached real spine $) |

**CSV:** `C:\SoftDentFinancialExports\carrier_alias_mapping.csv`  
**Catalog:** `C:\SoftDentFinancialExports\insco_ada_catalog_matrix_2026-07-13.csv`

### Why ≤20 gate is unmet (honesty)

Moonshot warned fuzzy matching can over-match. The remaining **89** likely_active names have no blocked/safe spine partner (Assurant, Bankers, Beauty First, etc.). Accepting the **19** pending manuals would only reach ~89 still above 20, and several pending proposals are dubious (e.g. Guardian Advantage → Aetna Medicare). HAL confirmation: `python scripts/reconcile_carrier_aliases.py --accept-pending "NAME"`.
