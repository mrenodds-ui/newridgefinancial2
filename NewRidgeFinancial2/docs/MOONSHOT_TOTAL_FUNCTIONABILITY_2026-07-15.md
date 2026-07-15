# Moonshot AI — Total Functionability Plan (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_total_functionability_consult.py`
**Base:** `https://127.0.0.1:8765`
**Inventory:** `.local_logs/moonshot_functionability_inventory.json`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> now show moonshot ai the program and what needs to be done to make this totally functionable

---

# Verdict (functionability %)
**23% functionable** — Landing optics are live-wired for core metrics (claims, revenue, sync, tax planning), but the critical reconciliation module is dead (500), the refresh-period endpoint hangs, HAL chat suffers from monetary dishonesty vs. live APIs, and **100% of Pages Hub subpages remain unbound shells displaying mock currency** ($35,842, $48,100) without live data or empty-state honesty.

## 0. Operator Intent (verbatim)
> now show moonshot ai the program and what needs to be done to make this totally functionable

## 1. What the program is today
**Build:** `nr2-11000-clean` / `nr2-12015-honest-beams` (optical landing)  
**Architecture:** Single-page optical interferometer bench with live-wired landing beams, plus a hub of skeletal HTML subpages (SoftDent, QB, Claims, AR, Taxes, Narratives, OM, Content) that contain only bind-hint comments and hardcoded mock values. Legacy Apex SPA (`hal-core`, `apex-core`, `app.js`) removed; CSP `script-src 'self'` enforced.

**Live Inventory:**
- **LIVE:** `GET /api/browser-session`, `GET /api/import-readiness`, `GET /api/softdent/claims-outstanding`, `GET /api/qb/monthly-revenue`, `POST /api/apex/sync/trigger`, `POST /api/apex/tax/calculate-planning`, `POST /api/hal/evaluate-query`
- **DEAD/BROKEN:** `POST /api/apex/hal/reconciliation` (500—missing `apex_reconciliation_pack`), `POST /api/apex/softdent/refresh-period` (timeout/hang), `nr2_contracts/` directory (imported by `apex_backend.py` but missing on disk)
- **SHELLS:** All `/nr2-optical-page-*.html` except HAL chat contain no JavaScript transport layer; they display static mock currency values that violate the `empty ≠ $0` constraint.

## 2. Bindability matrix (landing + pages)

| Surface | Widget/Flow | State | Live API | Notes |
|---------|-------------|-------|----------|-------|
| **Landing** | SoftDent Pulse (Claims AR) | **LIVE** | `GET /api/softdent/claims-outstanding` | Honest empty handling present |
| **Landing** | QuickBooks Beam (Revenue) | **LIVE** | `GET /api/qb/monthly-revenue` | Wired in `nr2-optical-beam-touch.js` |
| **Landing** | Tax Prism | **LIVE** | `POST /api/apex/tax/calculate-planning` | Returns planning scenarios, not posted to QB |
| **Landing** | Master SYNC | **LIVE** | `POST /api/apex/sync/trigger` | Triggers multi-source refresh |
| **Landing** | Alignment Lasers | **LIVE** | `GET /api/import-readiness` | Red/green crosshair bound to blocking gaps |
| **Landing** | Period Refresh | **PARTIAL** | `POST /api/apex/softdent/refresh-period` | **Times out without UI timeout handling** |
| **Landing** | HAL Reconcile Button | **DEAD** | `POST /api/apex/hal/reconciliation` | **500 error**—module missing |
| **Landing** | SCRAM | **DEAD** | *None* | Demoted to DEMO; no halt API exists |
| **Subpage** | SoftDent Bench | **SHELL** | *None bound* | Shows fake `$35,842` AR; no `nr2-optical-page-softdent.js` |
| **Subpage** | QB Bench | **SHELL** | *None bound* | Shows fake `$48,100`; no live P&L wiring |
| **Subpage** | Claims/ERA | **SHELL** | *None bound* | Kanban hints present; no `GET /api/claims/kanban` wired |
| **Subpage** | A/R Aging | **SHELL** | *None bound* | Static stale indicator; no `GET /api/softdent/ar-aging` |
| **Subpage** | Taxes | **SHELL** | *Partial* | Landing Tax Prism works, but subpage has no standalone wiring |
| **Subpage** | Narratives | **SHELL** | *None bound* | No `POST /api/hal/narrative-draft` wiring |
| **Subpage** | Office Manager | **SHELL** | *None bound* | RBAC visual only; no ops API bound |
| **Subpage** | Content | **SHELL** | *None bound* | Static document list |
| **Subpage** | HAL Chat | **LIVE** | `POST /api/hal/evaluate-query` | **Dishonesty risk**: Answers may contradict live Claims API |

