# Moonshot AI — How to Improve the Program (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10380  
**Script:** `scripts/run_moonshot_program_improve_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> ask moonshot ai hiw to improve the program. report do not code intil approval

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only; no code until approval)

> "ask moonshot ai hiw to improve the program. report do not code intil approval"

**Confirmed CONSULT-ONLY.** This is a recommendations and feasibility report only. **Moonshot/Cursor will NOT write, apply, or deploy any code** until the operator explicitly states "proceed," "approve," or "do it" with specific scope. All improvements listed below require operator approval before implementation.

---

## 1. Current Program Snapshot (what is strong vs weak at hal-10380)

**Strong (do not redo):**
- **Data Honesty Architecture**: Never invents dollars, claim IDs, ERA %, or clinical facts; honest empty states when imports missing.
- **SoftDent Full Extract**: 1284/1284 transaction parity (ratio 1.0) with register and operatory schedule live.
- **Claims Workbench Phase 1**: Read-only kanban (5-column) + 30/60/90 aging shelves hybrid shipped; HAL focus/filter working.
- **Narratives Insurance Workflow**: Context lock, payer-specific appeals, consent checkboxes, audit trail (`nr2:v2:narratives:audit`), requires human review.
- **Taxes/EBITDA**: C0 import guidance widget, scrubber with citation drill-down, variance detection, voice-to-slider.
- **HAL Board Control**: Sync imports, refresh widgets, navigate, focus claims buckets, filter high-risk/unmatched.

**Weak / Blocking:**
- **Read-Only Constraint**: Claims kanban has **no drag write-back**; cannot update SoftDent status directly. Phase 1 is view-only.
- **July 2026 Data Gap**: `missingPeriods` lists 2026-07 until manual Register export provided (SoftDent CLI auto-export disabled).
- **No True ERA 835 Pipeline**: "ERA Matched" column populated only when SoftDent import happens to contain ERA data; no 835 parsing.
- **Attachment Imaging Gap**: Attachment chips show only when import contains references; no direct imaging integration.
- **HAL Reactivity**: HAL acts on operator command; lacks proactive daily briefings or exception alerts.
- **Underutilized Pages**: Documents, Library, and Office Manager pages lack deep integration with dental workflows (generic placeholders).

---

## 2. Top Improvements — Ranked MUST / SHOULD / NICE

| ID | Rank | Area | Improvement | Why | Effort | Depends on |
|---|---|---|---|---|---|---|
| IMP-001 | **MUST** | Claims | **Workbench Phase 2: Card Actions** — Add "Generate Narrative," "Add Follow-Up Note," and "Schedule Callback" buttons to kanban cards (no drag-drop). Stores actions in NR2 audit log, not SoftDent. | Eliminates dead-end UI; turns read-only kanban into actionable workflow without violating SoftDent read-only constraint. | M (3d) | — |
| IMP-002 | **MUST** | Data | **July 2026 Period Unblock** — Document scheduled Windows Task to export SoftDent Register/Daysheet weekly; add HAL alert when `missingPeriods` detected. | Closes tax/EBITDA data gap immediately; satisfies CPA period-close requirements. | S (1d) | Operator provides Windows Task schedule |
| IMP-003 | **MUST** | HAL | **Proactive Import Health Monitor** — HAL chip/alert when SoftDent export >7 days stale or QuickBooks import missing. Auto-suggests "Refresh SoftDent period imports." | Prevents silent data decay; reduces operator cognitive load. | S (2d) | IMP-002 |
| IMP-004 | **SHOULD** | Claims | **ERA 835 Parser** — Parse electronic remittance files (835) into `era_transactions` table; auto-match to claims by claim ID + patient; populate "ERA Matched" column with real denial codes (CO-45, etc.). | Transforms mockup parity into functional revenue cycle management; honest denial tracking. | L (5d) | IMP-001 (schema stability) |
| IMP-005 | **SHOULD** | A/R | **Aging Forecast Widget** — Project 30/60/90 outlook based on payer historical payment velocity (from 835 data) and current claim velocity. | Gives office manager forward visibility for cash flow planning. | M (3d) | IMP-004 (payer velocity data) |
| IMP-006 | **SHOULD** | Documents | **Claim Attachment Bridge** — Upload/view claim attachments (EOB, pre-auth, x-rays) linked to claim ID; chips in kanban show count. | Completes the claims workflow; supports narrative generation evidence. | M (4d) | — |
| IMP-007 | **SHOULD** | Office Manager | **Daily Huddle Dashboard** — Morning mosaic: operatory utilization (from `sd_operatory_schedule`), claims >90 days, unpaid A/R >$5k, HAL-generated "today's priorities." | Operational command center for S-corp owner. | M (3d) | IMP-003 |
| IMP-008 | **NICE** | Narratives | **Batch Narrative Generation** — Select multiple denied claims; generate appeal narratives with shared context; bulk export to Word/PDF. | Efficiency gain for high-volume denial months. | M (3d) | IMP-001 |
| IMP-009 | **NICE** | HAL | **Voice Context Carry** — "HAL, draft appeal for the high-risk claim I just clicked" — carries claim context into narrative voice input without manual lock. | Reduces clicks; seamless bridge between pages. | S (2d) | IMP-001 |
| IMP-010 | **NICE** | Financial | **EBITDA Trend Chart** — 6-month rolling EBITDA visualization with variance annotations (from existing workpaper data). | Visual storytelling for CPA and banking relationships. | S (2d) | — |

---

## 3. Page-by-Page Improvement Map

### Financial
- **Hold**: EBITDA scrubber and variance detection are strong. 
- **Boost**: Add 6-month trend chart (IMP-010). Add "Export to CPA" button that zips workpapers + citations.

### Taxes
- **Boost**: Complete July 2026 period automation (IMP-002). Add estimated quarterly tax payment tracker widget (manual entry with due-date alerts).

### SoftDent
- **Boost**: Scheduled task documentation for Register export (IMP-002). Add "Data Freshness" KPI widget showing last export timestamp and row counts.

### QuickBooks
- **Boost**: Reconciliation widget comparing SoftDent payments to QB deposits (variance detection). COA mapping visibility (show which QB accounts map to dental revenue categories).

### A/R
- **Boost**: Aging forecast widget (IMP-005). Payer velocity table (average days to pay by insurance carrier).

### Claims
- **Boost**: Phase 2 card actions (IMP-001) — narrative, note, callback. ERA 835 parser (IMP-004). Claim attachment bridge (IMP-006).
- **Hold**: 30/60/90 shelves and kanban layout (do not redesign).

### Narratives
- **Boost**: Batch generation (IMP-008). Payer-specific template library expansion (add 5 common Kansas Medicaid denial templates).
- **Hold**: Context lock, consent flow, audit trail.

### Documents
- **Boost**: Claim attachment viewer (IMP-006). CPA document request workflow — HAL generates checklist of docs needed for tax filing, operator uploads, HAL verifies completeness.

### Library
- **Boost**: Searchable narrative template repository (tagged by procedure, payer, denial code). ERA code reference (CO-45, CO-253 explanations).

### Office Manager
- **Boost**: Daily Huddle Dashboard (IMP-007). Operatory utilization heatmap (from live `sd_operatory_schedule`).

### HAL
- **Boost**: Proactive import health monitor (IMP-003). Voice context carry (IMP-009). "Morning Briefing" chip — one-click summary of overnight import changes, new denials, aging shifts.

---

## 4. HAL Direction Gaps

**What HAL Should Control Next:**

1. **Proactive Data Stewardship**: HAL should surface "Import Health" chips automatically when `softdent.transactionExtract` timestamp >7 days or `missingPeriods` non-empty. Currently HAL waits for operator query.

2. **Claim Lifecycle Orchestration**: HAL actions for "Schedule 30-day follow-up," "Generate appeal narrative," and "Mark as appealed" (stored in NR2 audit table, not SoftDent). These should be board-actions triggered by operator voice or chip click.

3. **Cross-Page Context Carry**: When operator clicks a claim in Workbench then navigates to Narratives, HAL should auto-lock that claim context without manual selection (voice: "HAL, draft appeal for this claim").

4. **Exception-Based Alerts**: HAL should highlight "Claims at Risk" on page load if >5 claims in 90+ bucket or ERA match % drops below threshold (based on real 835 data post-IMP-004).

5. **CPA Collaboration Mode**: HAL action to "Prepare tax package" — zips workpapers, narratives audit log, and variance reports for CPA portal upload.

---

## 5. Data / Import / Honesty Gaps

**SoftDent**:
- **Gap**: July 2026 period missing; requires manual Register export. No vendor CLI automation available.
- **Block**: Schema drift risk if SoftDent v20 changes transaction codes.
- **Mitigation**: Document current v19 code mappings; add version detection to `softdent_transaction_extract.py`.

**QuickBooks**:
- **Gap**: No automated daily sync; relies on manual QB export/import.
- **Block**: QB Online API not connected (local file only).
- **Mitigation**: Add file-watcher on QB export directory for near-real-time import.

**ERA/Attachments**:
- **Gap**: ERA Matched column relies on SoftDent import fields; no native 835 parsing.
- **Block**: Prevents true denial management and appeal automation.
- **Mitigation**: IMP-004 (835 parser) and IMP-006 (attachment bridge).

**Data Honesty**:
- **Constraint**: Cannot invent payer denial scores or claim values.
- **Risk**: Operator may expect drag-drop status update to write back to SoftDent (impossible with current architecture).
- **Mitigation**: UI clearly labels kanban as "Read-Only View" with "Actions" buttons for NR2-side workflow tracking only.

---

## 6. Recommended Phases (I0 validate → In) + Validation Gate

### Phase I0: Validation (Week 1)
**Goal**: Confirm hal-10380 stability before adding features.
- Operator manually exports July 2026 SoftDent Register; verifies C0 widget clears.
- Test Claims kanban with live data; confirm no console errors.
- **Validation Gate**: `parity_ratio == 1.0` on transactions; `missingPeriods` empty; kanban renders <2s.

### Phase I1: Claims Actions + Health (Weeks 2-3)
**Scope**: IMP-001, IMP-002, IMP-003.
- Add card action buttons (narrative, note, callback) to kanban.
- Document Windows Task for weekly SoftDent exports.
- HAL proactive import health alerts.
- **Validation Gate**: Operator can click "Generate Narrative" from kanban card; HAL alerts when export >7 days old.

### Phase I2: ERA Pipeline (Weeks 4-5)
**Scope**: IMP-004, IMP-006.
- Build 835 parser; populate ERA Matched column with real data.
- Claim attachment upload/view.
- **Validation Gate**: Upload sample 835; observe claim move to "ERA Matched" with correct denial code; attachment chips clickable.

### Phase I3: A/R Intelligence (Week 6)
**Scope**: IMP-005, IMP-007.
- Aging forecast widget based on payer velocity.
- Daily Huddle dashboard.
- **Validation Gate**: Forecast chart shows projected 30-day A/R within 5% of actual (test against historical data).

### Phase I4: HAL Autonomy + Polish (Week 7)
**Scope**: IMP-008, IMP-009, IMP-010.
- Batch narratives, voice context carry, EBITDA trends.
- **Validation Gate**: Operator uses voice to draft appeal from kanban without manual context lock; EBITDA chart exports to PDF.

**Moonshot/Cursor codes only after operator approves each phase explicitly.**

---

## 7. Risks, PHI / CPA Disclaimer & Rollback

**PHI Risks**:
- Narrative generation processes claim data locally (safe), but batch export (IMP-008) could expose PHI if saved to unencrypted location. **Mitigation**: Export to `NR2_SECURE_OUTPUTS` directory only; encrypt at rest.
- 835 files contain patient identifiers. **Mitigation**: Parse and immediate redact into NR2 schema; delete raw 835 after import (configurable retention).

**CPA/Tax Risks**:
- EBITDA calculations are advisory only; operator must verify before filing. **Disclaimer**: All tax widgets display "For estimation only — verify with CPA before filing."
- Automated import health does not guarantee data accuracy, only freshness.

**Technical Risks**:
- **SoftDent Schema Drift**: If v20 changes transaction codes, extract will fail. **Rollback**: Revert to `softdent_odbc_extract.py` backup; manual CSV fallback.
- **ERA Parse Errors**: Malformed 835 files could crash parser. **Mitigation**: Wrap in try/except; log failures to `era_import_errors.log`; HAL alerts operator.
- **Read-Only Confusion**: Operator may expect kanban drag-drop to update SoftDent. **Clarification**: UI must clearly state "NR2 Actions Only — Does Not Write to SoftDent."

**Rollback Procedure**:
- All changes additive (new widgets, new tables). Rollback = hide widget in `APEX_PAGES` builder or drop new SQLite tables (`era_transactions`, `claim_actions`). No impact on existing SoftDent/QB import tables.

**DO NOT APPLY until operator says proceed / approve.**