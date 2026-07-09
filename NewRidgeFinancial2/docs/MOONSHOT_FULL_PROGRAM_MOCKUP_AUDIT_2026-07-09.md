# Moonshot AI — Full Program Mockup / Live-Wire Error Audit
**Date:** 2026-07-09
**Model:** kimi-k2.5 via OPENROUTER_API_KEY
**Status:** REVIEW ONLY — do not apply until operator validates
**Script:** `scripts/run_moonshot_full_program_mockup_audit.py`
**Build context:** hal-10167 (post no-overlay)

---

# Verdict
The live-wire pilot pages fail to match elite Jul 8 mockups because three hard errors remain after hal-10167: (1) `moonshot-page-registry.js` contains a stale heuristic in `staffMockOnly()` that returns `true` whenever the `__NR2_MOCKUP_ELITE_PAGES` catalog exists, force-overriding the `live-wire-pilot` boot flag and triggering sidebar-collapse CSS; (2) `validate-pages.mjs` encodes assertions that enforce mock-embed patterns (solo layout, hidden sidebar, mock-embed nav) even for live-wire pages, masking the true state and breaking CI; and (3) `MoonshotLayoutEngine.render()` omits the page header structure (title, subtitle, filter-bar) present in all elite mockups, causing the "old schema" appearance even when mode detection is corrected.

## Executive Summary
- **Boot flags are correct** (index.html sets `live-wire-pilot`), but **registry heuristics ignore them**.
- **CSS/Chrome** collapses to mock-embed mode because `staffMockOnly()` lies to the system.
- **Layout structure gap**: Live-wire renders naked widget grids without the elite page-header chrome (title, filters).
- **Validator is adversarial**: It asserts that pilot mode must use mock-embed attributes, preventing correct configuration.

## Full Program Error Inventory

| ID | Severity | Area | File | Evidence | Why it breaks live↔mockup | Fix summary |
|----|----------|------|------|----------|---------------------------|-------------|
| **REG-001** | Critical | Registry | `moonshot-page-registry.js` | `staffMockOnly()` returns `true` if `window.__NR2_MOCKUP_ELITE_PAGES.length > 0` (stale comment: "elite catalog implies mock-embed staff shell") | Forces mock-embed mode regardless of `NR2_STAFF_MOCK_ONLY=false`, triggering `html[data-nr2-staff-render="mock-embed"]` CSS that hides `#sidebar` and strips live chrome | Remove elite catalog length check; rely solely on explicit flags |
| **VAL-001** | Critical | Validator | `validate-pages.mjs` | Asserts `indexHtml.includes('data-nr2-staff-render="mock-embed"')` and `app--mock-embed-solo` for pilot mode; asserts `mock-embed-nav` must exist for live-wire pages | Validation fails on correct live-wire config; forces developers to break live-wire to pass tests | Distinguish pilot live-wire from mock-embed in assertions |
| **LAY-001** | Critical | Layout | `moonshot-layout-engine.js` | `render()` outputs `widget-grid` panels directly without page header shell (no `ms-page-header`, title, or filters) | Elite mockups show distinct page-title, subtitle, and filter-chip bars; live-wire shows anonymous grid | Generate header from spec.title/spec.subtitle before panels |
| **CHROME-001** | High | Chrome | `nr2-moonshot-mockup-chrome.js` | `staffMockEmbedMode()` checks `window.__NR2_MOCKUP_ELITE_PAGES` array at end of function | Mirrors REG-001; causes chrome to strip live elements (sync badges, export tools) from live-wire pages | Remove elite catalog check; trust explicit mode flags only |
| **CSS-001** | High | CSS | `nr2-mission-control-glass.css` vs `nr2-mockup-page-vocabulary.css` | Glass targets `.ms-mission-control`; vocabulary targets `.ms-page` and `[data-nr2-staff-render="mock-embed"]` | If mode is wrong, vocabulary hides sidebar; if mode is right, some vocabulary rules may not apply to mission-control classes | Ensure consistent wrapper classes; verify no `!important` conflicts in cascade |
| **VIEW-001** | Medium | Views | `page-views.js` | `stripMockEmbedLiveChrome()` calls `staffMockEmbedPage(pageId)` which relies on registry | Will strip live chrome (filters, HAL strips) if registry lies about mode | Fix propagates from REG-001 |
| **APP-001** | Medium | Boot | `app.js` | `syncStaffRenderModeAttr()` calls `MC.staffMockEmbedPage(pageId)` | May flip HTML attribute to `mock-embed` mid-session if chrome.js returns true | Fix propagates from CHROME-001 |
| **SW-001** | Low | Cache | `sw.js` | Cache name `nr2-offline-v12-mock-embed` | Misleading name suggests stale cache strategy; may cause confusion during debug | Rename to `nr2-offline-v13-livewire` (cosmetic) |

