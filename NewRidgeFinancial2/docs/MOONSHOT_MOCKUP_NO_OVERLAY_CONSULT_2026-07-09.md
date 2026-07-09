# Moonshot AI — Mockup on Live Pages (No Overlay / No Legacy Interrupt)
**Date:** 2026-07-09
**Model:** kimi-k2.5 via OPENROUTER_API_KEY
**Status:** REVIEW ONLY — do not apply until operator validates
**Script:** `scripts/run_moonshot_mockup_no_overlay_consult.py`
**Scope:** Elite mock look on live-wire pages; kill mock-embed overlay + conflicting flags

---

# Verdict
The elite mockups are currently blocked by three hard conflicts in the boot sequence: `NR2_STAFF_MOCK_ONLY = true` forces the sidebar-hiding JS path, the `app--mock-embed-solo` class on #app triggers unconditional CSS grid collapse, and the inline `<style id="nr2-mock-embed-critical">` contains a bare `#sidebar { display: none !important; }` rule that hides the navigation regardless of later attribute flips. Additionally, `page-canvas.js` retains an iframe fallback (`mockupPreviewGate`) that would render the elite HTML as an overlay if the Layout Engine ever failed to load. By flipping the flag to false, removing the solo class, deleting the critical style block, and replacing the iframe fallback with a hard error for live-wire pages, the MoonshotLayoutEngine will render elite structure directly into the live shell with full sidebar, tools, and mission-control glass styling—no iframe, no legacy mock-embed chrome.

## 1. Root Cause: Why mockup look / procedures are interrupted
| Conflict | Location | Evidence | Impact |
|---|---|---|---|
| **NR2_STAFF_MOCK_ONLY = true** | `index.html:15` | `window.NR2_STAFF_MOCK_ONLY = true;` | Forces `staffMockEmbedNavHidden()` → true in `app.js`, causing `renderSidebar()` to detach the nav rail and hide `#sidebar` via JS. |
| **data-nr2-staff-render="mock-embed"** | `index.html:24` | `document.documentElement.setAttribute('data-nr2-staff-render','mock-embed');` | Triggers CSS rules in `nr2-mockup-page-vocabulary.css` that suppress sync badges, filter bars, and HAL strips. |
| **app--mock-embed-solo class** | `index.html:~100` | `<div id="app" class="app app--moonshot-mockup app--mock-embed-solo">` | The inline critical style block targets this class with `grid-template-columns: 1fr !important` and unconditional `#sidebar { display: none !important; }`. |
| **nr2-mock-embed-critical style block** | `index.html:~105-125` | `<style id="nr2-mock-embed-critical">…` | Contains bare `#sidebar { display: none !important; }` (no attribute prefix) which hides the sidebar even after JS flips the attribute to live-wire. |
| **mockupPreviewGate iframe fallback** | `page-canvas.js:renderBody` | `if (!LE …) return … + mockupPreviewGate(pageId);` | If Layout Engine is missing, live-wire pages would render the elite mockup inside an iframe overlay, violating the "no overlay" rule. |
| **staffMockEmbedMode() checks** | `nr2-moonshot-mockup-chrome.js` | Checks `NR2_STAFF_MOCK_ONLY` or attribute | Keeps chrome in mock-embed state even when build.json declares live-wire-pilot. |

## 2. Target Architecture (no overlay)
```
index.html boot
  ├─ NR2_STAFF_MOCK_ONLY = false
  ├─ data-nr2-staff-render="live-wire-pilot" (initial)
  ├─ #app class: app--moonshot-mockup (no app--mock-embed-solo)
  └─ nr2-mock-embed-critical style block DELETED

app.js boot
  └─ staffMockEmbedNavHidden() → false
      └─ renderSidebar() renders full nav rail

page-canvas.js renderBody(pageId)
  ├─ shouldLiveWire(pageId) → true
  ├─ MoonshotLayoutEngine.render(pageId, H) → elite HTML
  └─ NO fallback to mockupPreviewGate (iframe forbidden for live-wire)
      └─ Error banner if LE missing (rollback available)

CSS cascade
  ├─ nr2-moonshot-mockup-theme.css (base)
  ├─ nr2-mission-control-glass.css (glass/obsidian elite surfaces)
  └─ ms-mission-control classes present on widget-grid
```

