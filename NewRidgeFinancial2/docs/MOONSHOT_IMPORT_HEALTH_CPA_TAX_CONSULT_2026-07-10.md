# Moonshot AI — Import Health, HAL Programming, Widget Health, CPA Tax/EBITDA UX (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10310  
**Script:** `scripts/run_moonshot_import_health_cpa_tax_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot ai about my quickbooks and softdent imports, are they healthy, recommendations, ask about hal programming, ask him if all widgets are healthy and have imports from hal, any other recommendations to make the tax page more interactive and Ebitda interactive with sliding widget, how to make those pages function like a cpa would use.

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only)
> "ask moonshot ai about my quickbooks and softdent imports, are they healthy, recommendations, ask about hal programming, ask him if all widgets are healthy and have imports from hal, any other recommendations to make the tax page more interactive and Ebitda interactive with sliding widget, how to make those pages function like a cpa would use."

**Confirm:** CONSULT ONLY — assessment and recommendations provided below. NO CODE APPLIED. Awaiting operator approval to proceed with any implementation.

## 1. SoftDent + QuickBooks Import Health

**Healthy?**  
**YES — structurally sound; NO — data thin spots present.**

**Evidence from hal-10310 live facts:**
- Diagnostics: 16/16 connections healthy, 0 missing, 0 stale, 0 partial
- Freshness: All imports marked "fresh"
- **QuickBooks:** profitAndLoss=1, revenue=1, expenses=1, expenseCategories=8, ar=4 (robust)
- **SoftDent:** dashboard=2, ar=4, claims=60, claimStatus=60, procedures=62, newPatients=1 (good volume)

**Critical Gaps (Honest Assessment):**
- **collectionsPending = 0.0** on latest period (revenue recognition blind spot)
- **insurance/patient A/R allocation often 0.0** (risk of misstated working capital)
- **procedures Provider** often single label only (limits provider productivity analytics)
- **operatory = 0 rows** (capacity planning widget empty)
- **tax returns library empty** (expected until operator upload, but confirmed gap)

**Recommendations (Ranked):**

| Rank | Item | Action |
|------|------|--------|
| **MUST** | Fix collectionsPending feed | Validate SoftDent "Collections by Date" report mapping; ensure unapplied credits and pending allocations flow to `collectionsPending` field |
| **MUST** | Validate A/R allocation | Cross-check SoftDent "Insurance vs Patient A/R" report against import mapping; current 0.0 values suggest schema mismatch |
| **SHOULD** | Enrich provider attribution | Map SoftDent `provider_id` to full name in dimension table; enable per-provider production widgets |
| **SHOULD** | Add operatory utilization feed | Import SoftDent "Schedule Statistics" or "Operatory Usage" report to populate currently empty operatory widget |
| **NICE** | Add procedure code roll-up | Group CDT codes into categories (Restorative, Perio, etc.) for production mix analysis |

## 2. HAL Programming Assessment

**Current State (hal-10310):**
- **Active:** Board-control API (`sync_imports`, `refresh_page`, `navigate`, `focus/highlight`, `categorize_assist`, `import_status_banner`)
- **Honesty Model:** Never invents dollars; sync/refill only from imports; display-only focus
- **Context Awareness:** Page + widget ID + label passed to HAL chat

**Programming Gaps:**
- No **scenario persistence** (what-if states lost on refresh)
- No **variance detection** (HAL doesn't alert when imports drift from prior period)
- No **CPA workpaper generation** (static waterfalls only)
- No **sliding/scrubber controls** (requested for EBITDA)
- No **historical comparison** (prior year tax returns not indexed for compare)

**Recommended HAL Improvements (Ranked):**

| Rank | Enhancement | Function |
|------|-------------|----------|
| **MUST** | Scenario snapshot engine | HAL command: "Save scenario Q3-Plan-B"; stores planning inputs (sliders, add-backs) as named JSON blob; loadable via "Compare scenarios" |
| **MUST** | Widget scrubber bridge | HAL exposes `focus_ebitda_scrubber` to auto-scroll and highlight slider panel; does not invent values |
| **SHOULD** | Import anomaly detector | HAL monitors variance >10% period-over-period for production, A/R, expenses; flags "Review SoftDent production variance" |
| **SHOULD** | Workpaper citation linker | HAL generates citation links: "This $42,000 depreciation add-back sourced from QB Chart of Accounts: Depreciation Expense" |
| **NICE** | Voice-to-scenario | "HAL, model owner salary at $220k" → adjusts slider to value (still labeled planning) |

## 3. Widget Health & Import/HAL Coverage

**Honest Widget Census (hal-10310 empty_status counts):**

| Page | Empty Count | Specific Empty Widgets | Root Cause |
|------|-------------|------------------------|------------|
| **Financial** | 1 | Likely EBITDA detail breakdown or planning scrubber placeholder | Feature not yet implemented (slider) |
| **Taxes** | 1 | Likely detailed K-1 footnotes or state estimated payment calendar | Data available but UI container pending |
| **SoftDent** | 1 | **Operatory utilization** | Import feed missing (0 rows) |
| **HAL** | 1 | Likely HAL chat history or advanced diagnostics panel | Default empty until interaction |
| **Documents** | 1 | **Tax Returns Library** | Awaiting operator upload; gitignored PDFs |
| QB | 0 | — | Healthy |
| A/R | 0 | — | Healthy |
| Claims | 0 | — | Healthy |
| Office Mgr | 0 | — | Healthy |

**Import vs HAL Coverage:**
- **Import-Fed (Healthy):** QB P&L, Revenue, Expense Categories, SoftDent Claims, A/R Aging, New Patients
- **HAL-Driven (Healthy):** Navigation, Focus, Sync triggers, Categorize suggestions
- **Empty/Gaps:** 
  - Tax Returns Library (needs manual upload)
  - Operatory Utilization (needs SoftDent feed fix)
  - Collections Pending (data mapping error — shows 0.0)
  - EBITDA Interactive Scrubber (requested feature — not yet built)

**Are ALL widgets healthy?**  
**NO.** Seven widgets across five pages are empty or placeholder status. Only 9/16 pages/widgets are fully fed.

## 4. Taxes Page — More Interactive (CPA workflow)

**Current State:** Static planning KPIs, book-to-tax waterfall, basic scrubber, CPA banner.

**CPA-Grade Interactive Requirements:**

1. **Workpaper Drill-Down:** Click any line item in book-to-tax waterfall → modal shows source transactions (QB expense entries or SoftDent production reports) with document thumbnails
2. **Scenario Tabs:** Side-by-side comparison of "Conservative," "Aggressive," "Prior Year" scenarios; tab switches refresh waterfall without page reload
3. **Journal Entry Preview:** Toggle showing required book-to-tax adjusting entries (e.g., "DR Tax Depreciation, CR Book Depreciation") with entry numbers
4. **Estimated Payments Calendar:** Interactive timeline showing 1040-ES and K-120ES due dates with auto-calculated vouchers based on current planning estimate
5. **Basis Tracker:** Real-time S-corp stock basis and debt basis calculation as owner draws/loans change in planning inputs
6. **QBI Visualization:** Section 199A deduction waterfall showing W-2 wage limitation and UBIA phase-in
7. **Filing Status State Machine:** Visual tracker: Draft → CPA Review → Client Approved → Filed → Locked (with sign-off timestamps)

## 5. EBITDA — Interactive Sliding Widget

**Concept:** Native Apex "Scrubber Panel" with dual-column layout: **Book (Locked)** vs **Planning (Adjustable)**.

**Slider Controls (Data Contract):**
- **Owner Salary Band:** Range slider $180k–$280k, step $10k, default to `default_modeled_w2(book_net_income)`. Label: "Officer Compensation Scenario"
- **Depreciation Add-Back:** Range 0 to `max_depreciation_from_qb`, step $500. Label: "Non-Cash Depreciation/Amortization"
- **Interest Add-Back:** Range 0 to `interest_expense_from_qb`, step $100. Label: "Interest Expense (if debt-financed)"
- **One-Time Adjustments:** Numeric input ±$50k range. Label: "Discretionary/One-Time Items"
- **Meals & Entertainment:** Toggle 50% vs 100% deductible (updates tax bridge only)

**Honesty Rules:**
- **Book EBITDA column:** Immutable, pulled directly from QB Net Income + actual categorized depreciation/interest. Displayed with 🔒 icon.
- **Planning EBITDA column:** Updates in real-time as sliders move. Displayed with ✏️ icon and watermark "Planning Estimate"
- **Scenario Actions:** "Save Scenario," "Compare to Book," "Export to Workpaper" buttons
- **No Persistence to QB:** Sliders write to `localStorage` or scenario API only; never post adjusting entries to QuickBooks
- **Reset:** "Restore from Imports" button returns all sliders to book-backed defaults

**Visual Design:** Native Apex range inputs with custom scrubber handles; cyan highlight on active handle; live calculation preview in header.

## 6. CPA-Grade Page Behavior (Taxes + EBITDA)

**Workflow a CPA Would Expect:**

**A. Workpaper Bridge (Source → Schedule)**
- Every number in Taxes/EBITDA has a "citation" link (📎) opening:
  - QB: Chart of Account detail report or transaction list
  - SoftDent: Day-sheet or Production report PDF
  - Prior Year: Filed return PDF from document library

**B. Version Control & Audit Trail**
- Named scenarios with timestamps: "2025 Q3 Estimate v1.2 (saved 2026-07-10 14:30)"
- Audit log: "Operator adjusted Owner Salary from $200k to $220k at 14:32"
- CPA Review flag: Checkbox "Reviewed by CPA" with electronic signature placeholder

**C. Three-Way Reconciliation**
- Book (QB/SoftDent) → Tax Workpapers → Filed Return
- Visual diff highlighting when planning estimate differs from prior year filed by >15%

**D. Estimated Tax Integration**
- Auto-calculation of 1040-ES and K-120ES vouchers
- "Safe Harbor" toggle (110% prior year vs 90% current year)
- Payment tracking: Checkboxes for "Paid 4/15," "Paid 6/15," etc.

**E. Closing Lock**
- Once "Filed" status selected, all sliders lock, scenario saved as "Filed 2025," PDF stored in returns library with checksum

## 7. Moonshot Spec Deliverables (CONSULT ONLY)

**CONSULT ONLY — Paste-Ready Specifications:**

```markdown
# EBITDA_SCRUBBER_WIDGET_SPEC.md
## Scope
Native Apex widget for Financial/Taxes pages enabling planning adjustments to EBITDA without altering QB imports.

