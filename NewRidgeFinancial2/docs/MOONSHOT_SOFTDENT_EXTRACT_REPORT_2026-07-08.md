# Moonshot SoftDent Full Data Extraction Analysis

**Date:** 2026-07-08  
**Model:** Codebase audit + live runtime state (Moonshot API returned 401; local Ollama fallback was too shallow)  
**Script:** `scripts/run_moonshot_softdent_extract_analysis.py`  
**Runtime snapshot:** `C:\SoftDentFinancialExports\softdent_financial_analytics.db` inspected 2026-07-08

---

# Verdict

**You already have most SoftDent financial data on disk — the bottleneck is wiring, not discovery.**

The live export lane at `C:\SoftDentFinancialExports` is actively refreshing (daily + 45-min jobs ran today). The analytics DB holds **1,317 financial rows**, **1,226 transactions**, **2,815 production-by-ADA rows**, and **264 provider production rows**. NR2's `import_sync.py` already pulls from this folder.

What's missing for "all data out of SoftDent":

1. **Payments and adjustments** are not landing in `sd_payments` / `sd_adjustments` (both 0 rows) — daysheet fallback mis-classifies payment codes.
2. **ODBC lane is not configured** (`SOFTDENT_ODBC_DSN` unset) — the deepest patient/appointment/claim extract path is idle.
3. **Bridge exports are stale** (June 2026 sample data in `C:\Users\mreno\SoftDentBridge\exports`) — not your production source anymore.
4. **Operatory schedule** has no dedicated export (`operatory_schedule.json` missing).
5. **Several analytics tables are empty** (insurance_claims, collection_summary, treatment_plan_summary, outstanding_claims) — report profiles exist but aren't being ingested into those tables.

**Recommended priority:** Fix payment/adjustment parsing → wire analytics DB tables to widgets → configure ODBC for patient-level depth → add operatory export.

---

## SoftDent Data Inventory (what NR2 already ingests vs missing)

### Already ingesting (live, refreshed today)

| Domain | Source file / table | Rows (live DB) | NR2 consumer |
|--------|---------------------|----------------|--------------|
| Daily production/collections | `daysheet.jsonl` → `daysheet_totals` | 3 periods | Dashboard, period sync |
| Transactions | `transactions_for_period.jsonl` → `transactions` | 1,226 | Analytics, claims pipeline |
| Production by ADA | report ingest → `production_by_ada` | 2,815 | Treatment plan widgets |
| Production by provider | report ingest → `production_by_provider` | 264 | Provider production widget |
| Financial rows | various JSONL → `financial_rows` | 1,317 | Cross-analytics |
| A/R aging | `account_aging.jsonl` → `account_aging` | 1 | AR widgets |
| Write-offs | `writeoff_totals.jsonl` → `writeoff_totals` | 10 | Adjustment log (partial) |
| Claims (derived) | daysheet pipeline → `sd_claims` | 60 | Claims outstanding |
| Patients (derived) | daysheet → `sd_patients` | 40 | New patients MTD |
| Procedures (derived) | daysheet → `sd_procedures` | 60 | Production daily |
| Appointments (derived) | daysheet → `sd_appointments` | 23 | Appointments snapshot |
| Dashboard bundle | `softdent_dashboard_data.json` | current month | KPI ribbon, funnel |
| Claims export | `softdent_claims_export.csv` | 11 KB | HAL claims workbench |
| Clinical notes | `softdent_clinical_notes_data.json` | 20 KB | HAL narrative draft |
| Case acceptance | `case_acceptance.csv` | present | Funnel widget |
| Hygiene recall | `hygiene_recall_summary.csv` | present | Recall widget |
| New patients | `softdent_new_patients.csv` | present | New patients widget |
| Treatment plans | `treatment_plan_summary.csv` | present | Treatment plan widget |
| AR aging CSV | `softdent_ar_aging.csv` | present | AR heatmap |

### Missing or empty (gaps to close)