## Architecture Diagnosis
The elite mockups are standalone HTML files with a consistent shell: fixed `nav-rail` (210px), `page-shell` (margin-left), `page-header` (title + subtitle + filter-chips), and content grids. The live-wire architecture should render this same structure directly into the app shell via `MoonshotLayoutEngine`, but currently:
1. **Mode detection is corrupted** by the registry heuristic that treats the existence of elite page definitions as a signal to enable "mock-embed" (hidden sidebar).
2. **Structure is incomplete** because the Layout Engine renders only the content panels, omitting the page-specific header chrome that gives each page its identity.

The correct mapping is: `live-wire-pilot` mode → full sidebar + Layout Engine rendering → page header (from spec) + widget grid (from spec) → mission-control glass CSS.

## Moonshot Code Deliverables

### File: NewRidgeFinancial2/site/moonshot-page-registry.js
```javascript
  function staffMockOnly() {
    if (typeof globalThis !== "undefined" && globalThis.NR2_STAFF_MOCK_ONLY) return true;
    if (typeof window === "undefined") return false;
    if (window.NR2_STAFF_MOCK_ONLY) return true;
    try {
      if (document.documentElement.getAttribute("data-nr2-staff-render") === "mock-embed") return true;
    } catch (_e) {
      /* ignore */
    }
    // CRITICAL FIX (REG-001): Remove stale heuristic. Elite catalog presence does NOT imply mock-embed mode.
    // The __NR2_MOCKUP_ELITE_PAGES array is used for layout lookups, not mode detection.
    // if (Array.isArray(window.__NR2_MOCKUP_ELITE_PAGES) && window.__NR2_MOCKUP_ELITE_PAGES.length > 0) {
    //   return true;
    // }
    return false;
  }
```

### File: NewRidgeFinancial2/site/nr2-moonshot-mockup-chrome.js
```javascript
  function staffMockEmbedMode() {
    /* Moonshot no-overlay: mock-embed only when explicitly requested — elite catalog alone must not force overlay. */
    if (typeof globalThis !== "undefined" && globalThis.NR2_STAFF_MOCK_ONLY) return true;
    if (typeof window !== "undefined" && window.NR2_STAFF_MOCK_ONLY) return true;
    if (
      typeof document !== "undefined" &&
      document.documentElement.getAttribute("data-nr2-staff-render") === "mock-embed"
    ) {
      return true;
    }
    const mode =
      (typeof window !== "undefined" && window.NR2_STAFF_RENDER_MODE) ||
      (typeof window !== "undefined" &&
        window.NR2_BUILD &&
        window.NR2_BUILD.staffRenderMode) ||
      "";
    if (mode === "live-wire-pilot" || mode === "live-wire") return false;
    
    // HIGH FIX (CHROME-001): Do not infer mode from elite pages catalog.
    // This check was causing live-wire pages to be treated as mock-embed.
    // return (
    //   typeof window !== "undefined" &&
    //   Array.isArray(window.__NR2_MOCKUP_ELITE_PAGES) &&
    //   window.__NR2_MOCKUP_ELITE_PAGES.length > 0
    // );
    return false;
  }
```

