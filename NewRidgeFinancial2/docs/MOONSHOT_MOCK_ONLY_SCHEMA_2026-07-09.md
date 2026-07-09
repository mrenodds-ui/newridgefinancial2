# Moonshot AI — Mock-Only Schema Purge

**Date:** 2026-07-09  
**Model:** Local architect report (Moonshot cloud HTTP 401 — refresh `OPENROUTER_API_KEY` or `MOONSHOT_API_KEY` and rerun `scripts/run_moonshot_mock_only_schema_consult.py`)  
**Script:** `scripts/run_moonshot_mock_only_schema_consult.py`  
**Build:** hal-10100 · epoch `moonshot-mockup`

---

# Verdict

Staff pages are **already mock-only at render time**: `PageCanvas.renderBody()` returns an elite mock iframe (`/mockup-elite-embed/<page>`), legacy `page-schema.js` / `page-chrome.js` / `moonshot-layout-engine.js` are **not loaded**, and validators block `pv-*` / `hp-*` in staff HTML. What remains is **bundle bloat and latent wiring** (chart scripts, `page-canvas-data.js`, layout manifest, HAL widget bridges) that can still confuse operators and invite re-wiring before sign-off. The mock-only program should **trim the staff load path**, keep HAL live on `#hal`, and treat elite HTML as the sole staff body surface until operator approval.

---

## 1. Legacy Schema Still Present (inventory)

| Area | Status | Action |
|------|--------|--------|
| `page-schema.js`, `page-chrome.js`, `hal-page-schema.js` | **Deleted** | None |
| `moonshot-layout-engine.js` | On disk, **not in index.html** | Keep for future wiring; do not re-add to index |
| `moonshot-page-layouts.js` | **Loaded** in index (manifest data only) | Optional trim for mock-only; registry reads widget keys from it |
| `page-canvas-data.js` | **Loaded**; staff `renderBody` does not use it for panels | Defer load to HAL route or post-sign-off |
| `charts/*.js`, `nr2-moonshot-ui.js` | Loaded; `enhancePage` **skipped** when `.ms-mockup-preview-frame` present | Safe; can lazy-load for HAL only |
| `desktop-boot.js` | Checks `MoonshotMockupChrome` + `PageSchema` epoch | **Done** |
| `components.js` pv-* stubs | Partially retired; ErrorState uses `ms-boot-error` | **Done** |
| CSS `styles.css` | Legacy pv/hp bulk **pruned** | **Done** |
| HAL memos / docs | Sources updated to `moonshot-page-registry.js` | **Done** |
| Service worker `sw.js` | May cache old assets | Purge via `?__nr2_purge=1` after deploy |

**P0 latent risk:** Re-enabling `MoonshotLayoutEngine.render()` in `page-canvas.js` or re-adding `moonshot-layout-engine.js` to index without operator sign-off.

---

## 2. Mock-Only Target Architecture

```
Start Program (8765)
  index.html  [NR2_FINANCIAL_ONLY, epoch moonshot-mockup]
    moonshot-page-registry.js  → PageSchema (nav, filters, widget metadata)
    nr2-moonshot-mockup-chrome.js → nav-rail + ms-page-chrome header
    page-canvas.js → renderBody() → mockupPreviewGate() → iframe
    mockup_elite_embed.py route → static elite HTML (page_mockups_elite/)
  Staff hash routes (#financial … #office-manager)
    ms-page shell + iframe elite mock ONLY
  #hal
    hal-page.js + hal-page-canvas.js (live HAL — unchanged)
```

**Staff page HTML shape:**

```html
<article class="ms-page" data-ms-page="financial">
  <!-- ms-page-chrome: title, filters, hal-insight from MoonshotMockupChrome -->
  <div class="ms-mockup-preview-frame">
    <iframe src="/mockup-elite-embed/financial"></iframe>
  </div>
</article>
```

---

## 3. Deletion / Trim List

**Do not delete (HAL / imports):** `hal-*.js`, `services.js`, `snapshot-store.js`, `import-*`, `desktop-bridge.js`.

**Trim from staff critical path (mock-only phase):**

- `moonshot-page-layouts.js` — only needed when wiring layout engine; registry can inline minimal widget list
- `page-canvas-data.js` — not used by mock iframe body
- `charts/import-timeline.js`, `charts/ar-heatmap.js`, `charts/practice-pulse.js`, `charts/posting-kanban.js` — staff pages skip chart hosts
- `nr2-tier3.js` — tier-3 mounts disabled on staff pages
- `nr2-analytics.js`, `nr2-qb-reports.js`, `nr2-softdent-daily.js` — defer until live wiring

