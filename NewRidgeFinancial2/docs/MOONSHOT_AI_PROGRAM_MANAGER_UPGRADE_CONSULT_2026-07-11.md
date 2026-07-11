# Moonshot AI — AI Program Manager + SoftDent/QB Automation Upgrade (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10470  
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

# Verdict — Path to AI Program Manager + full SoftDent/QB automation

## 0. Operator Intent (quote; note truncation; consult-only)

> *"I need you to audit, refactor, and massively upgrade my self-built dental practice financial dashboard... I want this system to become fully functional, highly polished, beautifully organized, and driven by my AI models acting as the core 'program manager.'... Build an 'AI Orchestrator' middleware layer... Implement structured JSON outputs from the LLMs... Full SoftDent & QuickBooks Data Automation... unified local database/state management system (e.g.,"*

**Note:** Message truncated at "unified local database/state management system (e.g.,".  
**Assumption:** Operator intends **SQLite/LocalStore/NR2 app_data** as the unified local store (consistent with existing `nr2_local_db.py`, `local_store.py`, and import cache architecture).  

**Status:** CONSULT ONLY — No code applied. Paste-ready sketches provided below await operator "approve / proceed".

---

## 1. Current Architecture Audit (what exists at hal-10470)

### 1A Model lanes & routing (8B/30B)
- **GPU Layout (R9700 32 GB):** `hal-chat:8b` (chat8b lane) + `hal-escalate:30b` (escalate30b/reason21b lanes) pinned via Ollama on `127.0.0.1:11434`. Optional `qwen2.5-coder:32b` on-demand (`hal-models.json`: `hybridGpuLayout`).
- **Routing:** Deterministic **board-actions first** (`apex_backend.resolve_hal_board_actions`) → if no match, `/api/hal/evaluate-query` → `nr2_hal_gateway.route_by_complexity()` → lane selection (`chat8b`, `reason21b`, `escalate30b`).
- **Pre-route patterns:** Regex-based intent detection (`hal-core.js` preRoute) for escalation, research, narrative drafting, import checks. No structured JSON schema enforcement on outputs yet.
- **Gap:** No formal "AI Orchestrator" middleware; routing is split between client-side preRoute and server-side gateway. No structured output contracts for widget consumption.

### 1B SoftDent import automation
- **Direct-First Mode (default):** `import_sync.py` scans upstream export roots (`C:\SoftDentBridge\exports`, `C:\SoftDentFinancialExports`, Sensei DataSync) before cache fallback.
- **Parser coverage:** Register (production), Daysheet/Collections (insurance/patient split), Claims, A/R Aging, Hygiene Recall, Treatment Plans, New Patients, Case Acceptance (`import_contract.py` name maps).
- **Known gap:** **DEF-001** (hal-10470 consult) — Collections/Daysheet export missing causes `revenue-composition` widget empty; insurance/patient split pending until export available.
- **Honesty:** Empty KPIs when imports missing; no SoftDent write-back.

### 1C QuickBooks import automation
- **Current:** P&L style imports via `quickbooks_import_dir`; expense categories mapped in `import_contract.py` (`QUICKBOOKS_EXPENSE_NAMES`, `QUICKBOOKS_EXPENSE_CATEGORY_NAMES`).
- **Gap:** Payroll detail, Accounts Payable aging, and net profit drill-down may be partial or require manual CSV/Excel exports; no automated AP/payroll ledger sync like SoftDent Direct-First.

### 1D Unified local state (LocalStore / SQLite / bundles)
- **SQLite:** `nr2_local_db.py` — tasks, huddle history, collection notes, payer guidelines.
- **LocalStore:** Browser `localStorage` for session tokens, HAL history, UI state.
- **Import bundles:** `import_loader.py` assembles JSON bundles for HAL consumption; cache TTL 90s.
- **Gap:** Not a unified warehouse — SoftDent data lives in import bundles, QB in separate imports, tasks in SQLite, UI state in LocalStore. Cross-reference queries (e.g., "compare production to payroll") require runtime assembly rather than SQL joins.

### 1E Apex widget honesty / structured payloads
- **Widget safety:** `resolve_hal_board_actions` explicitly rejects inventing dollar amounts; actions limited to focus/highlight/navigate/sync.
- **Payloads:** HAL returns markdown/text; widgets parse raw text for insights. No JSON schema validation for AI-generated KPIs.
- **Gap:** No structured JSON insight schema — widgets cannot dynamically render AI-generated charts/alerts without brittle regex parsing.

---

