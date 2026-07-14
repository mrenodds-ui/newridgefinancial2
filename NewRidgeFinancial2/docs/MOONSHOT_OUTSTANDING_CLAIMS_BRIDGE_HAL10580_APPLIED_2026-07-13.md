# Moonshot Outstanding Claims by Carrier Bridge — APPLIED (HAL-10580)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_SOFTDENT_COMPREHENSIVE_INGEST_HAL_2026-07-13.md`  
**Operator:** proceed  
**Status:** Applied (read-only bridge; no SoftDent write-back; no invented carriers/Ins Plan $)  
**Build stamp:** kept `hal-10576` (package HAL-10580)

## Verdict shipped

SoftDent **Account Aging** AR truth is bridged to **`sd_claims` by payer**. Unnamed “Insurance” payers stay unnamed. Live gap correctly reports payer attribution required + aging insurance `$0` vs pending claims billed (empty ≠ $0).

## Live snapshot (this workstation)

| Metric | Value |
|--------|-------|
| Aging true receivables | **$49,111.03** |
| Aging outstanding insurance | **$0.00** (SoftDent print truth) |
| sd_claims outstanding-ish | **61** (named=1, unnamed=60) |
| Claims billed | **~$7,714** |
| gapCode | `CLAIMS_PAYER_ATTRIBUTION_REQUIRED` |

## What shipped

| Item | Detail |
|------|--------|
| Bridge module | `softdent_outstanding_claims_bridge.py` |
| Aging parse | Account Aging CSV → AR + insurance totals |
| Claims aggregate | by carrier; generic payers → `(unnamed / Insurance)` |
| Reconcile | claims vs aging insurance; honest mismatch when Ins=$0 |
| Schema | optional `total_fee` / `balance` on `sd_claims` (NULL balance ≠ $0) |
| HAL policy | `policy:outstanding-claims-by-carrier` |
| SoftDent widget | Outstanding Claims by Carrier status chip |
| Master reports | `outstanding_claims_by_co` promoted out of phase2_reserved |
| Resolver alias | `resolve_account_transactions_db()` |

## Validation

| Gate | Result |
|------|--------|
| Unit `test_outstanding_claims_bridge_hal10580` | **PASS** |
| HAL “Show outstanding claims by carrier” | **PASS** |
| No invented carriers / Ins Plan $ | **PASS** |

```text
cd NewRidgeFinancial2
python -m unittest test_outstanding_claims_bridge_hal10580 -v
```

## Files

| File | Change |
|------|--------|
| `softdent_outstanding_claims_bridge.py` | NEW |
| `softdent_odbc_extract.py` | claims total_fee/balance columns + ingest |
| `softdent_transaction_extract.py` | `resolve_account_transactions_db` |
| `nr2_hal_gateway.py` | HAL policy |
| `apex_backend.py` | SoftDent widget |
| `softdent_master_reports.json` | promote outstanding_claims_by_co |
| `test_outstanding_claims_bridge_hal10580.py` | NEW |
| `docs/MOONSHOT_SOFTDENT_COMPREHENSIVE_INGEST_HAL_2026-07-13.md` | consult |
| `docs/MOONSHOT_OUTSTANDING_CLAIMS_BRIDGE_HAL10580_APPLIED_2026-07-13.md` | NEW (this file) |

## Not done

- Named-payer ODBC refresh / `sd_patient_insurance` populate (unblock attribution)  
- ERA-835 procurement  
- Phase-2 production_by_provider / deposit slip  
- BUILD_ID bump / commit (await operator)
