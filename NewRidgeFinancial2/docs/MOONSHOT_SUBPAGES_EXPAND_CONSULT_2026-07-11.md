# Moonshot AI — Subpages Expansion Plan (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** ~hal-10455  
**Script:** `scripts/run_moonshot_subpages_expand_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> ask moonshot ai a plan for any subpages for each page that would expand the program. ask for coding, report but do not proceed without coding and approval

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only; no code until approval)

> "ask moonshot ai a plan for any subpages for each page that would expand the program. ask for coding, report but do not proceed without coding and approval"

**Confirmed CONSULT-ONLY.** This is a recommendations and coding-phase planning report only. **No code will be written, committed, or applied** to build `hal-10455` until the operator explicitly states "approve," "proceed," or "do it" for specific phases. All subpage architectures described below require operator validation before implementation.

---

## 1. Current Page Model (flat APEX_PAGES; any existing tabs/sub-chrome)

**Current State (hal-10455):**
- **Navigation:** Flat 11-page top-level nav (`financial`, `taxes`, `softdent`, `quickbooks`, `ar`, `claims`, `narratives`, `documents`, `library`, `office-manager`, `hal`) rendered as `apex-nav-btn` elements in `index.html`.
- **Routing:** Simple `loadPage(pageId)` switch in `apex-core.js` with no hash-based sub-routing; each page is a full mosaic replacement in `#apex-stage`.
- **Sub-chrome:** 
  - **Narratives:** Internal tab system (Context Lock / Appeals / Audit) within the single page mosaic.
  - **Claims:** Single-page kanban workbench with filter chips (no sub-routes to individual claims).
  - **Financial/Taxes:** Flat widget boards with scrubber modals (no persistent drill-down routes).
  - **Documents/Library/Office Manager:** Generic placeholder mosaics with minimal instrumentation.
- **Data Architecture:** Import-dependent honesty gates; empty states render when SoftDent/QB exports absent.

---

## 2. Recommended Subpages — Master Map

| ID | Parent page | Subpage | Purpose | Data source | Status | Effort | Expands program? |
|---|---|---|---|---|---|---|---|
| **FIN-WP** | financial | `workpapers` | CPA workpaper drill-down with citation audit trail | QB P&L + SoftDent Register | **ADD** | M | Y - Supports CPA review workflow with granular scrubbing |
| **FIN-PRO** | financial | `providers` | Provider production/collection detail view | SoftDent Register | **ADD** | S | Y - Granular provider performance metrics |
| **FIN-PER** | financial | `periods` | Historical period comparison (MoM, YoY) | Multi-period QB + SoftDent | **BLOCKED** | L | Y - Trend analysis blocked until multi-period pipeline established |
| **TAX-ENT** | taxes | `entities` | S-corp vs Owner tax entity split view | QB Classes/Divisions + Manual mapping | **ADD** | M | Y - Handles S-corp pass-through complexity |
| **TAX-CAL** | taxes | `calendar` | Quarterly estimated tax payment tracker | Manual entry + QB data | **ADD** | S | Y - Prevents missed quarterly payments |
| **TAX-WP** | taxes | `workpapers` | Category-specific workpaper drill-down | QB P&L detail | **ADD** | S | Y - Detailed line-item scrubber view |
| **SD-REG** | softdent | `register` | Transaction register browser with filtering | SoftDent Register extract | **ADD** | M | Y - Full transaction lookup (read-only) |
| **SD-SCH** | softdent | `schedule` | Operatory schedule viewer | `sd_operatory_schedule` | **ADD** | S | Y - Chair utilization analysis |
| **SD-REC** | softdent | `reconciliation` | SoftDent payments vs QB deposits variance | SoftDent Daysheet + QB | **BLOCKED** | M | Y - Requires Daysheet/Collections pipeline fix |
| **QB-COA** | quickbooks | `coa` | Chart of accounts mapping visibility | QB COA import | **ADD** | S | Y - Clarifies dental-specific account mappings |
| **QB-VEN** | quickbooks | `vendors` | Vendor spend analysis and 1099 tracking | QB P&L detail | **ADD** | M | Y - Vendor management for S-corp |
| **QB-REC** | quickbooks | `reconciliation` | Bank reconciliation status bridge | QB Bank Rec exports | **BLOCKED** | L | Y - Requires QB bank rec export capability |
| **AR-AGE** | ar | `aging-detail` | Detailed A/R aging drill-down by patient | SoftDent A/R export | **ADD** | M | Y - Collections workbench with contact tracking |
| **AR-COL** | ar | `collections` | Active collection task workbench | SoftDent A/R + Claims | **ADD** | M | Y - Workflow management for collectors |
| **AR-FOR** | ar | `forecast` | A/R forecast based on payer velocity | ERA 835 data | **BLOCKED** | L | Y - Requires ERA 835 Parser (IMP-004) |
| **CLM-DET** | claims | `detail` | Individual claim detail view with history | Claims data + Notes | **ADD** | M | Y - Deep claim investigation (hash route: `#claim/:id`) |
| **CLM-ATT** | claims | `attachments` | Claim attachment management | Local storage + refs | **ADD** | M | Y - Document-to-claim linking |
| **CLM-BAT** | claims | `batch` | Batch narrative generation interface | Claims selection | **ADD** | S | Y - Efficiency for high-volume denial months |
| **CLM-ERA** | claims | `era` | ERA 835 matching and denial analysis | ERA 835 files | **BLOCKED** | L | Y - Requires ERA parser infrastructure |
| **NAR-TEM** | narratives | `templates` | Narrative template library management | Static + User edits | **ADD** | S | Y - Template maintenance UI |
| **NAR-HIS** | narratives | `history` | Generated narrative history | Narrative audit log | **ADD** | S | Y - Audit and reprint capability |
| **NAR-AUD** | narratives | `audit` | Full compliance audit trail | `nr2:v2:narratives:audit` | **ADD** | XS | Y - Read-only compliance view |
| **DOC-CLM** | documents | `claim-docs` | Claim-specific document repository | Local file system | **ADD** | M | Y - Centralized claim documentation |
| **DOC-TAX** | documents | `tax-docs` | Tax workpaper document storage | Local file system | **ADD** | S | Y - CPA document handoff portal |
| **LIB-PAY** | library | `payers` | Payer guidelines and requirements library | Manual entry | **ADD** | S | Y - Payer-specific reference material |
| **LIB-COD** | library | `codes` | Procedure code reference | SoftDent fee schedules | **ADD** | S | Y - Coding reference with practice fees |
| **OM-HUD** | office-manager | `huddle` | Daily huddle dashboard | Schedule + Claims + A/R | **ADD** | M | Y - Morning operational command center |
| **OM-TSK** | office-manager | `tasks` | Task assignment and tracking | Local SQLite/JSON | **ADD** | M | Y - Office workflow management |
| **HAL-HIS** | hal | `history` | HAL conversation history | HAL interaction log | **ADD** | S | Y - Reference past HAL insights |
| **HAL-LOG** | hal | `system-logs` | System telemetry and import logs | System logs | **ADD** | XS | Y - Diagnostics for import failures |