## 2. Gap Map (CURRENT → TARGET)

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **AI Orchestrator** | Board-actions + gateway split | Middleware layer with intent router, context manager, structured output validator | M (3d) | None |
| **8B/30B Hierarchy** | Regex preRoute + complexity heuristics | Formal lane contracts: 8B for widget parse/summary/routing (latency <500ms), 30B for forecast/audit/cross-reference (depth >10s) | S (2d) | Orchestrator |
| **Structured JSON Outputs** | Markdown/text only | JSON schema per widget type (kpi-card, trend-chart, alert-banner) with source citations | M (3d) | Orchestrator |
| **SoftDent Parser Hardening** | Direct-First + CSV fallback | Fault-tolerant Collections/Daysheet gap handling (DEF-001), ERA 835 parser (DEF-005), auto-export detection | M (3d) | None |
| **QuickBooks Automation** | Manual export dependent | Automated payroll/AP/net profit mapping; scheduled QB SDK pulls | L (5d) | Unified DB |
| **Unified State** | Fragmented (bundles + SQLite + LocalStore) | Single local warehouse: `nr2_unified.db` with views joining SoftDent production, QB expenses, tasks, payroll | M (4d) | QB Automation |
| **Proactive AI** | Reactive only (DEF-007) | Background health monitor: stale import alerts, daily briefing generation | S (2d) | Orchestrator |
| **Widget Dynamic Rendering** | Static HTML + HAL text | JSON-driven widget updates without page reload (Apex reactive bindings) | M (3d) | Structured JSON |

---

## 3. Target Architecture (AI Orchestrator + data plane)

```
┌─────────────────────────────────────────────────────────────┐
│  UI Layer (Chrome/HTTPS 127.0.0.1:8765)                     │
│  ├─ Board Actions (deterministic: sync, nav, focus)        │
│  ├─ Widget Container (reactive JSON binding)               │
│  └─ HAL Chat Panel (streaming)                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│  AI Orchestrator Middleware (apex_orchestrator_pack.py)    │
│  ├─ Intent Router (8B fast classify → lane select)         │
│  ├─ Context Manager (session state + unified DB snapshot)  │
│  ├─ Lane Dispatcher (8B/30B/coder32b)                      │
│  └─ Output Validator (JSON schema enforcement)             │
└──────────────────┬──────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐
│ chat8b  │  │escalate30b│  │coder32b  │
│(fast)   │  │(deep)     │  │(on-demand)│
└────┬────┘  └────┬─────┘  └────┬─────┘
     │            │             │
     └────────────┴─────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│  Structured JSON Insights (apex_structured_insight_pack.py) │
│  ├─ schema/kpi-card.json (value, delta, source_ref)        │
│  ├─ schema/trend-chart.json (series[], annotations)        │
│  └─ schema/alert-banner.json (severity, action_cta)        │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│  Unified Local Data Plane (SQLite + Import Cache)          │
│  ├─ softdent_ledger (production, collections, adjustments) │
│  ├─ qb_ledger (expenses, payroll, ap)                      │
│  ├─ tasks_notes (SQLite existing)                          │
│  └─ import_health (staleness timestamps)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Coding Plan — Phase I0..In (CONSULT ONLY sketches)

### Phase I0: Foundation — Orchestrator Shell & Schema Definitions
**Duration:** 2 days  
**Validation:** Orchestrator responds to `/api/orchestrator/route` with correct lane selection.

```python
# CONSULT ONLY: apex_orchestrator_pack.py (skeleton)
"""
AI Orchestrator Middleware — Program Manager layer for NR2.
Routes queries to appropriate lane (8B/30B) and enforces structured outputs.
"""
import json
import re
from typing import Any, Literal
from pydantic import BaseModel, ValidationError  # add to requirements

LaneType = Literal["chat8b", "reason21b", "escalate30b", "coder32b"]

class InsightPayload(BaseModel):
    widget_type: Literal["kpi-card", "trend-chart", "alert-banner", "table"]
    title: str
    data: dict
    source_refs: list[str]  # e.g., ["softdent:register:2026-07-11", "qb:p&l:2026-07"]
    confidence: Literal["high", "medium", "low"]
    generated_at: str  # ISO timestamp