### File: NewRidgeFinancial2/site/moonshot-layout-engine.js
```javascript
  function render(pageId, H) {
    const spec = pageSpec(pageId);
    if (!spec || !H) return "";
    const D = H.dataApi ? H.dataApi() : null;
    const accent = accentFor(pageId);
    const panels = spec.panels || [];
    const shell = spec.shell || "widget-grid";

    // CRITICAL FIX (LAY-001): Generate page header to match elite mockup structure
    let headerHtml = "";
    if (spec.title) {
      const subtitle = spec.subtitle || "";
      // Generate filter chips if page has date filters (common to all elite mocks)
      const filtersHtml = `
        <div class="ms-page-filters">
          <button class="ms-filter-chip active">30 Days</button>
          <button class="ms-filter-chip">90 Days</button>
          <button class="ms-filter-chip">YTD</button>
          <button class="ms-filter-chip">All</button>
        </div>
      `;
      headerHtml = `
        <header class="ms-page-header">
          <h1 class="ms-page-title">${H.esc(spec.title)}</h1>
          ${subtitle ? `<p class="ms-page-sub">${H.esc(subtitle)}</p>` : ""}
          ${filtersHtml}
        </header>
      `;
    }

    if (shell === "dashboard-grid") {
      let inner = "";
      if (pageId === "office-manager") {
        if (D && D.opsDataPanelHtml) inner += D.opsDataPanelHtml();
        if (H.canvasStatsBar && D && D.officeKpis) inner += H.canvasStatsBar(D.officeKpis());
      }
      if (pageId === "quickbooks") {
        inner += renderQuickbooksDashboard(panels, D, H, accent);
      } else {
        inner += `<div class="dashboard-grid">${panels.map((p) => renderDashboardTile(p, D, H, pageId, accent)).join("")}</div>`;
      }
      return `${H.dashboardPageOpen(`${pageId}-moonshot ms-mission-control`)}${headerHtml}<div class="widget-grid">${inner}</div></div>`;
    }

    let body = panels.map((p) => H.gridCol(p.colSpan || 12, renderWidgetGridPanel(p, D, H, pageId, accent))).join("");
    if (pageId === "softdent" && H.renderSoftdentOdbcStrip && D && D.softdentOdbcStatus) {
      body += H.renderSoftdentOdbcStrip(D.softdentOdbcStatus());
    }
    const pageClass =
      pageId === "claims"
        ? "claims-moonshot ms-mission-control"
        : pageId === "narratives"
          ? "narratives-moonshot ms-mission-control"
          : pageId === "taxes"
            ? "taxes-moonshot ms-mission-control"
            : `${pageId}-moonshot ms-mission-control`;
    return `${H.stackOpen(pageClass)}${headerHtml}${body}</div>`;
  }
```

### File: NewRidgeFinancial2/site/validate-pages.mjs
```javascript
    if (mockEmbedMode || (pilotMode && !liveWirePages.includes(page.id))) {
      // Mock-embed or non-live pilot pages: compact chrome
      assert.ok(html.includes("ms-page-chrome--mock-embed"), `${page.id} must use compact mock-embed chrome`);
      assert.ok(html.includes("mock-embed-nav"), `${page.id} must render top mock-embed page nav`);
      assert.ok(!html.includes("sync-badge"), `${page.id} mock-embed must not show live sync badges`);
      // ... (keep existing mock-embed assertions)
    } else if (pilotMode && liveWirePages.includes(page.id)) {
      // CRITICAL FIX (VAL-001): Live-wire pilot assertions corrected
      assert.ok(html.includes("ms-live-wire-pilot-banner"), `${page.id} live-wire pilot must show pilot banner`);
      assert.ok(!html.includes("mock-embed-nav"), `${page.id} live-wire pilot must NOT use mock-embed nav (uses sidebar)`);
      assert.ok(!html.includes("ms-page-chrome--mock-embed"), `${page.id} live-wire pilot must NOT use mock-embed chrome`);
      assert.ok(!html.includes("ms-mockup-preview-iframe"), `${page.id} live-wire pilot must not use mock iframe`);
      // NEW: Assert presence of live-wire structure (header or mission control)
      assert.ok(
        html.includes("ms-mission-control") || html.includes(`${page.id}-moonshot`),
        `${page.id} live-wire pilot must render layout engine shell`
      );
      // NEW: Assert page header present (from LAY-001 fix)
      assert.ok(
        html.includes("ms-page-header") || html.includes("ms-page-title"),
        `${page.id} live-wire pilot must render page header from spec`
      );
    }

    // ... later in file ...

    if (pilotMode) {
      assert.ok(indexHtml.includes("deferred-live-wire/moonshot-page-layouts.js"), "pilot must load layout manifest");
      assert.ok(indexHtml.includes("deferred-live-wire/moonshot-layout-engine.js"), "pilot must load layout engine");
      assert.ok(indexHtml.includes("NR2_LIVE_WIRE_PAGES"), "pilot index must declare live-wire pages");
      
      // CRITICAL FIX (VAL-001): Remove assertions that enforce mock-embed patterns for pilot
      // DELETED: assert.ok(indexHtml.includes('data-nr2-staff-render="mock-embed"') ...);
      // DELETED: assert.ok(indexHtml.includes("app--mock-embed-solo"), ...);
      // DELETED: assert.ok(!indexHtml.includes('id="sidebar"'), ...);
      
      // ADDED: Correct live-wire assertions
      assert.ok(
        indexHtml.includes('data-nr2-staff-render="live-wire-pilot"'),
        "pilot index must declare live-wire-pilot render mode"
      );
      assert.ok(
        !indexHtml.includes("app--mock-embed-solo"),
        "pilot index must NOT use mock-embed-solo class (sidebar should be visible)"
      );
      assert.ok(
        indexHtml.includes('id="sidebar"'),
        "pilot index must include sidebar element for live-wire navigation"
      );
    }
```

