# Moonshot AI — Claims Mockup Parity vs page_mockups/claims.html (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10370  
**Mockup:** `_archive/2026-07-10/.local_logs/moonshot_financial_eval/page_mockups/claims.html`  
**Script:** `scripts/run_moonshot_claims_mockup_parity_consult.py`  
**Apply:** DO NOT APPLY until operator approves. Moonshot codes after approve.

## Operator request (verbatim)

> ask moonshot ai if he can make the claims page function like the attached html and look like the claims in there can be presented that way? then report

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only)

> "ask moonshot ai if he can make the claims page function like the attached html and look like the claims in there can be presented that way? then report"

**Confirmed:** This is a **CONSULT-ONLY** feasibility and recommendations report. No code will be applied until operator explicitly approves. Moonshot will implement post-approval; Cursor must not code now.

---

## 1. What the 2026-07-07 claims.html Mockup Is

The mockup depicts a **full-screen Claims Workbench** with five distinct functional zones:

**A. Layout**
- **5-Column Kanban Board**: Submitted → Pending Review → ERA Matched → Denied → Paid
- **Right Side Panel**: Denial Risk Analysis (progress bars), Recent ERA Matches (list), Quick Actions
- **Header Stats**: Pending $48.2K, At Risk 12, ERA Match 94%
- **Filter Bar**: All Claims | High Risk | Unmatched | Missing Attachments

**B. Claim Card Schema (per card)**
- Claim ID (e.g., CLM-2024-0892)
- Risk Badge (High/Med/Low/Denied/Paid color-coded)
- Patient Name
- Procedure (CDT Code + Description, e.g., "D4341 • Scaling/Root Planing")
- Payer Name
- Dollar Amount ($X,XXX.00)
- Attachment Indicator (📎 Complete | 1/2 | 0/3)
- ERA Status (ERA Pending | ERA Matched | Posted | Denial Code CO-45)

**C. Interactions**
- Drag-and-drop claim cards between columns to update status
- Auto-save on drag
- Click card → detail view (implied)
- Filter buttons toggle visible claims

---

## 2. Feasibility — Look (presentation)

**Assessment: HIGH feasibility.** Apex can present claims exactly this way.

**Achievable Today:**
- **Card CSS**: The dark-theme cards, risk badge colors (cyan/amber/rose/purple), and typography match existing Apex design tokens (`--accent-cyan`, `--bg-card`, etc.)
- **5-Column Grid**: CSS Grid or Flexbox container within a full-width widget; responsive collapse to 2-3 columns on smaller viewports
- **Attachment/ERA Chips**: Small pill components already exist in the component library (reuse from claim-shelf tiles)
- **Right Panel Widgets**: Standard Apex mosaic widget pattern—can place Denial Risk and ERA Matches as stacked widgets beside the kanban

**Required CSS/Widget Work:**
- New widget type: `claims-kanban-board` (full-width, replaces or supplements 30/60/90 shelves)
- Card component variant: `claim-card-kanban` (taller than shelf tiles, shows procedure + attachment footer)
- Column header component with drop-zone styling for drag states

**Constraint Honesty:**
- Mockup shows fictional CT practice branding ("Ridgefield, CT") and invented claim IDs. Live implementation must use Kansas S-corp branding and **only imported SoftDent claim IDs**—no fictional data.

---

## 3. Feasibility — Function (behavior)

**Assessment: MIXED—visual behavior yes, data-dependent features need new pipes.**

