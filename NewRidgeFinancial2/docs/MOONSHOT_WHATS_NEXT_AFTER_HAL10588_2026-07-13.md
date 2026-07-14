# Moonshot AI — What's Next After HAL-10588 Gold Pipeline (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10588  
**Prior:** HAL-10588 gold payment pipeline (`b6f561b`)  
**Script:** `scripts/run_moonshot_whats_next_after_hal10588_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
The next package is **OPS-10589 SoftDent Gold CSV Drop Facilitation & Ingest Verification** — operator execution of the Insurance Payment Analysis export playbook paired with lightweight automated verification to unblock live gold payment lines.

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
**Name:** OPS-10589 SoftDent Gold CSV Drop Facilitation & Ingest Verification

**Why now:** HAL-10588 definitively diagnosed `GOLD_CSV_MISSING` as the root cause of zero payment lines—the ETL pipeline is code-complete and tested (fixture ingestion proves `GOLD_OK` state is reachable), yet live data famine persists. The Expert SE consult identified this data famine as the critical compromise making the probabilistic stack a liability rather than asset. No remittance validation, catalog growth, or ERA cross-check can proceed safely without ground truth gold lines flowing first. This is the unblocking prerequisite for all downstream value.

**Effort:** 1–2 hours operator time + 30 minutes light code (automated verification checklist).

**REAL files/ops steps:**
1. **Operator action:** SoftDent menu **Reports → Insurance → Insurance Payment Analysis**
2. **Parameters:** Date range = Last 24 months (or max available), All carriers selected, **Include write-offs = Yes**, Format = **CSV** (Excel often unavailable)
3. **Save to:** `C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv`
4. **Optional but recommended:** Export **Procedure Code Listing** to same directory for cross-reference
5. **Sync:** Execute Sync or trigger `run_gold_payment_pipeline_repair` to initiate ingest
6. **Light code verification (automated checklist):**
   - Verify file exists at expected path
   - Validate CSV headers match expected schema (Carrier, Patient, PaidAmount, WriteOff, ADACode, DatePosted)
   - Confirm row count > 0
   - Monitor ingest completion
   - Query DB to confirm `sd_insurance_payment_lines` incremented from 0

**Validation gate:** `sd_insurance_payment_lines > 0` AND `gapCode == 'GOLD_OK'` AND `newestPaymentCsv` is not null (timestamped file present).

## 2. Why this beats the other candidates now
- **Candidate 2 (Remittance validation):** Blocked until gold or ERA lines exist. Cannot execute without data.
- **Candidate 3 (Empty≠$0 UI audit):** Valuable defensive hygiene, but the system currently correctly surfaces `GOLD_CSV_MISSING` rather than rendering `$0.00`. Resolving the root cause data famine takes precedence over auditing display logic for an empty dataset.
- **Candidate 4 (Async HAL/ASGI):** Performance optimization is premature when the bottleneck is data absence, not inference latency.
- **Candidate 5 (Catalog cell growth):** Expanding the probabilistic surface from 46 cells without ground truth validation increases "liability" per Expert SE warning; deferred until gold validates existing cells.
- **Candidate 6 (ERA835 first-drop):** Inbox contains only manifest files (`manifest_*.json`) with `era835Payments: 0` and `era835: null`; blocked on external file delivery.
- **Candidate 7 (Uncovered CDT playbook):** Adding 47 CDTs to the spine without gold remittance validation compounds unvalidated assumptions; unsafe to expand before validating current 46 exact-usable cells.

## 3. Runner-ups (2–3, why not now)
1. **CODE: Empty≠$0 programmatic UI enforcement audit (HON-001)**
   - *Why not now:* While the Expert SE questioned whether empty≠$0 is programmatically enforced, the current widgets correctly handle the `GOLD_CSV_MISSING` state without rendering false zeros. This audit is defensive maintenance that should follow the unblocking of real data to ensure new gold lines don't introduce null-rendering bugs.

2. **CODE: ERA835 first-drop / payment cross-check**
   - *Why not now:* No ERA files are present in the live inbox (only JSON manifests). Awaiting external payer file delivery; parallel effort to gold CSV but lower priority given SoftDent internal export is immediately available.

3. **CODE: Catalog cell growth / spine reliability**
   - *Why not now:* Growing beyond 46 exact-usable cells requires validation against remittance data to avoid inflating the "unvalidated fallback assumptions" liability identified by Expert SE. Deferred until gold payment lines provide validation substrate.

## 4. What NOT to redo
- SoftDent write-back of any insurance payment data
- Inventing gold lines from ledger spine, DaySheet, or `sd_payments` (empty ≠ $0)
- Re-executing HAL-10580 through HAL-10588 (already shipped, BUILD_ID coupled)
- Re-exporting Ins Plan Register (incorrect data source; not ADA×InsCo payment lines)
- GitHub/PR as the primary delivery mechanism (this is local operational execution)

## 5. Acceptance criteria
- [ ] Physical file `insurance_payments_YYYYMMDD.csv` exists in `C:\SoftDentFinancialExports\` with non-zero byte size
- [ ] CSV contains >0 data rows with required headers: `Carrier`, `Patient`, `PaidAmount`, `WriteOff`, `ADACode`
- [ ] Automated ingest completes: `run_gold_payment_pipeline_repair` exits 0 with log confirmation
- [ ] Database state transitions: `sd_insurance_payment_lines` > 0 (actual count, not NULL)
- [ ] Gap code transition: `GOLD_CSV_MISSING` → `GOLD_OK`
- [ ] Exact usable spine consistency maintained: 46/46 cells still pass validation (no regression)
- [ ] No widget renders null/missing as `$0.00` (empty ≠ $0 preserved)
- [ ] `newestPaymentCsv` field populated with filename and timestamp

## 6. Executive Summary (5 bullets)
- **Data famine is the critical blocker:** HAL-10588 proved the pipeline is ready, but live `paymentLines=0` because the SoftDent Insurance Payment Analysis CSV has not been exported; this OPS step is the sole unlock for all downstream financial validation.
- **OPS-first with light automation:** The package prioritizes operator execution of the documented export playbook, augmented by a lightweight verification script to confirm file presence, schema validity, and successful ingest without manual DB querying.
- **Unblocks first-class validation:** Only after gold lines flow can remittance cross-checks (Candidate 2) and safe catalog expansion (Candidate 5) proceed without creating unvalidated probabilistic liability.
- **Preserves architectural honesty:** Ingesting real payment data maintains the `empty != $0` contract; no synthesis from ledger fallbacks occurs.
- **Additive and local:** Requires no GitHub/PR cycle; executes entirely within existing NR2 infrastructure with immediate feedback via the HAL-10588 gold pipeline audit widget.

## 7. Approval checklist
- [ ] Operator confirms access to SoftDent **Reports → Insurance → Insurance Payment Analysis** menu path
- [ ] Write permissions verified for `C:\SoftDentFinancialExports\` directory
- [ ] Backup/rollback plan acknowledged (retain original CSV until `GOLD_OK` confirmed)
- [ ] Time window scheduled for Sync execution immediately following CSV export
- [ ] Understanding confirmed that this is OPS-heavy (manual SoftDent export) but unblocks all subsequent CODE packages that depend on ground truth data