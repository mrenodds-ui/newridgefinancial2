# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #2 (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10480 (post MUST+SHOULD+N0)  
**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT_2026-07-11.md`  
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

# Verdict — AI Program Manager re-audit #2 (post MUST+SHOULD+N0)

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
**Assumption:** Operator intends **SQLite/NR2 app_data/nr2_unified.db** as the unified local store (consistent with Phase I3).  
**Status:** CONSULT ONLY — No code applied. Paste-ready sketches below await operator "approve / proceed".

---

## 1. Current Architecture Audit (what exists at hal-10480)

### 1A Model lanes & orchestrator (flag still OFF)
*   **Hybrid GPU Layout** (`hal-models.json`): `chat8b` (fast/widget) + `escalate30b` (deep/forecast) pinned resident; `coder32b` on-demand for agent loops.
*   **Orchestrator Pack** (`apex_orchestrator_pack.py`): Intent classification via `_FAST_LANE_RE` (8B) vs `_DEEP_LANE_RE` (30B); middleware routes to `/api/apex/hal/orchestrate`.
*   **Feature Flag**: `NR2_AI_ORCHESTRATOR` defaults to **OFF** (opt-in via `$env:NR2_AI_ORCHESTRATOR = "1"`). Phase I4 gates validate orchestrator status without Ollama calls.
*   **Status Endpoint**: Returns `phase: "I4"`, `mustWaveComplete: true`, `enabled: false` (until flag flipped).

### 1B SoftDent + DEF-001 + ERA aggregates
*   **DEF-001 Collections Honesty**: Empty SoftDent collections export surfaces `softdent-collections-gap` widget with fix hint; never renders `$0` for missing data.
*   **ERA 835 Harden** (`apex_softdent_era_pack.py`): Aggregates ERA payments into `era_835_aggregate` table (totals only); emits `ERA_835_AVAILABLE` proposal when ERA present but SoftDent collections pending.
*   **No Write-Back**: All SoftDent ingestion is read-only; proposals require manual posting in SoftDent.

### 1C QuickBooks payroll/AP + expenses
*   **Payroll Pack** (`apex_qb_payroll_pack.py`): Ingests `quickbooks_payroll*.csv`, redacts SSN patterns to `[REDACTED]`, surfaces `payroll_pending` gap when export missing.
*   **AP Pack**: Ingests unpaid bills/AP aging into `qb_ap_rows`; `ap_pending` gap when missing.
*   **Expenses**: Unified DB table `qb_expense_rows` holds prior expense data.
*   **Contract**: `import_contract.py` recognizes `quickbooks.payroll` and `quickbooks.ap` bundle keys.

### 1D Unified DB + practice_health_snapshot
*   **Schema** (`apex_unified_db_pack.py`): `nr2_unified.db` contains:
    *   `softdent_period_metrics` (collections, prior periods)
    *   `era_835_aggregate` (payment totals)
    *   `qb_expense_rows`, `qb_payroll_rows`, `qb_ap_rows`
    *   `health_audit_log`, `import_health_log`
*   **Snapshot View**: `practice_health_snapshot` provides cross-period aggregates for 30B deep analysis.

### 1E Structured insights + SSE widget binding
*   **Structured JSON** (`apex_structured_insight_pack.py` referenced): Schema-validated insights; PHI rejection pre-storage.
*   **SSE Stream** (`apex_insight_sse_pack.py`): Endpoint `/api/apex/hal/insight-stream` pushes `text/event-stream`; fallback 5s poll to `/api/apex/hal/insight-latest`.
*   **Widget Binding**: `site/nr2-insight-sse.js` patches `hal-ai-insight` widget for live updates without page reload.

---

## 2. Gap Map — REMAINING only

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **SoftDent Production** | MISSING | Parser + table for production metrics (procedures, production $, provider splits) | M | I3 schema |
| **SoftDent Patient Aging** | MISSING | Parser + table for AR aging buckets (0-30, 31-60, 61-90, 90+) | M | I3 schema |
| **SoftDent Case Acceptance** | MISSING | Parser + table for treatment plan vs accepted $ | M | I3 schema |
| **SoftDent Scheduling** | MISSING | Parser + table for fill rate, broken appointments, capacity | M | I3 schema |
| **QuickBooks Net Profit** | MISSING | Parser + table for P&L summary (revenue - expenses - payroll) | S | I3 schema |
| **Import Automation** | MISSING | File system watcher to auto-detect drops in import inbox (vs manual "Sync" click) | L | OS file events |
| **Cross-Reference Views** | MISSING | SQL views joining SoftDent production × QB expenses for 30B lane queries | S | Above tables |
| **Orchestrator Default** | DECISION | Flip `NR2_AI_ORCHESTRATOR` default to `ON` for GA | XS | Operator approval + burn-in |

---

## 3. Target Architecture (next wave only)
*   **Complete Data Plane**: All five SoftDent metric streams (production, collections, case acceptance, aging, scheduling) plus full QB suite (expenses, payroll, AP, net profit) resident in `nr2_unified.db`.
*   **Zero-Touch Imports**: Windows file-system watcher queues exports for processing without manual Sync button.
*   **Deep Cross-Reference**: SQL views enabling 30B lane to generate "Production vs Payroll Efficiency" and "Collection vs AP Cash Flow" audits without Python glue.
*   **GA Orchestrator**: Feature flag defaults ON; 8B/30B routing live for all HAL queries.

---

## 4. Coding Plan — Phase T0..Tn (CONSULT ONLY sketches for remaining work)

### Phase T0 — SoftDent Production & Case Acceptance (MUST)
**CONSULT ONLY — Schema Addition to `apex_unified_db_pack.py`**
```python
# Add to _ensure_schema()
"""
CREATE TABLE IF NOT EXISTS softdent_production (
    period TEXT NOT NULL,
    provider_id TEXT,
    procedure_code TEXT,
    procedure_description TEXT,
    production_amount REAL,
    quantity INTEGER,
    posted_date TEXT,
    source_file TEXT,
    ingested_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sd_prod_period ON softdent_production(period);

CREATE TABLE IF NOT EXISTS softdent_case_acceptance (
    period TEXT NOT NULL,
    provider_id TEXT,
    treatment_planned_amount REAL,
    accepted_amount REAL,
    acceptance_rate REAL,  -- computed 0.0-1.0
    source_file TEXT,
    ingested_at TEXT
);
"""
```

**CONSULT ONLY — Parser Sketch (`apex_softdent_production_pack.py`)**
```python
# Pattern: mirror apex_qb_payroll_pack.py
GAP_PRODUCTION_PENDING = "PRODUCTION_PENDING"
FIX_HINT_PRODUCTION = "Drop SoftDent Production by Provider report (production_*.csv), then Sync."

