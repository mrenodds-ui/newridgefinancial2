# Moonshot Mockup — Implementation Plan & Report

**Date:** 2026-07-07  
**Build:** `hal-10054` · epoch `moonshot-mockup`  
**Reference:** [MOONSHOT_AI_CONSULTATION_2026-07-07.md](./MOONSHOT_AI_CONSULTATION_2026-07-07.md)  
**Mockup gallery:** `.local_logs/moonshot_financial_eval/page_mockups/` · http://127.0.0.1:8799/index.html  
**Live app:** https://127.0.0.1:8765/?v=hal-10054&__nr2_purge=1

---

## Status Report (as of 2026-07-07)

### What is done

| Area | Status | Evidence |
|------|--------|----------|
| Legacy schema purge (8765 staff) | Complete | `LAYOUT_EPOCH = moonshot-mockup`; no `pv-*` / `hp-*` on staff pages |
| Staff page mockup vocabulary | Complete | `nr2-mockup-page-vocabulary.css` + `page-canvas.js` refactor |
| 10 staff page renderers | Complete | `audit-mockup-parity.mjs` — 10/10 pass |
| Left nav widget subpages | Complete | `nav-sublist` in `nr2-moonshot-mockup-chrome.js`; scroll in `app.js` |
| HAL partial mockup rename | In progress | `ms-hal-*` → mockup names; validators pass but some `app.js` selectors may remain |
| Moonshot consultation | Complete | Live kimi-k2.5 + codebase audit doc |
| Validators | Green | HAL 103 suites · pages · mockup parity |

### What is not done

| Area | Gap | Mockup reference |
|------|-----|------------------|
| QuickBooks page | Treemap-first layout; no sync badge header | `page_mockups/quickbooks.html` |
| SoftDent page | 3-stage funnel (need 4); no operatory grid | `page_mockups/softdent.html` |
| Canvas charts | `NR2MoonshotUI.enhancePage` skips all PageCanvas pages | `site/charts/*.js` unused on staff pages |
| Page command chips | Schema `commands[]` not wired to HAL drawer on staff chrome | HAL page has pattern; staff pages do not |
| SideNotes cross-port | 8765 HAL panel isolated from 8766 office channel | By design; hub badge not built |
| Workstation (8766) | Still `hp-*` legacy | Out of moonshot epoch scope |

### Risk register

| Risk | Severity | Mitigation |
|------|----------|------------|
| QuickBooks duplicate widget key in schema | Medium | Split `quickbooksExpenseBreakdown` before sub-nav goes live |
| Chart double-mount if enhancePage + inline SVG both run | Low | Target specific widget hosts only |
| Operatory grid without export data | Low | Empty state + validator for structure when data null |
| HAL rename regressions | Low | Re-run `validate-hal.mjs` after each HAL touch |

---

## Implementation Plan

### Guiding principles

1. **Smallest shippable slices** — one page or one wiring concern per PR-sized batch.
2. **Mockup gallery is acceptance criteria** — side-by-side with live at same viewport.
3. **Bump build stamp** (`hal-10055+`) only when validators + manual spot-check pass.
4. **Workstation stays legacy** until explicit operator request (P2 only).

---

### Phase 1 — QuickBooks mockup parity (P0)

**Goal:** QuickBooks page visually matches mockup header + grid layout.  
**Estimate:** 1 session · ~4 files  
**Build target:** `hal-10055`

| Step | Task | Files |
|------|------|-------|
| 1.1 | Add mockup CSS: `dashboard-grid`, `kpi-card`, `sync-badge`, `chart-large`, `chart-medium` | `nr2-mockup-page-vocabulary.css` |
| 1.2 | Rewrite `renderQuickbooks()` to dashboard-grid layout | `page-canvas.js` |
| 1.3 | Sync badge in page header for QuickBooks | `nr2-moonshot-mockup-chrome.js` |
| 1.4 | Fix duplicate widget key; add `quickbooksExpenseBreakdown` | `page-schema.js` |
| 1.5 | Add `quickbooksPlTrend()` binder (optional empty state) | `page-canvas-data.js` |
| 1.6 | Extend audit script for QB classes | `scripts/audit-mockup-parity.mjs` |

**Acceptance:**

- [ ] Header shows sync badge (green when fresh, amber when stale)
- [ ] Four KPI cards in top `dashboard-grid` row
- [ ] Large P&amp;L trend + medium expense chart row
- [ ] Reconciliation table full width below
- [ ] Sub-nav scrolls to each `data-hal-widget-key`
- [ ] Validators pass

---

### Phase 2 — SoftDent clinical parity (P0)

**Goal:** Funnel + operatory grid match mockup structure.  
**Estimate:** 1–2 sessions · ~5 files  
**Build target:** `hal-10056`

| Step | Task | Files |
|------|------|-------|
| 2.1 | Extend funnel to 4 stages; emit mockup class names | `page-canvas.js`, vocabulary CSS |
| 2.2 | Add `softdentOperatoryGrid()` + export fields | `page-canvas-data.js` |
| 2.3 | New widget `softdentOperatoryGrid` in schema | `page-schema.js` |
| 2.4 | `canvasOperatoryGrid()` helper + panel | `page-canvas.js` |
| 2.5 | Audit assertions for funnel steps + operatory grid | `scripts/audit-mockup-parity.mjs` |

**Acceptance:**

- [ ] Funnel shows Presented → Accepted → Scheduled → Completed
- [ ] Operatory grid renders 6 columns when export includes chairs; empty state otherwise
- [ ] Sub-nav lists new operatory widget
- [ ] Validators pass

