# Moonshot AI — Mockup Review: Improve + Will Widgets Work (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_mockup_improve_workability_consult.py`
**Landing:** `https://127.0.0.1:8765/nr2-optical-beam-touch-mockup.html`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> show the mock ups to moonshot ai and ask if anything can improve and will all the widgets work

---

# Verdict (schema)
**Current:** `nr2-12014-lower-ctrl-beam`  
**Recommended next:** `nr2-12015-honest-beams` (coherent wiring + honesty pass)

---

## 0. Operator Intent (verbatim)
> show the mock ups to moonshot ai and ask if anything can improve and will all the widgets work

---

## 1. Mockup review — what works visually
The optical interferometer metaphor remains intact and atmospheric.  
- **Beam choreography:** Lower placement of SoftDent (white pulse) and QuickBooks (orange) creates a stable “bench” foundation; Tax Prism (magenta) upper-right avoids crowding the control aperture.  
- **Control cluster:** Upper-left teal “CTRL beam” aperture keeps primary actions in the operator’s natural F-pattern without obscuring the HAL core.  
- **Spectral HAL core:** Conic gradient + incoherent/recon state text sells the “interference pattern” concept; the removed floating beam labels reduce UI chrome as requested.  
- **Alignment lasers:** Green/red crosshair overlay is a strong ambient indicator of system health—distinct from the beams themselves.  
- **Honesty banner:** The “empty ≠ $0” disclaimer in the hub is visible but does not break the vacuum aesthetic.  
- **RBAC shutters:** Role toggles (OM / Front Desk) are present as visual placeholders; they signal intent without cluttering the bench.

**Minor visual bug:** `.emitter.sd` references `qb-aperture-pulse` animation (copy-paste residue); should be `sd-aperture-pulse` to match the white pulse variable.

---

## 2. Will all the widgets work? (bindability matrix)
**Short answer:** No. As-is, the landing is **toast-bound mock only** (no live API wiring). Subpages have bind hints but no transport layer.

| Widget | State | Bindability | API/Transport Required | Constraint Note |
|--------|-------|-------------|------------------------|-----------------|
| **SoftDent Pulse** (white beam, $35,842) | Mock → Wireable | Read-only | `GET /api/softdent/ar`, `POST /api/softdent/refresh-period` | No write-back per constraint |
| **QuickBooks Beam** (orange, $48,100) | Mock → Wireable | Sync/Export | `POST /api/qb/sync`, `POST /api/qb/export` | empty = $0 allowed |
| **Tax Prism** (magenta, PLANS) | Mock → Wireable | Planning | `POST /api/tax/scenario` | Not posted to QB |
| **HAL Core Recon** | Mock → Wireable | Reconciliation | `POST /api/hal/reconciliation` | Shows INCOHERENT until beams converge |
| **Master SYNC** (Ctrl beam) | Mock → Wireable | Orchestration | `POST /api/master/sync` | Triggers multi-source refresh |
| **Period Wheel** | Mock → Wireable | State change | `POST /api/period/set` | Affects all downstream metrics |
| **Alignment Lasers** (red/green) | Mock → Wireable | Health check | `GET /api/import/readiness` | Red = critical gap (SoftDent ODBC/QB OAuth) |
| **SCRAM** | **Ornamental** | **NO-OP** | None exists | Safety theater; no halt API |
| **HAL Chat** (subpage) | Mock-transmission | Evaluate | `POST /api/hal/evaluate-query` | Local 32B model; needs backend ACK |
| **Film Strip Footer** (claims stubs) | Placeholder | Deep link | `GET /api/claims/stubs` | Links to Claims subpage |
| **Role Shutter** (OM / Front Desk) | Visual only | RBAC gate | Middleware + JWT scopes | Currently CSS-only; no enforcement |
| **RECONCILE button** | Mock → Wireable | Action | `POST /api/hal/recon` | Located in Ctrl panel per bindHints |

---

## 3. Gaps / honesty risks if shipped as-is
1. **Simulated currency authority:** Hardcoded values ($35,842, $48,100) appear as live ledger balances. Risk: Users act on fake financials.  
2. **SCRAM safety theater:** Red emergency button implies immediate process halt; without a kill-switch API this is deceptive (ethical liability).  
3. **Toast false-positives:** “Sync complete” toasts fire without API confirmation; operators may leave workstation thinking data is reconciled.  
4. **Laser placebo:** Red/green alignment lasers currently respond to no health check; they may show “green” while SoftDent ODBC is actually down.  
5. **Chat “LIVE” label:** HAL chat page displays “LIVE” bind hint but transmission is mock-only; user input is echoed or dropped without backend ACK.

---

## 4. Top improvements (ranked, max 5)
| Rank | Improvement | Impact | Effort | Theme Preservation |
|------|-------------|--------|--------|-------------------|
| 1 | **Simulation Watermark** — Overlay “SIMULATED DATA — APIs NOT WIRED” on landing until live endpoints connected. Prevents operational false confidence. | High | Low | Keep translucent; vacuum-safe |
| 2 | **SCRAM Truth-in-Labeling** — Disable button, change text to “SCRAM (DEMO — NO HALT API)”, add tooltip citing missing kill-switch backend. | High | Low | Maintains red warning color |
| 3 | **Wire Alignment Lasers** — Bind red/green crosshair to real `import-readiness` endpoint (SoftDent ODBC ping, QB OAuth token validity). | High | Medium | Uses existing CSS classes `.align` / `.align.bad` |
| 4 | **Responsive Beam Snapping** — Ensure `nr2-optical-beam-touch.js` recalculates `.beam-ray` rotation on resize/orientation change; current CSS transforms drift on tablets. | Medium | Medium | Pure JS math; no CSS theme change |
| 5 | **RBAC Functional Shutters** — Wire Role toggles to actually `disabled` DOM controls when Front Desk selected (gating Recon/Sync). | Medium | Medium | Uses existing `.role.on` classes |

---

## 5. Executive Summary (4 bullets)
- **Visual cohesion:** The lower + ctrl beam layout (nr2-12014) successfully densifies the optical bench without breaking the interferometer metaphor; colors and motion are production-ready.
- **Functional status:** Zero widgets are production-wired; all landing metrics are simulated. The system is a high-fidelity frontend shell awaiting API integration.
- **Critical blocker:** SCRAM button must be disabled or relabeled before any demo to avoid safety-theater liability; simulated currency values risk financial misrepresentation.
- **Next milestone:** Schema bump to `nr2-12015-honest-beams` upon completion of items 1–3 above (watermark, SCRAM honesty, laser health binding).

---

## 6. Approval checklist
- [x] **Data honesty:** Hardcoded $ values replaced with “—” / live claims+QB or “∅”
- [x] **SCRAM ethics:** Button disabled and annotated as ornamental pending kill-switch API
- [x] **Laser binding:** Alignment lasers reflect live import-readiness (SoftDent + QB connection status)
- [x] **Beam geometry:** External JS recalculates beam angles on viewport resize
- [x] **Chat truth:** HAL chat posts `/api/hal/evaluate-query`; badge STANDBY · LIVE GATE
- [x] **RBAC enforcement:** Role toggles disable mutate controls for Front Desk

**Applied wiring (2026-07-15):** `nr2-12015-honest-beams` · `/api/browser-session` · lasers · SoftDent claims · QB revenue · sync / refresh-period / tax / recon (recon may fail if pack archived) · HAL chat
