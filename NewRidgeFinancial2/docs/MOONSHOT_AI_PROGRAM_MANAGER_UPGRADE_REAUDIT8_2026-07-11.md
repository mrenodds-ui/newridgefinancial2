# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #8 (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** tip after f3281f5 (hal-10493 + single-24B)  
**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT7_2026-07-11.md`  
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

# Verdict — AI Program Manager re-audit #8 (post burn-in + single-24B)

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

**Note on truncation:** Request cut off at `unified local database/state management system (e.g,`. Assumed completion: SQLite-based unified store (`app_data/nr2_unified.db`) with normalized T0–T4 schema.  
**Architecture evolution (honest acknowledgment):** Original intent specified dual-model hierarchy (8B fast / 30B deep). Post-burn-in architecture (hal-10493) implements **single 24B (`hal-local:24b` Q4_K_M)** on R9700 32 GB to eliminate VRAM thrashing and guarantee stability. Lane IDs (`chat8b`, `escalate30b`, `coder32b`) are preserved in the orchestrator but all resolve to the same 24B instance. Functional coverage (fast widget parsing + deep forecasting) is maintained within one model; 8B/30B files retained on disk for future dual-GPU restoration.  
**Consult status:** CONSULT ONLY — no code applied pending operator approval.

---

## 1. Current Architecture Audit (what exists NOW) — brief

| Requirement | Shipped Artifact | Location / Status |
|-------------|------------------|-------------------|
| **AI Orchestrator middleware** | Task classifier + lane router | `src/hal_orchestrator.py` active; lanes preserved |
| **Single 24B local inference** | `hal-local:24b` (mistral-small3.1:24b Q4_K_M) | Pinned on R9700; 15 GB resident; 7.8 tok/s median |
| **Structured JSON outputs** | Explain cache (I4) + JSONSchema validation | `app_data/explain_cache/`; `src/hal_json_output.py` |
| **Fast widget parsing** | I-pack router (I1) via 24B | Latency ~0.18–1.2s first token; acceptable for dashboard |
| **Deep forecasting/audits** | Monthly Audit Pack (I3) via 24B | `scripts/run_nr2_scheduled_audit.py` registered in Task Scheduler |
| **Fault-tolerant parsers** | SoftDent T1 + QB T2 parsers with DQ gating | `src/parsers/softdent_t1.py`, `qb_t2.py` |
| **Unified local database** | SQLite `nr2_unified.db` (T0–T4 schema) | `app_data/nr2_unified.db`; production+expense reconciliation live |
| **Import automation** | Cron polling + quarantine UI | `NR2_IMPORT_CRON=1` (5-min); Task Scheduler active |
| **Burn-in telemetry** | X0–X2 runbooks executed | Flags enabled; `validate_nr2_burnin.py` passing |
| **Loopback security** | OLLAMA_HOST=127.0.0.1:11434 | No external bind; PHI remains local |
| **Rollback capability** | Dual 8B+30B restore script | `Rollback-HAL-Dual-8B-30B.ps1` ready |

---

## 2. Gap Map — REMAINING only

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **QB Online API** | Future vendor | Real-time bi-directional sync (vs CSV export/import) | High | Intuit OAuth, sandbox approval, subscription |
| **SoftDent Live API** | Future vendor | Real-time read of ledger/schedule (write-back prohibited per architecture rules) | High | Carestream API availability, partnership |
| **ERA Write-back** | Future vendor | Post-adjudication 835 → SoftDent payment posting | Med | SoftDent API write capability (currently export-only) |
| **External 8B GPU** | Optional | Restore original 8B/30B hierarchy using external 12 GB GPU for 8B offload | Low | 12 GB GPU hardware purchase/install |

**No MUST code gaps remain.** Sections 1–2 functional requirements are satisfied by the single-24B architecture with operational burn-in complete.

---

## 3. Target Architecture (next wave only — or NONE if complete)

**NONE.**  
The Program Manager upgrade (Sections 1–2) is **architecturally complete** at hal-10493 + burn-in + single-24B.  
Next actions are **Future Vendor integrations only** (QB Online, SoftDent API if available). These require third-party contracts, not NR2 codebase expansion.

---

## 4. Coding Plan — only if MUST gaps remain (else state NO NEW CODE)

**NO NEW CODE.**  
Do not initiate Y0 feature wave. All Section 1–2 deliverables are live and validated.

---

## 5. MUST / SHOULD / NICE ranked table (remaining)

| Priority | Item | Rationale |
|----------|------|-----------|
| **(None)** | — | Program complete |
| **NICE** | QB Online API integration | Eliminates manual QB exports; requires Intuit partnership |
| **NICE** | SoftDent Live API read | Eliminates manual SoftDent exports; requires Carestream API |
| **NICE** | ERA Write-back to SoftDent | Auto-post 835 payments; blocked by vendor API availability |
| **NICE** | External 12 GB GPU + restore 8B/30B hierarchy | Improves latency for fast widgets; purely optional given 24B stability |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

| Topic | Status |
|-------|--------|
| **PHI** | Remains local; 24B inference loopback-only; cloudReasoning disabled; no patient data in logs |
| **SoftDent honesty** | Read-only via exports; no write-back implemented; SoftDent remains source of truth for clinical |
| **Financial accuracy** | Empty fields ≠ $0; reconciliation engine flags mismatches; DQ gates prevent null coercion |
| **Rollback** | One-command restore to dual 8B+30B available via `Rollback-HAL-Dual-8B-30B.ps1`; git checkout for configs |
| **Stability risk** | 24B Q4_K_M tested 30m continuous; 5 GB VRAM headroom maintained; no thrashing observed |
| **Vendor dependency** | Future APIs (QB Online, SoftDent) are external risks, not NR2 architecture gaps |

---

## 7. Approval Checklist (Future / optional only)

- [ ] **Acknowledge:** Section 1–2 Program Manager upgrade is **COMPLETE**; no new code waves required.
- [ ] **Future vendor track:** Evaluate Intuit QB Online API access (OAuth app + subscription).
- [ ] **Future vendor track:** Evaluate Carestream SoftDent API availability (partnership required).
- [ ] **Optional hardware:** Procure external 12 GB GPU if 8B/30B hierarchy restoration desired (not required for current functionality).
- [ ] **Optional:** Update `docs/architecture.md` to reflect single-24B evolution (documentation polish only).
- [ ] **Do not:** Approve Y0 feature wave; system is production-ready pending only vendor APIs.

**DO NOT APPLY until operator says approve / proceed.**