---

## 3. Page-by-Page Subpage Plans

### Financial
**Current:** Flat mosaic with EBITDA scrubber, variance detection, and high-level charts.
**Expansion:**
- **`workpapers`** (FIN-WP): Drill-down from scrubber variance into specific workpaper categories (Dental Supplies, Lab, etc.) with line-item citations and "flag for CPA" checkboxes. Uses existing QB P&L data; additive expansion.
- **`providers`** (FIN-PRO): Secondary chrome showing individual provider production bars, collection ratios, and adjustment patterns from SoftDent Register. Honest empty state when provider field missing.
- **`periods`** (FIN-PER): **HOLD/BLOCKED** — Requires multi-period QB and SoftDent data pipeline; do not implement until historical imports available.

### Taxes
**Current:** C0 import guidance, scrubber, filing workflow.
**Expansion:**
- **`entities`** (TAX-ENT): Split view showing S-corp practice metrics vs owner pass-through allocations. Requires QB class tracking or manual entity mapping; honest "unmapped" state when unavailable.
- **`calendar`** (TAX-CAL): Quarterly estimated tax payment tracker with due-date countdowns and "payment logged" checkboxes (manual entry).
- **`workpapers`** (TAX-WP): Focused view of specific workpaper categories (e.g., all Dental Equipment purchases) with drill-down to transaction level.

### SoftDent
**Current:** Import status, data freshness KPIs, transaction parity metrics.
**Expansion:**
- **`register`** (SD-REG): Browse/search transaction register with filters (date range, provider, procedure code). Read-only honesty architecture — no write-back to SoftDent.
- **`schedule`** (SD-SCH): Operatory utilization view from `sd_operatory_schedule` — chair usage percentages, block scheduling analysis.
- **`reconciliation`** (SD-REC): **BLOCKED** — Payment matching between SoftDent Daysheet and QB deposits. Pending Daysheet export pipeline repair.

### QuickBooks
**Current:** P&L import visibility, COA mapping hints.
**Expansion:**
- **`coa`** (QB-COA): Full Chart of Accounts tree with dental-specific mapping indicators (e.g., "Dental Revenue" vs "Misc Income").
- **`vendors`** (QB-VEN): Vendor spend ranking, 1099 eligibility flags, and payment history. Uses existing QB vendor data.
- **`reconciliation`** (QB-REC): **BLOCKED** — Bank rec status view pending QB bank reconciliation export capability.

