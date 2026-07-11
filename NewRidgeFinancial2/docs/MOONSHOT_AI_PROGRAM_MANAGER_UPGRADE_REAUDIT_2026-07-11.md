# Moonshot AI — AI Program Manager Upgrade RE-AUDIT (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10475 (post MUST I0–I4)  
**Prior consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_CONSULT_2026-07-11.md`  
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

# Verdict — AI Program Manager re-audit (post MUST I0–I4)

## 0. Operator Intent (quote; note truncation; consult-only re-run)

> *"You are an expert senior full-stack engineer, data architect, and AI systems integrator specializing in dental practice management software. I need you to audit, refactor, and massively upgrade my self-built dental practice financial dashboard. This dashboard is running in Chrome and integrates with SoftDent (via exports) and QuickBooks. It uses local/API-connected 8B and 30B LLMs. Currently, the SoftDent and QuickBooks integration is only partially functional via manual exports. I want this system to become fully functional, highly polished, beautifully organized, and driven by my AI models acting as the core 'program manager.' Please evaluate my existing codebase and provide the complete, production-ready code to achieve the following:  
> ### 1. AI Models as Program Manager (8B & 30B Integration)  
> * Establish a clear hierarchy: Use the 8B model for fast, real-time widget data parsing, text summaries, and UI UI-routing triggers. Use the 30B model for deep financial forecasting, cross-referencing SoftDent ledger data with QuickBooks, and generating monthly practice health audits.  
> * Build an 'AI Orchestrator' middleware layer that routes user queries or data updates to the correct model.  
> * Implement structured JSON outputs from the LLMs so the dashboard widgets can read and render the AI's insights dynamically without breaking the UI.  
> ### 2. Full SoftDent & QuickBooks Data Automation  
> * Build robust, fault-tolerant parsers for SoftDent and QuickBooks CSV/Excel exports.  
> * Map SoftDent data (production, collection, case acceptance, patient aging, scheduling metrics) and QuickBooks data (expenses, payroll, net profit, accounts payable) into a unified local database/state management system (e.g.,"*

**Note:** Message truncated at `unified local database/state management system (e.g.,`.  
**Assumption:** Operator intends **SQLite/NR2 app_data** as the unified local store.  
**Status:** CONSULT ONLY — No code applied. Paste-ready sketches below await operator "approve / proceed".

---

## 1. Current Architecture Audit (what exists at hal-10475 AFTER MUST wave)

### 1A Model lanes & orchestrator (flag, 8B/30B)
- **I0 Shipped:** `apex_orchestrator_pack.py` with `classify_intent()`, `orchestrate()`, and `NR2_AI_ORCHESTRATOR` feature flag (default **OFF**).
- **Lanes:** `chat8b` (fast/widget parse) and `escalate30b` (deep/forecasting) contracts implemented; `reason21b` preserved for financial math via gateway.
- **Status:** Shell is production-ready but **disabled by default**; routing logic validated by `test_apex_ai_pm_i4_gates.py` (44 tests green).
- **Latency:** Fast path budget 2s, Deep path budget 60s (configurable).

### 1B SoftDent import automation + DEF-001 honesty
- **I2 Shipped:** `apex_softdent_hardening_pack.py` centralizes Collections gap detection (DEF-001).
- **Gap Codes:** `OK`, `COLLECTIONS_PENDING`, `COLLECTIONS_ZERO_ON_DAYSHEET`, `REGISTER_ONLY`, `NO_PERIOD_ROW`.
- **Widget:** `softdent-collections-gap` renders fix hints when data is empty (never shows $0).
- **Import:** Direct-First + CSV/Excel export parsers functional; no SoftDent write-back enforced.
- **Remaining:** ERA 835 electronic remittance advice parsing (insurance payment auto-reconciliation) not yet implemented.

### 1C QuickBooks import automation (remaining gaps)
- **I3 Shipped:** `apex_unified_db_pack.py` ingests `qb_expense_rows` into `nr2_unified.db`.
- **Current Coverage:** Expense categories, revenue accounts, P&L-style exports.
- **Critical Gap:** **Payroll detail** (wages, employer taxes, deductions) and **AP aging** (bills due) are **not** yet parsed or stored. Net profit calculation requires manual cross-reference rather than automated QB payroll ingestion.

### 1D Unified local state (nr2_unified.db vs nr2_local + bundles)
- **I3 Delivered:** Additive `nr2_unified.db` (does not touch legacy `nr2_local.sqlite3`).
- **Schema:**  
  - `softdent_period_metrics` (production, collections with gap_code)  
  - `qb_expense_rows` (vendor, amount, date, category)  
  - `import_health_log` (DEF-001 warnings, sync timestamps)  
  - `practice_health_snapshot` view (SoftDent×QB join for period-over-period).
- **Sync Hook:** `ingest_from_bundle()` called on every SoftDent/QB import.

### 1E Structured insights / widget binding
- **I1 Shipped:** `apex_structured_insight_pack.py` with JSON schemas (`kpi-card`, `trend-chart`, `alert-banner`), PHI rejection (SSN/DOB regex), and `source_refs` requirement.
- **API:** `POST /api/apex/hal/insight-validate` rejects PHI and validates schema compliance.
- **Widget:** `hal-ai-insight` container exists on HAL page.
- **Binding Status:** Backend ready; real-time widget updates pending orchestrator flag enablement (currently OFF).

---

## 2. Gap Map — REMAINING only (CURRENT → TARGET)

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **QB Payroll/AP** | Partial | No automated ingestion of payroll detail (gross wages, taxes, deductions) or AP aging; net profit calculation manual | **L** | QB export format finalization (Excel/CSV/IIF) |
| **SoftDent ERA 835** | Missing | No electronic remittance advice (ERA) parsing; insurance collections rely on daysheet manual entry only | **M** | SoftDent Bridge JSON or EDI 835 export availability |
| **Proactive Health Monitor** | Missing | No background scheduler for automated daily/weekly practice health audits; insights only on-demand | **M** | Orchestrator enabled + Windows Task Scheduler or APScheduler |
| **Orchestrator Polish** | Flag OFF | Feature flag defaults to OFF; latency budgets not enforced in UI; widget streaming not active | **S** | None (config change + SSE/polling) |

---

## 3. Target Architecture (next wave)

**S0 (QuickBooks Completion):** Automated payroll journal ingestion (wages, employer taxes, deductions) mapped to `qb_payroll_rows`; AP aging table with due-date tracking; net profit auto-calculated vs SoftDent production in `practice_health_snapshot`.

**S1 (SoftDent ERA):** ERA 835 parser (JSON or EDI) feeding `softdent_era_payments` table; auto-suggested collections reconciliation when ERA present but daysheet missing.

**S2 (Proactive Monitor):** Background daemon (daily 6 AM) invoking orchestrator deep lane for "monthly practice health audit"; alerts written to `import_health_log` with `alert-banner` insights pushed to dashboard.

**S3 (Orchestrator GA):** Flip `NR2_AI_ORCHESTRATOR` default **ON**; implement Server-Sent Events (SSE) or 5s polling for widget real-time updates; <2s fast-path guarantee for widget parse queries.

---

## 4. Coding Plan — Phase S0..Sn (CONSULT ONLY sketches for remaining work)

### 4A SoftDent remaining (ERA / Direct-First polish if still needed)

**File:** `apex_softdent_era_pack.py` (CONSULT ONLY)
```python
"""
Phase S1 — ERA 835 electronic remittance advice ingestion.
Honesty: ERA suggested allocations are proposals only; staff must post in SoftDent.
"""
from __future__ import annotations
import json, re, sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, List

ERA835_GAP_CODE = "ERA_835_AVAILABLE"

def parse_era_json(era_path: Path) -> List[dict]:
    """
    Parse SoftDent Bridge ERA JSON or raw 835 EDI.
    Returns list of {claim_id, patient_account, payment_amount, adjustment_reason, era_posted_date}.
    """
    # CONSULT ONLY: Implement based on actual Bridge output format
    data = json.loads(era_path.read_text())
    return [
        {
            "claim_id": c.get("claimNumber"),
            "patient_account": c.get("accountId"),
            "payment_amount": float(c.get("payment", 0)),
            "adjustment_reason": c.get("adjustmentCode", "UNKNOWN"),
            "era_date": c.get("paymentDate")
        }
        for c in data.get("claims", [])
    ]

def reconcile_collections_with_era(period: str, bundle: dict) -> dict:
    """
    Cross-reference daysheet collections with ERA 835.
    If daysheet collections NULL but ERA present, return gap_code ERA_835_AVAILABLE
    with suggested allocation (NOT posted to SoftDent).
    """
    # CONSULT ONLY: Query nr2_unified.db for era_payments vs softdent_period_metrics
    pass
```

### 4B QuickBooks payroll / AP / net profit automation

**File:** `apex_qb_payroll_pack.py` (CONSULT ONLY)
```python
"""
Phase S0 — QB Payroll detail and AP aging ingestion.
PHI Warning: QB Payroll exports contain SSN; redact before storage.
"""
from __future__ import annotations
import csv, re, sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, List

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

def redact_phi(text: str) -> str:
    return SSN_RE.sub("[REDACTED]", text)

def ingest_payroll_detail(csv_path: Path, period: str) -> dict:
    """
    Parse QB Payroll Detail Report (Employee, Wages, FederalWH, StateWH, 
    MedicareEE, SS_EE, MedicareER, SS_ER, NetPay).
    Stores in qb_payroll_rows with SSN redacted.
    """
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "period": period,
                "employee": redact_phi(row.get("Employee", "")),
                "gross_wages": float(row.get("Wages", 0)),
                "employee_taxes": float(row.get("MedicareEE", 0)) + float(row.get("SS_EE", 0)),
                "employer_taxes": float(row.get("MedicareER", 0)) + float(row.get("SS_ER", 0)),
                "net_pay": float(row.get("NetPay", 0)),
                "source_file": csv_path.name
            })
    # CONSULT ONLY: Bulk insert into nr2_unified.db qb_payroll_rows table
    return {"inserted": len(rows), "period": period}