| Domain | Expected source | Current state | Impact |
|--------|-----------------|---------------|--------|
| **Payments** | daysheet payment codes / register JSONL / ODBC | `sd_payments`: **0** | Collections daily widget empty |
| **Adjustments** | writeoff codes 51/52 / adjustments table | `sd_adjustments`: **0** | Adjustment log empty |
| **Insurance claims detail** | SoftDent claims report / ODBC | `insurance_claims`: 0 | Claims depth shallow |
| **Outstanding claims** | claims aging report | `outstanding_claims`: 0 | Claims outstanding widget |
| **Treatment plans (DB)** | treatment plan report | `treatment_plan_summary`: 0 (CSV exists) | DB vs file mismatch |
| **Collection summary** | daysheet totals / register | `collection_summary`: 0 | Collection lag analytics |
| **Operatory schedule** | dedicated export | **file missing** | Operatory grid blank |
| **Provider reference** | master provider list | `provider_reference`: 0 | Provider name resolution |
| **Fee schedules** | fee schedule report | `fee_schedules`: 0 | Fee validation |
| **Payment plans** | payment plan report | `payment_plans`: 0 | Patient financing view |
| **Patient ledger** | ledger export CSV | not in import inbox | HAL ledger context |
| **Procedures export** | procedures CSV | not in import inbox | Insurance narratives |
| **EOD report A/R** | daily end-of-day PDF/txt | not staged | Bounded office AR total |

---

## Extraction Lanes Ranked (best → fallback)

### Lane 1 — `C:\SoftDentFinancialExports` (PRIMARY — already working)

This is your production lane. Automated refresh jobs write:

- `daysheet.jsonl` — daily production, collections, payment method breakdown
- `transactions_for_period.jsonl` — full transaction detail (842 KB)
- `account_aging.jsonl` — A/R buckets
- `writeoff_totals.jsonl` — write-off totals
- `register_for_period.jsonl` — register/collections detail
- `report_profile_*.csv.json` — structured report metadata

`import_sync.py` already copies from `SOFTDENT_FINANCIAL_EXPORTS` and runs `softdent_dashboard_period_sync`, `softdent_operational_pipeline`, and `ensure_softdent_odbc_fresh`.

**Action:** Keep daily + 45-min refresh tasks running. This lane should remain authoritative for financial aggregates.

### Lane 2 — Daysheet JSONL pipeline (DERIVED — partial)

`softdent_operational_pipeline.py` parses `daysheet.jsonl` formatted rows into:

- Claims dataset → `softdent_claims_export.csv/json`
- Clinical notes dataset → `softdent_clinical_notes_data.json`

`softdent_odbc_extract.py` uses the same daysheet to populate `sd_*` tables via `_populate_from_daysheet()`.

**Gap:** Payment detection uses prefixes `1200`, `1400`, `4000`, `5000` and text tokens — SoftDent v19 daysheet payment codes (`2`, `11`, `12`, etc.) may not match, leaving `sd_payments` at 0.

**Action:** Extend `_is_payment()` and `_is_adjustment()` in `softdent_odbc_extract.py` to honor `INSURANCE_PAYMENT_CODES` and `INSURANCE_WRITEOFF_CODES` from `softdent_operational_pipeline.py` (codes `2`, `51`, `52`).

### Lane 3 — ODBC → SQL Server (DEEPEST — not configured)

SoftDent v14–19 runs on **Microsoft SQL Server** (Sensei/Carestream). Third-party integrations (Weave, OraCore) use read-only sync apps against the local server database.

NR2 already has:

- `softdent_odbc_extract.py` with 7 `sd_*` tables and env-var query templates
- `POST /api/admin/extract-softdent-odbc` (consent-gated)
- `ensure_softdent_odbc_fresh()` called from `import_sync.py`

**Blocker:** `SOFTDENT_ODBC_DSN` not set; `SOFTDENT_ODBC_*_QUERY` env vars empty.

**Action:** Configure Windows ODBC DSN → SoftDent SQL Server → supply read-only SELECT queries (see ODBC section below).

### Lane 4 — Bridge file drop (LEGACY — stale)

`C:\Users\mreno\SoftDentBridge\exports` has 3 files from **June 2026** (sample/seed data). The C# bridge worker only copies named files; it does not extract from SoftDent directly.

**Action:** Deprioritize bridge for financial data. Use it only if you add new export types the bridge can watch. Financial lane supersedes it.

### Lane 5 — Manual CSV/JSON exports (SUPPLEMENT)

NR2's `import_contract.py` defines canonical filenames for 10+ dataset types. Manual exports from SoftDent reports fill gaps ODBC can't easily reach (operatory grid, case acceptance, hygiene recall).

**Action:** Schedule weekly manual exports for operatory schedule and patient ledger; drop into `C:\SoftDentFinancialExports` or import inbox.