**Keep loaded:** registry, mockup chrome, page-canvas, page-views, app, desktop-boot, HAL stack for `#hal`.

---

## 4. Moonshot Code Deliverables

### FILE: `site/page-canvas.js` — **already correct (keep)**

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
  return mockupPreviewGate(pageId);
}
```

### FILE: `site/index.html` — **INSERT** mock-only flag (optional trim gate)

```javascript
window.NR2_STAFF_MOCK_ONLY = true; // staff bodies = elite iframe only; no live panel wiring
```

Add next to existing `NR2_FINANCIAL_ONLY` block in `<head>`.

### FILE: `site/nr2-moonshot-ui.js` — **already guards staff mock frames**

```javascript
if (root.querySelector(".ms-mockup-preview-gate, .ms-mockup-preview-frame")) return;
```

### FILE: `site/desktop-boot.js` — **already guards**

```javascript
if (typeof MoonshotMockupChrome === "undefined") {
  errors.push("nr2-moonshot-mockup-chrome.js failed to load (MoonshotMockupChrome is undefined).");
}
```

### FILE: `mockup_elite_embed.py` + `nr2_http_server.py` — **route (keep)**

```python
@app.get("/mockup-elite-embed/<page_id>")
def mockup_elite_embed(page_id):
    from mockup_elite_embed import render_embed_html
    html = render_embed_html(str(page_id or "").strip().lower())
    if html is None:
        bottle.abort(404, "Elite mock preview not found for this page.")
    return html
```

### FILE: `validate-pages.mjs` — **assert mock iframe**

```javascript
const MOCK_PREVIEW_CHECKS = ["ms-mockup-preview-frame", "mockup-elite-embed", "Elite mock preview"];
assert.ok(pageCanvasJs.includes("ms-mockup-preview-frame"), "page-canvas must embed elite mock previews");
assert.ok(!pageCanvasJs.includes("MoonshotLayoutEngine.render"), "page-canvas must not wire layout engine");
```

---

## 5. Migration Steps (ordered)

1. **P0 — Confirm mock embed live**  
   - Restart Start Program; open `https://127.0.0.1:8765/?v=hal-10100&__nr2_purge=1#financial`  
   - Accept: elite mock visible in iframe; no `pv-*` in DOM.

2. **P0 — Block layout engine re-entry**  
   - CI: `validate-pages.mjs` + grep index for `moonshot-layout-engine.js` → must be absent.

3. **P1 — Optional bundle trim**  
   - Create `moonshot-site-mock.manifest.json` with reduced script list for mock-only epoch.  
   - Load full HAL/chart bundle only when `location.hash === '#hal'`.

4. **P1 — Registry without layouts file**  
   - Inline widget keys in `moonshot-page-registry.js`; remove `moonshot-page-layouts.js` from index until wiring phase.

5. **P2 — Operator sign-off gate**  
   - Document in `nr2-build.json`: `"staffRenderMode": "mock-embed" | "live-wire"`.  
   - Flip to `live-wire` only after mock gallery approval.

6. **Smoke — validators**  
   ```powershell
   cd NewRidgeFinancial2
   node validate-pages.mjs
   node validate-hal.mjs
   ```

---

## 6. Operator Smoke Test

| Step | URL / action | Expected |
|------|----------------|----------|
| 1 | Start Program | Validators pass |
| 2 | `#financial` | Nav rail + **Elite mock preview** iframe |
| 3 | `#quickbooks` | Different elite mock in iframe |
| 4 | DevTools → Elements | No `pv-canvas`, no `data-nr2-chart-host` on staff page |
| 5 | `#hal` | Live HAL page (not iframe mock) |
| 6 | `/mockup-elite-embed/financial` | Raw elite HTML with embed CSS hiding mock nav |

**Gallery (standalone):** `.local_logs/moonshot_financial_eval/page_mockups_elite/index.html`

---

## Re-run live Moonshot consult

```powershell
# Set a valid key, then:
py -3 scripts/run_moonshot_mock_only_schema_consult.py
```

Reports: `.local_logs/moonshot_financial_eval/MOONSHOT_MOCK_ONLY_SCHEMA_YYYY-MM-DD.md`
