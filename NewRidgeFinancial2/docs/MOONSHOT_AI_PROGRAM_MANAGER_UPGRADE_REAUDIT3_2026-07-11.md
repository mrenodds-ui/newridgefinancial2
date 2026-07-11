# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #3 (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10481 (post I0–I4 + S0–S3 + N0 + T0–T5)  
**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT2_2026-07-11.md`  
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

# Verdict — AI Program Manager re-audit #3 (post T0–T5 / hal-10481)

## 0. Operator Intent (quote; note truncation; consult-only re-run)

> You are an expert senior full-stack engineer, data architect, and AI systems integrator specializing in dental practice management software. 
I need you to audit, refactor, and massively upgrade my self-built dental practice financial dashboard. This dashboard is running in Chrome and integrates with SoftDent (via exports) and QuickBooks. It uses local/API-connected 8B and 30B LLMs. 
Currently, the SoftDent and QuickBooks integration is only partially functional via manual exports. I want this system to become fully functional, highly polished, beautifully organized, and driven by my AI models acting as the core "program manager."
Please evaluate my existing codebase and provide the complete, production-ready code to achieve the following:
> ### 1. AI Models as Program Manager (8B & 30B Integration)
> * Establish a clear hierarchy: Use the 8B model for fast, real-time widget data parsing, text summaries, and UI UI-routing triggers. Use the 30B model for deep financial forecasting, cross-referencing SoftDent ledger data with QuickBooks, and generating monthly practice health audits.
> * Build an "AI Orchestrator" middleware layer that routes user queries or data updates to the correct model.
> * Implement structured JSON outputs from the LLMs so the dashboard widgets can read and render the AI's insights dynamically without breaking the UI.
> ### 2. Full SoftDent & QuickBooks Data Automation
> * Build robust, fault-tolerant parsers for SoftDent and QuickBooks CSV/Excel exports.
> * Map SoftDent data (production, collection, case acceptance, patient aging, scheduling metrics) and QuickBooks data (expenses, payroll, net profit, accounts payable) into a unified local database/state management system (e.g.,

**Note:** Message truncated at `unified local database/state management system (e.g.,`.  
**Assumption:** Operator intends **SQLite/NR2 app_data/nr2_unified.db** as the unified local store (consistent with Phase I3/T-wave).  
**Status:** CONSULT ONLY — No code applied. Paste-ready sketches below await operator "approve / proceed".

---

## 1. Current Architecture Audit (what exists at hal-10481)

### 1A Model lanes & orchestrator (default ON)
- **Shipped:** `apex_orchestrator_pack.py` (I0) routes intents to `chat8b` (fast widget parse/summarize) vs `escalate30b` (deep cross-ref).
- **Shipped:** `NR2_AI_ORCHESTRATOR` defaults **ON** (T5); disable via `=0/false/no/off`.
- **Shipped:** Hybrid GPU layout pins `chat8b`+`escalate30b`; coder32b on-demand.
- **Gap:** Deep lane (`escalate30b`) routes queries but lacks a **structured "Monthly Practice Health Audit"** generator or **time-series forecasting** module using unified DB views.

### 1B SoftDent production/aging/scheduling + DEF-001 + ERA
- **Shipped:** `apex_softdent_production_pack.py` (T0) → `softdent_production`, `softdent_case_acceptance` with gap codes (`PRODUCTION_PENDING`, `CASE_ACCEPTANCE_PENDING`).
- **Shipped:** `apex_softdent_aging_schedule_pack.py` (T1) → aging buckets (summary totals, no PHI), scheduling metrics; gap codes (`AGING_PENDING`, `SCHEDULING_PENDING`).
- **Shipped:** ERA aggregates (S1) + `ERA_835_AVAILABLE` proposal (no parser).
- **Honesty:** Empty ≠ $0; no SoftDent write-back.

### 1C QuickBooks payroll/AP/net profit + expenses
- **Shipped:** QB payroll/AP with SSN redaction (S0).
- **Shipped:** `apex_qb_net_profit_pack.py` (T2) → `qb_net_profit` (P&L summary or derived); gap code `NET_PROFIT_PENDING`.
- **Shipped:** Expense ingestion to unified DB.

### 1D Unified DB + cross-ref views + practice_health_snapshot
- **Shipped:** `apex_unified_db_pack.py` (I3) → `nr2_unified.db` with tables: `softdent_period_metrics`, `qb_expense_rows`, `qb_payroll_rows`, `practice_health_snapshot`, `softdent_aging_summary`, `softdent_scheduling`, `era_835_available` (stub).
- **Shipped:** Views `v_production_vs_payroll`, `v_collection_vs_ap` (T4) for cross-reference.
- **Gap:** No **automated variance detection** or **AI explainer** consuming these views.

### 1E Structured insights + SSE + efficiency_audit binding
- **Shipped:** `apex_structured_insight_pack.py` (I1) → JSON schemas (`kpi-card`, `trend-chart`, `alert-banner`), PHI rejection (SSN/DOB), `source_refs` required.
- **Shipped:** `apex_insight_sse_pack.py` (N0) → `/api/apex/hal/insight-stream` (SSE) + `/insight-latest` (5s poll fallback).
- **Shipped:** `efficiency_audit` cross-reference binding on `hal-ai-insight` widget (T4).
- **Gap:** No **scheduled insight generation** (e.g., auto-emit monthly audit to SSE).

### 1F Import poll/watcher automation
- **Shipped:** `apex_import_watcher_pack.py` (T3) → `scripts/run_nr2_import_poll.py`, debounce 2s, retry ×3, queue to ingest.
- **Gap:** No **quarantine** for poisoned files; limited **Excel format auto-detection** (relies on consistent export templates).

---

## 2. Gap Map — REMAINING only

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **Deep Audit & Forecast** | Partial | No structured 30B module for monthly practice health audits or time-series forecasting; no scheduled trigger. | M | Unified DB views (exists) |
| **ERA 835 Ingestion** | Proposal only | No ERA 835 EDI/CSV parser; collections incomplete without remittance detail. | M | SoftDent import path |
| **Smart Reconciliation** | Views only | `v_production_vs_payroll` exists but no automated variance detection + AI explainer (30B). | S-M | Deep lane |
| **Import Resilience** | Basic retry | No quarantine for unparseable files; no admin alert on persistent failure. | S | Import watcher |
| **Dashboard Polish** | Functional | "Beautifully organized" layout engine not implemented; widgets static. | L | Frontend/SSE |

---

## 3. Target Architecture (next wave only)

**U0 — Deep Audit & Forecast Pack:** Structured 30B prompts for monthly health audits (variance analysis, trend forecasting) emitting schema-validated JSON to SSE. Scheduled execution via `run_nr2_import_poll.py` hook or cron.

**U1 — ERA 835 Ingestion Pack:** Parse ERA 835 EDI (or print-image CSV) into `era_835_payments` (aggregated by payer/CPT, no patient names) to close the collections loop.

**U2 — Reconciliation Engine Pack:** Background job comparing `v_production_vs_payroll` vs `v_collection_vs_ap`; auto-generates `alert-banner` insights via 30B when variance exceeds threshold.

**U3 — Dashboard Layout Pack:** Responsive grid system for HAL insights, draggable widgets, and "beautifully organized" CSS polish (consult-only sketch).

---

## 4. Coding Plan — Phase U0..Un (CONSULT ONLY sketches for remaining work)

### U0 — Deep Audit & Forecast Pack (CONSULT ONLY)
```python
# apex_deep_audit_pack.py
"""
Phase U0 — 30B Deep Lane: Monthly Practice Health Audit + Forecasting.
Structured JSON output → insight SSE. Never invent $; use gap codes if data missing.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from apex_unified_db_pack import open_unified
from apex_structured_insight_pack import validate_insight, save_insight

AUDIT_SYSTEM_PROMPT = (
    "You are a dental practice CFO AI. Using the provided unified DB snapshot "
    "(production, payroll, collections, AP, net profit), generate a Monthly Practice Health Audit. "
    "Output ONLY valid JSON matching schema: widget_type='alert-banner' or 'trend-chart', "
    "title, summary, data.values for last 6 months if available, source_refs for every number. "
    "If data is missing, set data=null and confidence='low' with gap_code like 'PRODUCTION_PENDING'. "
    "No PHI. No prose outside JSON."
)

def generate_monthly_audit(period: str | None = None) -> dict[str, Any]:
    period = period or datetime.now(timezone.utc).strftime("%Y-%m")
    with open_unified() as conn:
        # Fetch 6-month window
        cur = conn.execute(
            """SELECT * FROM v_production_vs_payroll 
               WHERE period >= ? ORDER BY period DESC LIMIT 6""",
            (f"{period[:5]}{int(period[5:7])-5:02d}",)  # naive 6mo back
        )
        rows = [dict(r) for r in cur.fetchall()]
    # Build context for 30B
    context = {"period": period, "rows": rows, "gap_codes": []}
    if not rows:
        context["gap_codes"].append("PRODUCTION_PENDING")
    # NOTE: Actual LLM call to escalate30b via existing orchestrator lane
    # payload = route_to_lane(query=AUDIT_SYSTEM_PROMPT, context=context, lane_hint="escalate30b")
    # insight = validate_insight(payload)
    # save_insight(insight)
    # return insight
    return {"status": "CONSULT_ONLY", "period": period, "row_count": len(rows)}

def forecast_next_quarter() -> dict[str, Any]:
    # Similar structure using time-series from unified DB
    pass
```

### U1 — ERA 835 Ingestion Pack (CONSULT ONLY)
```python
# apex_era835_pack.py
"""
Phase U1 — ERA 835 remittance parsing (EDI X12 835 or CSV print-image).
Aggregates only: payer, total_paid, adjustment_reasons (codes only), claim_count.
PHI: No patient names, account numbers, or DOB stored. SSN redacted if present.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GAP_ERA835_PENDING = "ERA835_PENDING"

def parse_era835_file(path: Path) -> dict[str, Any]:
    """
    CONSULT ONLY sketch.
    Detect EDI vs CSV by header. Extract:
    - payer_name
    - period (check_date)
    - total_paid
    - adjustment_reason_summary (code:count)
    - claim_count
    """
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if raw.startswith("ISA*"):  # X12 EDI
        return _parse_x12_835(raw)
    else:
        return _parse_csv_835(raw)

def _parse_x12_835(raw: str) -> dict[str, Any]:
    # Stub: regex for CLP segments (claim payment), PLB (provider adjustment)
    # Aggregate only; discard patient name (NM1*QC segments)
    return {"status": "CONSULT_ONLY", "format": "X12", "pending": True}

def _parse_csv_835(raw: str) -> dict[str, Any]:
    # Stub: pandas read_csv, map columns, aggregate
    return {"status": "CONSULT_ONLY", "format": "CSV", "pending": True}

def ingest_era835_to_unified(path: Path) -> dict[str, Any]:
    parsed = parse_era835_file(path)
    if parsed.get("pending"):
        return {"ok": False, "gap": GAP_ERA835_PENDING, "fix_hint": "ERA 835 file unreadable or missing required columns."}
    # Insert into nr2_unified.db table era_835_payments (aggregated)
    # from apex_unified_db_pack import open_unified; ...
    return {"ok": True, "period": parsed.get("period")}
```

### U2 — Reconciliation Engine Pack (CONSULT ONLY)
```python
# apex_reconciliation_pack.py
"""
Phase U2 — Automated variance detection + AI explainer.
Compares SoftDent vs QB via v_production_vs_payroll and v_collection_vs_ap.
If variance > threshold (e.g., 5% or $500), generate 30B insight explaining likely cause.
"""
from __future__ import annotations
from apex_unified_db_pack import open_unified
from apex_structured_insight_pack import validate_insight, save_insight
from apex_orchestrator_pack import route_to_lane

VARIANCE_THRESHOLD_PCT = 0.05
VARIANCE_THRESHOLD_ABS = 500.0

def check_variance(period: str) -> dict[str, Any] | None:
    with open_unified() as conn:
        row = conn.execute(
            "SELECT * FROM v_production_vs_payroll WHERE period = ?", (period,)
        ).fetchone()
    if not row:
        return None
    diff = float(row["production"] or 0) - float(row["payroll"] or 0)
    pct = abs(diff) / max(float(row["production"] or 1), 1)
    if pct > VARIANCE_THRESHOLD_PCT or abs(diff) > VARIANCE_THRESHOLD_ABS:
        prompt = (
            f"Explain why production (${row['production']}) and payroll (${row['payroll']}) "
            f"differ by ${diff:.2f} for period {period}. Consider timing, bonuses, or data latency. "
            f"Output structured JSON insight widget_type='alert-banner'."
        )
        # insight = route_to_lane(query=prompt, lane_hint="escalate30b")
        # return validate_insight(insight)
        return {"status": "CONSULT_ONLY", "period": period, "diff": diff}
    return None
```

### U3 — Dashboard Layout Pack (CONSULT ONLY)
```python
# apex_dashboard_layout_pack.py
"""
Phase U3 — Responsive grid layout engine for 'beautifully organized' HAL dashboard.
Consumes structured insights; allows drag-drop configuration persisted to localStorage (frontend).
Backend provides layout schema endpoint.
"""
from __future__ import annotations
from typing import Any

DEFAULT_LAYOUT = {
    "grid": [
        {"id": "hal-ai-insight", "x": 0, "y": 0, "w": 12, "h": 4},
        {"id": "production-widget", "x": 0, "y": 4, "w": 6, "h": 4},
        {"id": "collections-widget", "x": 6, "y": 4, "w": 6, "h": 4},
        {"id": "qb-payroll", "x": 0, "y": 8, "w": 6, "h": 4},
        {"id": "aging-buckets", "x": 6, "y": 8, "w": 6, "h": 4},
    ],
    "theme": "starship-bridge-dark"
}

def get_layout(user_id: str | None = None) -> dict[str, Any]:
    # Stub: load from nr2_unified.db user_prefs or return default
    return DEFAULT_LAYOUT

def save_layout(user_id: str, layout: dict[str, Any]) -> dict[str, Any]:
    # Stub: persist layout JSON
    return {"ok": True, "user_id": user_id}
```

---

## 5. MUST / SHOULD / NICE ranked table (remaining)

| Rank | Phase | Deliverable | Effort | Business Value |
|------|-------|-------------|--------|----------------|
| **MUST** | U0 | Deep Audit & Forecast Pack (30B structured monthly audits) | M | Core "Program Manager" value; closes operator requirement for deep analysis. |
| **SHOULD** | U1 | ERA 835 Ingestion Pack | M | Completes collections automation; required for accurate reconciliation. |
| **SHOULD** | U2 | Reconciliation Engine (variance detection + explainer) | S-M | Automates cross-ref insight; uses existing views. |
| **SHOULD** | U2b | Import Quarantine & Alerting | S | Robustness for "fault-tolerant" requirement. |
| **NICE** | U3 | Dashboard Layout Polish | L | "Beautifully organized" UI; purely cosmetic. |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

- **PHI:** ERA 835 files contain patient names and account numbers. U1 must **aggregate immediately** and store only payer-level totals + adjustment reason codes. Never persist patient identifiers to `nr2_unified.db`. SSN redaction (existing) applies.
- **SoftDent Honesty:** No write-back to SoftDent. ERA 835 gaps must use code `ERA835_PENDING`, not $0.
- **Rollback:** Each U-phase wrapped in feature flag (`NR2_DEEP_AUDIT=1`, `NR2_ERA835=1`). Disable via env to revert to T5 behavior.
- **Staging:** U0–U2 require burn-in with historical exports before trusting 30B forecasts.
- **Risk:** ERA 835 EDI parsing is complex; fallback to "print image" CSV exports from SoftDent may be necessary if EDI schema varies by payer.

---

## 7. Approval Checklist (next wave only)

- [ ] **Confirm U0 scope:** Should monthly audits run automatically (cron) or on-demand via HAL chat only?
- [ ] **Approve U1 PHI handling:** Confirm ERA 835 aggregation rules (no patient names stored) acceptable.
- [ ] **Set variance thresholds:** Define % or $ thresholds for U2 reconciliation alerts (default 5% / $500).
- [ ] **Prioritize U3:** Is dashboard layout polish required now, or defer until after U0–U2 stable?
- [ ] **Staging plan:** Provide 3 months of historical SoftDent + QB + ERA exports for U0/U1 validation.

**DO NOT APPLY until operator says approve / proceed.**