def ingest_softdent_production(bundle: dict, db_path: Path | None = None):
    rows = _section_rows(bundle, "production")  # filename pattern contract
    if not rows:
        return {"gap": GAP_PRODUCTION_PENDING, "fixHint": FIX_HINT_PRODUCTION}
    # Normalize: handle $ and commas, validate required cols (Provider, ProcCode, Amount)
    # Insert into softdent_production
    # Return {"ok": True, "rows": len(rows)}
```

### Phase T1 — SoftDent Patient Aging & Scheduling (MUST)
**CONSULT ONLY — Schema Addition**
```python
"""
CREATE TABLE IF NOT EXISTS softdent_patient_aging (
    period TEXT NOT NULL,
    bucket_0_30 REAL,
    bucket_31_60 REAL,
    bucket_61_90 REAL,
    bucket_90_plus REAL,
    total_ar REAL,
    source_file TEXT,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS softdent_scheduling (
    period TEXT NOT NULL,
    total_appointments INTEGER,
    broken_appointments INTEGER,
    fill_rate REAL,  -- 0.0-1.0
    capacity_hours REAL,
    used_hours REAL,
    source_file TEXT,
    ingested_at TEXT
);
"""
```

**CONSULT ONLY — Parser Notes**
*   Patient Aging: Expect SoftDent "Insurance Aging" or "Patient Aging" summary export (not detail to minimize PHI exposure). Parse bucket totals only.
*   Scheduling: Expect "Appointment Analysis" or "Schedule Report" export. Calculate fill rate = used_hours / capacity_hours.

### Phase T2 — QuickBooks Net Profit (MUST)
**CONSULT ONLY — Schema Addition**
```python
"""
CREATE TABLE IF NOT EXISTS qb_net_profit (
    period TEXT NOT NULL PRIMARY KEY,
    total_income REAL,
    total_expenses REAL,
    total_payroll REAL,
    net_profit REAL,
    source_file TEXT,
    ingested_at TEXT
);
"""
```

**CONSULT ONLY — Parser Sketch**
*   Ingest QB P&L Summary (monthly) or calculate from existing `qb_expense_rows` + `qb_payroll_rows` + income accounts if QB export unavailable.
*   Gap code: `NET_PROFIT_PENDING` when neither P&L export nor sufficient detail rows exist.

### Phase T3 — File System Watcher & Import Automation (SHOULD)
**CONSULT ONLY — Watcher Sketch (`apex_import_watcher_pack.py`)**
```python
# Windows-specific; uses `watchdog` or `win32file` (ReadDirectoryChangesW)
# CONSULT ONLY
from pathlib import Path
import time
from watchdog.observers import Observer  # dependency: pip install watchdog
from watchdog.events import FileSystemEventHandler

WATCH_PATH = Path("app_data/nr2/import_inbox")

class ImportHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.csv', '.xlsx', '.xls')):
            # Debounce 2s, then queue to existing import_loader
            time.sleep(2)
            queue_import(event.src_path)

def start_watcher():
    observer = Observer()
    observer.schedule(ImportHandler(), str(WATCH_PATH), recursive=False)
    observer.start()
    return observer