## 3. Blockers to totally functionable
1. **Backend Contract Incoherence:** `apex_backend.py` imports `nr2_contracts` (directory missing), creating import-time crashes on certain code paths and preventing module restoration.
2. **Reconciliation Module Absence:** `apex_reconciliation_pack` missing → 500 on recon endpoint. Button on landing promises "COHERENT" state but cannot compute.
3. **Refresh-Period Hang:** `POST /api/apex/softdent/refresh-period` timeouts leave UI in perpetual "syncing" state without error surface.
4. **Monetary Dishonesty in HAL:** `POST /api/hal/evaluate-query` can return "0" or invented figures while `GET /api/softdent/claims-outstanding` shows real $35k+ balances (empty≠$0 violation via hallucination).
5. **Subpage Shells:** All financial subpages display hardcoded mock values ($35,842, $48,100) without API binding, creating operational false confidence.
6. **Stale Data Non-Blocking:** SoftDent AR can be stale (critical soft gap) while alignment lasers show green because `/api/import-readiness` does not treat AR staleness as blocking.

## 4. Sequenced plan (P0 blocker / P1 must / P2 should / P3 polish) — concrete tasks

### P0 — Blockers (Ship-stop)
1. **Backend Import Hygiene**  
   - File: `apex_backend.py`  
   - Action: Remove `import nr2_contracts` or create `nr2_contracts/__init__.py` with minimal coherent stubs so the process boots without ImportError.
2. **Kill or Cure Reconciliation**  
   - Route: `POST /api/apex/hal/reconciliation`  
   - Action: **Either** restore `apex_reconciliation_pack` module with coherent SoftDent↔QB reconciliation logic, **or** return `503 UNAVAILABLE` with JSON `{"available": false, "reason": "Module removed in clean-slate cutover"}` and disable the landing button.
3. **Fix Refresh-Period Timeout**  
   - Route: `POST /api/apex/softdent/refresh-period`  
   - Action: Add server-side timeout (30s max) with partial progress return; client-side add `AbortController` timeout in `nr2-optical-beam-touch.js` (10s UI timeout → "Refresh stalled—check SoftDent ODBC").
4. **HAL Money Honesty Gate**  
   - Route: `POST /api/hal/evaluate-query`  
   - Action: Pre-flight check against `/api/import-readiness`; if `softdent` stale or `claims-outstanding` has data, inject context: "Live claims: $X. If I say 0, that is hallucination." Block money answers when `blocking` array non-empty.

### P1 — Must (Functionability floor)
5. **SoftDent Subpage Wiring**  
   - File: `nr2-optical-page-softdent.html` + new `nr2-optical-page-softdent.js`  
   - Bind: `GET /api/softdent/claims-outstanding`, `GET /api/softdent/ar-aging` (new or existing), `POST /api/apex/softdent/refresh-period`  
   - Requirement: Display real AR buckets or "STALE / EMPTY" vacuum state; never show `$35,842` mock.
6. **QuickBooks Subpage Wiring**  
   - File: `nr2-optical-page-quickbooks.html` + new `nr2-optical-page-quickbooks.js`  
   - Bind: `GET /api/qb/monthly-revenue`, `POST /api/qb/payroll-ap-export` (if exists) or mark UNAVAILABLE.
7. **Claims Kanban Wiring**  
   - File: `nr2-optical-page-claims.html` + new `nr2-optical-page-claims.js`  
   - Bind: `GET /api/softdent/claims-outstanding` (filtered by status), `POST /api/era/ingest-835` (if exists).
