# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #6 (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10492 (post W0–W2)  
**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT5_2026-07-11.md`  
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

# Verdict — AI Program Manager re-audit #6 (post W0–W2 / hal-10492)

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
**Assumed completion:** SQLite-based unified store (`app_data/nr2_unified.db`) with normalized T0–T4 schema, consistent with shipped T3 architecture and W0–W2 ingest pipelines.  
**Consult status:** CONSULT ONLY — no code applied pending operator approval.

---

## 1. Current Architecture Audit (what exists at hal-10492)

### 1A Orchestrator + telemetry + deep audit
- **AI Orchestrator** (`hal-models.json` + I-packs): **SHIPPED**. Routes 8B (fast/widget) vs 30B (deep/cross-reference) based on task complexity tokens. Defaults ON; disable via `NR2_AI_ORCHESTRATOR=0`.
- **Telemetry pack** (I2): **SHIPPED**, flag `NR2_AI_TELEMETRY` defaults **OFF**. Captures 8B/30B latency, fallback rates, cache hits.
- **Deep audit pack** (I3): **SHIPPED**, flag `NR2_AUDIT_CRON` defaults **OFF**. Provides `v_monthly_practice_health_audit` view (30B cross-reference of SoftDent ledger + QB P&L).
- **Explain cache** (I4): **SHIPPED**, flag `NR2_EXPLAIN_CACHE` defaults **OFF**. Stores 30B JSON explanations for widget rendering without UI breakage.

### 1B SoftDent extended metrics + ERA + fixtures (W0/U1/V1)
- **Extended metrics** (W0): **SHIPPED**. `v_case_acceptance`, `v_patient_aging`, `v_scheduling_efficiency` mapped to T1 tables. Flag `NR2_EXTENDED_METRICS` defaults **ON**.
- **ERA ingest** (U1): **SHIPPED**. 835/ERA parsing with PHI redaction; no write-back.
- **Fixture loader** (V1): **SHIPPED**. SoftDent fixtures for chair capacity, fee schedules.

### 1C QuickBooks + reconciliation + explain cache
- **QB parsers** (S0–S2): **SHIPPED**. CSV/Excel IIF/CSV parsers for P&L, AP, payroll.
- **Reconciliation engine** (V2): **SHIPPED**. SoftDent Collections ↔ QB Deposits matching; gap codes when unmatched.
- **Cross-reference views**: `v_softdent_qb_reconciliation` exposes 30B-ready structured JSON for "deep financial forecasting" requests.

### 1D Unified DB + import cron/DQ/quarantine UI (W1/W2)
- **Unified SQLite store** (T3): **SHIPPED**. `app_data/nr2_unified.db` with normalized schema bridging SoftDent (T0/T1) and QB (T2) entities.
- **DQ gates** (W1): **SHIPPED**. `apex_import_dq_pack.py` — reject-only validation before `ingest_from_bundle`. Flag `NR2_IMPORT_DQ` defaults **ON**.
- **Import cron** (W1): **SHIPPED**. `apex_import_scheduler_pack.py` + `scripts/run_nr2_import_cron.py`. Flag `NR2_IMPORT_CRON` defaults **OFF** (burn-in).
- **Quarantine UI** (W2): **SHIPPED**. `apex-quarantine-panel.js` with retry/purge actions. Flag `NR2_QUARANTINE_UI` defaults **ON**.

### 1E Insights SSE + layout + mobile polish
- **Insights SSE** (T5): **SHIPPED**. Server-sent events for real-time widget updates.
- **Responsive layout** (T4): **SHIPPED**. Mobile-first CSS grid; 8B-triggered UI routing active.

---

## 2. Gap Map — REMAINING only

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **Production Burn-in** | Coded, flagged OFF | Flags `NR2_IMPORT_CRON`, `NR2_AUDIT_CRON`, `NR2_AI_TELEMETRY`, `NR2_DATA_FRESHNESS`, `NR2_EXPLAIN_CACHE` must flip ON for autonomous operation | S | Ops approval |
| **Task Scheduler Ops** | CLI shipped, not scheduled | Windows Task Scheduler entries for `run_nr2_import_cron.py` (5-min) and `run_nr2_audit_cron.py` (monthly) | S | Admin rights |
| **30B Monthly Audit** | View exists, not scheduled | `NR2_AUDIT_CRON=1` enables automated monthly 30B cross-reference reports; currently requires manual trigger | S | Task Scheduler |
| **Data Freshness Sentinel** | Coded, flagged OFF | `NR2_DATA_FRESHNESS=1` enables stale-data warnings when SoftDent export >24h | S | NR2_IMPORT_CRON |
| **Telemetry Dashboard** | Coded, flagged OFF | `NR2_AI_TELEMETRY=1` exposes 8B/30B performance metrics to admin panel | S | None |

**Verdict:** Sections 1 (AI Program Manager hierarchy + JSON outputs) and 2 (Unified DB + fault-tolerant parsers + SoftDent/QB automation) are **architecturally complete and shipped**. The system is in "safe mode" pending burn-in flag flips. No new feature waves required to meet the original request.

---

## 3. Target Architecture (next wave only)

**Target:** Production-hardened NR2 with autonomous data pipelines and AI-driven monthly audits.

- **State:** All burn-in flags ON; Windows Task Scheduler managing cron loops; 30B monthly health audits auto-generating; telemetry visible in admin panel.
- **No new code required.** Only operational enablement of existing W0–W2 + I0–I4 assets.

---

## 4. Coding Plan — Phase X0..Xn (CONSULT ONLY sketches for remaining work)

**No new feature code required.** Remaining work is operational enablement only.

### Phase X0 — Burn-in Flag Flip Runbook (CONSULT ONLY)
```batch
:: Production enablement runbook (CONSULT ONLY — do not apply until approved)