## Per-Page Elite Parity Gaps (financial, claims, quickbooks, narratives, softdent, ar, taxes, documents, library, office-manager, hal)

After applying code fixes, the following structural gaps remain between Layout Engine output and elite mockups:

- **financial**: Elite has "Owner Financial Dashboard" title + subtitle "Real-time practice financial intelligence" + filter chips (30d/90d/YTD/All). Layout engine currently omits header. **Fix**: LAY-001 adds header.
- **claims**: Elite has "Claims · Insurance Pipeline" header + filter pills (All/Open/Closed/Denied). Gap: missing header structure. **Fix**: LAY-001 + ensure spec has subtitle.
- **quickbooks**: Elite has "QuickBooks — Financial Synchronization" with blue accent dot. Gap: missing header. **Fix**: LAY-001.
- **narratives**: Elite has kanban lanes with specific headers (Draft, Review, Approved, Library). Gap: Layout engine may not render kanban headers. **Fix**: Verify `renderWidgetGridPanel` handles `type: "kanban"` with lane headers.
- **softdent**: Elite shows ODBC connection status strip. Gap: `renderSoftdentOdbcStrip` exists but may not render if `D.softdentOdbcStatus` missing. **Fix**: Ensure dataApi provides this method.
- **taxes/ar/documents/library/office-manager/hal**: All missing page-header chrome (title, filters). **Fix**: LAY-001 applies universally.

## Validation Gate

**Browser (Live)**:
1. Load `https://<host>/?__nr2_purge=1`
2. Verify `<html data-nr2-staff-render="live-wire-pilot">` (not mock-embed)
3. Verify `<div id="app" class="app app--moonshot-mockup">` (no `app--mock-embed-solo`)
4. Verify `<aside id="sidebar">` is visible (left rail, 210px or 56px depending on config)
5. Navigate to Financial: verify presence of "Owner Financial Dashboard" title and filter chips (30d/90d/YTD/All)

**Node (CI)**:
```bash
cd NewRidgeFinancial2
node validate-pages.mjs
# Must exit 0 with no assertion failures
```

**Visual Diff**:
- Financial live-wire page should visually match `elite/financial.html` structure: dark obsidian panels, cyan accents, monospace figures, identical header text.

## Prioritized Commits (max 5) — WAIT for operator proceed

1. **REG-001**: Kill stale heuristic in `moonshot-page-registry.js` (unblocks mode detection)
2. **VAL-001**: Fix `validate-pages.mjs` assertions (unblocks CI/CD)
3. **CHROME-001**: Fix `nr2-moonshot-mockup-chrome.js` mode detection (ensures chrome consistency)
4. **LAY-001**: Add page headers to `moonshot-layout-engine.js` (achieves elite parity)
5. **CSS-001**: Verify `nr2-mission-control-glass.css` selectors match new `ms-page-header` classes (polish)

## Risks & Rollback

| Risk | Mitigation | Rollback |
|------|------------|----------|
| **HAL or other subsystems rely on `__NR2_MOCKUP_ELITE_PAGES` length check for feature detection** | Verify HAL uses explicit `NR2_STAFF_MOCK_ONLY` flag before proceeding; search codebase for `__NR2_MOCKUP_ELITE_PAGES` references | Restore length check in registry and chrome if live-wire detection fails in production |
| **Double headers** if `page-canvas.js` or `app.js` also injects page titles | Inspect `page-canvas.js` `renderBody` to ensure it doesn't add headers; Layout Engine should be sole source | Remove header generation from Layout Engine if duplication occurs |
| **Validate-pages still fails** due to other hidden assumptions | Run validator after each commit; keep `NR2_STAFF_MOCK_ONLY=true` path intact for legacy | Revert VAL-001 changes to validator if blocking release |
| **SW cache name change causes offline failures** | SW-001 is cosmetic (name only), but if changed, ensure old caches are deleted in activate | Keep cache name as-is if any risk |
