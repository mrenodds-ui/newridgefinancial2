# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #5 (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10489 (post V0–V2)  
**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT4_2026-07-11.md`  
**Script:** `scripts/run_moonshot_ai_program_manager_upgrade_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> You are an expert senior full-stack engineer, data architect, and AI systems integrator specializing in dental practice management software. 
I need you to audit, refactor, and massively upgrade my self-built dental practice financial dashboard. This dashboard is running in Chrome and integrates with SoftDent (via exports) and QuickBooks. It uses local/API-connected 8B and 30B LLMs. 
Currently, the SoftDent and QuickBooks integration is only partially functional via manual exports. I want this system to become fully functional, highly polished, beautifully organized, and driven by my AI models acting as the core "program manager."
Please evaluate my existing codebase and provide the complete, production-ready code to achieve the following:
### 1. AI Models as Program Manager (8B & 30B Integration)
* Establish a clear hierarchy: Use the 8B model for fast, real-time widget data parsing, text summaries, and UI UI-routing triggers. Use the 30B model for deep financial forecasting, cross-referencing SoftDent ledger data with QuickBooks, and generating monthly practice health audits.
* Build an "AI Orchestrator" middleware layer that routes user queries or data updates to the correct model.
* Implement structured JSON outputs from the LLMs so the dashboard widgets can read and render the AI's insights dynamically without breaking the UI.
### 2. Full SoftDent & QuickBooks Data Automation
* Build robust, fault-tolerant parsers for SoftDent and QuickBooks CSV/Excel exports.
* Map SoftDent data (production, collection, case acceptance, patient aging, scheduling metrics) and QuickBooks data (expenses, payroll, net profit, accounts payable) into a unified local database/state management system (e.g.,

---

# Verdict — AI Program Manager re-audit #5 (post V0–V2 / hal-10489)

## 0. Operator Intent (quote; note truncation; consult-only re-run)

> You are an expert senior full-stack engineer, data architect, and AI systems integrator specializing in dental practice management software. 
> I need you to audit, refactor, and massively upgrade my self-built dental practice financial dashboard. This dashboard is running in Chrome and integrates with SoftDent (via exports) and QuickBooks. It uses local/API-connected 8B and 30B LLMs. 
> Currently, the SoftDent and QuickBooks integration is only partially functional via manual exports. I want this system to become fully functional, highly polished, beautifully organized, and driven by my AI models acting as the core "program manager."
> Please evaluate my existing codebase and provide the complete, production-ready code to achieve the following:
> ### 1. AI Models as Program Manager (8B & 30B Integration)
> * Establish a clear hierarchy: Use the 8B model for fast, real-time widget data parsing, text summaries, and UI UI-routing triggers. Use the 30B model for deep financial forecasting, cross-referencing SoftDent ledger data with QuickBooks, and generating monthly practice health audits.
> * Build an "AI Orchestrator" middleware layer that routes user queries or data updates to the correct model.
> * Implement structured JSON outputs from the LLMs so the dashboard widgets can read and render the AI's insights dynamically without breaking the UI.
> ### 2. Full SoftDent & QuickBooks Data Automation
> * Build robust, fault-tolerant parsers for SoftDent and QuickBooks CSV/Excel exports.
> * Map SoftDent data (production, collection, case acceptance, patient aging, scheduling metrics) and QuickBooks data (expenses, payroll, net profit, accounts payable) into a unified local database/state management system (e.g.,

**Note:** Request truncated at `unified local database/state management system (e.g,`.  
**Assumed completion:** SQLite-based unified store (`app_data/nr2_unified.db`) with frontend state persistence via LocalStore/SSE, consistent with shipped T3 architecture.  
**Consult status:** CONSULT ONLY — no code applied pending operator approval.

---

## 1. Current Architecture Audit (what exists at hal-10489)

### 1A Orchestrator + telemetry + deep audit (V0/U0)
* **AI Orchestrator** (`apex_orchestrator_pack.py`): Lane routing live — 8B (`chat8b`) for fast widget parse/summarize/route queries; 30B (`escalate30b`) for deep forecasting/audit/cross-reference. Feature flag `NR2_AI_ORCHESTRATOR` (default ON).
* **Structured JSON outputs** (I4 shipped): Schema-validated widgets (`alert-banner`, `trend-chart`, `table`, `kpi-grid`) enforced via Pydantic-style validation in orchestrator; deep audit pack emits strict JSON per `AUDIT_SYSTEM_PROMPT`.
* **Telemetry** (`apex_ai_telemetry_pack.py`): Lane latency/error tracking without PHI. Flag `NR2_AI_TELEMETRY` (default OFF pending burn-in).
* **Deep Audit** (`apex_deep_audit_pack.py`): Monthly 30B practice health audit + quarterly forecast scaffolding. Flag `NR2_DEEP_AUDIT` (default ON).

### 1B SoftDent + ERA + synthetic fixtures (U1/V1)
* **Parsers** (S0–S3): Robust CSV/Excel ingest for SoftDent (production, collection) and ERA 835 (X12 parsing without `NM1*QC` segments). Quarantine logic for malformed rows.
* **Synthetic fixtures** (`test/fixtures/generate_synthetic_nr2.py`): Quiet/noisy MoM scenarios and synthetic 835 for reconciliation testing (V1).

### 1C QuickBooks + reconciliation + explain cache (U2/V2)
* **QB Parsers**: Expense, payroll, AP, net profit ingestion from QB exports.
* **Reconciliation engine** (`apex_reconciliation_pack.py`): Auto-detects SoftDent×QB variance (threshold 5% or $500). Gap codes (`RECON_DATA_PENDING`, `RECON_VARIANCE`) when views empty.
* **30B Explain Cache** (V2): LRU (128 entry) for `explain_variance()` keyed by `(period, delta_hash)`. Invalidates on import completion. Flag `NR2_EXPLAIN_CACHE` (default OFF pending burn-in).

### 1D Unified DB + import poll/quarantine + freshness (T3/U2b/V0)
* **Unified Store**: SQLite `app_data/nr2_unified.db` with views `v_production_vs_payroll`, `v_collection_vs_ap`.
* **Import Pipeline** (T3): Polling drop-folder (`NR2_IMPORT_POLL_SEC`), quarantine for schema violations, atomic merge on validation.
* **Freshness chips** (`apex_sync_status_pack.py`): Last successful import timestamps surfaced via SSE. Flag `NR2_DATA_FRESHNESS` (default OFF pending burn-in).
* **Audit Cron** (V0): Scheduled monthly audit runner (`scripts/run_nr2_scheduled_audit.py`). Flag `NR2_AUDIT_CRON` (default OFF pending burn-in).

### 1E Insights SSE + dashboard layout + mobile polish (N0/U3/V2)
* **Insights SSE**: Server-sent events stream (`/api/apex/hal/insights`) for real-time widget updates.
* **Mosaic layout**: Responsive grid (U3) with mobile hardening (V2): single-column stack ≤768px (`apex-mobile-polish.css`).

---

## 2. Gap Map — REMAINING only

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **SoftDent Extended Metrics** | PARTIAL | Case acceptance %, Patient aging buckets (0-30, 31-60, 61-90, 90+), Scheduling fill rate / production scheduled vs actual — not yet mapped to unified DB or reconciliation views. | M | S0–S3 parsers, T3 schema |
| **Import Job Scheduler** | SHIPPED (Poll) / MISSING (Cron trigger) | T3 provides poll endpoint; missing background cron to auto-trigger poll every `NR2_IMPORT_CRON_SEC` (distinct from audit cron). | S | T3 poll logic, V0 cron runner |
| **Data Quality Validator** | MISSING | Unified DB validation rules (orphaned patients, negative production, duplicate claim IDs, future-dated transactions) to catch export errors before merge. | M | Unified DB |
| **Quarantine UI** | MISSING | Frontend widget to review, reprocess, or purge quarantined import files (backend quarantine exists in T3). | S | T3 backend, N0 SSE |
| **Burn-in Ops** | READY | Flags `NR2_AI_TELEMETRY`, `NR2_AUDIT_CRON`, `NR2_DATA_FRESHNESS`, `NR2_EXPLAIN_CACHE` remain OFF until operator burn-in validation complete. | S (ops) | V0–V2 shipped code |

---

## 3. Target Architecture (next wave only)

* **W0 — Metric Completeness**: Extend SoftDent ingestion to cover case acceptance (accepted/treatment planned ratio), aging buckets (insurance + patient AR), and scheduling metrics (scheduled production vs actual). Add unified views `v_case_acceptance`, `v_patient_aging`, `v_scheduling_efficiency`.
* **W1 — Automation Hardening**: Import cron scheduler + data quality gate (DQ) to block merge on critical violations (negative dollars, orphaned foreign keys).
* **W2 — Operational UI**: Quarantine review panel in dashboard; burn-in runbook for flag activation.

---

## 4. Coding Plan — Phase W0..Wn (CONSULT ONLY sketches for remaining work)

### W0 — SoftDent Extended Metrics (CONSULT ONLY)

**`apex_softdent_extended_pack.py`**
```python
"""
Phase W0 — Extended SoftDent metrics (Moonshot REAUDIT5 MUST).
Case acceptance, patient aging, scheduling fill rate.
Honesty: empty ≠ $0; gap codes when export columns missing.
"""

from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Dict

GAP_AGING_PENDING = "AGING_DATA_PENDING"
GAP_CASE_ACCEPT_PENDING = "CASE_ACCEPT_DATA_PENDING"
GAP_SCHEDULE_PENDING = "SCHEDULE_DATA_PENDING"

def parse_softdent_aging(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Expects SoftDent AR Aging export: PatientID, Name, 0-30, 31-60, 61-90, 90+, InsPending
    Returns rows with gap codes if columns missing.
    """
    # CONSULT ONLY: Implementation would use pandas/pyarrow for speed,
    # validate numeric columns, reject negative dollars, map to unified schema.
    pass

def calculate_case_acceptance(treatment_planned: float, treatment_accepted: float) -> dict:
    """
    Returns ratio 0.0-1.0 with confidence low if denominator < 5 cases.
    Never invent dollars; return null with gap code if inputs empty.
    """
    # CONSULT ONLY: Guard against div/zero; return structured dict for widget rendering.
    pass

def build_scheduling_efficiency(scheduled_production: float, actual_production: float) -> dict:
    """
    Variance metric for schedule accuracy.
    """
    pass
```

**Schema migration (CONSULT ONLY)**
```sql
-- CONSULT ONLY: Add to nr2_unified.db
CREATE VIEW v_patient_aging AS
SELECT 
    datestamp,
    patient_id,
    bucket_0_30,
    bucket_31_60,
    bucket_61_90,
    bucket_90_plus,
    insurance_pending,
    (bucket_0_30 + bucket_31_60 + bucket_61_90 + bucket_90_plus) as total_ar
FROM softdent_aging_staging
WHERE validated = 1;

CREATE VIEW v_case_acceptance AS
SELECT 
    period,
    cases_presented,
    cases_accepted,
    CASE 
        WHEN cases_presented > 0 THEN ROUND(cases_accepted * 1.0 / cases_presented, 4)
        ELSE NULL 
    END as acceptance_rate,
    CASE WHEN cases_presented < 5 THEN 'low' ELSE 'high' END as confidence
FROM softdent_case_acceptance_staging;
```

### W1 — Import Scheduler & Data Quality (CONSULT ONLY)

**`apex_import_scheduler_pack.py`**
```python
"""
Phase W1 — Import cron + DQ rules (Moonshot REAUDIT5 SHOULD).
Flag: NR2_IMPORT_CRON (default OFF).
"""

import os
import time
import schedule  # CONSULT ONLY: lightweight scheduler
from pathlib import Path
from apex_sync_status_pack import record_import_timestamp

def job_poll_and_ingest():
    # CONSULT ONLY: Hook into existing T3 poll logic
    # 1. Scan drop folder
    # 2. Run DQ rules (see below)
    # 3. On pass, merge to unified DB
    # 4. On fail, move to quarantine with reason code
    pass

def run_scheduler():
    interval = int(os.getenv("NR2_IMPORT_CRON_SEC", "300"))
    # CONSULT ONLY: schedule.every(interval).seconds.do(job_poll_and_ingest)
    # while True: schedule.run_pending(); time.sleep(1)
```

**Data Quality Rules (CONSULT ONLY)**
```python
# CONSULT ONLY: DQ validators to be run before merge
RULES = [
    ("no_negative_production", lambda row: row.get("production", 0) >= 0),
    ("no_future_dates", lambda row: row.get("service_date") <= datetime.now().date()),
    ("valid_claim_id", lambda row: row.get("claim_id") not in (None, "", "NULL")),
    ("foreign_key_patient", lambda row: row.get("patient_id") in master_patient_index),
]
```

### W2 — Quarantine UI (CONSULT ONLY)

**`site/widgets/apex-quarantine-panel.js`**
```javascript
/**
 * Phase W2 — Quarantine review widget (Moonshot REAUDIT5 NICE).
 * CONSULT ONLY: Frontend component for T3 quarantine backend.
 */
class ApexQuarantinePanel extends HTMLElement {
  // CONSULT ONLY: 
  // - Fetch /api/apex/hal/quarantine-list
  // - Render table: filename, error_code, row_count, retry_button, purge_button
  // - Actions POST /api/apex/hal/quarantine-retry or /quarantine-purge
  // - SSE refresh on quarantine change
}
```

---

## 5. MUST / SHOULD / NICE ranked table (remaining)

| Rank | Item | Phase | Effort | Business Value |
|------|------|-------|--------|----------------|
| **MUST** | SoftDent Extended Metrics (case acceptance, aging, scheduling) | W0 | M | Required to fulfill "Full SoftDent... Automation" for all metrics listed in operator Section 2. |
| **MUST** | Import Job Scheduler (cron trigger) | W1 | S | Required for "fully functional" automation vs manual poll. |
| **SHOULD** | Data Quality Validator (unified DB rules) | W1 | M | Prevents garbage-in-garbage-out; required for trustworthy AI audit output. |
| **SHOULD** | Quarantine UI | W2 | S | Operational necessity for self-healing without CLI access. |
| **NICE** | 30B Predictive Scheduling | Future | L | Vendor-gated; requires 6+ months historical scheduling data + SoftDent API (not export). |
| **NICE** | Automated ERA 835 Posting | Future | L | Vendor-gated; requires SoftDent write-back capability (currently prohibited). |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

* **PHI**: W0 aging parser handles patient AR; must hash PatientID to `NR2_PATIENT_UUID` before storage. No names in unified DB.
* **SoftDent Honesty**: W0 metrics are read-only from exports. No write-back to SoftDent. Gap codes (`AGING_DATA_PENDING`) required when export columns missing or empty; empty ≠ $0.
* **DQ Safety**: W1 DQ rules must not auto-correct data (no imputation); only reject/quarantine.
* **Rollback**: W0–W2 are additive packs. If failure, disable flags `NR2_EXTENDED_METRICS=0`, `NR2_IMPORT_CRON=0` and revert to hal-10489 baseline.
* **Vendor Limitations**: True real-time SoftDent integration requires Carestream API (unavailable); automation is limited to export-drop-folder polling.

---

## 7. Approval Checklist (next wave only)

**Do not proceed until operator confirms:**

- [ ] **Approve W0**: Implement case acceptance, patient aging, and scheduling metrics parsers + unified views?
- [ ] **Approve W1**: Implement import cron scheduler (5 min default) and DQ validation rules?
- [ ] **Approve W2**: Implement quarantine review UI widget?
- [ ] **Burn-in Ready**: Confirm hal-10489 V0–V2 flags (`NR2_AI_TELEMETRY`, `NR2_AUDIT_CRON`, `NR2_DATA_FRESHNESS`, `NR2_EXPLAIN_CACHE`) validated for 7 days and ready to flip ON?
- [ ] **SoftDent Export Format**: Provide sample export files containing Case Acceptance, AR Aging, and Schedule reports to finalize W0 column mapping?

**DO NOT APPLY until operator says approve / proceed.**