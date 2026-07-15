# Moonshot AI — Landing Main Bench + HAL Chat (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_landing_hal_chat_consult.py`
**Apply:** DO NOT APPLY production cutover until operator approves.

## Operator request (verbatim)

> tell moonshot ai the main branch should be the landing page and hal's page needs a high tech chat box

---

# Verdict (schema)

## 0. Operator Intent (verbatim)
> "tell moonshot ai the main branch should be the landing page and hal's page needs a high tech chat box"

## 1. Landing = Main Bench (routing / shell changes)
**Current state inversion required.** The `nr2-12009-interference` optical bench (QuickBooks right-panel / SoftDent left-panel / HAL spectral core) currently resides at `/nr2-optical-qb-right-sd-left-mockup.html`. The Pages Hub (`nr2-12010-pages`) currently serves as the default entry point.

**Routing delta:**
- **Default route `/` → Main Bench** (`nr2-12009-interference`). This is the financial optical interferometer; users land directly on the live QuickBooks/SoftDent interference pattern.
- **Pages Hub demoted to `/hub`** or `/optical-pages`. Retain as secondary navigation for deep-linking to individual optical pages (HAL, Audit, Import).
- **Redirect rule:** Existing `/nr2-optical-pages-hub.html` → 302 to `/hub`, preserving SEO juice while fixing the entry vector.

**Shell changes:**
- Remove "Enter Lab" gateway modal from Pages Hub; that UX friction now belongs to authentication gates, not navigation.
- Main Bench receives a "Pages" beam-splitter icon in the top-right vacuum space to access the hub without losing optical context.

## 2. HAL high-tech chat box (spec, visuals, binds, states)
**Component codename:** `hal-core-console` (spectral chat interferometer).

### Visual Schema (Optical Theme)
- **Vacuum Black:** `#000000` background with `#0a0a0a` subtle grid (interference fringe pattern).
- **Spectral HAL Core:** Central "eye" pulsing between `#ff6600` (amber alert) and `#00ffff` (cyan logic), 2px glow blur using `box-shadow` with optical decay.
- **Beam Accents:** Input cursor is a vertical 1px beam `#ffffff` with 0.3s blink cycle; message send trigger draws a horizontal scanning line (CRT raster effect).
- **Mono HUD:** `font-family: 'Courier Prime', monospace`; text color `#33ff00` (phosphor green) for user queries, `#ffaa00` (sodium vapor) for HAL responses.

### Functional Binding
- **Endpoint:** `POST /api/hal/evaluate-query`
- **Payload:** `{"query": string, "session_id": uuid, "financial_context": boolean, "rbac_token": jwt}`
- **Response handler:** Streams tokens via `text/event-stream` or polls for optical interference animation during processing.

### State Machine (4-phase interferometry)
1. **IDLE:** Core pulses slowly (2s cycle). Placeholder text: *"Awaiting optical input..."*
2. **LISTENING:** Waveform visualization in header (SVG sine wave modulating to voice/text input). Input field active with beam cursor.
3. **PROCESSING:** Interference pattern animation (concentric rings collapsing toward center). HAL core shifts to rapid cyan flicker. Display confidence interval as spectral fringe density.
4. **RESPONDING:** Typed text effect (40ms/char) with trailing beam. Financial data gated: if `query` matches `/\$|amount|balance|revenue/i`, UI overlays *"Import-readiness check required"* badge until `financial_context: true` is verified via RBAC.

### Honesty & Safety Gates
- **No hallucinated $:** Response parser strips ungrounded currency symbols; if HAL returns financial figures without `source_document_id`, UI renders `[VERIFICATION REQUIRED]` overlay.
- **RBAC:** Send button disabled until `rbac_token` validates `hal:query` scope.
- **Audit trail:** All queries logged to `hal_interference_log` table with optical path timestamp.