| Mockup Feature | Live Capability (hal-10370) | Gap Analysis |
|---|---|---|
| **Kanban Columns (5 statuses)** | ❌ Not shipped | Currently only 30/60/90 aging buckets. Need status classification from SoftDent ClaimStatus field or mapping logic. |
| **Drag-to-Update Status** | ❌ Not shipped | Current system is **read-only** import. Drag would require write-back to SoftDent or NR2 status tracking layer. |
| **Risk Badges (High/Med/Low)** | ❌ Not shipped | No risk scoring algorithm. Could derive from: payer history + denial rate + missing attachments + age, OR import SoftDent "Risk" field if available. |
| **CDT Procedure Display** | ⚠️ Partial | SoftDent export includes procedure codes, but current `apex_claims_narratives_pack.py` doesn't surface them in shelf widgets. API field addition needed. |
| **Attachment Completeness (X/Y)** | ❌ Not shipped | Requires SoftDent attachment export or imaging system integration. Currently unknown field. |
| **ERA Match % (Header)** | ❌ Not shipped | Current "ERA Matched" column in mockup requires ERA import + matching algorithm against claim IDs. Not in hal-10370. |
| **Dollar Amounts** | ⚠️ Partial | SoftDent has claim totals, but current aging buckets don't prioritize dollar aggregation. Summation logic needed for "$48.2K Pending". |
| **Denial Codes (CO-45, CO-16)** | ❌ Not shipped | Requires ERA/denial reason code import. Not available in current SoftDent extract. |
| **Filters (High Risk, Unmatched, Missing Attachments)** | ⚠️ Partial | "All Claims" works. Others need the data gaps above filled first. |
| **Click → Detail Drawer** | ✅ **SHIPPED** | hal-10350+ claim detail drawer with Draft Narrative seeding works today. |
| **Bulk Select/Appeal** | ✅ **SHIPPED** | hal-10350+ bulk checkbox + appeal to Narratives. |

**Critical Honesty Check:**
The mockup shows specific invented data (e.g., "Sarah Mitchell", "$1,240.00", "Delta Dental CT"). **NR2 must never invent these.** If SoftDent import lacks procedure codes, attachment counts, or ERA match status, the live UI must show honest empty states ("Procedure code not in import") or hide those fields rather than fabricate them.

---

## 4. Gap Matrix (Mockup feature → Live capability → Blocker)

| Mockup Feature | Live Today | Needs Data/API | Blocker | Honest Empty State |
|---|---|---|---|---|
| 5-Column Kanban layout | Widget shell only | Status column mapping | SoftDent ClaimStatus→Column mapping rules | "Import claims to view status columns" |
| Drag card → update status | None | POST /api/apex/claims/status | Write-back to SoftDent or NR2 state mgmt | Static display only |
| Risk badge (High/Med/Low) | None | Risk algorithm or import field | Payer denial history data | Hide badge or show "Risk: Unknown" |
| CDT Procedure (D4341) | None | Add to `build_aging_buckets` | SoftDent ProcCode field export | Hide procedure line |
| Attachment indicator (1/2) | None | Attachment count import | Imaging/SoftDent attachment export | Hide attachment footer |
| ERA Match % header | None | ERA import + match logic | ERA file ingestion pipeline | Hide ERA stats |
| Denial codes (CO-45) | None | ERA denial code import | ERA 835/Reason code parsing | Hide denial column |
| $48.2K Pending total | Partial | Sum(ClaimTotal) where status=Pending | Dollar field reliability in import | Show count instead of $ |
| Filters (Risk/Unmatched) | None | All above data | All above | Disable filter buttons |

---

## 5. Recommended Approach

**Option A: Hybrid Mosaic (RECOMMENDED — MUST)**
Preserve the existing Apex shell and 30/60/90 shelves (which work well for aging focus), but **add a new full-width Kanban widget** below the shelves for status-based workflow. This avoids the "full page replacement" complexity while delivering the mockup's core value—visual status pipeline.

- **Why**: Uses existing HAL focus patterns, keeps aging shelves (proven useful), allows gradual rollout of columns as data improves.
- **Trade-off**: Right-panel widgets (Risk Analysis, ERA Matches) become standard Apex mosaic widgets rather than fixed side panel.

**Option B: Dedicated Claims Workbench Page (SHOULD)**
Create a new page mode `/apex#/claims-workbench` that recreates the mockup's full layout (sidebar nav suppressed, full kanban + fixed right panel). 

- **Why**: Matches mockup exactly; dedicated space for claims management; can add drag-drop zones more naturally.
- **Trade-off**: Diverges from Apex mosaic pattern; needs new route and chrome handling; higher maintenance.

**Option C: Enhanced Shelves Only (NICE)**
Keep current 30/60/90 shelf widgets but style them like mockup cards, add procedure codes and attachment badges when data available.

- **Why**: Minimal change, low risk.
- **Trade-off**: Doesn't achieve the "function like the HTML" request—no kanban workflow, no drag status.

