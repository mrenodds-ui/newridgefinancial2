# HAL-10604 — Moonshot industry HIGH carrier aliases (applied)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_REJECTED_CARRIER_ALIAS_COMPLETE_2026-07-13.md`  
**Operator:** proceed (HIGH only; MEDIUM → pending)  
**BUILD_ID:** `hal-10604`

## Verdict applied

Accept Moonshot **HIGH** industry-identity aliases (7). Keep Coventry **MEDIUM** as `pending` (not auto-resolved). Leave **77** NONE rejected.

## What shipped

| Piece | Detail |
|-------|--------|
| HIGH accepted (7) | Assurant→SUN LIFE FINANCIAL; Connecticut General→CIGNA DENTAL; Met Life (+2 variants)→METLIFE DENTAL; UniCare (+entity)→ANTHEM - 1115 |
| MEDIUM pending (2) | Coventry / Coventry Health Care Of Kansas → AETNA (`moonshot_industry_medium`) |
| Still rejected | 77 (TPA/ASO, employers, niche, ambiguous) |
| Helper | `apply_moonshot_industry_aliases()` + constants in `softdent_carrier_alias.py` |
| TP resolve | Accepted manuals (any confidence) resolve; pending still blocked |
| Tests | `test_hal10604_moonshot_industry_alias.py` |
| Excel | `C:\SoftDentFinancialExports\carrier_alias_mapping.xlsx` |

## Live probes (2026-07-13)

| Probe | Result |
|-------|--------|
| Assurant × D2391 | `viaAlias` → SUN LIFE FINANCIAL; no publishable D2391 cell (empty ≠ $0) |
| Met Life × D2391 | `viaAlias` · sufficient · `ledger_episode_5yr_via_alias` → METLIFE DENTAL |
| Connecticut General × D2391 | `viaAlias` · sufficient → CIGNA DENTAL |
| UniCare × D0220 | `viaAlias` → ANTHEM - 1115; insufficient n=3 (honest) |
| Coventry × D2391 | `blockedPending` · source `carrier_alias_pending` · null $ |
| Aetna Healthcare × D2391 | still `viaAlias` → AETNA (regression check) |

## Status after apply

Accepted **136** (107 auto + prior manuals + 7 industry) · Pending **2** · Rejected **77** · total **215**

## Honesty

empty ≠ $0 · no SoftDent write-back · no invented gold · MEDIUM not blindly accepted · force token_set unblock remains reverted