## 3. Updated page tree notes
```
/                           [NEW] Main Bench (nr2-12009-interference) ← LANDING
├── /hub                    [MOVED] Pages Hub (nr2-12010-pages) 
│   ├── /hal                [ENHANCED] HAL page + hal-core-console
│   ├── /audit              [UNCHANGED] Audit beam
│   └── /import             [UNCHANGED] Import chamber
├── /api/hal/evaluate-query [EXISTS] Bound to console
└── /static/optical/        [NEW ASSETS] hal-core-console.css, interference.js
```

## 4. Mockup change list
**File:** `nr2-optical-page-hal.html`
- [ ] Inject `<div id="hal-core-console">` below existing HAL status panel.
- [ ] Import `hal-optical-theme.css` (vacuum black, spectral gradients).
- [ ] Initialize `HalInterferometer` JS class on `DOMContentLoaded`.
- [ ] Bind `#chat-input` to `evaluate-query` POST with debounce (300ms).
- [ ] Add CRT scanline overlay `<div class="scanlines">` for retro-futuristic HUD feel.
- [ ] Implement `FinancialGate` middleware: intercepts outbound messages, checks `/api/session/financial-ready`, appends `financial_context` flag.

**File:** `nr2-optical-qb-right-sd-left-mockup.html` (Main Bench)
- [ ] Add `<a href="/hub" class="beam-splitter-nav">Pages</a>` to header vacuum.
- [ ] Set `<meta rel="canonical" href="/">` to establish this as root.

**File:** `nr2-optical-pages-hub.html`
- [ ] Remove "Landing" meta tags; add `<meta name="robots" content="noindex">` to prevent search engine confusion.
- [ ] Add prominent "Return to Main Bench" optical beam button.

## 5. Schema bump justification
**Current:** `nr2-12010-pages` (Pages Hub as entry; HAL page static)  
**Proposed:** `nr2-12011-landing-chat`  

**Breaking changes requiring bump:**
1. **Entry point semantics:** Root route `/` remapped from Hub to Main Bench (major UX architecture shift).
2. **New component surface:** Introduction of `hal-core-console` adds API contract (`evaluate-query` streaming) and WebSocket-like behavior.
3. **RBAC expansion:** Financial gating on HAL chat requires new permission scope `hal:financial-query`.
4. **Asset pipeline:** New optical theme CSS/JS adds 40KB critical render path.

**Migration path:** Blue-green deploy; old `/index.html` → `/legacy-hub-redirect.html` for 48h grace period.

## 6. Executive Summary (5 bullets)
- **Landing Inversion:** The Main Optical Interferometer (QuickBooks/SoftDent bench) becomes the default entry point; Pages Hub relocates to `/hub` to reduce navigation friction for financial operators.
- **HAL Spectral Console:** New vacuum-black chat interface with phosphor-green typography and pulsing cyan core, bound live to `POST /api/hal/evaluate-query` with streaming response handling.
- **Financial Honesty Gates:** HAL chat automatically detects monetary queries and enforces import-readiness verification, preventing hallucinated dollar amounts through RBAC-gated context injection.
- **State Visualizer:** Four-phase optical interference animation (Idle/Listening/Processing/Responding) provides immediate system status feedback via CRT-style HUD elements.
- **Schema Evolution:** Bump to `nr2-12011-landing-chat` formalizes the routing changes and new HAL component contract, ensuring backward compatibility via 48h redirect grace period.

## 7. Approval checklist
- [ ] **Architect:** Confirm Main Bench routing inversion does not break existing deep links to `/hub`.
- [ ] **Security:** Review RBAC implementation on `hal:financial-query` scope.
- [ ] **UX:** Validate optical theme contrast ratios meet WCAG AA (amber on black).
- [ ] **Backend:** Verify `/api/hal/evaluate-query` supports SSE streaming or adjust to polling fallback.
- [ ] **Database:** Confirm `hal_interference_log` table exists for audit trail.
- [ ] **DevOps:** Schedule blue-green deployment for schema `nr2-12011-landing-chat`.

---
**Status:** DESIGN COMPLETE. Awaiting approval for implementation.