8. **AR Aging Deep Page**  
   - File: `nr2-optical-page-ar.html` + new JS  
   - Bind: `GET /api/softdent/ar-aging` (0-30, 31-60, 61-90, 90+) with staleness watermark.

### P2 — Should (Safety & completeness)
9. **Import-Readiness Blocking Logic**  
   - Route: `GET /api/import-readiness`  
   - Action: Add `softdent_ar_stale_hours` threshold; if >24h, add to `blocking` array so alignment lasers turn red.
10. **Narratives Draft Wiring**  
    - File: `nr2-optical-page-narratives.html`  
    - Bind: `POST /api/hal/narrative-draft` (new) or mark UNAVAILABLE until implemented.
11. **OM/Content Availability**  
    - Mark `nr2-optical-page-office-manager.html` and `nr2-optical-page-content.html` as `UNAVAILABLE — RBAC v2 pending` if no backend exists; remove mock action buttons.

### P3 — Polish (Coherence)
12. **Reconciliation Restoration (Optional)**  
    - If business requires: Rebuild `apex_reconciliation_pack` using `nr2_contracts` schema (once P0.1 fixed) to compute SoftDent↔QB variance.
13. **Schema Stamp Advance**  
    - Advance to `nr2-12016-honest-subpages` once P0-P1 complete and all subpages bind to real routes.
14. **Film Strip Claims Footer**  
    - Wire landing film strip to `GET /api/claims/stubs` for recent claim IDs.

## 5. Honesty risks still open
- **HAL Hallucination Gap:** Even after gating, local 32B model may invent tax figures not present in `/api/qb/monthly-revenue`. Money answers must include disclaimer: "HAL estimates—verify against live beams."
- **Stale AR Green Laser:** If `import-readiness` does not treat AR staleness as blocking, operators see green alignment while working with 48h-old SoftDent data (critical soft gap).
- **Timeout Silence:** If `refresh-period` hangs and UI lacks timeout, operator assumes sync succeeded when it did not.
- **Subpage Deep Linking:** Users can bookmark `/nr2-optical-page-softdent.html` and see mock $35k, acting on fake financials before P1 wiring completes.

## 6. Executive Summary (5 bullets)
- **Landing is 60% live** (claims, revenue, sync, tax, health), but **reconciliation is dead (500)** and **period refresh hangs**, blocking the full SoftDent↔QB loop.
- **All subpages are dangerous shells** displaying hardcoded mock currency ($35k–$48k) without API binding, violating `empty ≠ $0` and creating liability.
- **Backend incoherence:** `apex_backend.py` imports a missing `nr2_contracts` package; immediate fix required to prevent runtime import errors.
- **HAL chat suffers monetary dishonesty**—it can claim $0 claims while live API shows $35k+; requires context injection from `import-readiness` + claims API.
- **Path to 100%:** P0 fixes (backend imports, recon 503/restore, timeout handling), then P1 wiring of all subpages to real routes (`/api/softdent/*`, `/api/qb/*`), ensuring every dollar displayed is live or explicitly "STALE/EMPTY."

## 7. Approval checklist (checkboxes for operator)
- [ ] **P0.1** Remove `nr2_contracts` import from `apex_backend.py` or create the directory with valid modules
- [ ] **P0.2** Decide: Restore `apex_reconciliation_pack` or return 503 UNAVAILABLE for recon endpoint (no fake "COHERENT" state)
- [ ] **P0.3** Add 10s UI timeout + server-side 30s cap to `POST /api/apex/softdent/refresh-period`
- [ ] **P0.4** Gate HAL money answers with live claims/revenue data context (prevent $0 hallucination)
- [ ] **P1.1** Create `nr2-optical-page-softdent.js` binding to live AR/Claims APIs (remove mock $35,842)
- [ ] **P1.2** Create `nr2-optical-page-quickbooks.js` binding to live revenue/export APIs (remove mock $48,100)
- [ ] **P1.3** Wire Claims subpage to live claims feed or mark UNAVAILABLE
- [ ] **P2.1** Modify `import-readiness` to treat SoftDent AR staleness >24h as blocking (red laser)
- [ ] **Schema** Advance build stamp to `nr2-12016-honest-subpages` upon P0+P1 completion
