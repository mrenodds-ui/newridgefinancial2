# Moonshot AI — Collections/Daysheet After Phase 5 GO (CONSULT)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10563 + Phase 5 GO  
**Script:** `scripts/run_moonshot_collections_daysheet_after_phase5_consult.py`  
**Apply:** Operator already said proceed — apply after this consult lands.

## Operator request (verbatim)

> proceed

---

# Verdict

## 0. Operator Intent (proceed after Phase 5 GO)
Operator confirmed Phase 5 GO (190/190, 98.9% quality, 100% read-only, 13.6s avg) and explicitly queued the **Collections/Daysheet export gap → empty revenue-composition** remediation (DEF-001) as the next data package. Intent: Close the data loop so `revenue-composition` and collections vitals populate from SoftDent exports, or remain honestly empty with actionable context (never synthetic $0).

## 1. Recommended NEXT package (name, why now, effort, REAL files, phases)

**Name:** DEF-001 Collections/Daysheet Import Closure — Revenue Composition Data Gap  
**Why now:** Phase 5 safety gates passed; financial console is live but flying blind on collections split. Current period (2026-07) shows `collectionsPending` because the Register export (production) is present but the Collections/Daysheet export (insurance/patient split) is absent. Without this export, `revenue-composition` renders empty and vitals show "pending" tombstone, degrading trust in financial accuracy.  
**Effort:** Small–Medium (4–6 hours) — 1 hour ops export, 2–3 hours parser/widget hardening, 1 hour validation.  
**REAL files:**  
- `NewRidgeFinancial2/softdent_practice_exports.py` — add Collections/Daysheet filename pattern recognition (e.g., `*Collections*Daysheet*.csv`, `*COL*.csv`) to `SOFTDENT_EXPORT_PATTERNS`  
- `NewRidgeFinancial2/import_direct_pipeline.py` — extend `SoftDentImportParser` to handle Collections/Daysheet schema (Invoice #, Patient, Insurance Paid, Patient Paid, Adjustment, Date)  
- `NewRidgeFinancial2/import_loader.py` — map Collections dataset key `collections_daysheet_YYYYMM` to `Sync` bundle  
- `NewRidgeFinancial2/apex_financial_console_pack.py` — `revenue_composition_widget()` logic: check `collections_daysheet_{period}` existence; if missing, render empty strip with HAL hint; if present, compute insurance/patient mix  
- `NewRidgeFinancial2/apex_backend.py` — `get_collections_vitals()` — validate dataset presence before aggregation; return `{"status": "pending", "hint": "Export SoftDent Collections/Daysheet for {period}"}` when absent  
- `NewRidgeFinancial2/nr2_hal_gateway.py` — sync hint: if user asks "Why is revenue composition empty?" HAL responds with exact export path `C:\SoftDentReportExports` and filename pattern, not fabricated dollars  

**Phases:**  
1. **Ops Export** (immediate): Generate SoftDent Collections/Daysheet for current period (2026-07) to inbox  
2. **Parser Hardening** (code): Recognize and ingest the export even if headers vary slightly (case-insensitive column map)  
3. **Widget Integrity** (code): Honest empty state vs. populated split validation  
4. **Acceptance** (validation): Confirm `revenue-composition` renders payer mix OR "Awaiting Collections export" with specific remedy  

## 2. Ops checklist (exact export steps)

**Prerequisite:** SoftDent Practice Management open with administrative rights  
**Target period:** 2026-07 (or current closed period)  
**Destination:** `C:\SoftDentReportExports\` (verified writable by NR2 Sync service)  

**Step-by-step:**  
1. **SoftDent Menu:** Reports → Financial → Collections/Daysheet (or Daysheet/Collections Register — *not* the standard Register Report)  
2. **Date Range:** From: `07/01/2026` To: `07/31/2026` (match current production period)  
3. **Format:** Export to CSV (comma-delimited) — **not** PDF or Excel binary  
4. **Filename pattern:** Include "Collections" and period, e.g., `SoftDent_Collections_202607.csv` or `COL_202607_Daysheet.csv`  
5. **Save to:** `C:\SoftDentReportExports\`  
6. **Verify:** File appears in `C:\SoftDentReportExports\` with timestamp within last 5 minutes  
7. **Trigger Sync:** NR2 Dashboard → Settings → Import & Sync → "Run SoftDent Import Now" (or wait for next 15-min cycle)  
8. **Validation:** Check `IMPORT_HEALTH_*` log for `collections_daysheet_202607` dataset key registration  

**Alternative path (if UI export unavailable):**  
- SoftDent Reports → Register → Collections Register → Export CSV → rename to include "Collections" and move to `C:\SoftDentReportExports\`  

## 3. Code changes (if any) with validation gate

**A. Filename Pattern Recognition (`softdent_practice_exports.py`)**  
```python
# Add to SOFTDENT_EXPORT_PATTERNS
COLLECTIONS_DAYSHEET_PATTERNS = [
    r'(?i).*collections.*daysheet.*\.csv$',
    r'(?i).*col.*\d{6}.*\.csv$',
    r'(?i).*daysheet.*\d{4}[-_]?\d{2}.*\.csv$'
]
```
**Validation gate:** `pytest test_softdent_exports.py -k collections` passes with sample `SoftDent_Collections_202607.csv`

**B. Parser Schema (`import_direct_pipeline.py`)**  
- Column map (case-insensitive): `Invoice#` → `invoice_id`, `InsPaid`/`Insurance Paid` → `insurance_paid`, `PatPaid`/`Patient Paid` → `patient_paid`, `Adjust`/`Adjustment` → `adjustment`  
- Skip rows where all monetary fields are null/empty (header separators)  
- Aggregate by period key `collections_daysheet_YYYYMM`  

**Validation gate:** Unit test parses sample Collections CSV with mixed-case headers and produces `{"insurance_total": X, "patient_total": Y}` without hardcoding dollars.

**C. Dataset Key Registration (`import_loader.py`)**  
- On successful parse, register dataset key: `collections_daysheet_{period}` (e.g., `collections_daysheet_202607`)  
- Metadata: `source_file`, `row_count`, `period_start`, `period_end`  

**D. Widget Empty-State Logic (`apex_financial_console_pack.py`)**  
```python
def revenue_composition_widget(period):
    ds = get_dataset(f'collections_daysheet_{period}')
    if not ds:
        return {
            "widget": "revenue-composition",
            "status": "empty",
            "hint": f"Collections/Daysheet export missing for {period}. Export from SoftDent to C:\\SoftDentReportExports\\, then Sync.",
            "values": None  # Honest empty, not $0
        }
    # Compute split...
```
**Validation gate:** UI shows grey "Awaiting Collections export" strip with exact path hint when file missing; shows Insurance/Patient bars when present.

**E. HAL Sync Hint (`nr2_hal_gateway.py` system prompt addition)**  
- If `collectionsPending=true` detected in context, HAL must state: *"Revenue composition is empty because the SoftDent Collections/Daysheet export for [period] is not yet in C:\SoftDentReportExports. Please export the Collections/Daysheet report from SoftDent and run Sync."*  
- **Prohibited:** Inventing dollar amounts (e.g., "Insurance paid $12,345") when dataset absent.

## 4. What NOT to do

- **NO Synthetic Dollars:** Do not fabricate insurance/patient split amounts if the export is missing. Empty means "data not yet available," not zero revenue.  
- **NO SoftDent Write-Back:** Do not POST adjustments or payments back to SoftDent; this is read-only analytics.  
- **NO Hardcoded Periods:** Do not embed "2026-07" in code; derive from system date or latest Register export period.  
- **NO SQL Injection of Data:** Do not manually INSERT collection rows into local SQLite to "fill the gap" — only ingest from official exports.  
- **NO Treating Empty as $0:** Vitals must display "pending" or "—", not "$0.00", when Collections export absent.  

## 5. Acceptance criteria

| Check | Method |
|-------|--------|
| Ops export present | File `*Collections*202607*.csv` exists in `C:\SoftDentReportExports\` |
| Dataset registered | `IMPORT_HEALTH_*` log shows `collections_daysheet_202607` with non-zero row count |
| Parser integrity | Unit test passes: parser handles CSV with extra columns or swapped column order without crash |
| Widget populate | Financial console `revenue-composition` displays Insurance vs. Patient bars with real percentages when data present |
| Honest empty | If export removed (test scenario), widget shows "Awaiting Collections export" hint with exact path; HAL explains gap without inventing dollars |
| No regression | Phase 5 safety metrics maintained (read-only 100%, quality ≥85%) |

## 6. Approval checklist

- [ ] Operator confirms SoftDent access to run Collections/Daysheet report for 2026-07  
- [ ] `C:\SoftDentReportExports\` path writable and monitored by NR2 Sync service  
- [ ] Code review scheduled for `softdent_practice_exports.py` pattern additions (avoid over-broad globs)  
- [ ] Backup taken of `apex_financial_console_pack.py` before widget logic change  
- [ ] Staging validation plan: temporarily rename Collections file → confirm empty state → restore file → confirm populate  
- [ ] Operator explicitly approves with "proceed" or "apply DEF-001" to trigger implementation phase (currently CONSULT ONLY)