:: 1. Import automation (W1)
setx NR2_IMPORT_CRON "1"
setx NR2_IMPORT_CRON_SEC "300"

:: 2. Monthly 30B audit (I3)
setx NR2_AUDIT_CRON "1"

:: 3. Real-time telemetry (I2)
setx NR2_AI_TELEMETRY "1"

:: 4. Data freshness warnings (T3 sentinel)
setx NR2_DATA_FRESHNESS "1"

:: 5. Explain cache warming (I4)
setx NR2_EXPLAIN_CACHE "1"

:: Verify
python -c "import os; print('IMPORT_CRON:', os.getenv('NR2_IMPORT_CRON'))"
```

### Phase X1 — Task Scheduler Deployment (CONSULT ONLY)
```powershell
# Create Import Cron task (5-minute polling)
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\NR2\scripts\run_nr2_import_cron.py"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([System.TimeSpan]::MaxValue)
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "NR2_Import_Cron" -Description "NR2 W1 DQ-gated import polling"

# Create Monthly Audit task (1st of month, 06:00)
$auditAction = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\NR2\scripts\run_nr2_audit_cron.py --generate-report"
$auditTrigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1 -At "06:00"
Register-ScheduledTask -Action $auditAction -Trigger $auditTrigger -TaskName "NR2_Monthly_Audit" -Description "NR2 30B practice health audit"
```

### Phase X2 — Validation Suite (CONSULT ONLY)
```bash
# Post-enablement validation
python -m pytest NewRidgeFinancial2/test_apex_phase_w0_quarantine_ui.py -v
python -m pytest NewRidgeFinancial2/test_apex_import_dq_pack.py -v
python scripts/run_nr2_import_cron.py --force  # Dry-run test
```

---

## 5. MUST / SHOULD / NICE ranked table (remaining)

| Priority | Item | Effort | Business Impact |
|----------|------|--------|-----------------|
| **MUST** | Flip `NR2_IMPORT_CRON=1` + Task Scheduler 5-min polling | S | Achieves "Full Automation" requirement (Section 2) |
| **MUST** | Flip `NR2_AUDIT_CRON=1` + Task Scheduler monthly job | S | Achieves "30B monthly practice health audits" (Section 1) |
| **SHOULD** | Flip `NR2_AI_TELEMETRY=1` for 8B/30B performance visibility | S | Production monitoring for Program Manager hierarchy |
| **SHOULD** | Flip `NR2_DATA_FRESHNESS=1` for stale-data alerts | S | Prevents decisions on outdated SoftDent exports |
| **NICE** | Flip `NR2_EXPLAIN_CACHE=1` for sub-100ms insight loading | S | Polished UX for 30B deep explanations |
| **NICE** | Mobile viewport testing on physical devices | S | "Beautifully organized" polish validation |
| **Future** | QB Online API (OAuth) — vendor gated | L | Real-time QB vs batch CSV |
| **Future** | SoftDent live API/write-back — vendor gated | L | Eliminate exports entirely |

---

## 6. Risks, PHI, SoftDent Honesty, Rollback

**PHI:** All automation maintains current posture: patient names in SoftDent exports remain local-only; ERA parsing redacts before cloud transit (if ever enabled); QB data contains no PHI. Task Scheduler runs under practice admin account—ensure folder ACLs restrict `app_data/nr2/` to practice principals only.

**SoftDent Honesty:** No write-back implemented or planned. All retry/purge actions (W2) operate on local quarantine copies only. Empty values continue to emit gap codes (`CASE_ACCEPT_DATA_PENDING`, etc.)—never rendered as `$0`.

**Rollback:** If burn-in flags cause instability:
```batch
setx NR2_IMPORT_CRON "0"
setx NR2_AUDIT_CRON "0"
schtasks /Delete /TN "NR2_Import_Cron" /F
schtasks /Delete /TN "NR2_Monthly_Audit" /F
```
System reverts to manual import + manual audit generation (current safe state).

**Risk:** Enabling `NR2_IMPORT_CRON` without proper SoftDent export discipline (nightly CSV drops) may result in repeated quarantine events. Ensure export SOP documented before flag flip.

---

## 7. Approval Checklist (next wave only)

**DO NOT PROCEED until operator confirms:**

- [ ] **Acknowledge truncation:** Confirm that SQLite `app_data/nr2_unified.db` meets "unified local database/state management system" intent.
- [ ] **Approve burn-in:** Authorize flip of `NR2_IMPORT_CRON`, `NR2_AUDIT_CRON`, `NR2_AI_TELEMETRY`, `NR2_DATA_FRESHNESS`, `NR2_EXPLAIN_CACHE` from `0` → `1`.
- [ ] **Task Scheduler authority:** Confirm Windows admin rights available to create `NR2_Import_Cron` (5-min) and `NR2_Monthly_Audit` (monthly) tasks.
- [ ] **Export SOP readiness:** Confirm SoftDent nightly export procedure documented before enabling automated polling.
- [ ] **Validate W0–W2:** Run `pytest NewRidgeFinancial2/test_apex_phase_w2_quarantine_ui.py -q` and confirm pass.
- [ ] **Future gate:** Acknowledge that QB Online API and SoftDent live API are vendor-gated Future items, not required to meet Sections 1–2 of original request.

**Upon approval:** Execute Phase X0–X2 runbooks (no new code required). System will be production-ready with AI Program Manager (8B/30B hierarchy), unified SQLite store, and fully automated SoftDent/QB pipelines.

**CONSULT ONLY — DO NOT APPLY until operator says approve / proceed.**