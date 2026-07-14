# Moonshot AI — What's Next After Register XLS Ingest (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10566 + Phase 5 GO  
**Prior:** Register XLS ingest (`3027939`); period sync ingest (`b018d0d`); DEF-001; Phase 5 GO  
**Script:** `scripts/run_moonshot_whats_next_after_register_xls_10566_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
OPS SoftDent July 2026 Register/Collections Export (Ins-Patient Split) — staff must export 07/01/2026–today with Ins Plan > 0 to C:\SoftDentReportExports to unblock hal-10566 ingestion.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)

**Name:** OPS SoftDent July 2026 Register/Collections Export (Ins-Patient Split)

**Why now:** Hal-10566 XLS/CSV ingestion is live and validated, but the inbox only contains June content (`RegisterForPeriodReportFor07012026.xls` body = 2026-06, Ins Plan $0). July production ($45.6k) is confirmed in the dashboard, yet collections attribution is blocked by missing Ins/Patient split data. Code cannot invent dollars; the only blocker is the physical export file. This is pure OPS handoff with zero dev latency.

**Effort:** Staff minutes (SoftDent GUI navigation); zero code changes.

**REAL files:**
- `C:\SoftDentReportExports` (destination directory)

**Validation gate:**
- Inbox scan detects new file with periodHint = 2026-07 and `insurance > 0` or `patient > 0`
- `coversOpenMonth` flips to `true`
- Dashboard 2026-07 row populates `insurance` and `patient` columns (non-zero)
- `collectionsFormatRequired` clears for 2026-07

## 2. Runner-ups (2–3, why not now)

1. **Browser smoke of density/cache/DEF-001 after hard-refresh** — Why not now: Phase 5 190Q GO achieved 100% success with 98.4% quality and 0% CoT leak; dashboard data gap (collectionsPending) is higher ROI than UI polish while financial data is incomplete.

2. **SoftDent launch/automation assist for export** — Why not now: Prior OPS attempt confirmed `softdent_export_command` is empty and automation `enabled:false`. No real vendor CLI or GUI bot scripts exist in the repository; building fictional write-back automation violates DEF-001 honesty gates.

3. **HAL latency / read-only polish** — Why not now: Phase 5 latency (14.1s) is within the ≤15s target; 100% read-only OK score achieved. Collections data completeness takes precedence over marginal latency gains.

## 3. What NOT to redo

- DEF-001 honesty gates (shipped c645460)
- Period-sync ingestion (shipped b018d0d)
- Register XLS ingest (shipped hal-10566 3027939)
- SoftDentImportParser fiction (do not invent)
- SoftDent write-back or GUI bots (do not invent)
- Invent dollars or patient=collections allocations
- Phase 1–5 190Q (GO achieved)
- KPI density/cache coherence (Phase 5 clean)
- WHY-ERRORS timeout (shipped)
- CARC Phase 4 (complete)

## 4. Acceptance criteria

- [ ] SoftDent GUI launched and authenticated
- [ ] Reports → Accounting → **Register for a Period** OR **Collections** selected
- [ ] Date range set to **07/01/2026 – today** (or 07/31/2026)
- [ ] Export format: **CSV** (preferred) or **XLS/XLSX** (hal-10566 capable)
- [ ] File saved to `C:\SoftDentReportExports\`
- [ ] Content validation: Ins Plan Collections > $0.00 and Patient Collections > $0.00
- [ ] HAL Refresh SoftDent period executed (or auto-scan within 5 min)
- [ ] Inbox classify shows `classifiedPeriods` includes "2026-07" and `coversOpenMonth: true`
- [ ] Dashboard 2026-07 row: `collections` > 0, `insurance` > 0, `patient` > 0, `collectionsFormatRequired: null`

## 5. Executive Summary (5 bullets)

- **Hal-10566 XLS parser is live:** Successfully ingested June Register XLS with content-period detection and $0 honesty gates; ready for July data in CSV or XLS format.
- **July financial gap confirmed:** Production ($45,684.25) is live in dashboard, but Collections split (Ins/Patient) is absent because no July-period export exists with positive Ins Plan values.
- **Existing file is June content:** `RegisterForPeriodReportFor07012026.xls` body contains 2026-06 data with Ins Plan $0.00; parsing it cannot populate July dollars.
- **Zero code required:** Ingestion pipeline is complete; only missing input is the SoftDent GUI export for date range 07/01/2026–today with Ins Plan Collections > 0.
- **Unblocks DEF-001 closure:** Once exported, hal-10566 ingestion will auto-populate the 2026-07 dashboard row, clearing `collectionsExportRequired` and `collectionsFormatRequired` gaps.

## 6. Approval checklist

- [ ] Operator acknowledges this is **OPS-only** (no code package)
- [ ] SoftDent workstation accessible and `SDWIN.EXE` launchable
- [ ] Staff credentials available for Reports → Accounting menu
- [ ] Export destination `C:\SoftDentReportExports` confirmed writable (not read-only)
- [ ] HAL refresh procedure documented for post-export step
- [ ] Rollback plan: If export fails, re-attempt with CSV format (hal-10566 compatible)