### Lane 6 — End-of-Day report parse (BOUNDED A/R)

`docs/softdent_end_of_day_ar_inventory.md` documents parsing the **last page** of SoftDent DAYSHEET for `New Receivables Total`. Useful as a cross-check, not primary ledger.

**Action:** Stage EOD `.txt` exports to `app_data/nr2/document_inbox/softdent/daily_end_of_day/` for bounded office AR validation.

---

## Full Data Extraction Blueprint

### Financial / Production

| Data | Best extraction | NR2 destination |
|------|-----------------|-----------------|
| Daily production & collections | `daysheet.jsonl` (automated) | `daysheet_totals`, dashboard JSON |
| Monthly production by provider | report profile ingest | `production_by_provider` |
| Production by ADA code | report profile ingest | `production_by_ada` |
| Period transactions | `transactions_for_period.jsonl` | `transactions`, `financial_rows` |
| Write-offs | `writeoff_totals.jsonl` | `writeoff_totals`, `sd_adjustments` |

### Collections / Payments

| Data | Best extraction | NR2 destination |
|------|-----------------|-----------------|
| Daily collections | daysheet `collections` field | `daysheet_totals`, `sd_payments` |
| Payment method split | daysheet `check_total`, `credit_card_total`, etc. | dashboard enrichment |
| Register detail | `register_for_period.jsonl` | `sd_payments` (needs parser) |
| Insurance payments | daysheet `insurance_payment_total` | collection lag analytics |

### A/R & Aging

| Data | Best extraction | NR2 destination |
|------|-----------------|-----------------|
| Aging buckets | `account_aging.jsonl` | `account_aging`, `softdent_ar_aging.csv` |
| Patient balances | ODBC patient ledger query OR ledger CSV export | `sd_*` / HAL ledger context |
| Office total A/R | EOD report last page | bounded `total_ar` fact |

### Clinical / Patients

| Data | Best extraction | NR2 destination |
|------|-----------------|-----------------|
| Patient roster | ODBC `sd_patients` query | `sd_patients` |
| New patients | procedure codes 140/150 OR first_visit_date | `softdent_new_patients.csv` |
| Clinical notes | daysheet pipeline OR clinical notes export | `softdent_clinical_notes_data.json` |
| Treatment plans | treatment plan report CSV | `treatment_plan_summary` table + CSV |
| Hygiene recall | recall summary CSV | `hygiene_recall_summary.csv` |

### Insurance / Claims

| Data | Best extraction | NR2 destination |
|------|-----------------|-----------------|
| Claim lines | daysheet pipeline OR claims CSV | `sd_claims`, `softdent_claims_export.csv` |
| Claim status | claims status export CSV | HAL claims workbench |
| Outstanding claims | claims aging ODBC/report | `outstanding_claims` |
| Payer reference | insurance company report | `insurance_company_reference` |

### Scheduling / Operations

| Data | Best extraction | NR2 destination |
|------|-----------------|-----------------|
| Appointments | ODBC `sd_appointments` OR schedule export | `sd_appointments` |
| Operatory grid | **dedicated** `operatory_schedule.json` | operatory widget |
| Provider list | ODBC `sd_providers` OR provider reference report | `sd_providers` |
| Case acceptance funnel | case acceptance CSV | funnel widget stages |

---

## Recommended Export File Contracts

Drop these into `C:\SoftDentFinancialExports` (auto-pulled) or `app_data/nr2/document_inbox/softdent`:

| Filename | Required fields | Frequency | Unlocks |
|----------|-----------------|-----------|---------|
| `daysheet.jsonl` | report_date, gross/net production, collections, payment method totals | Daily (automated) | Dashboard, sd_procedures |
| `transactions_for_period.jsonl` | patientId, code, description, production, reportDate | Daily/period | transactions, claims derivation |
| `account_aging.jsonl` | bucket labels, amounts | Daily | AR widgets |
| `operatory_schedule.json` | chairs[], provider, patient, startTime, status | Every 15–45 min | Operatory grid |
| `softdent_patient_ledger_export.csv` | PatientName, MRN, Date, Code, Description, Charge, Payment, Balance | Weekly | HAL ledger, collection lag |
| `softdent_procedures_export.csv` | PatientName, MRN, Date, Code, Tooth, Production, Provider | Weekly | Insurance narratives |
| `softdent_claim_status_export.csv` | ClaimId, Status, Payer, ServiceDate, Amount, DenialReason | Daily | Claims depth |
| `treatment_plan_summary.csv` | Period, Presented, Accepted, Scheduled, Completed | Monthly | Case acceptance funnel |
| `hygiene_recall_summary.csv` | Period, Due, Completed, Overdue | Monthly | Hygiene recall widget |