**Ranking:**
1. **MUST**: Option A (Hybrid) — delivers kanban look/function inside existing architecture.
2. **SHOULD**: Option B (Dedicated Page) — if operator wants full immersive workbench experience.
3. **NICE**: Option C — if data gaps prove insurmountable short-term.

---

## 6. Moonshot Spec (CONSULT ONLY)

Paste-ready specification for post-approval implementation:

**Widget IDs:**
- `claims-kanban-board` — Main 5-column container
- `claims-risk-analytics` — Right panel risk bars widget
- `claims-era-matches` — Right panel ERA list widget
- `claims-header-stats` — Pending $ / At Risk / ERA Match % KPI row

**Data Contract Extensions (apex_claims_narratives_pack.py):**
```python
# Extend build_aging_buckets return or new build_status_columns()
{
  "columns": {
    "submitted": [{"claimId": "real-softdent-id", "patient": "...", "risk": "high"|null, 
                   "procedure": {"code": "D4341", "desc": "Scaling"}, 
                   "attachments": {"current": 1, "required": 2}, 
                   "eraStatus": "pending"|"matched"|"denied-CO45",
                   "amount": 1240.00}],
    "pendingReview": [...],
    "eraMatched": [...],
    "denied": [...],
    "paid": [...]
  },
  "meta": {
    "pendingDollars": 48200.00,
    "atRiskCount": 12,
    "eraMatchRate": 0.94,
    "missingFields": ["procedure", "attachments"]  # Honest disclosure
  }
}
```

**HAL Actions:**
- `focus_claim_column(columnId: string)` — Scroll to/highlight kanban column
- `filter_claims(filterType: "high-risk"|"unmatched"|"missing-attachments")` — Apply filter chips
- `open_claim_detail(claimId: string)` — Open drawer (existing)
- `drag_claim_status(claimId: string, fromColumn: string, toColumn: string)` — **Future** when write-back enabled

**CSS Classes (apex-bridge.css):**
- `.claims-kanban-container` — Grid 5 columns
- `.claim-card-kanban` — Card with procedure + footer
- `.risk-badge-{high,medium,low,denied,paid}` — Color variants
- `.attachment-indicator-{complete,missing}` — 📎 chips

---

## 7. Phases + Validation Gate

**Phase 1: Read-Only Visual Parity (MUST)**
- Implement Option A (Hybrid) with Kanban widget using **existing** aging data mapped to columns:
  - 30-day bucket → "Submitted" or "Pending Review" (based on SoftDent Status)
  - 60/90-day → "Pending Review" 
  - Denied status → "Denied" column
  - Paid status → "Paid" column
- Honest empty states for missing procedure/attachment data
- **Validation Gate**: Operator reviews staging build with real SoftDent import—confirms no invented data appears.

**Phase 2: Enhanced Data Import (SHOULD)**
- Extend SoftDent extract to include: ProcedureCode, AttachmentCount, ClaimTotal
- Add ERA import pipeline for match status
- **Validation Gate**: Header stats ($Pending, ERA Match %) reflect real sums, not placeholders.

**Phase 3: Interactivity (NICE)**
- Drag-and-drop status updates (requires write-back architecture decision)
- Risk scoring algorithm
- **Validation Gate**: End-to-end test with operator dragging claim to "Paid" and status persisting.

**State**: **CONSULT PHASE** — Awaiting operator "approve" or "proceed" to begin Phase 1 implementation. Cursor must not write code.

---

## 8. Risks, PHI / Honesty & Rollback

**PHI Risks:**
- Claim cards display patient names and procedure codes (PHI). Kanban view must respect existing Apex authentication/authorization—no additional exposure, but confirm HTTPS-only and no caching of claim data in localStorage beyond current session.

**Honesty Risks:**
- **HIGH**: If SoftDent export lacks fields, the UI must not fabricate "D4341" or "$1,240.00" to match mockup aesthetics. Spec includes `missingFields` array to gray out or hide speculative data.
- **MEDIUM**: Risk badges without data could default all to "Low"—this is deceptive. Better to hide badges until risk algorithm is validated.

**Rollback Plan:**
- Kanban widget is additive; can disable via `apex_backend.py` widget list removal.
- 30/60/90 shelves remain untouched in Phase 1—fallback to current functionality instant.
- If dedicated page (Option B) chosen, route removal reverts to mosaic view.

**DO NOT APPLY until operator says proceed / approve.**