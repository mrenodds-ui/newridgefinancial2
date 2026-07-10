# Moonshot AI — Claims 30/60/90 Tiles + Narratives Insurance HAL (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10330  
**Script:** `scripts/run_moonshot_claims_narratives_consult.py`  
**Apply:** DO NOT APPLY until operator approves. Moonshot codes after approve.

## Operator request (verbatim)

> ask moonshot ai to design the claims page with rows of 30 day claims, 60 day claims, 90 day claims widget that line of boxes, when clicked brings up the actual claim, the claim box should be a box with the claim id, patient name and date.  this widget hal also has control, I need also the narative page to have access to clinical notes, claims, insurance informaton and expand ability to have hal produce naratives to inurance companies.  if he has any other high and better recommendations report, but do not code.  Let moonshot code for you and do not proceed until i approve

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only; Moonshot codes after approve)

> "ask moonshot ai to design the claims page with rows of 30 day claims, 60 day claims, 90 day claims widget that line of boxes, when clicked brings up the actual claim, the claim box should be a box with the claim id, patient name and date. this widget hal also has control, I need also the narative page to have access to clinical notes, claims, insurance informaton and expand ability to have hal produce naratives to inurance companies. if he has any other high and better recommendations report, but do not code. Let moonshot code for you and do not proceed until i approve"

**Status:** CONSULT ONLY — Design specification and recommendations report.  
**Implementation Authority:** Moonshot AI (not Cursor) shall implement after explicit operator approval.  
**Current Hold:** DO NOT APPLY / DO NOT CODE until operator states "proceed," "validated," or "approve."

---

## 1. Claims Page Design — 30 / 60 / 90 Day Tile Rows

**Layout Pattern:** Apex mosaic extension — three horizontal "shelf" widgets (`claims-aging-30`, `claims-aging-60`, `claims-aging-90`), each containing a scrollable row of claim tiles (boxes). Retains existing KPI mosaic above (claims-total, claims-open, claims-denied) for continuity.

