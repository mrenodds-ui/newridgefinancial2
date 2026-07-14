# Moonshot AI — Comprehensive SoftDent Ingestion for HAL Reports (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** Production max-merge honesty (`15099e8` / hal-10579)  
**Script:** `scripts/run_moonshot_softdent_comprehensive_ingest_hal_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot ai about a comprehensive ingestion of all data from softdent so that HAL can give a comprehensive report

---

# Verdict
Implement **HAL-10580: Outstanding Claims by Carrier Bridge** to complete the accounts-receivable drill-down layer, enabling payer-attributed outstanding claims that reconcile to period-close AR aging while ERA-835 procurement proceeds in parallel.

## 0. Operator Intent (verbatim)
ask moonshot ai about a comprehensive ingestion of all data from softdent so that HAL can give a comprehensive report

## 1. Can HAL already give a "comprehensive" SoftDent report? (honest yes/partial/no + why)
**No — partial only.**  
HAL possesses period-close financial truth (Register/Daysheet Excel) and operational granularity (ODBC `sd_*` tables), but the **reconciliation layer** between dollars and detail is incomplete. Specifically:  
- **Insurance collections** are blocked (ERA-835 procurement required; Register correctly shows Ins Plan $0).  
- **Outstanding claims** lack payer attribution (Daysheet-derived claims have no payer without `sd_claims` join).  
- **Account ledger** has a live ImportError blocking the 549k-row resolver.  
- **Provider production & ADA-code drill-down** remain in Phase 2 reserved catalog, unwired.  

Until the claims-to-payer bridge is built and the ledger resolver repaired, HAL cannot produce a comprehensive practice report that ties period-close AR to actionable claim-level workflows.

## 2. Target architecture for comprehensive SoftDent → HAL report
**Layer 1: Period-Close Financial Truth (Immutable)**  
Source: `C:\SoftDentReportExports` Register/Daysheet Excel  
Purpose: Production, Collections (Patient vs. Insurance), AR Aging totals.  
Doctrine: Desktop Excel is source of truth; never overridden by ODBC aggregates.

**Layer 2: Operational Detail (Line-item)**  
Source: ODBC `sd_*` (patients, appointments, procedures, claims, payments, adjustments, patient_insurance)  
Purpose: Scheduling, dossier, clinical activity, carrier demographics.

**Layer 3: Insurance Remittance (Collections Detail)**  
Source: ERA-835 files (when procured) → `app_data/nr2/document_inbox/softdent/era`  
Purpose: Insurance collections breakdown, denial coding, auto-posting candidates.

**Layer 4: Reconciliation & Drill-down (Join Layer)**  
Source: Joins between Layer 1 totals and Layer 2/3 line items  
Purpose: Outstanding claims by carrier, production by provider, collection reconciliation, deposit slip validation.

## 3. Gap matrix (domain | status live/partial/missing | source lane | HAL report use)

| Domain | Status | Source Lane | HAL Report Use |
|--------|--------|-------------|----------------|
| **Period-Close $ (Production/Collections)** | Partial | Desktop Excel (`C:\SoftDentReportExports`) | Financial truth, gap analysis, DEF-001 |
| **Regular (Patient) Collections** | Live | Register Excel (DEF-001 applied) | Patient-side collections |
| **Insurance Collections** | Missing | ERA-835 (procurement blocker) | Ins Plan split, denial analysis |
| **Account Ledger (Multi-year)** | Live / Broken | Excel year-chunks → `sd_account_transactions` | Transaction drill-down, coverage chip |
| **Ops Detail (Patients/Appts/Procedures)** | Live | ODBC `sd_*` | Scheduling, dossier, chair utilization |
| **Insurance Master (Carriers/Policies)** | Live | Sensei Reference → `sd_patient_insurance` (HAL-10581); ODBC/CSV when DSN available | Eligibility, payer mix |
| **Claims (Outstanding by Carrier)** | Live (bridge) | Aging Excel + `sd_claims` by named payer (HAL-10580/10581) | AR aging by payer, collections targeting |
| **Production by Provider** | Reserved | Excel (Phase 2) | Productivity analytics |
| **Production by ADA Code** | Reserved | Excel (Phase 2) | Procedure mix analysis |
| **Collection Reconciliation** | Reserved | Excel/ODBC hybrid (Phase 2) | Payment line-item to deposit validation |
| **Deposit Slip** | Reserved | Excel (Phase 2) | End-of-day cash controls |

## 4. Recommended NEXT package toward comprehensive reporting
**Name:** **HAL-10580: Outstanding Claims by Carrier Bridge**  

**Why now:**  
- Unlocks the largest AR blind spot without waiting for ERA procurement.  
- Fixes the blocker: "Daysheet-derived claims lack payer without `sd_claims` join."  
- Prepares the data model for ERA auto-posting (claims must exist to match remittance).  
- Reconciles Layer 1 (Register AR aging) to Layer 2 (ODBC claim lines), proving comprehensive reporting integrity.

**Effort:** Medium (2–3 days)

**REAL files touched:**  
- `softdent_odbc_extract.py` (extend `sd_claims` extractor with `total_fee`, `balance`, `status` filters)  
- `C:\SoftDentReportExports` (AR aging Excel for validation baseline)  
- `softdent_master_reports.json` (promote `outstanding_claims_by_co` from Phase 2 Reserved to active)  
- `softdent_dashboard_period_sync.py` (add AR reconciliation validator: sum(odbc_claims.balance) ≈ Register.AR)

**Validation gate:**  
1. Sum of outstanding claim balances from `sd_claims` matches Register/Daysheet AR aging total within rounding tolerance.  
2. Payer distribution (carrier count × avg balance) matches `sd_patient_insurance` active policy mix.  
3. Zero synthetic dollars: if claim balance is NULL, treat as "unbilled" not $0.

## 5. Phased roadmap (3–5 phases; each with exit criteria)

**Phase 1: AR Bridge + Ledger Repair (Immediate)**  
- Fix `ImportError` on `resolve_account_transactions_db` (maintenance).  
- Build HAL-10580 Outstanding Claims by Carrier Bridge.  
- *Exit criteria:* Account ledger queries return; outstanding claims total reconciles to Register AR; payer mix widget live.

**Phase 2: Productivity Drill-down**  
- Ingest `production_by_provider` and `production_by_ada_code` Excel exports (Phase 2 reserved).  
- Join with `sd_procedures` for clinical context.  
- *Exit criteria:* Provider production reconciles to Register totals (max-merge honesty enforced); ADA-code trend visible.

**Phase 3: Collection Reconciliation**  
- Ingest `collection_reconciliation` and `deposit_slip` reports.  
- Match payment line items (ODBC `sd_payments`) to Register deposits.  
- *Exit criteria:* Deposit slip total matches Daily Collections Summary; unreconciled payments < 1%.

**Phase 4: ERA-835 Integration (Unblocked by procurement)**  
- ERA files discovered → parsed → matched to claims from Phase 1.  
- Insurance collections populate `gap.insurance` (replacing $0 placeholder).  
- *Exit criteria:* ERA-discovered insurance dollars = Register Ins Plan dollars; auto-posting candidates identified.

**Phase 5: End-of-Day Reconciliation**  
- Full Layer 1-to-4 validation: Production = Procedures; Collections = Payments + Adjustments; AR = Claims - Payments.  
- *Exit criteria:* Comprehensive practice report generates without manual gap codes.

## 6. What NOT to do
- **Boil the ocean:** Do not attempt overnight ODBC ingestion of all 100+ SoftDent tables; ingest only tables required for the reconciliation layers above.  
- **Invent Ins Plan dollars:** Do not fabricate insurance collections when Register shows Ins Plan $0; wait for ERA-835.  
- **Register re-export:** Do not recommend re-exporting period-close Register files to "fix" missing splits; honor the original Excel truth.  
- **SoftDent write-back:** Never INSERT/UPDATE/DELETE against the production SoftDent database; remain read-only.  
- **PDF scraping:** Do not build OCR pipelines for EOB PDFs as an ERA workaround; procure standard 835 files.

## 7. Executive Summary (5 bullets)
- HAL currently holds period-close financial truth (Excel) and operational granularity (ODBC), but lacks the **claims-to-payer bridge** required for comprehensive AR management.  
- **ERA-835 procurement** is the only path to insurance collections detail; strategy proceeds with patient-side completeness while insurance waits.  
- **HAL-10580** (Outstanding Claims by Carrier Bridge) is the single highest-leverage next step, connecting `sd_claims` to Register AR aging without boiling the ocean.  
- **Account transaction resolver** requires immediate repair to maintain the 549k-row ledger functionality.  
- All ingestion remains **read-only**; `C:\SoftDentReportExports` Excel files are immutable period-close truth—never overridden by database aggregates.

## 8. Approval checklist
- [ ] Confirm ERA-835 procurement timeline (parallel track; do not block Phase 1).  
- [ ] Approve HAL-10580 scope: `sd_claims` extraction + `outstanding_claims_by_co` ingestion + AR reconciliation validator.  
- [ ] Schedule baseline Register AR aging export (`C:\SoftDentReportExports`) for validation.  
- [ ] Acknowledge Account TX ImportError fix as maintenance prereq (not new ingestion).  
- [ ] Reject synthetic Ins Plan dollars; maintain July Register Ins Plan $0 truth.

---

## Amendment 2026-07-13 — HAL-10581 (applied)

Operator `proceed` after `MOONSHOT_WHATS_NEXT_AFTER_CLAIMS_BRIDGE_2026-07-13.md`. SoftDent ODBC DSN was unavailable; Sensei Gateway **Reference** (`patient_*.json` + `insco_*.json`) populated `sd_patient_insurance` and attributed daysheet `sd_claims` payers via chart MRN (`DS-YYYYMMDD-{chart}-…`). Live: insurance rows **5415**, named claims **61/61**, gap `CLAIMS_PAYER_ATTRIBUTION_REQUIRED` cleared; remaining honest gap `CLAIMS_AR_RECONCILE_MISMATCH` (aging Ins **$0** vs claims billed **$7,714**). See `MOONSHOT_PAYER_ATTRIBUTION_REFRESH_HAL10581_APPLIED_2026-07-13.md`.

