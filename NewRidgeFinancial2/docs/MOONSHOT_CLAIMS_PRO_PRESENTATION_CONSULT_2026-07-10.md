# Moonshot AI — Professional Claims Presentation (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10390  
**Script:** `scripts/run_moonshot_claims_pro_presentation_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> have moonshot ai look at my claims page and make a better suggestion to present claims in a more highly professional manner then 3 huge widgets.

---

# Verdict

## 0. Operator Intent (quote; consult-only)

> "have moonshot ai look at my claims page and make a better suggestion to present claims in a more highly professional manner then 3 huge widgets."

**Confirmed:** Consult-only professional presentation redesign. No code will be generated or applied until operator explicitly approves a specific option.

---

## 1. Critique of Current Claims Page Layout

**The Problem with Three Full-Width Shelves (30/60/90)**

The current layout stacks three `size: "full"` horizontal tile shelves (`claims-aging-30`, `claims-aging-60`, `claims-aging-90`), each consuming 120–140px height plus header chrome. This creates:

*   **Visual Obesity:** 60% of the first viewport is consumed by repetitive scrolling tracks that display the same metadata (Claim ID, Patient, Payer) in oversized 220×100px cards.
*   **Executive Disconnect:** RCM professionals expect "at-a-glance" exposure summaries (counts + dollars), not three separate carousel interfaces requiring horizontal scrolling to assess risk.
*   **Hierarchy Collapse:** The full-width kanban (`claims-kanban-board`) and full-width header stats push the actual risk analytics and follow-up actions below the fold, burying actionable intelligence.
*   **Wasted Chrome:** Each shelf repeats widget headers, scroll indicators, and empty-state messaging. Three widgets to answer one question: *"What is my aging distribution?"*

**Why this feels unprofessional:** It resembles a developer-first "widget dump" rather than a curated revenue cycle command center. Density is low; cognitive load is high.

---

## 2. Recommended Professional Presentation (primary design)

**Pattern: Executive RCM Console**

Replace the "shelf warehouse" with a **dense, hierarchical mosaic** that respects Apex's small/medium/large/full sizing system.

**Design Principles:**
1.  **Above-Fold Executive Summary:** One consolidated aging exposure widget (not three) plus critical action queue.
2.  **Data-Dense Primary View:** Table-first workbench (compact rows) with kanban as a toggle/secondary view, not default.
3.  **Merged Chrome:** Combine header stats, KPIs, and follow-up hints into a single "Command Strip" to eliminate widget proliferation.
4.  **Honest Constraints:** Empty states remain; no invented dollars; SoftDent read-only integrity preserved.

**Layout Hierarchy:**
*   **Level 1 (Header):** Import Health (compact strip) + Executive KPI Strip (counts only).
*   **Level 2 (Primary):** Aging Exposure Matrix (30/60/90 columns in one widget) paired with Critical Actions (denied/unmatched/attachments).
*   **Level 3 (Workbench):** Claims Workbench Table (full-width, dense rows, 32px line-height) with view-mode toggle (Table ↔ Kanban).
*   **Level 4 (Analytics):** Risk sparklines and ERA match trends (bottom row, half-width each).

---

## 3. Wireframe (text)

```
┌─────────────────────────────────────────────────────────────────┐
│ [IMPORT HEALTH: SoftDent last sync 14m ago ● Status OK]        │  ← 40px strip, full
├─────────────────────────────────────────────────────────────────┤
│ [Total 142] [Open 38] [Denied 12] [At Risk $48K]               │  ← 4× small KPIs, full row
├───────────────────────────────┬─────────────────────────────────┤
│ CLAIMS AGING EXPOSURE         │ CRITICAL ACTIONS QUEUE          │  ← Row 2
│ (size: large)                 │ (size: medium)                  │
│ ┌────────┬────────┬────────┐  │ • Denied >30d: 4  [ Appeal ]   │
│ │  30d   │  60d   │  90d+  │  │ • ERA Mismatch: 2 [ Review ]   │
│ │   18   │   7    │   4    │  │ • Missing Att: 3  [ Upload ]   │
│ │ $12.4K │ $8.1K  │ $28K   │  │                                 │
│ │[████░░]│ [██░░░░]│[██████]│  │ [Sync Imports]                  │
│ └────────┴────────┴────────┘  │                                 │
│ Click column → filter below   │                                 │
├─────────────────────────────────────────────────────────────────┤
│ CLAIMS WORKBENCH — Table View ( density: compact )             │  ← Row 3, full
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ClaimID│Patient    │Payer   │Age│Status    │Amount│Att│Act │ │
│ │C-0892 │Smith, J.  │Delta   │12d│Pending   │$450  │●  │[>]│ │
│ │C-0891 │Doe, A.    │Cigna   │45d│Denied    │$1,200│○  │[>]│ │
│ │...    │...        │...     │...│...       │...   │.. │...│ │
│ └─────────────────────────────────────────────────────────────┘ │
│ [View: ●Table | Kanban ]  [Filter: All ▼]  [HAL: Focus high-risk]│
├───────────────────────────────┬─────────────────────────────────┤
│ RISK TREND (7d sparkline)     │ ERA MATCH RATE (gauge)          │  ← Row 4
│ Denied volume ↓ 12%           │ 94% matched | 6% unmatched      │
│ (size: medium)                │ (size: medium)                  │
└───────────────────────────────┴─────────────────────────────────┘
```

**Below-Fold (if needed):**
*   Detailed Claim Drawer (existing)
*   Batch Actions Footer (bulk appeal, export)

---

## 4. Widget / Instrument Spec (CONSULT ONLY)

**MUST — New Composite: `claims-aging-exposure`**
*   **Purpose:** Replace `claims-aging-30`, `claims-aging-60`, `claims-aging-90` shelves.
*   **Size:** `large` (66% width) or `full` depending on pairing.
*   **Schema:**
    *   3 columns: 30-Day, 60-Day, 90+ Day.
    *   Per column: Count (large typography), Dollar Exposure (secondary, honest-empty if missing), mini progress-bar (visual weight of bucket).
    *   Interaction: Column header click emits `filter:ageBucket` to workbench below.
    *   Honesty: If `missingAgeField`, display unified "Aging data unavailable — import SoftDent Age/Days" message instead of empty columns.
*   **HAL Chips:** `Focus 30-day exposure`, `Focus high-risk aging`.

**MUST — Modify: `claims-kanban-board` → `claims-workbench`**
*   **Change:** Add `viewMode: "table" | "kanban"` (default: `"table"`).
*   **Table Spec:**
    *   Row height: 32px (vs current 100px cards).
    *   Columns: Claim ID, Patient (Last, First), Payer, Age (days), Status (badge), Amount (tabular nums), Attachment indicator (dot), Action (chevron/detail).
    *   Density: 12–15 rows visible without scroll vs current 3–4 cards.
*   **Size:** Remains `full` but height collapses from ~600px to 400px in table mode.
*   **Filters:** Retain `all`, `high-risk`, `unmatched`, `missing-attachments` but move to inline toolbar, not widget chrome.

**SHOULD — Merge: `claims-executive-strip` (new composite)**
*   **Consumes:** `claims-total`, `claims-open`, `claims-denied`, `claims-aging-count`, `claims-header-stats`, `claims-follow-up`.
*   **Size:** `full` but height-constrained (max 120px).
*   **Layout:** Flex row of 4–5 KPI "pills" with sparkline micro-charts (last 7 days). No individual widget borders; unified card.
*   **Content:** Total Claims | Open $ | Denied Count | At Risk $ | ERA Match %.

**SHOULD — Relocate: `claims-critical-actions`**
*   **Content:** Denied >30d requiring appeal, ERA mismatches, Missing attachments (from current risk analytics and kanban meta).
*   **Size:** `medium` (33% width), placed adjacent to Aging Exposure.
*   **Interaction:** Each row is a filter-link to the workbench (e.g., "Show me denied >30d").

**NICE — New: `claims-aging-minimap` (alternative to exposure matrix)**
*   **Type:** Heatmap sparkline (30/60/90 as color intensity bar).
*   **Size:** `small`.
*   **Use:** If operator prefers to keep detailed shelves, collapse them into this minimap as a navigation aid.

---

## 5. Alternatives (2 options) ranked

### Option A: Executive Table-First (RECOMMENDED)
*   **Change:** Implement MUST specs above. Default to table view, kill the three shelves entirely, consolidate headers.
*   **Pros:** Maximum density; aligns with dental practice management software conventions (Dentrix/Eaglesoft use table views); fastest scanability.
*   **Cons:** Less "modern app" visual appeal; requires view-mode toggle for users who prefer kanban cards.
*   **Effort:** Medium (new widget types, table renderer).

### Option B: Collapsed Shelf Accordions (Conservative)
*   **Change:** Keep the 30/60/90 shelves but convert to `size: "medium"` accordion pattern (only one expanded at a time, default to 90+ expanded if non-zero).
*   **Pros:** Minimal code change; retains existing card interactions; backward compatible with HAL "Focus 30-day" queries.
*   **Cons:** Still wastes space on shelf chrome; still horizontal scrolling inside accordions; not truly executive density.
*   **Effort:** Low (CSS/JS behavior change only).

### Option C: Kanban-First with Minimap (Aspirational)
*   **Change:** Keep full-width kanban as primary, replace 3 shelves with a single `small` "Aging Minimap" heatmap widget that acts as a filter controller.
*   **Pros:** Visual wow factor; maintains kanban paradigm for task-oriented users.
*   **Cons:** Kanban cards remain oversized; minimap requires new D3/visualization dependency; less scannable for high-volume practices (>100 claims).
*   **Effort:** High.

---

## 6. Phases + Validation Gate

**Phase 1: Consolidation (hal-10400)**
*   Build `claims-aging-exposure` (replaces 3 shelves).
*   Build `claims-critical-actions` (extracted from risk analytics).
*   Validate: HAL queries `Focus 30-day claims` still target the new matrix (maintain widget ID aliases or update HAL intent mapping).
*   **Gate:** Operator approves wireframe density; verify no invented dollar amounts appear in Exposure columns.

**Phase 2: Density Upgrade (hal-10410)**
*   Implement `claims-workbench` table view mode; switch default from kanban to table.
*   Merge header widgets into `claims-executive-strip`.
*   **Gate:** Usability test with 20+ claim rows; confirm click-through to claim detail drawer persists.

**Phase 3: Polish (hal-10420)**
*   Add view-mode persistence (remember user preference Table/Kanban).
*   Mobile-responsive table (horizontal scroll with sticky first column).
*   **Gate:** Mobile viewport test (<768px).

---

## 7. Risks & Rollback

| Risk | Mitigation | Rollback |
|------|------------|----------|
| **Table view feels too "accounting"** | Provide prominent toggle to Kanban view; persist user preference. | Revert default to Kanban; keep table as secondary. |
| **Missing dollar amounts create ugly empty columns** | Hide "Exposure" column entirely if `meta.missingFields` includes `Amount` or `Charge`; show only counts. | Fallback to count-only display. |
| **HAL voice commands break** | Preserve widget IDs (`claims-aging-30` etc.) as hidden anchors or HAL aliases pointing to new matrix filters. | Restore original shelf widgets alongside new ones (duplicate temporarily). |
| **SoftDent import lacks Age field** | Matrix shows unified "Aging unavailable" message rather than three empty shelves. | N/A (honest state is correct). |
| **Performance: Table with 500+ rows** | Implement virtual scrolling or pagination (20 rows default) in table view. | Cap at 50 rows with "Load more" button. |

**DO NOT APPLY until operator approves.** Awaiting explicit "Option A approved" or wireframe modifications before generating implementation code.