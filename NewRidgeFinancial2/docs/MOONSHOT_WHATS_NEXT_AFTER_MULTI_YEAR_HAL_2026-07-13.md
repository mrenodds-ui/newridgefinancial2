# Moonshot AI — What's Next After Multi-Year HAL (CONSULT)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** multi-year HAL shipped (`2906b0e`)  
**Script:** `scripts/run_moonshot_whats_next_after_multi_year_hal_consult.py`  
**Operator:** proceed (after 'any more programming')

## Operator request (verbatim)

> proceed

---

# Verdict  
CODE: Small SoftDent-page transaction-ledger coverage chip in `apex_better_backend_widgets_pack.py` — surfaces the live 549k-row multi-year ledger with honest `empty != $0` metadata.

## 0. Operator Intent (verbatim: proceed)  
proceed

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)  
**Name:** Transaction-Ledger Coverage Chip (Multi-Year HAL)  

**Why now:**  
- The 549,564-row `sd_account_transactions` ledger (1996–2026) is live and HAL-accessible, but invisible to staff in the UI.  
- This is the highest-leverage remaining CODE work: it makes the expensive year-chunk ingest and multi-year HAL wiring immediately discoverable without altering SoftDent or inventing dollars.  
- Additive only: renders coverage metadata (`db_total`, `available_range`) already produced by `nr2_hal_gateway.py`.  

**Effort:** Small (1–2 hrs) — single widget class + binding to existing HAL coverage helper.  

**REAL files:**  
- `NewRidgeFinancial2/apex_better_backend_widgets_pack.py` (append widget class)  
- `NewRidgeFinancial2/nr2_hal_gateway.py` (reuse `account_tx_ledger_coverage()`; already returns `db_total`, `serviceDateMin`, `serviceDateMax`)  

**Validation gate:**  
- Widget renders chip: “549,564 account transactions (1996–2026)”  
- Drill-down hint shows sample query: “Try ‘Show account 27002 transactions in 2018’”  
- Empty account result displays “No transactions” (not “$0”)  

## 2. Runner-ups (2–3, why not now)  
1. **OPS: Concrete payer-portal / clearinghouse 835 acquisition** — Not CODE; external procurement dependency; discovery (10575) proved zero local candidates exist and no automation harness is present in the repo.  
2. **CODE: Deduplicate cross-source account-tx rows** — No evidence of duplicates today; ingest already purged-by-`source_file` (TXN260201 superseded) and DB count matches manifest parity.  
3. **OPS: July Register/Collections with Ins Plan Collections > 0 SoftDent export** — Data missing (ERA_835_REQUIRED gap); requires manual SoftDent export procurement, not local programming.  

## 3. What NOT to redo  
- Year-chunk pull / ingest (already shipped)  
- Multi-year HAL gateway wiring (already shipped)  
- 10575/10576 discovery or Collections Excel-temp reliability (already shipped)  
- Widgets MUST/SHOULD/NICE lists (out of scope)  
- Invent Ins Plan/ERA dollar amounts or SoftDent write-back (forbidden)  

## 4. Acceptance criteria  
- [ ] `apex_better_backend_widgets_pack.py` contains new `AccountTxLedgerCoverageChip` widget class  
- [ ] Chip queries `nr2_hal_gateway.account_tx_ledger_coverage()` and displays real `db_total` (549,564) and date range (1996-02-07 → 2026-07-12)  
- [ ] Empty account queries render “No transactions” — `empty != $0` preserved (no fabricated dollar sums)  
- [ ] No SoftDent write-back attempted; read-only ledger contract maintained  
- [ ] Local validation: widget renders without external API calls (no `liveDiscoverApiError` dependency)  

## 5. Executive Summary (5 bullets)  
- **549,564 transactions** now live in `sd_account_transactions` spanning 1996–2026, queryable via HAL year/span filters.  
- **Visibility gap:** Staff cannot see the ledger coverage in the UI; the database is “dark” despite being wired.  
- **Solution:** Add one coverage chip to the existing widget pack, binding to HAL metadata already produced.  
- **Honesty preserved:** Chip shows row counts and date ranges, never inventing dollar amounts or claiming zero balances for empty accounts.  
- **Strategic value:** Unblocks self-service account history lookups immediately, parallel to any future ERA procurement.  

## 6. Approval checklist  
- [ ] Confirm `NewRidgeFinancial2/apex_better_backend_widgets_pack.py` exists and is writable  
- [ ] Confirm `nr2_hal_gateway.py` exposes `account_tx_ledger_coverage()` with `db_total`, `serviceDateMin`, `serviceDateMax`  
- [ ] Verify widget uses `count(*)` or coverage metadata, never `sum(amount)` for empty accounts  
- [ ] Local dev test: chip renders “549,564 transactions (1996–2026)”  
- [ ] Confirm no GitHub/PR step required; local file edit only
