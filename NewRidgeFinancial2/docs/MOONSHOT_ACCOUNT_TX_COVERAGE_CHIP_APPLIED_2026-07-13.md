# Moonshot Account-TX Coverage Chip — APPLIED

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_MULTI_YEAR_HAL_2026-07-13.md`  
**Operator:** proceed (after “any more programming”)  
**Status:** Applied (UI coverage chip; counts/dates only; empty ≠ $0; no SoftDent write-back)

## Verdict shipped

SoftDent / Office Manager **Account TX Ledger Coverage** status chip showing live multi-year ledger size and date span, plus SQL `LIMIT` so unfiltered ledger widgets do not scan 549k rows.

## What shipped

| Item | Detail |
|------|--------|
| Coverage chip | `build_account_tx_ledger_coverage_chip` → `type: status` |
| SoftDent page | Chip + ledger table |
| Office Manager | Chip + ledger table |
| SQL limit | `_query_account_transactions_db` filters + `LIMIT` in SQL |
| Honesty | Message is row counts / years only — no `$` rollups; empty = “No transactions found” |

## Live validation

| Gate | Result |
|------|--------|
| Chip message | `549,564 account transactions (1996–2026) · multi-year ledger live` |
| Hint | HAL sample: “Show account 27002 transactions in 2018” |
| Empty filter | “No transactions found” (not `$0`) |
| Unit tests | **15/15 PASS** |

## Files

| File | Change |
|------|--------|
| `apex_better_backend_widgets_pack.py` | coverage chip + ledger coverage fields |
| `apex_backend.py` | wire chip on softdent + office-manager |
| `softdent_transaction_extract.py` | SQL date filter + LIMIT |
| `test_account_tx_coverage_chip.py` | NEW |
| `scripts/run_moonshot_whats_next_after_multi_year_hal_consult.py` | consult |
| `docs/MOONSHOT_WHATS_NEXT_AFTER_MULTI_YEAR_HAL_2026-07-13.md` | consult |

## Not done

- ERA / Ins Plan Collections procurement  
- BUILD_ID bump  
- SoftDent write-back / invented dollars  
