# Moonshot AI — Expert SE Program Review & Recommendations (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10498  
**Script:** `scripts/run_moonshot_expert_se_program_recommendations_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> right now as an expert software enginger ask moonshot ai about this program and recommendations

---

# Verdict
NR2 hal-10498 has a critical coupling defect where HAL telemetry endpoints are incorrectly gated behind "fresh" financial import readiness, causing a false "HAL Standby" UI state despite the 24B model being GPU-resident and Ollama-responsive. The program is architecturally sound on data honesty and local PHI containment, but requires immediate gate-policy decoupling and async HAL threading to unblock the operator experience.

## 0. Operator Intent (quote; confirm consult-only)
> "right now as an expert software enginger ask moonshot ai about this program and recommendations"

**Confirmed CONSULT-ONLY.** This is a diagnostic assessment and ranked recommendation report. **No code will be generated, modified, or applied** until the operator explicitly approves a specific remediation phase with "proceed," "approve," or "do it."

## 1. Program Snapshot (what NR2 is now at this build)
- **Build:** hal-10498 (2026-07-11), schemaVersion hal-10498, staffRenderMode=apex
- **Runtime:** Bottle Python HTTPS loopback server on 127.0.0.1:8765 (TLS required), single-threaded default
- **HAL Layout:** Single GPU-pinned 24B (mistral-small3.1:24b Q4_K_M, 8192 ctx) on AMD Radeon AI PRO R9700 32GB, keep_alive=-1 (resident), numParallel=1. External cloud disabled (`cloudReasoning.enabled: false`).
- **Data Model:** Direct-first import mode; SoftDent READ-ONLY ODBC (1284/1284 transaction parity) + QuickBooks CSV imports; `sd_patient_insurance` extract recently shipped (Wave 5 subpages expansion completed same day).
- **Current Import State:** Readiness `level=degraded`, `completeness≈30%`, `connected≈3/19`. Missing: softdent.dashboard, softdent.ar, quickbooks.revenue, quickbooks.payroll, quickbooks.ap. QB inbox has partial CSVs (P&L, expenses) but lacks revenue/payroll datasets.
- **Live Symptom:** `/api/ollama/tags` returns 200 (modelCount=12, hal-local:24b resident), yet Apex sidebar displays **"HAL Standby"** with **"Awaiting telemetry…"** tombstone. Financial page widgets empty/initializing.
- **Root Cause Verified:** `GET /api/apex/hal/status` returns **403 import_read_forbidden**. The path `/api/apex/hal` is under `FINANCIAL_READ_PREFIXES`; `before_request` hook requires readiness level **"fresh"** for all GETs under these prefixes. Current level is "degraded" → 403. Chat endpoint `/api/hal/evaluate-query` is in `FINANCIAL_READ_EXEMPT`, so HAL chat actually works while status/widgets appear dead (coupling illusion).

## 2. Architecture Strengths (keep)
- **Data Honesty Architecture:** Never invents dollars, claim IDs, ERA percentages, or clinical facts; empty widgets show honest tombstones rather than mock data.
- **Local PHI Containment:** GPU inference pinned to local R9700; cloud reasoning explicitly disabled; PHI redaction layer present for optional cloud lane (currently off).
- **SoftDent Read-Only Parity:** 1284/1284 transaction sync ratio with register and operatory schedule live; insurance extract schema (`sd_patient_insurance`) shipped with honest NULL handling.
- **TLS Loopback Security:** SessionVault with 15-minute token rotation, CSP headers, `FINANCIAL_READ_PREFIXES` gating (intent correct, scope overly broad), and loopback-only binding.
- **Claims Workbench Phase 1:** Read-only kanban (5-column) + aging shelves hybrid operational; HAL focus/filter functional.

## 3. Ranked Defects & Risks

| ID | Rank | Area | Defect | Evidence | Root cause | Effort |
|---|---|---|---|---|---|---|
| **DEF-001** | **MUST** | Coupling/UX | **HAL Offline Illusion:** Telemetry endpoints (`/api/apex/hal/status`, widgets) return 403 when import readiness is "degraded," causing UI to show "HAL Standby" despite GPU model resident and chat functional. | LIVE FACTS: 403 on `/api/apex/hal/status`; UI "HAL Standby"; `/api/ollama/tags` ok=true; chat works via exempt path. | `FINANCIAL_READ_PREFIXES` includes `/api/apex/hal` and gate requires "fresh" for all financial reads, failing to distinguish money/PHI reads from system status reads. | S (1d) — Split gate policy or add specific exemptions |
| **DEF-002** | **MUST** | Performance | **Single-Threaded HAL Blocking:** Long Ollama evaluate-query (~5s) monopolizes Bottle worker, blocking concurrent page loads ("Loading bridge instruments…" hang). | LIVE FACTS: "Bottle single-threaded: long HAL evaluate-query (~5s) can block concurrent page pages." | Bottle default single-threaded server; synchronous Ollama calls without async queue. | M (3d) — Threading or async queue |
| **DEF-003** | **MUST** | Reliability | **Legacy AutoStart Conflict:** Scheduled task `NewRidgeDashboardServersAutoStart` points to stale path `"C:\New folder\…"` with last result failed (`-196608`), confusing boot sequence. | LIVE FACTS: Task Scheduler shows legacy path and failed exit code. | Development artifact not cleaned up; conflicts with new "New Ridge NR2 Program" task. | XS (0.5d) — Delete stale task |
| **DEF-004** | **SHOULD** | Performance | **Cold-First Load Latency:** Multi-second widget assembly when caches empty due to direct-first pipeline cost on cache miss. | LIVE FACTS: "Cold first widget load still multi-second when caches empty." | No background warming; full dataset assembly on cache miss without stubbed fast-path. | M (2d) — Cache warming or stubbed fast-path |
| **DEF-005** | **SHOULD** | Claims | **No True ERA 835 Pipeline:** "ERA Matched" column populated only when SoftDent import happens to contain ERA data; no actual 835 EDI parsing or auto-match logic. | Docs: "No 835 parsing"; "ERA Matched" mockup parity only. | No `era_transactions` table or 835 parser implemented. | L (5d) — 835 parser + match engine |
| **DEF-006** | **SHOULD** | Claims | **Workbench Read-Only Dead-End:** Claims kanban cards have no actions; cannot generate narrative, add follow-up note, or schedule callback from card. | Docs: "Read-Only Constraint: Claims kanban has no drag write-back." | Phase 1 shipped as view-only; Phase 2 audit-log-only actions not implemented. | M (3d) — Card action buttons + audit log |
| **DEF-007** | **NICE** | HAL | **Reactive-Only Architecture:** HAL acts only on operator command; no proactive alerts when SoftDent export >7 days stale or QB import missing. | Docs: "HAL Reactivity: lacks proactive daily briefings." | No background scheduler or polling mechanism; HAL is request-response only. | S (2d) — Background health monitor |

## 4. HAL Offline Illusion — Specific Diagnosis & Fix Options

**Diagnosis:**
The `before_request` hook in `nr2_http_server.py` applies `financial_read_path()` gating to all `GET` requests under `FINANCIAL_READ_PREFIXES`. This tuple includes `/api/apex/hal`, which captures `/api/apex/hal/status`. The gate requires readiness level `"fresh"` (100% imports current). When the system is `"degraded"` (30% complete, missing SoftDent AR/QB revenue), the gate returns `abort_import_read()` → 403. 

However, `/api/hal/evaluate-query` is listed in `FINANCIAL_READ_EXEMPT`, so the chat path bypasses the gate entirely. Result: HAL is technically online (GPU resident, Ollama responding, chat functional) but the Apex shell cannot fetch telemetry or widgets, rendering the UI "dead" despite the backend being alive. This is a **coupling bug** between data freshness (financial imports) and system availability (HAL telemetry).

**Fix Options:**

**(A) Data/Import Recovery (Operator Action)**
- Operator manually provides missing SoftDent AR export and QB revenue/payroll CSVs to raise readiness to `"fresh"`.
- *Pros:* Immediate fix without code change; satisfies original security intent.
- *Cons:* Leaves coupling bug latent; HAL will appear "off" again whenever imports lag; does not fix the architectural dishonesty that HAL availability depends on accounting data freshness.

**(B) Gate Policy Split — Status vs. Money Reads (Recommended)**
- Refactor `FINANCIAL_READ_PREFIXES` into two tiers:
  1. `FINANCIAL_DATA_PREFIXES` (money, PHI, patient data): Require `"fresh"` readiness.
  2. `SYSTEM_STATUS_PREFIXES` (HAL telemetry, import health meta, widget schema): Require `"connected"` readiness (system up, regardless of data staleness).
- Move `/api/apex/hal/status`, `/api/apex/import-health`, and widget metadata endpoints to tier 2.
- *Pros:* Fixes the illusion permanently; HAL shows "Ready" even when data is stale; maintains strict gating on actual financial data.
- *Cons:* Requires careful audit to ensure tier 2 endpoints never leak PHI or dollar amounts.

**(C) UI Honesty Copy — Distinguish "HAL Off" vs "Data Stale"**
- Change Apex shell to detect 403 `import_read_forbidden` specifically and render "HAL Ready • Import Degraded" instead of "HAL Standby."
- *Pros:* No backend security changes; honest UX.
- *Cons:* Workaround rather than fix; widgets still blocked from fetching data (empty state remains).

**Recommended Path: (B) with immediate (C) as UX mitigation.**
Implement the gate split so that HAL telemetry requires only `"connected"` (system up) while financial data reads retain `"fresh"` requirement. Simultaneously update the Apex shell to display degraded status honestly ("Data Stale" badge) rather than "Standby."

## 5. Recommendations — MUST / SHOULD / NICE

| ID | Rank | Recommendation | Why | Effort | Depends on |
|---|---|---|---|---|---|
| **REC-001** | **MUST** | **Decouple HAL telemetry from financial readiness gates.** Split `FINANCIAL_READ_PREFIXES` or add specific exemptions for `/api/apex/hal/status` and widget metadata endpoints; require only `"connected"` readiness for system status, keep `"fresh"` for money/PHI reads. | Fixes DEF-001 (false HAL offline); restores UI functionality while maintaining data security. | S (1d) | None |
| **REC-002** | **MUST** | **Implement threaded or async HAL queue.** Move Ollama calls off the main Bottle thread using `gevent`, `threading`, or a local queue worker to prevent 5s queries from blocking page loads. | Fixes DEF-002 (blocking); improves perceived responsiveness. | M (3d) | None |
| **REC-003** | **MUST** | **Remove legacy AutoStart task.** Delete `NewRidgeDashboardServersAutoStart` scheduled task pointing to "C:\New folder\…" to prevent boot confusion. | Fixes DEF-003 (reliability). | XS (0.5d) | None |
| **REC-004** | **SHOULD** | **Add proactive import health monitor.** Background thread or HAL evaluation that alerts when SoftDent export >7 days stale or QB import missing; suggests "Refresh SoftDent period imports." | Addresses DEF-007; prevents silent data decay; satisfies IMP-003 from previous consult. | S (2d) | REC-001 (status visibility) |
| **REC-005** | **SHOULD** | **Implement ERA 835 parser pipeline.** Parse 835 EDI into `era_transactions`; auto-match to claims by claim ID + patient; populate "ERA Matched" with real denial codes (CO-45, etc.). | Addresses DEF-005; transforms mockup into functional revenue cycle management. | L (5d) | None |
| **REC-006** | **SHOULD** | **Claims Workbench Phase 2: Card Actions.** Add "Generate Narrative," "Add Follow-Up Note," "Schedule Callback" buttons to kanban cards (audit-log only, no SoftDent write-back). | Addresses DEF-006; eliminates dead-end UI. | M (3d) | None |
| **REC-007** | **SHOULD** | **Cache warming for cold loads.** Stubbed fast-path widget response when caches empty, backfilled by async pipeline assembly. | Addresses DEF-004; reduces cold-start latency. | M (2d) | None |
| **REC-008** | **NICE** | **Batch narrative generation.** Select multiple denied claims; generate appeals with shared context; bulk export to PDF. | Efficiency gain for high-volume denial months. | M (3d) | REC-006 |
| **REC-009** | **NICE** | **Voice context carry.** "HAL, draft appeal for the high-risk claim I just clicked" — carries claim context into narrative voice input without manual lock. | Reduces clicks; seamless workflow. | S (2d) | REC-006 |

## 6. Suggested Fix Order (phases) + Validation Gates

**Phase 1: Critical Coupling & Stability (Consult → Approve → Code)**
1. **REC-003:** Remove legacy AutoStart task.
2. **REC-001:** Split gate policy — exempt `/api/apex/hal/status` from "fresh" requirement (require "connected" instead); verify `/api/apex/widgets` metadata paths also use "connected".
3. **UI Update (part of REC-001):** Apex shell distinguishes "HAL Ready" vs "Data Stale" states.

*Validation Gate:*
- `curl -k https://127.0.0.1:8765/api/apex/hal/status` returns 200 with `readiness.level=degraded` (not 403).
- Apex sidebar shows "HAL Ready • Import Degraded" (not "Standby").
- Chat functionality remains operational.
- Financial data endpoints (`/api/apex/financial-reports/*`) still return 403 when readiness is degraded (security maintained).

