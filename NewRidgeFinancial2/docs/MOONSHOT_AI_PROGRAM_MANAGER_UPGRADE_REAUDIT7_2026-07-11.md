# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #7 (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10493 (post X0–X2)  
**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT6_2026-07-11.md`  
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

# Verdict — AI Program Manager re-audit #7 (post X0–X2 / hal-10493)

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

**Note on truncation:** Request cut off at `unified local database/state management system (e.g,`. **Assumed completion:** SQLite-based unified store (`app_data/nr2_unified.db`) with normalized T0–T4 schema, consistent with shipped T3 architecture and W0–W2 ingest pipelines.  
**Consult status:** CONSULT ONLY — no code applied pending operator approval.

---

## 1. Current Architecture Audit (what exists at hal-10493) — brief

| Requirement | Shipped Artifact | Location / Flag |
|-------------|------------------|-----------------|
| **8B fast/widget routing** | AI Orchestrator (`hal-models.json` + I-packs) | `NR2_AI_ORCHESTRATOR` (default ON) |
| **30B deep/forecasting** | Deep Audit Pack (I3) + Explain Cache (I4) | `NR2_AUDIT_CRON`, `NR2_EXPLAIN_CACHE` (default OFF) |
| **AI Orchestrator middleware** | Task classifier + lane router | `src/hal_orchestrator.py` |
| **Structured JSON outputs** | Explain cache LRU + JSONSchema validation | `app_data/explain_cache/`, `src/hal_json_output.py` |
| **Fault-tolerant parsers** | SoftDent T1 + QB T2 parsers with DQ gating | `src/parsers/softdent_t1.py`, `qb_t2.py` |
| **Unified local database** | SQLite `nr2_unified.db` (T0–T4 schema) | `app_data/nr2_unified.db` |
| **Extended metrics** | Case acceptance, aging, scheduling | `NR2_EXTENDED_METRICS` (default ON) |
| **Import automation** | 5-min cron + quarantine UI | `NR2_IMPORT_CRON` (default OFF until X0) |
| **Burn-in runbooks** | X0 (flags), X1 (tasks), X2 (validation) | `scripts/nr2_burnin_*.ps1`, `validate_nr2_burnin.py` |

**Critical:** All burn-in features (telemetry, scheduled audits, import cron) remain **DEFAULT OFF** pending operator execution of X0–X2 scripts.

---

## 2. Gap Map — REMAINING only

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **Burn-in Enablement** | Shipped (Opt-in) | Operator must execute X0–X2 PowerShell/scripts to flip env flags and register Task Scheduler jobs | 15 min | SoftDent nightly export SOP ready |
| **Future Vendor APIs** | Not in scope | QB Online API (real-time), SoftDent live API (SQL bridge), ERA write-back | Weeks | Vendor contracts / API keys |

**Verdict:** No code gaps remain for Sections 1–2. System is architecturally complete.

---

## 3. Target Architecture (next wave only — or NONE if complete)

**NONE.**  
Sections 1–2 (AI Program Manager + Full Data Automation) are **architecturally complete** at hal-10493. The system awaits operational enablement only (X0–X2 burn-in).

---

## 4. Coding Plan — only if MUST gaps remain (else state NO NEW CODE)

**NO NEW CODE REQUIRED** for Sections 1–2.  
Do not write, modify, or delete Python/JS/SQL beyond the existing hal-10493 baseline. Awaiting operator execution of burn-in scripts.

---

## 5. MUST / SHOULD / NICE ranked table (remaining)

| Priority | Item | Action | Owner |
|----------|------|--------|-------|
| **MUST** | X0 Flag Enablement | Run `.\scripts\nr2_burnin_enable_flags.ps1` in elevated PowerShell; restart NR2 | Operator |
| **MUST** | X1 Task Registration | Run `.\scripts\nr2_register_scheduled_tasks.ps1` (as Admin) | Operator |
| **MUST** | X2 Validation | Run `python scripts\validate_nr2_burnin.py` | Operator |
| **SHOULD** | Vendor API Migration | Evaluate QB Online API vs CSV exports; assess SoftDent SQL bridge for live read (no write-back) | Future Phase |
| **NICE** | UI Theming Polish | Dashboard CSS refinements (non-blocking, cosmetic) | Future Phase |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

| Category | Detail |
|----------|--------|
| **PHI** | All patient data remains local in `app_data/nr2_unified.db`. No PHI transmitted to Moonshot API (only aggregated metrics). |
| **SoftDent Honesty** | System is **read-only** via CSV exports. No write-back to SoftDent. Empty fields in exports are treated as `NULL`, never `$0`. |
| **Rollback** | **Flags:** `.\scripts\nr2_burnin_disable_flags.ps1` reverts env vars. **Tasks:** `.\scripts\nr2_unregister_scheduled_tasks.ps1` removes Task Scheduler entries. **Data:** Quarantine purge is local-only; original SoftDent exports remain untouched. |
| **Risk** | Running X0–X2 before SoftDent nightly export SOP is ready will cause cron to poll empty directories (quarantine will catch missing files, but generates noise in logs). |
| **AI Safety** | 30B deep audit runs under `NR2_AUDIT_CRON` flag; if disabled, dashboard falls back to cached last audit (or "Audit Pending" state). No UI breakage. |

---

## 7. Approval Checklist (burn-in enablement / Future only)

**DO NOT PROCEED to code changes.** Complete these operational steps to activate the shipped architecture:

- [ ] **SOP Ready:** SoftDent nightly export to `imports/softdent/` documented and active
- [ ] **X0 Executed:** `.\scripts\nr2_burnin_enable_flags.ps1` (elevated PowerShell)
- [ ] **X0 Verified:** `.\scripts\nr2_burnin_enable_flags.ps1 -Verify` shows all flags = 1
- [ ] **Restart:** Close and reopen NR2 dashboard (or reboot) to pick up `setx` env vars
- [ ] **X1 Executed:** `.\scripts\nr2_register_scheduled_tasks.ps1` (as Administrator)
- [ ] **X2 Validated:** `python scripts\validate_nr2_burnin.py` passes all pytest gates
- [ ] **UI Confirmation:** Dashboard shows "Data Freshness" chips (`NR2_DATA_FRESHNESS=1`)
- [ ] **Audit Confirmation:** "Monthly Practice Health Audit" tab populates (`NR2_AUDIT_CRON=1`)
- [ ] **(Future)** Evaluate QB Online API integration vs current CSV automation

**Status:** `PROGRAM COMPLETE PENDING BURN-IN` — Awaiting operator approval to execute X0–X2 scripts.