Existing contracts in `import_contract.py` already alias these names — no schema change needed, just file production.

---

## ODBC Query Strategy

### Setup steps

1. On the SoftDent server workstation, open **ODBC Data Source Administrator (64-bit)**.
2. Add a **System DSN** using **ODBC Driver 17/18 for SQL Server**.
3. Server: your SoftDent SQL instance (find via SoftDent → Help → About, or ask IT).
4. Database: typically `NextGenV2` or practice-specific name (verify with `SELECT DB_NAME()`).
5. Use a **read-only SQL login** (never sa). Grant SELECT only on required views/tables.
6. Set environment variables (`.env` or system):

```ini
SOFTDENT_ODBC_DSN=SoftDentReadOnly
SOFTDENT_ODBC_USER=nr2_reader
SOFTDENT_ODBC_PASSWORD=<secret>
NR2_SOFTDENT_ODBC_MAX_AGE_MINUTES=60
```

### Table discovery (run once on SQL Server)

```sql
-- List tables (schema varies by SoftDent version — discover, don't assume)
SELECT TABLE_SCHEMA, TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;

-- Common Sensei/SoftDent entities to search for:
-- Patient, Appointment, Procedure, Claim, Provider, Payment, Adjustment, Ledger
```

### Env-var query templates (after discovery)

Map query results to columns expected by `softdent_odbc_extract._populate_from_odbc()`:

```ini
SOFTDENT_ODBC_PATIENTS_QUERY=SELECT PatientID AS patient_id, LastName+', '+FirstName AS patient_name, FirstVisitDate AS first_visit_date, LastVisitDate AS last_visit_date FROM Patient WHERE Active=1
SOFTDENT_ODBC_PROCEDURES_QUERY=SELECT PatientID AS patient_id, ProcDate AS proc_date, ADACode AS ada_code, Tooth AS tooth, Surface AS surface, ProviderID AS provider_code, Description AS description, Production AS production FROM Procedures WHERE ProcDate >= DATEADD(month, -24, GETDATE())
SOFTDENT_ODBC_PAYMENTS_QUERY=SELECT PatientID AS patient_id, PaymentDate AS payment_date, Amount AS amount, Payer AS payer, Method AS method FROM Payments WHERE PaymentDate >= DATEADD(month, -24, GETDATE())
SOFTDENT_ODBC_CLAIMS_QUERY=SELECT ClaimID AS claim_id, PatientName AS patient_name, Payer AS payer, ServiceDate AS service_date, ClaimAmount AS claim_amount, ClaimStatus AS claim_status FROM Claims WHERE ServiceDate >= DATEADD(month, -24, GETDATE())
SOFTDENT_ODBC_APPOINTMENTS_QUERY=SELECT PatientID AS patient_id, ApptDate AS appt_date, ProviderCode AS provider_code, Status AS status FROM Appointments WHERE ApptDate >= CAST(GETDATE() AS DATE)
SOFTDENT_ODBC_PROVIDERS_QUERY=SELECT ProviderCode AS provider_code, ProviderName AS provider_name FROM Providers
SOFTDENT_ODBC_ADJUSTMENTS_QUERY=SELECT PatientID AS patient_id, AdjDate AS adj_date, ADACode AS ada_code, Amount AS amount, Description AS description FROM Adjustments WHERE AdjDate >= DATEADD(month, -24, GETDATE())
```

**Important:** Table/column names above are illustrative. Run discovery against your actual SoftDent database before deploying. Carestream does not publish a public schema — treat discovery as a one-time operator task.

### Trigger extract

```powershell
# After DSN + queries configured:
python C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\import_sync.py

# Or via NR2 admin API (requires NR2_CONSENT_EXECUTOR=1):
# POST https://127.0.0.1:8765/api/admin/extract-softdent-odbc
```

---

## Integration Roadmap

### Phase 1 — Fix payment/adjustment gap (1 commit, highest ROI)