**DELETED:** `app--mock-embed-solo` class, `nr2-mock-embed-critical` style block, `NR2_STAFF_MOCK_ONLY=true`  
**DISABLED:** `mockupPreviewGate` for live-wire pages (kept behind rollback comment)  
**KEPT:** `mockupPreviewGate` function for non-live-wire legacy pages (P2 dead-code path), `live-wire-pilot-banner` (informational, can be hidden via CSS if desired).

## 3. Exact Operator Instructions (numbered, copy-paste order)

1. **Backup** `index.html`, `page-canvas.js`, `app.js` (git stash or cp).
2. **Edit `NewRidgeFinancial2/site/index.html`**
   - Line ~15: Change `window.NR2_STAFF_MOCK_ONLY = true;` → `window.NR2_STAFF_MOCK_ONLY = false;`
   - Line ~24: Change `document.documentElement.setAttribute('data-nr2-staff-render','mock-embed');` → `document.documentElement.setAttribute('data-nr2-staff-render','live-wire-pilot');`
   - Line ~100 (the #app div): Remove `app--mock-embed-solo` from the class list.
   - Lines ~105-125: Comment out or delete the entire `<style id="nr2-mock-embed-critical">…</style>` block.
3. **Edit `NewRidgeFinancial2/site/page-canvas.js`**
   - Locate `renderBody` function, inside the `if (shouldLiveWire(pageId))` block.
   - Find the `if (!LE || typeof LE.render !== "function" || !LE.hasPage(pageId))` condition.
   - Replace the return statement as shown in File 2 below (adds rollback comment and error instead of iframe).
4. **Verify `NewRidgeFinancial2/site/app.js`** (no edit required if flags flipped correctly, but confirm `syncStaffRenderModeAttr` exists—it will keep attribute as live-wire-pilot).
5. **Hard refresh** browser with `?__nr2_purge=1` once to clear service worker cache of the old critical CSS.
6. **Validate** per Section 6 checklist.

## 4. Moonshot Code Deliverables

### File: NewRidgeFinancial2/site/index.html
```html
<!-- P0: BOOT FLAG FLIP — Line ~15 -->
<script>
(function(){
  window.NR2_FINANCIAL_ONLY = true;
  window.NR2_WORKSTATION_ONLY = false;
  window.NR2_STAFF_MOCK_ONLY = false; /* CHANGED: true → false */
  window.NR2_STAFF_RENDER_MODE = 'live-wire-pilot';
  window.NR2_LIVE_WIRE_PAGES = ['financial', 'softdent', 'quickbooks', 'ar', 'taxes', 'claims', 'narratives', 'documents', 'library', 'hal', 'office-manager'];
  window.__NR2_REQUIRED_EPOCH = 'moonshot-mockup';
  window.__NR2_REQUIRED_BUILD = 'hal-10166';
  try {
    delete window.LEGACY_PAGE_SCHEMA;
    delete window.OLD_NR2_SCHEMA;
    delete window.WorkstationSchema;
    document.documentElement.setAttribute('data-nr2-epoch','moonshot-mockup');
    document.documentElement.setAttribute('data-nr2-program','financial');
    document.documentElement.setAttribute('data-nr2-staff-render','live-wire-pilot'); /* CHANGED: mock-embed → live-wire-pilot */
    /* … rest of purge logic unchanged … */
  } catch(e){}
})();
</script>

<!-- P0: SHELL CLASS CLEANUP — Line ~100 -->
<div id="app" class="app app--moonshot-mockup">
  <!-- REMOVED: app--mock-embed-solo -->

<!-- P0: DELETE OR COMMENT OUT entire block — Lines ~105-125 -->
<!-- ROLLBACK: Restore the style block below to re-enable mock-embed chrome
<style id="nr2-mock-embed-critical">
  …
</style>
-->
```

### File: NewRidgeFinancial2/site/page-canvas.js
```javascript
function renderBody(pageId, feed, programSnapshot) {
  if (
    typeof window !== "undefined" &&
    (!window.PageSchema || window.PageSchema.LAYOUT_EPOCH !== "moonshot-mockup")
  ) {
    throw new Error("[NR2] PageCanvas: Moonshot epoch required. Legacy layout retired.");
  }
  activePageId = pageId;
  activeFeed = feed || null;
  activeSnapshot = programSnapshot || null;
  const D = dataApi();
  if (D) D.bind(activeFeed, activeSnapshot);
  if (shouldLiveWire(pageId)) {
    const H = buildMoonshotHelpers();
    const noticeHtml = canvasImportNotice(pageImportNotice(pageId));
    const LE = typeof MoonshotLayoutEngine !== "undefined" ? MoonshotLayoutEngine : null;
    if (!LE || typeof LE.render !== "function" || !LE.hasPage(pageId)) {
      /* P0: ROLLBACK PATH — To restore iframe overlay fallback, replace the next 8 lines with:
         return liveWirePilotBanner(pageId) + noticeHtml + mockupPreviewGate(pageId);
      */
      return (
        liveWirePilotBanner(pageId) +
        noticeHtml +
        `<div class="ms-layout-error" style="padding:24px;border:1px solid rgba(248,113,113,.4);background:rgba(248,113,113,.08);border-radius:8px;color:#f87171;">
          <strong>Layout Engine required for live-wire pilot</strong><br>
          <code style="color:#e5e5e7;">${H.esc(pageId)}</code>
          <p style="margin:8px 0 0;color:#a3a3a3;font-size:12px;">
            Ensure moonshot-layout-engine.js loads before page-canvas.js. 
            Elite mockups render without iframe overlay.
          </p>
        </div>`
      );
    }
    const html = LE.render(pageId, H);
    return liveWirePilotBanner(pageId) + noticeHtml + (html || "");
  }
  /* P2: Legacy non-live-wire path — iframe preview gate kept for rollback */
  return mockupPreviewGate(pageId);
}
```

### File: NewRidgeFinancial2/site/app.js
*No patch required* — `staffMockEmbedNavHidden()` automatically returns false when `NR2_STAFF_MOCK_ONLY` is false and attribute is `live-wire-pilot`, causing `renderSidebar()` to render the full rail. Verify this function exists around the sidebar render logic.

### File: NewRidgeFinancial2/site/nr2-mission-control-glass.css (Optional P1 Strengthen)
If visual delta remains weak after flag flip, append to strengthen elite surfaces:
```css
/* P1: Strengthen elite glass distinction */
.app--moonshot-mockup .ms-mission-control .ms-panel,
.app--moonshot-mockup .ms-mission-control .widget-card {
  background: rgba(16, 16, 20, 0.85);
  backdrop-filter: blur(14px) saturate(120%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 12px 40px rgba(0,0,0,0.45);
}
.app--moonshot-mockup .ms-mission-control .ms-panel:hover {
  border-color: var(--mc-accent);
  box-shadow: 0 0 0 1px var(--mc-accent), 0 16px 48px rgba(0,0,0,0.55);
}
```

## 5. Legacy / Overlay Kill List

| Artifact | Path | Action | Why |
|---|---|---|---|
| `NR2_STAFF_MOCK_ONLY` flag | `index.html:15` | Set `false` | P0: Blocks sidebar render in app.js |
| `data-nr2-staff-render="mock-embed"` | `index.html:24` | Set `"live-wire-pilot"` | P0: Triggers mock-embed CSS vocabulary |
| `app--mock-embed-solo` | `index.html:~100` | Remove class | P0: Unconditional grid collapse & sidebar hide |
| `nr2-mock-embed-critical` style block | `index.html:~105-125` | Delete/Comment | P0: Contains bare `#sidebar {display:none}` |
| `mockupPreviewGate` iframe (live-wire) | `page-canvas.js:renderBody` | Replace with error | P0: Prevents iframe overlay on elite pages |
| `mockupPreviewGate` function | `page-canvas.js` | Keep (dead flag) | P2: Rollback path for non-live-wire pages |
| `ms-mockup-preview-frame` CSS | `nr2-mockup-page-vocabulary.css` | Keep (unused) | Harmless when live-wire active |
| `live-wire-pilot-banner` | `page-canvas.js` | Keep | Informational; hide via CSS if undesired |

## 6. Validation Gate (browser)

Open Financial, Claims, QuickBooks pages and confirm:

- [ ] **No iframe**: `document.querySelector('.widget-grid iframe, .ms-mission-control iframe')` returns `null`.
- [ ] **Attribute locked**: `document.documentElement.getAttribute('data-nr2-staff-render')` equals `"live-wire-pilot"` (not mock-embed).
- [ ] **Sidebar visible**: `#sidebar` is visible with nav items (not `display:none`).
- [ ] **Solo class absent**: `document.getElementById('app').classList.contains('app--mock-embed-solo')` is `false`.
- [ ] **Flag false**: Console `window.NR2_STAFF_MOCK_ONLY` is `false`.
- [ ] **Elite classes present**: `.widget-grid` has `financial-moonshot ms-mission-control` (or page-specific variant).
- [ ] **Honesty empties**: Empty widgets name exact export files (e.g., "Add `softdent_procedures.csv` to import inbox").
- [ ] **No mock-embed chrome**: No `.mock-embed-nav` element rendered in page.

## 7. Prioritized Commits (max 4) — WAIT for operator proceed

**WAIT** — Do not push until operator validates report.

1. **P0**: `index.html` — Flip `NR2_STAFF_MOCK_ONLY` to false, set initial `data-nr2-staff-render="live-wire-pilot"`, remove `app--mock-embed-solo` class, delete `nr2-mock-embed-critical` style block.  
   *Acceptance*: Sidebar visible, app shell renders full grid.

2. **P0**: `page-canvas.js` — Disable `mockupPreviewGate` iframe fallback for live-wire pages; return Layout Engine error instead.  
   *Acceptance*: Financial page renders via `MoonshotLayoutEngine.render()`, zero iframes in DOM.

3. **P1**: `nr2-mission-control-glass.css` — Strengthen glass panel opacity/backdrop-filter for elite visual delta (optional, only if operator reports weak contrast).  
   *Acceptance*: Panels show obsidian glass with cyan/gold/accent hover glow matching elite HTML.

4. **P2**: `page-canvas.js` — Wrap `mockupPreviewGate` invocation in dead-flag check `if (window.__NR2_LEGACY_MOCKUP_FALLBACK)` to formally deprecate non-live-wire path.  
   *Acceptance*: Function exists but is unreachable unless explicit rollback flag set in console.

## Risks & Rollback

**Risk**: If `moonshot-layout-engine.js` fails to load (network/cache), live-wire pages will show red error block instead of graceful iframe.  
**Mitigation**: Verify Layout Engine loads in Network tab; error message includes explicit remediation steps.

**Rollback** (immediate restoration of mock-embed):
1. Restore `index.html` lines: `NR2_STAFF_MOCK_ONLY = true;`, attribute to `mock-embed`, add `app--mock-embed-solo` class, restore `<style id="nr2-mock-embed-critical">`.
2. Restore `page-canvas.js` iframe fallback line (see rollback comment in code).
3. Hard refresh with `?__nr2_purge=1`.
