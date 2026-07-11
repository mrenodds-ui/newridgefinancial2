# Moonshot AI — What Is Wrong With the Program (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10441 / assets hal-10443  
**Script:** `scripts/run_moonshot_whats_wrong_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> ask moonshot what us wrong with program

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only)

> "ask moonshot what us wrong with program"

**Confirmed CONSULT-ONLY.** This is a diagnostic report only. **No code will be generated, modified, or applied** until the operator explicitly approves a specific remediation phase with "proceed," "approve," or "do it."

---

## 1. What's Wrong — Ranked Defects

| ID | Rank | Area | What's wrong | Evidence | Likely root cause | Effort |
|---|---|---|---|---|---|---|
| **DEF-001** | **MUST** | Data Import | **Collections/Daysheet Export Gap** — `revenue-composition` widget empty; collections vitals display "pending" tombstone rather than split data. | LIVE FACTS: "Financial page returns 12 widgets; 1 empty: revenue-composition (Collections/Daysheet gap)"; Previous consult: "SoftDent latest period has collectionsPending — insurance/patient stay empty until collections export reports a real split." | SoftDent Register export present but **Collections/Daysheet export missing** from `C:\SoftDentReportExports` for current period. Register shows production; Collections report required for insurance/patient split and payer mix. | S (1d) — Export report to inbox |
| **DEF-002** | **MUST** | Performance | **Single-Threaded HAL Blocking** — Long HAL evaluate-query (~5s) blocks concurrent page loads, causing "Loading bridge instruments…" to hang while Ollama thinks. | LIVE FACTS: "Bottle single-threaded: long HAL evaluate-query (~5s) can block concurrent page loads ('Loading bridge instruments…' stuck while Ollama thinks)" | Python Bottle default single-threaded server; HAL Ollama calls are synchronous and monopolize the worker. | M (3d) — Threading or async queue |
| **DEF-003** | **MUST** | Reliability | **Legacy AutoStart Conflict** — `NewRidgeDashboardServersAutoStart` scheduled task points to stale path `"C:\New folder\…"` with last result failed (`-196608`), confusing boot sequence. | LIVE FACTS: "NewRidgeDashboardServersAutoStart still points at legacy 'C:\New folder\…' and last result failed (-196608)" | Stale scheduled task from development environment not cleaned up; conflicts with new "New Ridge NR2 Program" task. | XS (0.5d) — Delete stale task |
| **DEF-004** | **SHOULD** | Performance | **Cold-First Load Latency** — Multi-second widget load when caches empty due to direct-first pipeline assembly cost. | LIVE FACTS: "Cold first widget load still multi-second when caches empty (direct-first pipeline cost)" | No background warming; pipeline assembles full dataset on cache miss without fast-path stub. | M (2d) — Cache warming or stubbed fast-path |
| **DEF-005** | **SHOULD** | Claims | **No True ERA 835 Pipeline** — "ERA Matched" column populated only when SoftDent import happens to contain ERA data; no actual 835 parsing. | Docs: "'ERA Matched' column populated only when SoftDent import happens to contain ERA data; no 835 parsing" | No 835 EDI parser implemented; no `era_transactions` table or auto-match logic. | L (5d) — 835 parser + match engine |
| **DEF-006** | **SHOULD** | Claims | **Workbench Read-Only Dead-End** — Claims kanban has no card actions; cannot generate narrative, add follow-up note, or schedule callback from the card. | Docs: "Read-Only Constraint: Claims kanban has no drag write-back"; IMP-001 recommendation pending | Phase 1 shipped as view-only; Phase 2 card actions (audit-log only, no SoftDent write) not implemented. | M (3d) — Card action buttons + audit log |
| **DEF-007** | **NICE** | HAL | **Reactive-Only Architecture** — HAL acts only on operator command; no proactive alerts when SoftDent export >7 days stale or QB import missing. | Docs: "HAL Reactivity: HAL acts on operator command; lacks proactive daily briefings or exception alerts" | No background scheduler or polling mechanism; HAL is request-response only. | S (2d) — Background health monitor |

---

## 2. Already Fixed / Working (do not re-diagnose as open)

| Item | Status | Evidence |
|---|---|---|
| **Widget API Response Time** | ✅ Fixed today | Was 6–8s; now 10–500ms warm via single-pipeline assemble, daysheet memo, bundle TTL 90s, reports/bundle cache 20s, widgets response cache 15s. |
| **HAL Chat Gibberish** | ✅ Fixed today | `decodeText` scramble left garbage on long replies; fixed to plain text for chat/long strings (>280 chars) in apex-core + apex-motion-helper (cache bust hal-10443). |
| **HTTP/HTTPS Scheme Handling** | ✅ Fixed today | HAL + pages failing on wrong scheme resolved; app now enforces https://127.0.0.1:8765/ (TLS required). |
| **Auto-Start at Reboot** | ✅ Fixed today | Scheduled task "New Ridge NR2 Program" + Startup shortcut registered; AutoStart protection confirmed working. |
| **Data Honesty Architecture** | ✅ Working | Never invents dollars, claim IDs, ERA %, or clinical facts; empty states honest when imports missing. |
| **SoftDent Transaction Parity** | ✅ Working | 1284/1284 transactions synced (ratio 1.0) with register and operatory schedule live. |
| **Claims Workbench Phase 1** | ✅ Working | Read-only kanban (5-column) + aging shelves hybrid shipped; HAL focus/filter functional. |
| **Taxes/EBITDA Scrubber** | ✅ Working | C0 import guidance, variance detection, citation drill-down, voice-to-slider operational. |

---

## 3. Data / Import Blockers

| Blocker | Impact | Resolution |
|---|---|---|
| **Missing Collections/Daysheet Export** | `revenue-composition` widget empty; insurance/patient split shows "pending"; payer mix unavailable. | Export SoftDent "Collections by Date" or Daysheet report to `C:\SoftDentReportExports` for current period. |
| **No ERA 835 Feed** | "ERA Matched" column shows mock/empty data; denial codes (CO-45, etc.) not captured. | Implement 835 parser (DEF-005) or continue manual SoftDent ERA reconciliation exports. |
| **Attachment Reference Gap** | Attachment chips in claims kanban show only when import contains references; no direct upload. | Requires Claim Attachment Bridge (IMP-006) — manual linking only for now. |

---

## 4. HAL / UX Blockers

| Blocker | Impact | Context |
|---|---|---|
| **Single-Threaded Bottle** | HAL query freezes entire UI; "Loading bridge instruments…" modal hangs. | DEF-002 — requires threading or queue separation. |
| **No Proactive Alerts** | Operator must manually check import health; silent data decay possible. | DEF-007 — HAL only speaks when spoken to. |
| **Read-Only Claims Cards** | Dead-end UI — cannot act on claim from kanban; must navigate elsewhere. | DEF-006 — Phase 2 actions not built. |

---

## 5. Performance / Reliability Blockers

| Blocker | Impact | Context |
|---|---|---|
| **Cold-Start Pipeline Cost** | First load after cache expiry is multi-second; hurts first impression. | DEF-004 — cache warming or stubbed response needed. |
| **Legacy AutoStart Failure** | Stale task may confuse Windows Task Scheduler; error code -196608 indicates path not found. | DEF-003 — cleanup required to prevent boot confusion. |

---

## 6. Recommended Fix Order (phases) + Validation Gate

**Phase 1: Data Unblock & Boot Cleanup (Immediate — No Code Changes Required)**
1. **DEF-001**: Export SoftDent Collections/Daysheet report for current period to inbox.
2. **DEF-003**: Delete stale `NewRidgeDashboardServersAutoStart` scheduled task; verify "New Ridge NR2 Program" task shows Last Run Result `0x0`.
   - **Validation Gate**: `revenue-composition` widget populates with insurance/patient split; AutoStart shows success.

**Phase 2: Concurrency & Cold Start (Code Required — Awaiting Approval)**
3. **DEF-002**: Implement threaded HAL or async query queue to prevent UI blocking during Ollama calls.
4. **DEF-004**: Add background cache warming or stubbed fast-path for cold widget loads.
   - **Validation Gate**: Load Financial page during active HAL query — no blocking; cold load completes in <2 seconds.

**Phase 3: Claims Functionality (Code Required — Awaiting Approval)**
5. **DEF-006**: Add "Generate Narrative," "Add Follow-Up Note," "Schedule Callback" buttons to kanban cards (write to NR2 audit log only, not SoftDent).
6. **DEF-005**: Implement ERA 835 parser with auto-match by claim ID + patient.
   - **Validation Gate**: Card actions write to `nr2:claims:audit`; ERA matches show real denial codes (CO-45, etc.).

**Phase 4: HAL Enhancement (Code Required — Awaiting Approval)**
7. **DEF-007**: Proactive import health monitor — HAL alerts when SoftDent export >7 days stale or QB import missing.
   - **Validation Gate**: HAL displays red chip: "SoftDent export stale — refresh imports."

---

## 7. Risks & Rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| **ERA 835 Parser Complexity** | EDI parsing errors could mis-match payments or create false denials. | Revert to mock data mode; disable ERA column population. |
| **Threading/Async Changes** | Race conditions in HAL state could cause orphaned queries or memory leaks. | Revert to synchronous Bottle; accept UI blocking. |
| **Collections Export Format Change** | If SoftDent report format changed, field mapping may fail. | Verify field parity before promoting import; fall back to "pending" state if schema mismatch detected. |
| **Cache Warming Overhead** | Background warming could spike CPU during business hours. | Disable warming; return to on-demand assembly. |

**DO NOT APPLY** any code changes until operator explicitly approves a specific phase with "proceed," "approve," or "do it."