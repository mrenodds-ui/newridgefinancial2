# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #4 (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10486 (post U0–U3 / U2b)  
**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT3_2026-07-11.md`  
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

# Verdict — AI Program Manager re-audit #4 (post U0–U3 / hal-10486)

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
**Assumed completion:** SQLite-based unified store (`nr2_unified.db`) with frontend state persistence via LocalStore/SSE, consistent with shipped I3 architecture.

---

## 1. Current Architecture Audit (what exists at hal-10486)

### 1A Orchestrator + deep audit/forecast (U0)
* **8B/30B Hierarchy:** `apex_orchestrator_pack.py` implements fast-lane regex (`_FAST_LANE_RE`) routing to `chat8b` for parse/summarize/route queries, and deep-lane regex (`_DEEP_LANE_RE`) routing to `escalate30b` for forecast/audit/cross-reference tasks.
* **Deep Audit Pack:** `apex_deep_audit_pack.py` executes monthly practice health audits and quarter forecasts via 30B with `classifyOnly` gating. Emits schema-validated JSON (`widget_type`, `data`, `source_refs`, `confidence`) to `save_last_insight` for SSE consumption.
* **Structured Outputs:** All AI packs enforce JSON-only responses with gap codes (e.g., `AUDIT_DATA_PENDING`) when unified views are empty; never invent dollars.

### 1B SoftDent + ERA 835 aggregates (U1) + DEF-001
* **ERA 835 Ingestion:** `apex_era835_pack.py` parses X12 835 EDI and remittance CSV into payer/procedure/CAS-code aggregates only. PHI (SSN, DOB, account numbers, patient names) is discarded pre-storage.
* **Mirror Tables:** Updates `softdent_era_aggregates` for S1 compatibility while maintaining `era_835_payments` isolation.
* **Gap Handling:** `ERA835_PENDING` alert when files missing/unreadable.

### 1C QuickBooks + reconciliation (U2)
* **Reconciliation Engine:** `apex_reconciliation_pack.py` provides MoM variance detection across `v_production_vs_payroll` and `v_collection_vs_ap`.
* **Thresholds:** Configurable via `NR2_VARIANCE_PCT` (default 5%) and `NR2_VARIANCE_ABS` (default $500).
* **30B Explainer:** Optional deep-lane call to explain variances using mirrored deltas only (`classifyOnly` dry-run capable).
* **Gap Codes:** `RECON_DATA_PENDING`, `RECON_VARIANCE` surfaced via SSE.

### 1D Unified DB + import poll/quarantine (T3/U2b)
* **Unified Store:** `apex_unified_db_pack.py` maintains `nr2_unified.db` (SQLite) with transactional mirroring of SoftDent period metrics and QB expense/payroll rows.
* **Import Quarantine:** `apex_import_quarantine_pack.py` moves files to `app_data/nr2/import_quarantine/` after `NR2_IMPORT_FAIL_THRESHOLD` (default 3) persistent failures, with `.reason.json` sidecars.
* **Admin Alerts:** Quarantine state emits `IMPORT_QUARANTINED` gap alerts (value `null`) via SSE to `hal-ai-insight` banner.

### 1E Insights SSE + dashboard layout (N0/U3)
* **Real-time Stream:** `save_last_insight` SSE endpoint (N0) broadcasts structured AI insights to all connected dashboard clients without page refresh.
* **Starship-Bridge Layout:** `apex_dashboard_layout_pack.py` persists per-page grid schemas (`financial`, `softdent`, `claims`) with mosaic ordering. Frontend applies via `nr2-dashboard-layout.js` using existing CSS tokens (`apex-mosaic--u3`).
* **API Surface:** `GET/POST /dashboard-layout`, `POST /dashboard-layout-reset`.

---

## 2. Gap Map — REMAINING only

**Assessment:** Operator Sections 1 (AI Hierarchy/Orchestrator/JSON) and 2 (Parsers/Unified DB) are **substantially met** by hal-10486.  
Remaining work is **burn-in operations, staging validation, and polish gaps** only.

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **AI Lane Health Telemetry** | Gap | No visibility into 8B/30B latency/failure rates; ops blind to model degradation | S | U0 |
| **Automated Audit Scheduling** | Gap | Deep audit currently CLI/manual; needs Task Scheduler/cron entry for monthly auto-run | S | U0 |
| **Data Freshness Indicators** | Gap | UI lacks "Last successful sync" timestamps for SoftDent vs QB vs ERA sources | S | U2b |
| **Synthetic Fixture Validation** | Gap | No automated end-to-end test with anonymized SoftDent/QB fixtures to verify reconciliation math | M | U2 |
| **30B Explanation Cache** | Nice | Reconciliation explainers re-query 30B every time; LRU cache would reduce GPU load | M | U2 |
| **Mobile Viewport Hardening** | Nice | Starship-bridge layout schema assumes desktop widths; mobile mosaic stacking untested | S | U3 |
| **QB Online API (Future)** | Future | Currently file-based; live OAuth API sync requires Intuit developer partnership | L | External |
| **SoftDent Live API (Future)** | Future | Real-time integration requires Carestream vendor API access | L | External |

---

## 3. Target Architecture (next wave only)

**Goal:** Harden U0–U3 for production burn-in rather than add features.

* **V0 (Validation):** Health telemetry + automated scheduling + data freshness UI.
* **V1 (Verification):** Synthetic fixture suite proving reconciliation accuracy with known inputs.
* **V2 (Velocity):** 30B cache layer + mobile polish.

---

## 4. Coding Plan — Phase V0..Vn (CONSULT ONLY sketches for remaining work)

### V0: Burn-in & Observability (CONSULT ONLY)
```python
# apex_ai_telemetry_pack.py
# - Wraps existing orchestrator calls with timing/error counters
# - New endpoint GET /ai-lane-health returns:
#   {"chat8b":{"latency_p50_ms":120,"errors_1h":0},"escalate30b":{"latency_p50_ms":4500,"errors_1h":1}}
# - SSE insight type 'telemetry-alert' when error rate > threshold
```

```python
# scripts/run_nr2_scheduled_audit.py
# - Task Scheduler entry point (Windows) or cron (WSL)
# - Runs deep_audit_pack.generate_audit(classifyOnly=False) on 1st of month
# - Logs to audit_cron_log.jsonl with exit codes
```

```javascript
// site/nr2-data-freshness.js (CONSULT ONLY)
// - Consumes new /sync-status endpoint returning:
//   {softdent_last_import:"2026-07-11T14:00:00Z", qb_last_import:"...", era_last_import:"..."}
// - Renders subtle " freshness chips" in widget headers (green <24h, yellow 24-48h, red >48h)
```

### V1: Staging Validation (CONSULT ONLY)
```python
# test/fixtures/generate_synthetic_nr2.py
# - Creates anonymized SoftDent (10 patients, 3 providers) + QB (matching payroll) + ERA 835
# - Known reconciliation deltas: production $50k, payroll $48.5k (3% variance under threshold)
# - pytest verifies reconciliation engine detects expected state, no false positives
```

### V2: Polish (CONSULT ONLY)
```python
# apex_reconciliation_pack.py enhancement (CONSULT ONLY)
# - Add @lru_cache(maxsize=128) on explain_variance() keyed by (period, delta_hash)
# - Cache invalidated on new import completion
```

```css
/* site/apex-mobile-polish.css (CONSULT ONLY) */
/* Media query <768px: stack mosaic grid into single column, reduce HAL insight font size */
@media (max-width: 768px) {
  .apex-mosaic--u3 { grid-template-columns: 1fr; }
  .hal-insight-banner { font-size: 0.9rem; }
}
```

---

## 5. MUST / SHOULD / NICE ranked table (remaining)

| Priority | Item | Effort | Business Impact |
|----------|------|--------|-----------------|
| **MUST** | AI Lane Health Telemetry (V0) | S | Prevents silent AI failure in production |
| **MUST** | Automated Audit Scheduling (V0) | S | Ensures monthly audits actually run without manual CLI |
| **SHOULD** | Data Freshness Indicators (V0) | S | Users trust stale data less; reduces "why is this wrong?" support |
| **SHOULD** | Synthetic Fixture Validation (V1) | M | Guarantees reconciliation math accuracy before tax season |
| **NICE** | 30B Explanation Cache (V2) | M | Reduces GPU costs, faster reconciliation page loads |
| **NICE** | Mobile Viewport Hardening (V2) | S | Executive review on iPad viable |
| **NICE** | QB Online API (Future) | L | Eliminates manual export step (requires Intuit partnership) |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

* **PHI Exposure Risk:** V0 telemetry must redact patient counts/amounts in latency logs (use metric hashes only).
* **SoftDent Honesty:** All V0–V2 sketches maintain read-only stance; no write-back proposals.
* **Scheduling Risk:** Windows Task Scheduler requires `NT AUTHORITY\SYSTEM` or user context with saved credentials; document in runbook.
* **Cache Consistency:** V2 30B cache must invalidate on any import event to prevent stale explanations.
* **Rollback:** All V0–V2 features flag-gated (`NR2_AI_TELEMETRY`, `NR2_AUDIT_CRON`, etc.). Default OFF until burn-in complete.

---

## 7. Approval Checklist (next wave only)

**DO NOT PROCEED** until operator confirms:

- [ ] **Scope Confirm:** Burn-in/validation only (V0–V2), no new AI features or API integrations.
- [ ] **Priority:** V0 MUST items (telemetry + scheduling) approved for immediate consult.
- [ ] **QB Online API:** Defer to future phase (requires Intuit developer account)?
- [ ] **Mobile:** Is iPad/tablet support required for V0, or defer to V2?
- [ ] **Schedule:** Preferred cron pattern for monthly audit (1st of month 02:00 local?).
- [ ] **Staging:** Provide anonymized SoftDent/QB fixture files for V1 validation suite, or generate synthetic acceptable?

**Awaiting operator approval to proceed with V0 consult.**