class Orchestrator:
    def __init__(self, store, hal_gateway):
        self.store = store
        self.gateway = hal_gateway
    
    def classify_intent(self, query: str, context: dict) -> tuple[LaneType, int]:
        """Fast 8B classification for routing decision."""
        # Fast path: widget parsing, navigation = chat8b
        if re.search(r'\b(parse|summarize|highlight|focus)\b', query, re.I):
            return "chat8b", 200
        # Deep path: forecast, audit, cross-reference = escalate30b
        if re.search(r'\b(forecast|audit|cross.reference|compare.*with|why.*trend)\b', query, re.I):
            return "escalate30b", 30000
        return "reason21b", 8000
    
    def execute(self, query: str, context: dict) -> dict:
        lane, timeout = self.classify_intent(query, context)
        # Call existing gateway with structured output request
        raw = self.gateway.evaluate_query_structured(
            query=query, 
            lane=lane,
            schema_hint=InsightPayload.schema(),
            timeout_ms=timeout
        )
        try:
            validated = InsightPayload(**json.loads(raw["text"]))
            return {"ok": True, "insight": validated.dict(), "lane": lane}
        except (ValidationError, json.JSONDecodeError):
            # Fallback to markdown if structured fails
            return {"ok": True, "text": raw["text"], "lane": lane, "structured": False}
```

### Phase I1: SoftDent Parser Hardening (DEF-001, DEF-005)
**Duration:** 3 days  
**Validation:** Collections/Daysheet gap triggers graceful degradation; ERA 835 parser recognizes payment loops.

```python
# CONSULT ONLY: apex_softdent_hardening_pack.py
"""
Fault-tolerant SoftDent import with ERA 835 support.
"""
from pathlib import Path
from typing import Optional
import csv
import json

class SoftDentImportHardening:
    def __init__(self, sync_module):
        self.sync = sync_module
        self.required_exports = ["register", "collections", "daysheet", "claims"]
    
    def detect_gaps(self, period: str) -> dict:
        """Identify missing exports (DEF-001 mitigation)."""
        found = self.sync.scan_upstream(period)
        gaps = [r for r in self.required_exports if r not in found]
        return {
            "period": period,
            "gaps": gaps,
            "fallback_available": bool(self.sync.get_cache(period)),
            "health_status": "degraded" if gaps else "healthy"
        }
    
    def parse_collections_split(self, filepath: Path) -> dict:
        """Extract insurance vs patient split with validation."""
        # Defensive CSV parsing with dialect detection
        rows = []
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            dialect = csv.Sniffer().sniff(f.read(4096))
            f.seek(0)
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                # Validate required fields exist
                if not any(k in row for k in ['Amount', 'Payment']):
                    raise ValueError(f"Collections file missing amount fields: {filepath}")
                rows.append(row)
        return {"insurance_total": sum(...), "patient_total": sum(...), "row_count": len(rows)}
    
    def ingest_era_835(self, filepath: Path) -> list[dict]:
        """Parse ERA 835 for payment-to-claim matching (DEF-005)."""
        # Placeholder for X12 835 parsing logic
        # Returns list of {claim_id, paid_amount, adjustment_reasons, check_date}
        pass
```

### Phase I2: QuickBooks Automation Expansion
**Duration:** 4 days  
**Validation:** Payroll and AP appear in unified queries; no manual CSV export required for month-end.

```python
# CONSULT ONLY: apex_qb_automation_pack.py
"""
QuickBooks Direct-First automation for expenses, payroll, AP.
"""
class QBAutomation:
    def __init__(self, sdk_path: Optional[Path] = None):
        self.sdk_path = sdk_path or Path("C:/QuickBooksExports")
    
    def map_expense_categories(self, qb_pl_data: list[dict]) -> dict:
        """Map QB Chart of Accounts to dental practice categories."""
        category_map = {
            "Dental Supplies": "variable_clinical",
            "Payroll Salaries": "fixed_payroll",
            "Lab Expenses": "variable_lab",
            "Rent": "fixed_facility",
            "Marketing": "variable_marketing"
        }
        return {cat: sum(row['Amount'] for row in qb_pl_data if row['Account'] == cat) 
                for cat in category_map}
    
    def extract_payroll_detail(self, payroll_export: Path) -> list[dict]:
        """Parse payroll register for labor cost allocation."""
        # Handles QB Payroll Summary exports
        pass
    
    def calculate_net_profit_waterfall(self, production: float, expenses: dict) -> dict:
        """Reconcile SoftDent production to QB net profit."""
        return {
            "production": production,
            "total_expenses": sum(expenses.values()),
            "net_profit": production - sum(expenses.values()),
            "variance_note": "Exclude non-operating income"
        }
```

### Phase I3: Unified Local Database Schema
**Duration:** 3 days  
**Validation:** SQL JOIN between SoftDent production and QB payroll returns correct labor %.

```sql
-- CONSULT ONLY: schema/unified_state_v1.sql
-- Migration for nr2_unified.db (evolves nr2_local_db.py)