**Claim Tile (Box) Fields:**
- **Claim ID** (e.g., "CLM-2026-001234" or SoftDent Claim #)
- **Patient Name** (Last, First from import)
- **Date** (Date of Service / DOS)

**Visual Spec:**
- Tile size: Fixed width ~220px, height ~100px, Apex card styling with left accent bar (cyan for 30, amber for 60, rose for 90 days)
- Row behavior: Horizontal scroll with snap points; "Viewing X of Y" microcopy
- Empty/Honest States: 
  - "No claims aged 30–59 days in current SoftDent import" (not "0")
  - "Import SoftDent claims with Age/Days field to populate aging buckets"

**Interaction:**
- Click tile → opens `claim-detail-drawer` (slide-out from right, 640px width) displaying full import-backed claim record: Claim ID, Patient Name, DOS, Payer, Status, Age (days), Procedure codes (if present on import), Billed amount (if present).
- Close drawer → return to scroll position on claims page.

**Data Contract (Import-Backed Only):**
```yaml
ClaimTile:
  claimId: string      # From SoftDent ClaimId/Claim#
  patientName: string  # From SoftDent Patient/PatientName
  date: string(ISO)    # From SoftDent Date/DOS/ServiceDate
  ageDays: integer     # From SoftDent Age/Days/AgingDays (calculated if absent)
  payer: string        # From SoftDent Payer (optional)
  status: string       # From SoftDent Status (optional)
  procedures: string[] # From SoftDent ProcCodes (optional)
  billedAmount: number # From SoftDent Billed/Amount (optional, null if missing)
```

---

## 2. HAL Control on Claims Aging Widget

**Board-Actions Available (Apex HAL pattern):**

| Action | Trigger | Honesty Constraint |
|--------|---------|-------------------|
| **Sync & Refill Aging Tiles** | "Sync imports and populate 30/60/90 tiles" | Refreshes from SoftDent import only; never invents claim rows |
| **Focus Aging Row** | "Focus 60-day claims" or "Highlight aging over 60" | Cyan pulse on specific aging shelf widget; scroll into view |
| **Focus Specific Claim** | "Find claim [ID]" or "Highlight claim for [Patient]" | Cyan pulse on specific tile; opens drawer only on explicit click |
| **Refresh Tiles** | "Refresh claims tiles" | Reload from current cache (no new file sync) |
| **Import Status** | "Claims import status" | Banner: "Last SoftDent import: N claims, M with Age field" |

**Ask HAL Chips (Widget-Local):**
- "Show me 30-day claims"
- "Focus denied claims over 60 days" (if status available)
- "Sync and refill"

**HAL May:**
- Highlight widgets/tiles
- Navigate to Claims page
- Sync imports to refresh data
- Surface import-backed hints ("3 claims aged 90+ days lack payer info — verify SoftDent export includes Payer column")

**HAL May NOT:**
- Invent claim IDs, patient names, dates, or dollar amounts
- Fabricate aging days if missing from import
- Post adjustments to claims

---

## 3. Narratives Page — Clinical Notes + Claims + Insurance Context

**Context Panel Architecture (New Panel: `narr-context-panel`):**

Three selectable source streams (import-backed, read-only selectors):

1. **Clinical Notes Stream** (`narr-source-clinical`)
   - Lists SoftDent clinical notes from `_section_rows(bundle, "softdent", "clinicalNotes")`
   - Fields: Note ID, Patient, Date, Provider, Note snippet (first 120 chars)
   - Selection: Checkbox or "Add to Context" button; adds to narrative context buffer

2. **Claims Stream** (`narr-source-claims`)
   - Lists claims from SoftDent import (same source as Claims page)
   - Filterable by aging status (30/60/90) or patient
   - Selection: Adds Claim ID, DOS, Procedure codes, Payer to context

3. **Insurance Information Stream** (`narr-source-insurance`)
   - Payer directory from SoftDent import (unique Payer names + Payer ID if available)
   - Selection: Sets target payer for narrative generation

**UX Flow:**
- Composer sidebar (existing) gains "Context" tab alongside "Sections"
- User selects 1+ clinical notes + 1 claim + 1 payer → "Lock Context" button
- Locked context appears as summary chips above composer textarea
- HAL Rewrite button becomes context-aware (see Section 4)

**Honesty Gates:**
- All source lists show "Last updated: [import timestamp]"
- Empty states: "Import SoftDent clinical notes to enable selection" (not "No notes found")

---

## 4. HAL Insurance-Company Narratives

**Expanded Generation Types (Consent-Required):**

| Narrative Type | Purpose | Required Context | Output Format |
|----------------|---------|------------------|---------------|
| **Appeal Letter** | Denied claim reconsideration | Claim + Clinical notes + Denial reason (operator input) | Formal business letter |
| **Medical Necessity Narrative** | Justify procedure to payer | Clinical notes + Procedure codes + Diagnosis | Paragraph form with citation placeholders |
| **Attachment Cover Letter** | Accompany X-rays/charts | Claim + List of attachments (operator input) | Brief cover sheet |
| **Prior Authorization Request** | Pre-treatment estimate | Treatment plan + Insurance info | Structured request with clinical justification |

**Consent & Validation Flow:**
1. **Pre-Generation Gate:** Checkbox required — "I confirm this narrative is based solely on imported clinical data and accurate to the best of my knowledge [ ]"
2. **Source Attribution Footer:** Auto-appends to generated text — "Generated from NR2 import: SoftDent [date], Claim [ID], Notes [IDs]"
3. **Human Edit Requirement:** Generated text opens in composer as draft; must be manually edited before "Finalize" enabled
4. **No PHI Transmission:** Generation occurs locally via HAL; no patient data sent to external APIs without explicit operator opt-in per narrative

**HAL Prompt Constraints:**
- Must reference only selected Claim ID, Patient Name, DOS from context panel
- Must incorporate only selected clinical note text
- Must not invent diagnosis codes not present in notes
- Must use payer name from selected insurance context

---

## 5. Higher / Better Recommendations (beyond the ask)

**MUST (Foundation for compliance & usability)**
1. **Aging Buckets Backend Validation** — Extend `_claims_summary_from_bundle` to return `agingBuckets: {30: [...], 60: [...], 90: [...]}` with claim arrays, not just counts. *Rationale: Required for tile rows; maintains single source of truth.*
2. **PHI Audit Trail for Narratives** — Log every HAL-generated narrative with source claim IDs, note IDs, and operator consent timestamp to local audit log. *Rationale: Kansas dental S-corp liability protection; CPA/defense documentation.*

**SHOULD (Operational efficiency)**
3. **Claim Detail Quick Actions** — In the claim drawer, add "Draft Narrative for This Claim" button that auto-selects the claim + patient + payer in Narratives page and opens composer. *Rationale: Reduces clicks between Claims and Narratives workflows.*
4. **Bulk Selection Mode** — Allow shift-click or checkbox multi-select on 30/60/90 tiles for batch "Generate Appeal Packet" (generates multiple narratives into one document). *Rationale: Efficiency for 90-day aged claims often requiring simultaneous appeals.*
5. **Aging Alert Thresholds** — Add configurable HAL alerts: "Notify when claims aged 60+ exceed N count" using existing `_apply_threshold_alerts` pattern. *Rationale: Proactive A/R management.*

**NICE (Future-proofing)**
6. **Payer-Specific Template Library** — Extend `hal_narrative_library` to include Delta Dental, Guardian, MetLife specific appeal language (operator-maintained, not HAL-invented). *Rationale: Higher acceptance rates for appeals.*
7. **Voice-to-Narrative** — Extend existing voice-to-slider capability to voice-dictate narrative sections directly into composer. *Rationale: Hands-free clinical documentation workflow.*

---

## 6. Moonshot Spec Deliverables (CONSULT ONLY)

**A. Data Contracts (Backend)**

```yaml
# New endpoint: GET /api/apex/claims-aging
Response:
  buckets:
    30:
      - claimId: string
        patientName: string
        date: string(ISO)
        ageDays: integer
        payer: string | null
        status: string | null
    60: [...]
    90: [...]
  meta:
    lastImport: timestamp
    totalClaims: integer
    missingAgeField: boolean  # true if import lacks Age/Days column

# New endpoint: GET /api/apex/claims/{claimId}
Response:
  claimId: string
  patientName: string
  date: string(ISO)
  ageDays: integer
  payer: string | null
  status: string | null
  procedures: string[] | null
  billedAmount: number | null
  source: "softdent-import"
  importedAt: timestamp

# New endpoint: POST /api/apex/narratives/context
Body:
  clinicalNoteIds: string[]
  claimId: string | null
  payerId: string | null
Response:
  contextId: string  # Session context for HAL generation

# New endpoint: POST /api/apex/hal/narrative-generate
Body:
  contextId: string
  type: "appeal" | "medical-necessity" | "attachment-cover" | "prior-auth"
  operatorConsent: boolean  # Must be true
  denialReason: string | null  # For appeals
  attachments: string[] | null  # For cover letters
Response:
  draftText: string
  sourcesCited: string[]  # List of claim/note IDs used
  generatedAt: timestamp
  requiresHumanReview: true  # Always true
```

**B. Widget IDs (Frontend)**

```
claims-aging-30      # Horizontal scroll shelf widget
claims-aging-60      # Horizontal scroll shelf widget  
claims-aging-90      # Horizontal scroll shelf widget
claim-tile-{id}      # Individual tile instances
claim-detail-drawer  # Slide-out drawer component
narr-context-panel   # New sidebar panel in narratives page
narr-source-clinical # Clinical notes selector
narr-source-claims   # Claims selector
narr-source-insurance# Insurance/payer selector
```

**C. HAL Board-Actions Spec**

```yaml
# New action types for claims widget
{type: "focus_claims_bucket", bucket: "30"|"60"|"90"}
{type: "focus_claim_tile", claimId: string}
{type: "open_claim_detail", claimId: string}
{type: "sync_claims_imports"}  # Extends existing sync_imports scoped to claims

# Extended context for narratives
{type: "set_narrative_context", clinicalNoteIds: [...], claimId: ..., payerId: ...}
{type: "generate_narrative_draft", narrativeType: "appeal"|... , consent: true}
```

**D. CSS Classes (Apex Pattern)**

```css
.apex-claims-shelf          /* Horizontal scroll container */
.apex-claims-tile           /* Individual claim box */
.apex-claims-tile--30       /* Cyan accent */
.apex-claims-tile--60       /* Amber accent */
.apex-claims-tile--90       /* Rose accent */
.apex-claims-tile--empty    /* Disabled/empty state */
.apex-claim-drawer          /* Detail slide-out */
.narr-context-panel         /* Sidebar context */
.narr-source-list           /* Scrollable selector list */
```

---

## 7. Implementation Phases (C0 validate → Cn) + Validation Gate

**Phase C0: Validation Gate (Operator must approve before C1)**
- Verify SoftDent export includes: ClaimId, PatientName, Date/DOS, Age/Days (or calculate from Date), Payer
- Confirm narrative generation consent workflow meets S-corp compliance requirements
- **Gate:** Operator confirms "C0 validated; proceed to C1"

**Phase C1: Backend — Aging Buckets API**
- Extend `_claims_summary_from_bundle` to return bucketed claim arrays (30/60/90)
- Create `/api/apex/claims-aging` endpoint
- Create `/api/apex/claims/{id}` endpoint (import-backed only)

**Phase C2: Frontend — Tile Rows**
- Implement `claims-aging-30`, `-60`, `-90` shelf widgets
- Implement `claim-tile` component with ID/Name/Date display
- Implement horizontal scroll with snap points

**Phase C3: Frontend — Claim Detail Drawer**
- Implement `claim-detail-drawer` component
- Wire tile click → drawer open with full claim data
- Add "Draft Narrative" quick action button

**Phase C4: HAL Integration — Claims Widget**
- Extend `resolve_hal_board_actions` with focus_claims_bucket, focus_claim_tile
- Add Ask HAL chips for 30/60/90 navigation
- Implement sync_claims_imports action

**Phase C5: Narratives — Context Panel**
- Add `narr-context-panel` to narratives page
- Wire clinical notes, claims, insurance selectors to backend
- Implement "Lock Context" workflow

**Phase C6: HAL — Insurance Narratives**
- Implement `/api/apex/hal/narrative-generate` with consent gate
- Add narrative type selector (appeal, medical necessity, etc.)
- Implement source attribution footer auto-append
- Add audit logging for generated narratives

**Phase C7: Thresholds & Polish**
- Implement aging alert thresholds (SHOULD #5)
- Add bulk selection mode (SHOULD #4)

**Completion Criteria:**
- All 30/60/90 tiles populate from import only
- Click any tile opens accurate claim detail
- HAL can focus any bucket or specific claim
- Narratives page can select claims/notes/insurance as context
- HAL generates insurance narratives with consent gate and source attribution
- Audit log captures all narrative generation events

**Implementation Authority:** Moonshot AI will execute C1-C7 after operator approval. Cursor must not write implementation code until explicit "proceed" received.

---

## 8. Risks, PHI / CPA Disclaimer & Rollback

**PHI & Data Integrity Risks:**
- **Risk:** Claim tiles display patient names in scrollable row (visible to anyone viewing screen).
  - *Mitigation:* Tiles display only necessary fields (Name, ID, Date); full details require drawer click; session timeout enforced; screen lock recommended for clinical areas.
- **Risk:** HAL-generated insurance narratives could be submitted with errors if operator bypasses human review.
  - *Mitigation:* Mandatory consent checkbox + "requiresHumanReview" flag blocks finalization until manual edit confirmed; source attribution footer ensures traceability.

**CPA/S-Corp Compliance:**
- Narratives generated by HAL are **draft clinical/business correspondence**, not financial statements or tax returns.
- No dollar amounts (billed amounts) are invented; only displayed if present on SoftDent import.
- Appeal letters may affect A/R recognition; operator (CPA/client) must verify narratives accurately reflect services rendered before submission to payers.

**Rollback Plan:**
- Claims page: Remove three aging shelf widgets from mosaic config → reverts to KPI-only view (hal-10330 state).
- Narratives: Disable `narr-context-panel` via feature flag `narratives_context_v2: false` → reverts to composer-only workflow.
- HAL actions: Remove new action types from `resolve_hal_board_actions` → HAL ignores unknown actions gracefully.

**DO NOT APPLY until operator explicitly states:** "proceed," "validated," "approve," or "Moonshot implement now."

---

**End of Consult-Only Report**  
**Awaiting Operator Approval for Implementation**