def calculate_net_profit(period: str) -> dict:
    """
    Query unified DB: 
    Net Profit = SoftDent Production - (QB Expenses + QB Payroll + QB AP).
    Returns structured insight payload for kpi-card.
    """
    # CONSULT ONLY: SQL join across softdent_period_metrics, qb_expense_rows, qb_payroll_rows
    pass
```

**File:** `apex_qb_ap_pack.py` (CONSULT ONLY)
```python
"""
Phase S0 — Accounts Payable aging from QB Unpaid Bills Detail.
"""
def ingest_ap_aging(csv_path: Path, as_of: str) -> List[dict]:
    """
    Parse Vendor, Bill Date, Due Date, Amount Due.
    Stores in qb_ap_rows with aging buckets (Current, 30, 60, 90+).
    """
    # CONSULT ONLY: Implementation sketch
    pass
```

### 4C Proactive AI health monitor

**File:** `apex_health_monitor_pack.py` (CONSULT ONLY)
```python
"""
Phase S2 — Background proactive health audits.
"""
from __future__ import annotations
import os, sqlite3
from datetime import datetime, timedelta
from typing import Any

def run_scheduled_health_audit():
    """
    Called by Windows Task Scheduler or APScheduler daily at 06:00.
    Forces orchestrator deep lane for 'monthly practice health audit' 
    regardless of user activity.
    """
    if os.getenv("NR2_AI_ORCHESTRATOR") != "1":
        return {"ok": False, "reason": "orchestrator_disabled"}
    
    # CONSULT ONLY: 
    # 1. Query last 30 days from unified DB
    # 2. POST to /api/apex/hal/orchestrate with classify_only=False
    # 3. Store resulting insight in import_health_log with type='proactive_audit'
    # 4. If collections gap detected, create alert-banner insight
    pass