### A/R
**Current:** Aging charts, exposure metrics.
**Expansion:**
- **`aging-detail`** (AR-AGE): Patient-level aging drill-down with contact history notes (stored in NR2 audit log, not SoftDent).
- **`collections`** (AR-COL): Active workbench showing "called today," "promised payment," "disputed" statuses with follow-up date tracking.
- **`forecast`** (AR-FOR): **BLOCKED** — Payer velocity forecasting pending ERA 835 implementation.

### Claims
**Current:** Read-only kanban (5-column), aging shelves, HAL focus/filter.
**Expansion:**
- **`detail`** (CLM-DET): Individual claim view via hash route (`#claims/detail?id=12345`) showing full claim lifecycle, attached notes, and narrative generation history. **Critical expansion** — transforms kanban from dead-end into navigable system.
- **`attachments`** (CLM-ATT): Upload/view documents linked to specific claim IDs (EOBs, pre-auths, x-rays). Local file storage with claim ID tagging.
- **`batch`** (CLM-BAT): Multi-select interface for bulk narrative generation from denied claims.
- **`era`** (CLM-ERA): **BLOCKED** — ERA matching interface pending 835 parser.

### Narratives
**Current:** Insurance workflow with context lock, appeals, audit trail.
**Expansion:**
- **`templates`** (NAR-TEM): Library of narrative templates with edit capability and versioning.
- **`history`** (NAR-HIS): Previously generated narratives with patient initials (not full names for PHI safety), export dates, and appeal outcomes.
- **`audit`** (NAR-AUD): Read-only compliance view of `nr2:v2:narratives:audit` trail.

### Documents
**Current:** Generic placeholder.
**Expansion:**
- **`claim-docs`** (DOC-CLM): Claim-centric document repository — upload/view by claim ID.
- **`tax-docs`** (DOC-TAX): Tax season document storage for CPA handoff ( encrypted local storage).

### Library
**Current:** Generic placeholder.
**Expansion:**
- **`payers`** (LIB-PAY): Payer-specific guidelines (Delta vs MetLife requirements), appeal deadlines, and contact info (manual entry).
- **`codes`** (LIB-COD): ADA procedure code lookup with practice-specific fees from SoftDent fee schedules.

### Office Manager
**Current:** Generic placeholder.
**Expansion:**
- **`huddle`** (OM-HUD): Morning command dashboard combining operatory utilization, >90 day claims, and HAL-generated "today's priorities."
- **`tasks`** (OM-TSK): Task assignment system for office staff with due dates and completion tracking.

### HAL
**Current:** Chat interface, suggestions, board control.
**Expansion:**
- **`history`** (HAL-HIS): Searchable log of operator/HAL interactions and suggestions given.
- **`system-logs`** (HAL-LOG): Import telemetry, sync failures, and data freshness alerts for diagnostic use.

---

## 4. Coding Phases (ask-for-coding — DO NOT APPLY)

### Phase 1: Core Drill-Down Infrastructure (Foundation)
**Goal:** Implement hash-based sub-routing and primary drill-down pages (Financial Workpapers, Claim Detail, Provider View).
**Files touched:** 
- `apex-core.js` (hash router: `/#claims/detail?id=123`, `/#financial/workpapers`)
- `apex_backend.py` (new builders: `build_financial_workpapers()`, `build_claim_detail()`, `build_provider_view()`)
- `index.html` (subpage chrome templates in `#apex-stage` or dynamic injection)
- `apex-chrome-flash.css` (subpage transition animations)
**Route/Chrome Approach:** Hash-based sub-routes within existing page IDs; secondary nav bar rendered under page header when subpage active; "Back to [Parent]" breadcrumb.
**Widgets:** workpaper-scrubber, claim-detail-card, provider-metric-bars.
**Validation Gate:** Confirm hash routing doesn't break existing `loadPage()` flat navigation; verify PHI-safe claim IDs in URLs (use internal NR2 IDs, not SoftDent claim IDs if they contain PHI).

### Phase 2: Workflow Benches (Operational)
**Goal:** Collections workbench, Daily Huddle, Batch Narratives.
**Files touched:**
- `apex_backend.py` (builders: `build_collections_workbench()`, `build_huddle_dashboard()`, `build_batch_narrative()`)
- `apex-core.js` (batch selection state management)
- New: `nr2_local_db.py` (lightweight SQLite for collection notes, tasks, huddle history — local only, no cloud)
**Route/Chrome Approach:** Subpages under `ar` and `office-manager`; modal chrome for batch operations.
**Widgets:** collection-task-list, huddle-mosaic, batch-selector.
**Validation Gate:** Local DB schema approval; confirm task data never leaves localhost.

