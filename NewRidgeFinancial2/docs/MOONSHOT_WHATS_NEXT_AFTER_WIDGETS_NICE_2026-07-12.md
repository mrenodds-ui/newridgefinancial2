# Moonshot AI — What's Next After Widgets NICE (hal-10570)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build:** hal-10570  
**Prior:** Widgets NICE (88fd003); TXN ledger (hal-10569)  
**Script:** `scripts/run_moonshot_whats_next_after_widgets_nice_consult.py`  
**Operator:** next  
**Apply:** DO NOT APPLY until operator validates.

## Operator request (verbatim)

> next

---

# Verdict
OPS SoftDent July Register/Collections with Ins Plan Collections > 0 — exact export steps to unblock month-end practice truth (DEF-001 ingest ready; data missing).

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** OPS SoftDent July Register/Collections (Ins Plan Collections > 0)  
**Why now:**  
- Month-end reconciliation blocked on insurance collections truth; current `REG202607.XLS` (28 KB) and converted CSV (945 bytes) indicate empty or incomplete Ins Plan Collections column.  
- DEF-001 Register XLS ingest code already deployed (hal-10566); only missing input is the correct SoftDent export with Ins Plan Collections > 0.  
- Highest ROI: 15-minute operator action unblocks AR aging reconciliation vs. days of dev work.  

**Effort:** 15 minutes (SoftDent GUI export). Zero code changes.  

**REAL files:**  
- `C:\SoftDentReportExports\REG202607.XLS` (overwrite)  
- `C:\SoftDentReportExports\register_for_period_2026-07-01_2026-07-31.xls` (alternative naming)  
- `C:\SoftDentFinancialExports\tx_parsed\` (verify DEF-001 ingest picks up new register)  

**Validation gate:**  
1. Export file size > 100 KB (indicates populated collections rows).  
2. CSV conversion contains column `Ins Plan Collections` with non-zero values.  
3. HAL query *"What are July 2026 insurance collections?"* returns specific dollar amounts (not `emptyState`).  

**Exact SoftDent export steps:**  
1. SoftDent → **Reports** → **Register** → **Register for Period**.  
2. Date range: **2026-07-01** to **2026-07-31** (or MTD through current date).  
3. **Do not** filter provider; leave as "All".  
4. **Columns to include:** Ensure **Insurance Plan Collections** checkbox is **enabled** (critical; previously unchecked causing $0 export).  
5. **Export format:** Excel 97-2003 (`.xls`) to `C:\SoftDentReportExports\`.  
6. Filename: `REG202607.XLS` or `register_for_period_2026-07-01_2026-07-31.xls`.  
7. Run `python scripts/continue_softdent_txn_excel.py --ingest` (validates DEF-001 parse).  

## 2. Runner-ups (2–3, why not now)
1. **Wire SoftDent account-tx SQLite into Apex/HAL**  
   - JSONL (547 KB) is functional; SQLite wiring is performance polish, not a month-end blocker. Defer until after July collections validated.  
2. **Browser smoke / hard-refresh validation**  
   - QA hygiene, not a data unblocker. Perform after OPS export confirms widget renders new register data.  
3. **Trans-for-Period Excel auto-save**  
   - No evidence of existing auto-save scripts in snapshot; risk of inventing GUI automation. Defer until OPS export proven.  

## 3. What NOT to redo
- Better Backend Widgets MUST/SHOULD/NICE (hal-10567..10570).  
- TXN XLS ingest + HAL ledger (hal-10569/9cbf8c7).  
- DEF-001 Register XLS ingest logic (parsing code already exists; only data missing).  
- SoftDent GUI bots or write-back (prohibited).  

## 4. Acceptance criteria
- [ ] `REG202607.XLS` (or equivalent) contains **> 0 rows** with `Ins Plan Collections` > $0.  
- [ ] File size indicates data payload (minimum 50 KB; current 28 KB suspect).  
- [ ] HAL gateway query for July 2026 collections returns numeric totals (not null/empty).  
- [ ] No code changes required; pure operational export.  

## 5. Executive Summary (5 bullets)
- **Month-end blocked:** July insurance collections data missing from current register exports (likely unchecked column in SoftDent).  
- **Code ready:** DEF-001 Register XLS ingest awaits data; no dev cycle needed.  
- **Action required:** Operator export with "Insurance Plan Collections" column enabled.  
- **Validation:** File size growth + HAL query confirmation proves success.  
- **Risk:** If export is correct but HAL still shows empty, escalate to SQLite wiring (candidate #2).  

## 6. Approval checklist
- [ ] Operator confirms SoftDent access to Reports → Register.  
- [ ] Date range set: 2026-07-01 through 2026-07-31.  
- [ ] "Insurance Plan Collections" column explicitly selected in export dialog.  
- [ ] Export saved to `C:\SoftDentReportExports\` (overwrite existing small files).  
- [ ] Post-export: verify HAL query returns non-zero collections.