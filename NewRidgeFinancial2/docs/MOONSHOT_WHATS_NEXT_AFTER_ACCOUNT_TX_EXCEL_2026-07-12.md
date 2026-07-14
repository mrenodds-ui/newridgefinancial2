# Moonshot AI — What's Next After SoftDent Account-Tx Excel + HAL Teach (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10567  
**Prior:** SoftDent Trans Excel validated + HAL playbook (c4d2331); Better Backend Widgets MUST (hal-10567)  
**Script:** `scripts/run_moonshot_whats_next_after_account_tx_excel_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next program

---

# Verdict
Build the TXN Excel parser to ingest the validated account-transactions export (TXN260201.xls) into SoftDent analytics and HAL patient-ledger tools, enabling Donna-style account queries without SoftDent GUI dependency.

## 0. Operator Intent (verbatim: next program)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)

**Name:** Ingest/parse TXN*.xls into SoftDent analytics / HAL patient-ledger tools

**Why now:**  
- TXN260201.xls exists and is live-validated (1736 rows, Donna Nickel 27002 present, 8 lines confirmed).  
- The July collections gap (DEF-001) remains blocked pending OPS export with Ins/Patient split; meanwhile the account-transactions export path is proven but the data is unused.  
- Parsing this file immediately unlocks HAL patient-ledger capabilities (Donna-style account tx query) and provides a validated parser ready for July data when it arrives.  
- Zero GUI automation required (avoiding the blocked SoftDent session issue from hal-10566).  
- Builds additively on the just-shipped validation docs and HAL teach.

**Effort:** Low (single parser module + HAL integration; no GUI automation).

**REAL files:**
- `NewRidgeFinancial2/softdent_transaction_extract.py` (extend with XLS parser)
- `scripts/continue_softdent_txn_excel.py` (orchestration/CLI)
- `C:\SoftDentReportExports\TXN260201.xls` (source data)
- `NewRidgeFinancial2/nr2_hal_gateway.py` (HAL reply wiring)

**Validation gate:**  
- Parsed row count == 1736 (matches TXN260201.xls).  
- Donna Nickel (27002) line count == 8 (matches validation JSON).  
- HAL can answer "What are Donna Nickel's February 2026 transactions?" using parsed data, not live SoftDent query.  
- Empty/null amounts preserved (never cast to $0).

## 2. Runner-ups (2–3, why not now)

1. **Wire Trans-for-Period Excel auto-save** (`softdent_gui_export.export_transactions_for_period`): Automates the SaveCopyAs step from temp SDWIN*.csv. *Not now* because SoftDent GUI automation is currently blocked/unreliable (per hal-10566 OPS attempt notes), and we should consume the existing validated file before optimizing the export pipeline.

2. **OPS SoftDent July Register/Collections Export (Ins-Patient Split)**: Requires staff to export July 2026 Register with Ins Plan > 0. *Not now* because this is an OPS handoff, not a code package, and the GUI session remains blocked; code should proceed with available data (TXN260201.xls) while OPS resolves the export separately.

3. **Better Backend Widgets SHOULD follow-ups**: Additional tax tables or KPI density. *Not now* because MUST widgets just shipped (hal-10567) and the backend gap is data availability (collections null), not presentation.

## 3. What NOT to redo

- Account-tx Excel validation docs (already shipped in c4d2331 / a008f1c).  
- HAL teach for SoftDent sign-on/export paths (already shipped).  
- SoftDent write-back or invented dollar amounts (strict honesty: empty ≠ $0).  
- Phase 1–5 190Q, DEF-001 honesty gates, Register XLS parser (already applied).  
- GitHub/PR as the primary artifact (keep it local/additive).

## 4. Acceptance criteria

- [ ] `softdent_transaction_extract.py` grows `parse_account_transactions_xls(path)` returning typed records (date, account_num, patient_name, provider, procedure, amount, note_flag).  
- [ ] Parser handles both .xls (xlrd) and .xlsx (openpyxl) via existing validation logic.  
- [ ] `scripts/continue_softdent_txn_excel.py` can ingest `C:\SoftDentReportExports\TXN260201.xls` and emit JSONL to `C:\SoftDentFinancialExports\tx_parsed\`.  
- [ ] HAL gateway exposes `query_account_transactions(account_num=None, patient_name=None, date_range=None)` using parsed data, falling back to "data not yet exported" if file missing.  
- [ ] Validation: row count 1736, Donna Nickel mentions 8, zero invented dollars.  
- [ ] No SoftDent GUI automation in this package (read-only file parse only).

## 5. Executive Summary (5 bullets)

- **Leverage existing asset:** TXN260201.xls is live, validated, and unused; parsing it provides immediate analytics without waiting for GUI unblocking.  
- **Unblock HAL queries:** Enables Donna-style patient-ledger replies (account 27002, etc.) without querying SoftDent live database or GUI.  
- **Preserve honesty:** Parser respects empty/void amounts (null), never coercing to $0, and never writes back to SoftDent.  
- **Prepare for July:** Once OPS exports July transactions, the same parser ingests them instantly—no new code required.  
- **Additive only:** Extends `softdent_transaction_extract.py` and HAL gateway locally; no PR dependency, no Phase regression risk.

## 6. Approval checklist

- [ ] Operator confirms TXN260201.xls path is stable (`C:\SoftDentReportExports\`).  
- [ ] Confirm no SoftDent write-back requirement (read-only parse).  
- [ ] Confirm priority: analytics/ingestion > GUI automation (given blocked state).  
- [ ] Verify `softdent_transaction_extract.py` is the correct extension point (not new file).  
- [ ] HAL reply format approved for account-transaction queries (Donna Nickel test case).