CREATE TABLE IF NOT EXISTS unified_production (
    id INTEGER PRIMARY KEY,
    period TEXT NOT NULL,
    provider TEXT,
    production_amount REAL,
    collection_amount REAL,
    adjustment_amount REAL,
    source_file TEXT,
    imported_at TEXT
);

CREATE TABLE IF NOT EXISTS unified_expenses (
    id INTEGER PRIMARY KEY,
    period TEXT NOT NULL,
    category TEXT NOT NULL,
    vendor TEXT,
    amount REAL,
    qb_account TEXT,
    source_file TEXT,
    imported_at TEXT
);

CREATE TABLE IF NOT EXISTS unified_payroll (
    id INTEGER PRIMARY KEY,
    period TEXT NOT NULL,
    employee_initials TEXT,
    gross_pay REAL,
    taxes REAL,
    net_pay REAL,
    allocation_dept TEXT  -- 'clinical', 'admin', 'hygiene'
);

-- View for AI Program Manager queries
CREATE VIEW IF NOT EXISTS practice_health_snapshot AS
SELECT 
    p.period,
    p.production_amount,
    p.collection_amount,
    COALESCE(SUM(e.amount), 0) as total_expenses,
    COALESCE(SUM(py.gross_pay), 0) as total_labor,
    p.collection_amount - COALESCE(SUM(e.amount), 0) as net_operating
FROM unified_production p
LEFT JOIN unified_expenses e ON p.period = e.period
LEFT JOIN unified_payroll py ON p.period = py.period
GROUP BY p.period;

CREATE TABLE IF NOT EXISTS import_health_log (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,  -- 'softdent', 'quickbooks'
    export_type TEXT NOT NULL,
    file_path TEXT,
    row_count INTEGER,
    staleness_hours REAL,
    detected_at TEXT,
    gap_flags TEXT  -- JSON array of missing exports
);
```

### Phase I4: Structured JSON Insight Schemas
**Duration:** 3 days  
**Validation:** 30B model output passes schema validation and renders in EBITDA widget without page reload.

```json
// CONSULT ONLY: schema/insight-kpi-card.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "KPI Card Insight",
  "type": "object",
  "required": ["widget_type", "title", "data", "source_refs", "confidence"],
  "properties": {
    "widget_type": {"const": "kpi-card"},
    "title": {"type": "string"},
    "data": {
      "type": "object",
      "properties": {
        "value": {"type": "number"},
        "unit": {"type": "string", "enum": ["dollars", "percent", "count", "days"]},
        "trend_direction": {"type": "string", "enum": ["up", "down", "flat"]},
        "trend_percent": {"type": "number"},
        "benchmark": {"type": "number"}
      }
    },
    "source_refs": {
      "type": "array",
      "items": {"type": "string", "pattern": "^(softdent|qb):[a-z_]+:\\d{4}-\\d{2}(-\\d{2})?$"}
    },
    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    "explanation": {"type": "string", "maxLength": 280},
    "action_cta": {
      "type": "object",
      "properties": {
        "label": {"type": "string"},
        "route": {"type": "string", "enum": ["#financial", "#claims", "#ar"]},
        "query_params": {"type": "object"}
      }
    }
  }
}
```

```python
# CONSULT ONLY: apex_structured_insight_pack.py
"""
Structured output enforcement for HAL insights.
"""
class StructuredInsightGenerator:
    def __init__(self, orchestrator):
        self.orch = orchestrator
    
    def generate_monthly_audit(self, period: str) -> dict:
        """30B deep analysis with structured output."""
        prompt = f"""Analyze practice health for {period} using unified_production and unified_expenses.
Return ONLY valid JSON matching the kpi-card and trend-chart schemas.
Include source_refs for every number."""
        
        result = self.orch.execute(prompt, {"period": period, "require_structured": True})
        return result["insight"] if result.get("structured") else {"error": "structured_output_failed", "raw": result.get("text")}
