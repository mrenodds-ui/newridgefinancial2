# Moonshot NR2-Apex — Proceed Addendum (Mods 1–6 Addressed)

**Date:** 2026-07-10  
**Build:** `hal-10200`  
**Epoch:** `nr2-apex`  
**Operator:** CONDITIONAL APPROVE → **proceed**  
**Plan:** `MOONSHOT_COMPLETE_REDESIGN_PLAN_2026-07-10.md`  
**Validation:** `MOONSHOT_REDESIGN_PLAN_VALIDATION_2026-07-10.md`

---

## Definition of “complete” (Mod 6)

For this proceed pass, **complete** means:

1. **Wipe** — active mockup / moonshot / live-wire CSS+JS removed from the site load path into `site/_retired_pre_apex/` (not permanent delete).
2. **Apex foundations** — `apex-tokens.css`, `apex-core.js`, `apex-chart-widget.js`, Apex `index.html` shell with nav for all 11 pages.
3. **Financial page with real data** — `/api/apex/widgets/financial` maps **existing** NR2 data (`financial_reports.build_financial_reports`, `import_loader.load_import_bundle`) into KPI/chart widgets. Missing imports show honest empty states; **dollar amounts are never invented**.
4. **Phased migration of remaining pages** — taxes, softdent, quickbooks, ar, claims, narratives, documents, library, office-manager, hal return `status: "awaiting-migration"` widgets until P4.

This is **not** “100% of 11 pages fully coded on day one.” Foundations + one live financial page + explicit P4 migration is the agreed complete scope for P0/P1/P3 proceed.

---

## Mods 1–6 from validation — how addressed

| Mod | Validation ask | How addressed in proceed |
|-----|----------------|--------------------------|
| **1. Strengthen wipe audit** | No “if present” soft language; move ALL listed mockup/moonshot/live-wire assets out of load path | Listed CSS/JS **moved** to `site/_retired_pre_apex/` (and `deferred-live-wire/` / `data/` subfolders). Apex `index.html` does **not** load old mockup CSS/JS or `app.js`. Backup at `app_data/nr2-backup-P0/site-pre-apex/`. |
| **2. Clarify backend scope** | Not dummy-only; reuse NR2 data layer | `apex_backend.py` wraps `financial_reports` + `import_loader`. Dummy random production numbers from the consult plan are **not** used. |
| **3. Remove sensitive data** | Strip API key **values** from report headers | Docs retain key **name** only: `OPENROUTER_API_KEY`. No secret values in addendum or scrubbed headers. |
| **4. One complete page** | Financial with real data binding | Financial widgets: production, collections, A/R outstanding, A/R aging chart, claims counts, treatment/case rows — from import cache / reports, with empty states when absent. |
| **5. Complete rollback** | Full restore script from `nr2-backup-P0/` | `scripts/Rollback-Apex-P0.ps1` restores `site/` from `app_data/nr2-backup-P0/site-pre-apex/` and keeps a safety copy of the Apex tree. |
| **6. Define “complete”** | Foundations + migration vs 100% coded | Defined above: wipe + foundations + financial real data + phased P4 for remaining pages. |

---

## Backend contract

- **Module:** `NewRidgeFinancial2/apex_backend.py`
- **Registration:** `register_apex_routes(app, _json_response)` called from `nr2_http_server.py` immediately after `/api/financial-reports`.
- **Routes:**
  - `GET /api/apex/widgets/<page_id>`
  - `POST /api/apex/print/<packet_type>` (and `POST /api/apex/print/`)
  - `POST /api/apex/sync/trigger`
  - `GET /api/apex/hal/status`
- **Auth:** Frontend reads `sessionToken` from `/api/app-info` and sends `X-NR2-Session-Token` (same as `desktop-bridge.js`). `/api/apex/widgets` is listed under financial-read prefixes for audit/readiness gating.
- **Existing APIs preserved:** `/api/financial-reports`, import bundle, and other NR2 routes remain intact.

---

## Strengthened wipe (active load path)

**Moved to** `NewRidgeFinancial2/site/_retired_pre_apex/`:

- `nr2-moonshot-mockup-theme.css`
- `hal-mockup-overrides.css`
- `nr2-mockup-page-vocabulary.css`
- `nr2-moonshot-glow.css`
- `nr2-mission-control-glass.css`
- `nr2-mission-control-extreme.css`
- `workstation-moonshot-bridge.css`
- `nr2-moonshot-mockup-chrome.js`
- `moonshot-page-registry.js`
- `moonshot-kimi-wire-hal.js`
- `data/mockup-elite-pages.js`
- `deferred-live-wire/moonshot-layout-engine.js`
- `deferred-live-wire/moonshot-page-layouts.js`
- `index.pre-apex.html` (copy of pre-wipe `index.html`)

**Not moved (intentionally):** `desktop-bridge.js`, `app.js`, and other legacy modules may remain on disk unused. Critical rule: Apex `index.html` must not load mockup CSS/JS.

**Not done (operator constraint):** No destructive `Stop-Process` on all Python/Chrome. No deletion of `app_data` practice data.

---

## Rollback

```powershell
powershell -ExecutionPolicy Bypass -File NewRidgeFinancial2\scripts\Rollback-Apex-P0.ps1
```

Restores `site/` from `app_data/nr2-backup-P0/site-pre-apex/`. Then restart NR2 and hard-refresh the browser (Cache-Control no-store is set on Apex index).

---

## Build stamp

```json
{
  "BUILD_ID": "hal-10200",
  "REQUIRED_EPOCH": "nr2-apex",
  "staffRenderMode": "apex",
  "liveWirePages": []
}
```

Written to `NewRidgeFinancial2/nr2-build.json` and `site/nr2-build.json`.

---

## Next (P4+)

Migrate remaining 10 pages to real Apex widgets in sequence: taxes → softdent → quickbooks → ar → claims → narratives → documents → library → office-manager → hal. Keep empty/honest states until each page’s data adapter is wired.