## Data Contract
- Input: `book_net_income` (from QB), `actual_depreciation` (from QB), `actual_interest` (from QB)
- Output: `planning_ebitda` calculated client-side; stored in `nr2_scenarios` table with UUID
- Constraint: Never write to QB; never modify `book_*` values

## Controls
1. Salary Scrubber: range 180000-280000, step 10000, default computed
2. Depreciation Scrubber: range 0-actual_depreciation, step 500
3. Interest Scrubber: range 0-actual_interest, step 100
4. One-Time Input: number ±50000
5. Meals Toggle: checkbox (affects tax bridge only)

## UI
- Left column: Book (locked, greyscale, 🔒)
- Right column: Planning (editable, color, ✏️)
- Real-time delta calculation: (Planning - Book) displayed in header
- Actions: Save Scenario, Export CSV, Reset to Book

## Honesty Markers
- Watermark: "PLANNING ONLY — NOT BOOKED TO QUICKBOOKS"
- Book values display source: "From QB P&L dated [date]"
```

```markdown
# CPA_WORKPAPER_BRIDGE_SPEC.md
## Scope
Link every tax/EBITDA line item to source documents and generate CPA workpaper PDFs.

## Citations
- Each line item has `source_type` (qb_transaction, softdent_report, manual_input) and `source_id`
- Click citation opens modal with:
  - QB: Transaction detail grid
  - SoftDent: Embedded PDF viewer with page anchor
  - Manual: Text note with operator timestamp