```

### Phase I5: Integration & Validation Gates
**Duration:** 2 days  
**Validation Gates:**
1. **Import Health Gate:** `Verify-HAL-Readiness.ps1` confirms no gaps before month-end close.
2. **Lane Accuracy Gate:** Unit tests assert "forecast" queries route to escalate30b, "parse" to chat8b.
3. **PHI Safety Gate:** Structured outputs scrubbed by `nr2_browser_security.classify_financial_query` before display.
4. **Widget Render Gate:** JSON insights render in existing Apex widgets without HTML injection.

---

## 5. MUST / SHOULD / NICE ranked table

| Priority | ID | Item | Effort | Business Impact |
|----------|-----|------|--------|-----------------|
| **MUST** | M1 | **AI Orchestrator middleware** with lane routing (8B fast/30B deep) | M (3d) | Enables reliable Program Manager hierarchy |
| **MUST** | M2 | **Structured JSON schema** for widget-safe AI insights | M (3d) | Prevents UI breaks from markdown drift |
| **MUST** | M3 | **SoftDent Collections/Daysheet gap handling** (DEF-001) | S (2d) | Fixes empty revenue-composition widget |
| **MUST** | M4 | **Unified DB schema** (production + expenses + payroll views) | M (4d) | Enables cross-reference queries |
| **SHOULD** | S1 | **ERA 835 parser** for auto-match (DEF-005) | L (5d) | Reduces manual payment posting |
| **SHOULD** | S2 | **QuickBooks payroll/AP automation** | L (5d) | Eliminates manual QB exports for month-end |
| **SHOULD** | S3 | **Proactive health monitor** (stale import alerts) | S (2d) | Prevents decisions on stale data |
| **NICE** | N1 | **Voice-to-action** integration with orchestrator | M (3d) | Hands-free HAL commands |
| **NICE** | N2 | **Predictive cash flow** (30B forecast model) | L (5d) | 90-day A/R prediction |

---

## 6. Risks, PHI, SoftDent Honesty, Rollback

### Risks & Mitigations
- **Structured Output Failure:** LLM may return invalid JSON. **Mitigation:** Graceful fallback to markdown (Phase I0 code shows try/except); widget displays "AI insight unavailable" rather than crash.
- **Import Staleness Cascade:** Unified DB queries return stale joins if one source missing. **Mitigation:** `import_health_log` table tracks staleness; queries include `staleness_hours` filter; amber banners when >24h.
- **GPU Memory Exhaustion:** 30B + coder32b simultaneous load may OOM. **Mitigation:** Maintain "neverPin" list for 235B models; orchestrator queues deep requests if GPU busy.

### PHI & Compliance
- **Local-Only Enforcement:** Unified DB stays in `app_data/nr2/`; no replication.
- **PHI in AI Context:** Orchestrator passes only claim IDs + anonymized hashes to LLM context (per `apex_backend.py` current practice); full patient names never reach 8B/30B prompts.
- **Structured Output Sanitization:** JSON schemas reject fields matching SSN/DOB patterns before storage.

### SoftDent Honesty
- **No Write-Back Guarantee:** Orchestrator actions explicitly exclude `writeback`, `post`, `update` verbs (per `nr2_hal_gateway.py` `_OUTBOUND_ACTION_RE` patterns).
- **Empty Widget Policy:** If Collections export missing, widget shows "Import pending — showing Register-only view" rather than interpolated data.

### Rollback Plan
1. **Database:** `nr2_unified.db` is additive; original `nr2_local.sqlite3` untouched. Rollback = remove unified db, revert to bundle-based imports.
2. **Orchestrator:** Feature-flagged via `NR2_AI_ORCHESTRATOR=0` env var; falls back to existing `evaluate-query` endpoint.
3. **Parsers:** New parsers run in parallel with old; diff validation before switchover.

---

## 7. Approval Checklist

**DO NOT PROCEED until operator confirms:**

- [ ] **Scope Confirm:** Proceed with Phase I0–I5 as sketched (Orchestrator → Structured → SoftDent Hardening → QB Automation → Unified DB)?
- [ ] **Truncation Assumption:** Confirm SQLite/LocalStore is acceptable unified store (vs PostgreSQL/MongoDB)?
- [ ] **QB Access:** Confirm QuickBooks SDK/export paths for payroll/AP automation (`C:\QuickBooksExports` or different)?
- [ ] **ERA 835:** Confirm need for ERA parsing (Phase S1) vs current SoftDent ERA handling?
- [ ] **PHI Boundaries:** Confirm acceptable to pass claim IDs + anonymized hashes to local 30B model (no full names)?
- [ ] **Rollback OK:** Confirm additive approach (new tables/files) acceptable; no in-place migration of existing SQLite schema?
- [ ] **Start Phase:** Which phase to begin? (Recommend I0: Orchestrator shell)

**Operator instruction to proceed:** Reply with "approve Phase I0" or "approve all phases" or specific modifications.  
**Status:** Awaiting operator approval. No code changes applied to hal-10470.