# Moonshot AI — What's Next After TXN XLS Ingest + Widgets SHOULD

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build:** hal-10568  
**Prior:** SoftDent TXN XLS ingest (9cbf8c7); Widgets SHOULD (hal-10568)  
**Script:** `scripts/run_moonshot_whats_next_after_txn_xls_ingest_consult.py`  
**Operator:** continue  
**Apply:** DO NOT APPLY until operator validates.

## Operator request (verbatim)

> conti ue

---

# Verdict
Surface the validated TXN260201.jsonl ledger into Apex SoftDent and Office Manager widgets as a read-only transaction table with honest-empty states, closing the visibility gap on 1736 parsed rows without waiting for OPS-blocked July exports.

## 0. Operator Intent (verbatim continue)
`conti ue`

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** TXN Ledger Surface to Apex Widgets (SoftDent/OM)  
**Why now:** TXN260201.jsonl (548KB, 1,736 rows) is parsed and HAL-validated (Donna Nickel 27002 test passes) but remains "dark" to the frontend. Surfacing it unblocks immediate practice truth (account ledgers, provider splits, note flags) using existing data assets rather than waiting for the OPS-blocked July Register export with Ins>0. This is additive only—read-only display of existing JSONL.  
**Effort:** Medium (2–3 files, no GUI automation).  
**REAL files:**  
- `NewRidgeFinancial2/apex_better_backend_widgets_pack.py` — add `transaction-ledger-table` builder emitting `data-table` spec  
- `NewRidgeFinancial2/apex_backend.py` — wire `/api/softdent/ledger` endpoint; BUILD_ID **hal-10569**  
- `NewRidgeFinancial2/nr2_hal_gateway.py` — expose `query_account_transactions` to widget layer (reuse existing HAL policy)  
- `NewRidgeFinancial2/softdent_transaction_extract.py` — add `load_txn_jsonl()` helper to stream `C:\SoftDentFinancialExports\tx_parsed\TXN260201.jsonl`  
**Validation gate:**  
- Widget query `account_num=27002` returns 5 Donna Nickel rows (2026-02-18, etc.) matching TXN260201.xls validation  
- Unknown account returns `emptyState: true` with message "No transactions found" (cells with null money values render empty, never $0)  
- No SoftDent GUI automation or write-back triggered  

## 2. Runner-ups (2–3, why not now)
- **OPS SoftDent July Register/Collections (#2):** Deferred because "July Ins/Patient still OPS-blocked" (per DEF-001 status). The Register XLS ingest code shipped in hal-10566; the only missing input is the export with Ins Plan Collections > 0. Resume this OPS track once `C:\SoftDentReportExports` contains a July register XLS with non-zero insurance columns.  
- **Better Backend Widgets NICE (#1):** Pareto-chart, tax-calendar, and timeline-lanes are analytical polish. Lower priority than surfacing the 548KB of existing transaction truth already validated in the JSONL.  
- **Wire Trans-for-Period Excel auto-save (#3):** No evidence of existing auto-save scripts in real paths; risk of inventing GUI automation. Avoid until `softdent_gui_export.py` contains proven Excel COM hooks.  

## 3. What NOT to redo
TXN XLS ingest (shipped 9cbf8c7), widgets MUST/SHOULD (shipped hal-10567/10568), DEF-001 Register XLS ingest (shipped hal-10566), Register XLS ingest rewrites, Phase 1–5 190Q, KPI density refactors, cache coherence fixes, SoftDent write-back/GUI bots, or inventing fictional file trees outside the listed real paths.

## 4. Acceptance criteria
- [ ] Widget type `transaction-ledger-table` appears in `softdent` and `office-manager` page specs emitted by `apex_backend.py`  
- [ ] Data source remains `C:\SoftDentFinancialExports\tx_parsed\TXN260201.jsonl` (read-only, no copy/duplication)  
- [ ] Supports filtering by `account_num` (exact) and `patient_name` (substring); date range optional  
- [ ] Empty result sets render `emptyState: true` with honest nulls for money cells (never fabricates $0.00)  
- [ ] Donna Nickel (27002) query returns 5 rows matching prior validation; HAL phrase "Donna Nickel February 2026 transactions" returns consistent results via widget endpoint  
- [ ] No SoftDent GUI automation, Excel COM write-back, or file system writes to `C:\SoftDentReportExports`  
- [ ] Backend BUILD_ID increments to **hal-10569**; cache-bust query param updated in `site/apex-core.js` if applicable  

## 5. Executive Summary (5 bullets)
- **Data asset ready:** TXN260201.jsonl (548KB) is parsed, typed, and HAL-validated but currently invisible to practice staff.  
- **OPS-independent:** Proceeds without waiting for the July Register export that is blocked on Ins/Patient > 0 data availability.  
- **Honest empty states:** Widget respects DEF-001—null money cells stay empty; no zero-dollar invention.  
- **Additive closure:** Extends hal-10568 widget infrastructure (patient-dossier, action-list) with real ledger content rather than placeholder KPIs.  
- **Zero write-back:** Read-only surface of existing JSONL; no SoftDent GUI automation or mutation risk.

## 6. Approval checklist
- [ ] Operator confirms proceed with TXN ledger surface (vs. waiting for July Register OPS resolution)  
- [ ] Confirm `C:\SoftDentFinancialExports\tx_parsed\TXN260201.jsonl` remains available at that path  
- [ ] Confirm acceptable to increment BUILD_ID to hal-10569  
- [ ] Confirm no requirement for GitHub/PR workflow (local package only)