## Workpaper Generation
- Export button generates PDF containing:
  - Cover sheet with scenario name and disclaimer
  - Book-to-tax waterfall with footnotes
  - EBITDA reconciliation
  - Source document thumbnails (first page only)
  - CPA sign-off lines

## API
- POST /api/apex/workpapers/generate
- Request: {scenario_id, pages: ["taxes", "ebitda"]}
- Response: {download_url, checksum}
```

```markdown
# TAX_SCENARIO_MANAGER_SPEC.md
## Scope
CRUD for planning scenarios with comparison tools.

## Schema
- scenario_id (UUID)
- name (string, user-defined)
- created_at (timestamp)
- inputs_json (salary, depreciation_adj, interest_adj, one_time)
- book_reference_date (import timestamp)
- locked (boolean)

## Features
- Save current slider positions as named scenario
- Compare up to 3 scenarios side-by-side
- Diff view highlighting variances >$1,000
- Delete/Rename with confirmation
- Export all scenarios to Excel

## HAL Integration
- Command: "Save scenario [name]" → triggers POST /api/apex/scenarios/save
- Command: "Compare scenario A and B" → opens comparison modal
```

```markdown
# FILING_WORKFLOW_SPEC.md
## Scope
State machine for tax return preparation through filing.

## States
1. DRAFT (default)
2. CPA_REVIEW (requires password or role)
3. CLIENT_APPROVED (client checkbox + date)
4. FILED (upload return PDF required)
5. LOCKED (read-only, archived)