- **File:** `softdent_odbc_extract.py`
- Align `_is_payment()` / `_is_adjustment()` with `softdent_operational_pipeline.py` code sets (`2`, `51`, `52`, etc.)
- Add `register_for_period.jsonl` parser lane for `sd_payments`
- **Acceptance:** `sd_payments` > 0 and `sd_adjustments` > 0 after `import_sync.py`; `softdentCollectionsDaily` widget shows live data

### Phase 2 — Wire analytics DB → widgets (1–2 commits)

- **Files:** `nr2_softdent_daily.py`, `page-canvas-data.js`, `nr2_http_server.py`
- Point daily widgets at `daysheet_totals`, `production_by_provider`, `account_aging`, `transactions` when `sd_*` is empty
- **Acceptance:** All 9 SoftDent daily widgets render non-stub data

### Phase 3 — ODBC foundation (1 commit + operator setup)

- Configure DSN + discovered queries
- Run `ensure_softdent_odbc_fresh()` and verify `last_mode: odbc` in `sd_extract_meta`
- **Acceptance:** `sd_patients` > 40, `sd_appointments` populated from live schedule, HAL patient context works

### Phase 4 — Operatory + ledger exports (operator + bridge)

- Add operatory schedule export to financial refresh job OR manual weekly export
- Add `softdent_patient_ledger_export.csv` to insurance narrative export dir
- **Acceptance:** Operatory grid shows chairs; HAL ledger read returns bounded facts

### Phase 5 — HAL cross-domain briefings

- Teach HAL to compare `daysheet_totals.collections` vs QuickBooks deposits
- Proactive briefing when `sd_payments` vs QB deposits diverge > 5%
- **Acceptance:** HAL can answer "why is collections different from QuickBooks this month?"

---

## Risks & Compliance

| Risk | Mitigation |
|------|------------|
| PHI exposure | NR2 reads exports only; HAL broker returns bounded facts, never raw dumps |
| SoftDent warranty | ODBC must be **read-only** SELECT; no schema changes |
| Stale data | `import_sync` already rejects sample markers; stale badges on widgets |
| Writeback | `softdent_writeback_bridge.py` exists but must stay consent-gated; do not enable for financial extract |
| Bridge sample data | `_is_sample_dashboard` / `_is_sample_claims` reject seeded bridge files when not in full-pull mode |
| SQL credential leak | Store ODBC password in system env or Windows credential manager, not git |

---

## Operator Checklist

1. **Verify financial refresh is running**
   - Check `C:\SoftDentFinancialExports\daily_softdent_refresh.log` — last run should be today
   - Confirm `daysheet.jsonl` and `transactions_for_period.jsonl` timestamps are fresh

2. **Run import sync manually**
   ```powershell
   python C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\import_sync.py
   ```

3. **Check extract status**
   ```powershell
   python -c "from softdent_odbc_extract import read_extract_status; import json; print(json.dumps(read_extract_status(), indent=2))"
   ```
   - Target: `populatedTables` ≥ 6, `sd_payments` > 0 after Phase 1 fix

4. **Fix Moonshot API key** (for future AI consultations)
   - Current `MOONSHOT_API_KEY` returns 401 Invalid Authentication
   - Regenerate at [Moonshot AI platform](https://platform.moonshot.ai) and update user environment variable

5. **Configure ODBC** (when ready for deepest extract)
   - Create read-only DSN on SoftDent server
   - Run table discovery SQL
   - Set `SOFTDENT_ODBC_*` env vars
   - Test: `POST /api/admin/extract-softdent-odbc`

6. **Add operatory export**
   - Export today's schedule from SoftDent to `operatory_schedule.json`
   - Drop in `C:\SoftDentFinancialExports`
   - Re-run import sync

7. **Validate widgets on live NR2**
   - Open `https://127.0.0.1:8765` → SoftDent page
   - Confirm: production daily, collections daily, AR aging, claims, operatory grid

8. **Schedule automation** (if not already)
   ```powershell
   powershell -ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\import-automation\Register-HAL-Import-Automation.ps1"
   ```

---

## Summary

NR2's SoftDent integration architecture is **mature** — the gap is not "how to get data out" but **completing three connections**:

1. **Payment/adjustment code mapping** in the daysheet → `sd_payments` / `sd_adjustments` path
2. **Widget binders** reading from the rich `softdent_financial_analytics.db` that already exists
3. **ODBC DSN + queries** for patient-level depth and live appointments

The `C:\SoftDentFinancialExports` lane is your production firehose. Focus engineering effort there, not the stale June bridge samples.