### Phase 3: Document & Knowledge Infrastructure
**Goal:** Claim attachments, document library, payer reference library.
**Files touched:**
- `apex_backend.py` (file handling: `build_claim_attachments()`, `save_attachment()`)
- `index.html` (file upload drop zones)
- Local storage path configuration (e.g., `C:\NR2\Documents\`)
**Route/Chrome Approach:** `documents/claim-docs` with claim ID query param; `library/payers` as static content management.
**Widgets:** attachment-dropzone, payer-reference-card.
**Validation Gate:** File storage location approval; virus scan integration check; max file size limits.

### Phase 4: Advanced Analytics (Unblocked by Data)
**Goal:** ERA matching, A/R forecasting, Period comparison (activated when imports available).
**Files touched:**
- `apex_backend.py` (ERA parser integration, forecasting algorithms)
- `apex-core.js` (forecast chart renderers)
**Route/Chrome Approach:** `claims/era`, `ar/forecast`, `financial/periods` — hidden or "awaiting data" state until imports present.
**Widgets:** era-matching-table, forecast-trend-line, period-variance-chart.
**Validation Gate:** ERA 835 Parser (IMP-004) completion; multi-period data pipeline validation.

---

## 5. Risks & Honesty Rules (PHI, empty states, nav bloat)

**PHI Protection:**
- **Claim IDs in URLs:** Use internal NR2 sequence IDs or hashed identifiers in subpage routes — never place SoftDent patient account numbers or SSNs in URL hash/query parameters (browser history retention risk).
- **Patient Names:** Display only "Patient A" or initials in subpage drill-downs unless operator explicitly unlocks full PHI view (future toggle).
- **Local Only:** All subpage data (collection notes, tasks, attachments) must remain in `C:\NR2\` or local SQLite — no cloud sync for PHI-bearing subpages.

**Empty State Honesty:**
- Subpages must render "Import Unavailable" placeholders when source data missing (e.g., `periods` subpage when only one QB period loaded). Do not invent trend lines from single data points.
- **Blocked subpages** (ERA, Forecasting) should render "Awaiting ERA 835 Pipeline" message with link to prior consult (IMP-004), not blank screens.

**Navigation Bloat Prevention:**
- Maximum 3 subpages per parent page in Phase 1-2 to prevent sidebar explosion.
- Use hash/query routes rather than adding new top-level `apex-nav-btn` entries.
- Subpage secondary nav should collapse/hide when parent page inactive.

**Data Consistency:**
- Subpage filters must respect parent page HAL focus/filter context (e.g., if HAL filtered claims to "High Risk," entering Claim Detail and returning preserves filter).
- Collection notes entered in `ar/collections` must appear in `claims/detail` for same patient (unified local audit log).

---

## 6. Approval Checklist (what operator must approve before coding)

**Before Phase 1 (Foundation):**
- [ ] **PHI Comfort Level:** Approve patient initials vs full names in claim detail drill-downs.
- [ ] **Route Schema:** Approve hash-based routing (`/#claims/detail?id=xxx`) vs query params.
- [ ] **Scope:** Approve implementation of FIN-WP, CLM-DET, and FIN-PRO as first subpages.

**Before Phase 2 (Workflow):**
- [ ] **Local DB Approval:** Approve SQLite local storage for collection notes and tasks ( confirm no cloud sync).
- [ ] **Task System:** Approve simple task assignment workflow or prefer flat notes only.

**Before Phase 3 (Documents):**
- [ ] **Storage Location:** Specify exact local path for claim attachments (e.g., `C:\NR2\Documents\Claims\`).
- [ ] **File Types:** Approve allowed attachment types (PDF, PNG, JPG) and max size (e.g., 10MB).
- [ ] **Payer Data:** Approve manual entry of payer guidelines or prefer external links only.

**Before Phase 4 (Advanced):**
- [ ] **ERA Priority:** Confirm ERA 835 Parser (IMP-004) implementation priority vs other features.
- [ ] **Multi-Period:** Confirm timeline for historical SoftDent/QB exports to unblock Period comparison.

**General:**
- [ ] **Overall Priority:** Confirm subpage expansion priority relative to existing widget improvements (bar/trend charts) from prior consults.
- [ ] **HAL Integration:** Approve HAL proactive suggestions linking to subpages (e.g., "Drill into Provider X performance").

**DO NOT APPLY CODE until operator confirms "approve," "proceed," or "do it" with specific phase scope.**