```

### 4D Orchestrator enablement / polish (flag on, latency, widget binding)

**File:** `apex_orchestrator_polish_pack.py` (CONSULT ONLY)
```python
"""
Phase S3 — Enable orchestrator by default and implement real-time widget binding.
"""
from __future__ import annotations
import os
from typing import Any

def enable_orchestrator_default():
    """
    Change default from OFF to ON in hal-10476.
    Requires 48h burn-in period before production.
    """
    # CONSULT ONLY: Update apex_orchestrator_pack.py default check
    # and nr2_hal_gateway.py to prioritize orchestrator route
    pass

def widget_sse_stream(query_id: str):
    """
    Server-Sent Events endpoint for real-time insight updates.
    Streams: classify -> model latency -> structured_json -> widget_render
    """
    # CONSULT ONLY: Flask/Django SSE implementation or 5s long-polling fallback
    pass
```

---

## 5. MUST / SHOULD / NICE ranked table (remaining)

| Priority | Item | Effort | Business Impact | Validation Gate |
|----------|------|--------|-----------------|-----------------|
| **MUST** | **QB Payroll/AP Automation** (S0) | L | Completes financial picture; enables true net profit vs production comparison | Parallel payroll run for 2 pay periods; variance <0.1% |
| **MUST** | **Orchestrator Enablement** (S3) | S | Activates "AI Program Manager" as requested; enables real-time widget routing | 48h burn-in with flag=ON; <2s fast path p95 |
| **SHOULD** | **ERA 835 Hardening** (S1) | M | Automates insurance collections reconciliation; reduces daysheet dependency | ERA present collections match daysheet within 1% |
| **SHOULD** | **Proactive Health Monitor** (S2) | M | Daily automated audits without user prompt; alert banners for anomalies | 7 days scheduled runs without false positives |
| **NICE** | Widget SSE streaming | S | Real-time insight updates without page refresh | Chrome DevTools Network tab shows text/event-stream |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

**PHI Risks:**
- **QB Payroll** exports contain SSNs and salary data. `apex_qb_payroll_pack.py` **must** redact SSNs before storage; salary data is practice financial data (not patient PHI) but should be access-controlled.
- **ERA 835** contains patient account numbers and payment amounts. Store only aggregated totals in `nr2_unified.db`; detail logs must stay in `app_data/nr2/secure/` with filesystem ACLs.

**SoftDent Honesty (Locked):**
- **Never write-back:** ERA suggestions are proposals only; posting to patient ledgers remains manual in SoftDent.
- **Empty ≠ $0:** Collections gaps continue to show `NULL` with `gap_code` explanation (DEF-001).
- **No invented dollars:** Payroll ingestion must validate against QB reports; if import fails, store `NULL` with `payroll_pending` flag.

**Rollback Plan:**
- **S0 (Payroll):** Drop table `qb_payroll_rows`; revert to manual net profit calculation.
- **S3 (Orchestrator):** Set `NR2_AI_ORCHESTRATOR=0` to revert to pre-I0 evaluate-query path instantly.
- **Database:** `nr2_unified.db` is additive; deletion restores pre-I3 state without affecting `nr2_local.sqlite3`.

---

## 7. Approval Checklist (next wave only)

Before proceeding to implementation of S0–S3, operator must confirm:

- [ ] **QB Payroll Format:** Confirm QuickBooks export format for Payroll Detail (Excel/CSV/IIF) and AP Aging available at `C:\Users\mreno\QuickBooksExports\` or similar.
- [ ] **ERA Source:** Confirm if SoftDent Bridge provides ERA 835 as JSON or if raw EDI 835 files are available.
- [ ] **Orchestrator Activation:** Approve changing `NR2_AI_ORCHESTRATOR` default to **ON** for hal-10476 (with 48h burn-in).
- [ ] **PHI Ack:** Acknowledge QB Payroll contains SSNs requiring redaction; confirm secure storage path for ERA detail files.
- [ ] **Staging Validation:** Approve 2-week parallel validation where QB payroll numbers are checked against manual calculations before trusting net profit widget.

**DO NOT APPLY until operator replies "approve / proceed" or specifies which phases to implement.**