---

### Phase 3 — HAL cleanup + command wiring (P0/P1)

**Goal:** HAL fully on mockup vocabulary; staff page commands open HAL drawer.  
**Estimate:** 1 session · ~4 files  
**Build target:** `hal-10057`

| Step | Task | Files |
|------|------|-------|
| 3.1 | Remove remaining `ms-hal-*` querySelectors | `app.js`, `hal-page.js` |
| 3.2 | Dedupe redundant class pairs on sidenote/prompt elements | `hal-page.js`, theme CSS |
| 3.3 | Render `PageSchema.commands` as prompt chips in staff page header | `nr2-moonshot-mockup-chrome.js` |
| 3.4 | Wire chip click → `openHalDrawer({ seed, pageId })` | `app.js` |
| 3.5 | HAL context builders per page (financial, softdent, quickbooks) | `hal-page.js` or `app.js` |

**Acceptance:**

- [ ] No `ms-hal-*` in live DOM paths grep
- [ ] Clicking "Explain payer mix" on Financial seeds HAL chat
- [ ] `validate-hal.mjs` 103 suites pass

---

### Phase 4 — Chart bridge for PageCanvas (P1)

**Goal:** NR2Charts mount inside canvas widget hosts without legacy overlay.  
**Estimate:** 1 session · ~3 files  
**Build target:** `hal-10058`

| Step | Task | Files |
|------|------|-------|
| 4.1 | Add `enhanceCanvasCharts(pageId, root)` | `nr2-moonshot-ui.js` |
| 4.2 | Financial: practice pulse on production trend widget | `nr2-moonshot-ui.js`, charts |
| 4.3 | QuickBooks: import timeline for QB source | `nr2-moonshot-ui.js` |
| 4.4 | A/R: heatmap on aging widget (if not already inline) | `nr2-moonshot-ui.js` |

**Acceptance:**

- [ ] Canvas pages still skip legacy `.ms-page-body` overlay
- [ ] Charts appear only when data + canvas host exist
- [ ] No duplicate chart DOM on reload

---

### Phase 5 — SideNotes hub awareness (P1)

**Goal:** 8765 HAL shows office broadcast indicator when 8766 posts.  
**Estimate:** 1 session · ~3 files  
**Build target:** `hal-10059`

| Step | Task | Files |
|------|------|-------|
| 5.1 | `POST /api/hub/notify` + `GET /api/hub/last-broadcast` | `browser_app.py` |
| 5.2 | Workstation POST after office send | `workstation-page.js` |
| 5.3 | Poll + badge on HAL sidenote panel | `hal-page.js` |

**Acceptance:**

- [ ] Broadcast from 8766 sets badge on 8765 within poll interval
- [ ] Message text still not shown on 8765 (routing metadata only)
- [ ] Offline 8766 — no errors on 8765

---

### Phase 6 — Workstation visual bridge (P2, optional)

**Goal:** Shared color tokens; no class rename.  
**Estimate:** ½ session · 2 files  

| Step | Task | Files |
|------|------|-------|
| 6.1 | `workstation-moonshot-bridge.css` mapping `--bg-*` tokens | new CSS |
| 6.2 | Link from `workstation/index.html` | workstation entry |

**Acceptance:**

- [ ] 8766 messaging/HAL tabs visually closer to 8765
- [ ] No regression to SideNotesIM or pywebview flows

---

## Test plan (every phase)

```powershell
cd NewRidgeFinancial2
node validate-hal.mjs
node validate-pages.mjs
node scripts/audit-mockup-parity.mjs
node scripts/audit-page-schema.mjs
```

Manual:

1. Hard reload: `https://127.0.0.1:8765/?v=hal-100XX&__nr2_purge=1`
2. Walk each changed page vs mockup gallery tab
3. Click every sub-nav widget link — confirm scroll
4. HAL drawer: one command per changed page

---

## Recommended execution order

```
Phase 1 (QuickBooks)  →  Phase 2 (SoftDent)  →  Phase 3 (HAL/commands)
        ↓                                              ↓
Phase 4 (Charts)  ←──────────────────────────  Phase 5 (SideNotes hub)
        ↓
Phase 6 (Workstation) — only if requested
```

**First commit slice:** Phase 1 only — highest visual delta, lowest cross-file coupling.

---

## Sign-off checklist (program complete)

- [ ] All 10 staff pages pass mockup parity audit (including QB + SoftDent extensions)
- [ ] HAL page matches `page_mockups/hal.html` (no manager widget group box)
- [ ] Sub-nav on every page with widgets
- [ ] Page commands wire to HAL on Financial, SoftDent, QuickBooks, Taxes, A/R
- [ ] Charts live on Financial + QuickBooks + A/R where mockup shows charts
- [ ] SideNotes LIVE/OFFLINE + optional hub badge
- [ ] Operator runbook updated with reload URL pattern
- [ ] Build bumped and validators green

---

## Approval

| Phase | Scope | Approve? |
|-------|-------|----------|
| 1 | QuickBooks mockup | ☐ |
| 2 | SoftDent funnel + operatory | ☐ |
| 3 | HAL cleanup + command chips | ☐ |
| 4 | Canvas chart bridge | ☐ |
| 5 | SideNotes hub | ☐ |
| 6 | Workstation CSS (optional) | ☐ |

**Operator:** check phases to implement, then request implementation by phase number.
