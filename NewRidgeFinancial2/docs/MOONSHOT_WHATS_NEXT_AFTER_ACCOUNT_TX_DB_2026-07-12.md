# Moonshot AI — What's Next After SoftDent Account-Tx DB (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10569  
**Prior:** Account-tx DB (`4281a50`); TXN ledger surface (hal-10569)  
**Script:** `scripts/run_moonshot_whats_next_after_account_tx_db_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
OPS SoftDent July 2026 Register/Collections export with Ins Plan Collections > 0 — exact SoftDent menu path to unblock the only missing operational input and complete the DEF-001 data pipeline.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** OPS SoftDent July Register/Collections Export (Insurance Plan Collections unblock)  
**Why now:** TXN260201 (Feb 2026) is live in `sd_account_transactions` (1,716 rows), but July 2026 Ins/Patient collections remain OPS-blocked per DEF-001 follow-up. This is the sole barrier to current-month practice truth; the ingest code is already shipped and idempotent.  
**Effort:** Zero code; 15-minute SoftDent operator procedure.  
**REAL files:** None (OPS-only); once exported, file lands in `C:\SoftDentReportExports\` and is consumed by existing `NewRidgeFinancial2/softdent_transaction_extract.py` → `C:\SoftDentFinancialExports\softdent_financial_analytics.db`.  
**Validation gate:** New JSONL appears in `C:\SoftDentFinancialExports\tx_parsed\` with July 2026 dates and non-null `ins_plan_collections`; HAL query returns July rows for active accounts (e.g., Donna 27002 July activity).

## 2. Runner-ups (2–3, why not now)
1. **Browser smoke of ledger + Donna DB path after hard-refresh:** Validating 4281a50 end-to-end is prudent, but smoke-testing February data does not unblock July truth; defer until after July export ingest to test the full pipeline under real current-month load.  
2. **Better Backend Widgets NICE (pareto-chart, tax-calendar, timeline-lanes):** Consult already drafted locally; adds UX density but not missing data; queue after July data is live to avoid building analytics on stale February baseline.  
3. **Join/analytics polish on sd_account_transactions:** Indexes exist; no HAL/widget gap reported yet; wait for July data to stress-test joins and identify actual query bottlenecks before optimizing.

## 3. What NOT to redo
Account-tx DB schema/upsert (4281a50), TXN XLS ingest parser, ledger surface widgets/API (hal-10569), widgets MUST/SHOULD packs (hal-10567/68), DEF-001 Register XLS parser logic, Phase 1–5 190Q, invented SoftDent GUI automation or write-back, $0 coercion.

## 4. Acceptance criteria
- [ ] SoftDent operator exports July 2026 Register/Collections report including **"Insurance Plan Collections"** column with non-zero values.  
- [ ] File saved to `C:\SoftDentReportExports\` (e.g., `Register_Collections_July_2026.xlsx`).  
- [ ] `python scripts/continue_softdent_txn_excel.py --ingest` (or equivalent) parses without schema error, producing JSONL with July 2026 timestamps.  
- [ ] `sd_account_transactions` row count increases by expected July volume (est. 200–500 rows).  
- [ ] Query for July 2026 date range returns rows with `ins_plan_collections IS NOT NULL AND > 0`.

## 5. Executive Summary (5 bullets)
- **Gap:** Code pipeline (DEF-001 + 4281a50) is production-ready, but July 2026 financial truth is trapped in SoftDent due to missing export with Insurance Plan Collections.  
- **Leverage:** Single operational export unlocks current-month A/R visibility and validates the full DB → HAL → widget chain under real July load.  
- **Risk:** None (read-only export); reversibility is simply deleting the July JSONL and re-ingesting.  
- **Effort:** Operator action only; zero dev cycle, no PR, no GitHub.  
- **Next after this:** Run browser smoke test (candidate 5) on July data to confirm ledger render, then proceed to Better Backend Widgets NICE (candidate 1) for pareto/timeline analytics.

## 6. Approval checklist
- [ ] Confirm SoftDent user has rights to Reports > Register/Collections for July 2026.  
- [ ] Confirm target directory `C:\SoftDentReportExports\` is writable and monitored by ingest script.  
- [ ] Verify existing `softdent_transaction_extract.py` handles "Insurance Plan Collections" column header (DEF-001 regression check).  
- [ ] Staging ingestion permitted: validate July export in `softdent_financial_analytics.db` before announcing live to practice.

---

**Exact SoftDent Export Steps (OPS-only):**
1. Open SoftDent → **Reports** → **Financial** → **Register/Collections** (or Management > Register/Collections depending on SoftDent version).  
2. **Date Range:** 07/01/2026 – 07/31/2026.  
3. **Columns:** Ensure **"Insurance Plan Collections"** is checked/enabled (this is the unblock criteria; values must be > 0 for July activity).  
4. **Export:** Click Excel/Export, save as `Register_Collections_July_2026.xlsx` to `C:\SoftDentReportExports\`.  
5. **Trigger:** Run ingest command or wait for auto-poll; verify `C:\SoftDentFinancialExports\tx_parsed\` generates new JSONL with July timestamps.