```
*   **Alternative**: Windows Task Scheduler every 5 minutes calling `python -m apex_import_poll` if watchdog dependency unwanted.

### Phase T4 — Cross-Reference Views & Widget Binding (SHOULD)
**CONSULT ONLY — SQL View Sketch**
```sql
-- Add to apex_unified_db_pack.py _ensure_schema()
"""
CREATE VIEW IF NOT EXISTS v_production_vs_payroll AS
SELECT 
    p.period,
    COALESCE(SUM(p.production_amount), 0) as total_production,
    COALESCE(SUM(py.gross_pay), 0) as total_payroll,
    CASE 
        WHEN SUM(p.production_amount) > 0 
        THEN ROUND(SUM(py.gross_pay) / SUM(p.production_amount), 4)
        ELSE NULL 
    END as payroll_to_production_ratio
FROM softdent_production p
LEFT JOIN qb_payroll_rows py ON p.period = py.period
GROUP BY p.period;
"""
```
*   **Widget Binding**: Extend `hal-ai-insight` widget to render `v_production_vs_payroll` ratios when 30B lane returns `type: "efficiency_audit"`.

### Phase T5 — Orchestrator Default ON (GA Flip) (NICE/DECISION)
**CONSULT ONLY — One-Line Change**
```python
# In apex_orchestrator_pack.py
def orchestrator_enabled() -> bool:
    raw = str(os.getenv("NR2_AI_ORCHESTRATOR") or "").strip().lower()
    # CURRENT: defaults OFF
    # PROPOSED: default ON unless explicitly disabled
    return raw not in {"0", "false", "no", "off"}  # CONSULT ONLY
```
*   **Requirement**: 7-day burn-in with current opt-in usage before flip.

---

## 5. MUST / SHOULD / NICE ranked table (remaining)

| Priority | Item | Effort | Phase | Business Impact |
|----------|------|--------|-------|-----------------|
| **MUST** | SoftDent Production parser + unified table | M | T0 | Core metric for 30B forecasting |
| **MUST** | SoftDent Patient Aging parser + unified table | M | T1 | AR visibility for cash flow audits |
| **MUST** | QuickBooks Net Profit parser + unified table | S | T2 | Enables true "net profit" health audits |
| **SHOULD** | File system watcher for auto-import | L | T3 | Eliminates manual Sync clicks |
| **SHOULD** | Cross-reference SQL views (SD×QB) | S | T4 | Enables deep 30B reconciliation queries |
| **SHOULD** | Widget bindings for new metrics | M | T4 | Visualize production/aging in dashboard |
| **NICE** | SoftDent Case Acceptance parser | M | T0/T1 | Treatment plan efficiency metric |
| **NICE** | SoftDent Scheduling metrics parser | M | T1 | Operational efficiency (fill rate) |
| **NICE** | Orchestrator default ON | XS | T5 | Product decision; requires burn-in validation |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

**Risks**
*   **File Watcher Lock**: Windows may lock CSV files during SoftDent export; implement 2-second debounce and retry loop (max 3 attempts).
*   **Schema Migration**: Adding tables to `nr2_unified.db` is additive and safe; no migration scripts needed (SQLite `CREATE TABLE IF NOT EXISTS`).

**PHI Handling**
*   **Patient Aging**: Ensure exports are *summary* level (bucket totals) not patient detail. If detail export required, hash PatientID before storage; never store names/DOB.
*   **SSN**: Continue redacting in QB payroll (already implemented in S0).

**SoftDent Honesty**
*   All new parsers must return gap codes (e.g., `PRODUCTION_PENDING`, `AGING_PENDING`) when exports missing; never synthesize `$0` in UI.
*   No write-back: Production/aging parsers are read-only; any "post to SoftDent" proposals require manual user action.

**Rollback**
*   **Per-Phase**: Delete specific table from `nr2_unified.db` to rollback that metric.
*   **Orchestrator**: Set `NR2_AI_ORCHESTRATOR=0` to revert to pre-I0 evaluate-query path instantly.
*   **SSE**: Remove `nr2-insight-sse.js` script tag to revert to manual refresh.

---

## 7. Approval Checklist (next wave only)

- [ ] **Approve MUST gaps**: SoftDent Production, Patient Aging, and QuickBooks Net Profit parsers (Phases T0–T2).
- [ ] **Approve SHOULD gap**: File system watcher implementation (Phase T3) vs. continue manual Sync.
- [ ] **Confirm PHI policy**: Patient Aging export will be summary-level only (no patient names in CSV).
- [ ] **Confirm SoftDent honesty**: All new parsers return gap codes when exports missing (never `$0`).
- [ ] **Orchestrator GA Decision**: Confirm 7-day burn-in completed with current opt-in usage before flipping `NR2_AI_ORCHESTRATOR` default ON (Phase T5).
- [ ] **Staging test**: Validate T0–T2 parsers against sample SoftDent/QB exports in `test_data/` before production.
- [ ] **Rollback plan**: Confirm OK to drop `nr2_unified.db` tables if metrics need redesign.

**DO NOT APPLY until operator says "approve / proceed".**