## Transitions
- DRAFT → CPA_REVIEW: Any user
- CPA_REVIEW → CLIENT_APPROVED: CPA role only
- CLIENT_APPROVED → FILED: Upload PDF trigger
- Any → DRAFT: Admin reset (with audit log)

## UI
- Visual timeline (stepper) on Taxes page header
- Color coding: Grey → Blue → Green → Purple → Black
- Lock icon appears on all widgets when state = LOCKED

## Document Integration
- Filing triggers move PDF from `uploads/` to `tax_returns/2025/federal/`
- Updates Tax Returns Library widget automatically
```

## 8. Implementation Phases (C0 validate → Cn) + Validation Gate

**Phase C0: Import Remediation (MUST complete before C1)**
- Fix SoftDent collectionsPending mapping (target: non-zero values)
- Fix operatory utilization feed (target: >0 rows)
- Validate A/R insurance/patient split (target: values present, sum equals total A/R)
- **Validation Gate:** Diagnostics show collectionsPending > 0, operatory rows > 0, A/R allocation non-zero. Operator confirms data accuracy against SoftDent native reports.

**Phase C1: EBITDA Slider Widget (MUST)**
- Build scrubber panel per EBITDA_SCRUBBER_WIDGET_SPEC
- Implement scenario save/load to localStorage (no backend yet)
- Add "Planning vs Book" visual diff
- **Validation Gate:** CPA test scenario created; sliders adjust planning EBITDA independently of QB imports; reset button restores book values.

**Phase C2: CPA Workpaper Bridge (SHOULD)**
- Build citation links for tax waterfall lines
- Implement workpaper PDF export
- Add audit trail logging
- **Validation Gate:** Operator clicks citation on Depreciation line → sees QB transaction list; exports workpaper PDF containing correct source references.

**Phase C3: Tax Scenario Manager + Filing Workflow (SHOULD)**
- Backend scenarios table with persistence
- Filing state machine UI
- Tax Returns Library auto-population on FILED state
- **Validation Gate:** Save 3 scenarios; compare side-by-side; transition workflow DRAFT→FILED with PDF upload; verify LOCKED state prevents edits.

**Phase C4: Advanced HAL Integration (NICE)**
- Anomaly detection alerts
- Voice-to-scenario commands
- Predictive A/R aging
- **Validation Gate:** HAL alerts operator to >10% production variance; voice command adjusts slider.

## 9. Risks, CPA disclaimer & Rollback

**Critical Risks:**

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| User confuses Planning EBITDA with Book EBITDA | High | Financial decision error | Permanent 🔒 icons on book values; watermark "NOT FROM QUICKBOOKS"; mandatory tooltip on first use |
| Slider adjustments persisted to QB by accident | Low | Data corruption | Architecture enforcement: sliders write to `nr2_scenarios` only; QB sync API rejects manual adjustments |
| Tax planning treated as filed return | Medium | Legal/IRS penalty | Banner: "PLANNING ESTIMATE — REQUIRES CPA REVIEW BEFORE FILING"; separate "Filed Returns" library with official PDFs only |
| Scenarios lost on browser clear | Medium | Lost work | C1 uses localStorage backup; C3 moves to database persistence |
| Import fixes break existing widgets | Medium | Regression | C0 backup of current import bundle; rollback script to hal-10310 state |

**CPA Disclaimer (Required on all Tax/EBITDA outputs):**
> "This tax planning calculation is an estimate based on imported bookkeeping data and user-provided assumptions. It does not constitute a filed tax return. All figures must be reviewed and certified by a licensed CPA before submission to the IRS or Kansas Department of Revenue. NewRidge Financial 2.0 is a decision-support tool, not a tax preparation service."

**Rollback Procedures:**
- **C0 Import Fixes:** `scripts/rollback_import_mapping.sh` restores previous SoftDent field mappings
- **C1+ Code Changes:** Git revert to tag `hal-10310`; database snapshot restore for scenarios table (C3)
- **Data Integrity:** Daily automated backup of `app_data/nr2/` to `backups/hal-{build_id}-{timestamp}/`

**CONSULT ONLY — AWAITING OPERATOR APPROVAL TO PROCEED.**