**Phase 2: Performance & Reliability (Consult → Approve → Code)**
4. **REC-002:** Implement threaded/async HAL queue (gevent or worker thread).
5. **REC-004:** Add proactive import health monitor (background thread polling import readiness, HAL alert when stale).

*Validation Gate:*
- HAL evaluate-query (5s delay simulated) does not block concurrent `/api/apex/widgets` request.
- Import health chip appears in UI when SoftDent export >7 days old.

**Phase 3: Feature Completion (Consult → Approve → Code)**
6. **REC-006:** Claims Workbench Phase 2 card actions.
7. **REC-005:** ERA 835 parser pipeline (depends on stable claims schema from Phase 2).
8. **REC-007:** Cache warming (can ship alongside or after).

*Validation Gate:*
- ERA 835 file upload populates "ERA Matched" column with denial codes without requiring SoftDent re-import.
- Claims kanban card buttons generate narratives and log to audit trail.

## 7. Risks, PHI / honesty, Rollback

**PHI Exposure Risk:**
- Splitting the readiness gate (REC-001) risks exposing patient data if "connected" tier endpoints accidentally include PHI. **Mitigation:** Strictly limit tier 2 to telemetry (model loaded, version, generic import health boolean). Never include patient names, account numbers, or dollar amounts in `/api/apex/hal/status` or widget metadata endpoints. Audit all `/api/apex/hal/*` handlers to ensure they return only system state, not business data.

**Honesty / Trust Risk:**
- If the UI shows "HAL Ready" when data is stale, operators might trust AI analysis of outdated financials. **Mitigation:** UI must display "Data Stale" badge prominently alongside "HAL Ready." HAL responses should include a timestamp disclaimer when import age >24 hours.

**Rollback Plan:**
- If gate split causes security issues, restore `FINANCIAL_READ_PREFIXES` to original broad list and add a temporary manual override flag `NR2_HAL_BYPASS_IMPORT_GATE=1` (environment variable) for emergency operator use only, logged to audit trail.

**DO NOT APPLY until operator approves specific phase.**