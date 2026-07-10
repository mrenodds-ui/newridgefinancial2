# Moonshot AI — Desktop Icon, HAL↔Widgets, Sync Verify, S-Corp Tax + EBITDA + Returns (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10290  
**Script:** `scripts/run_moonshot_desktop_hal_tax_ebitda_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> now ask moonshot ai how to make a desktop icon, hook up hal to all widgets, sync data and verify they work with softdent and quickbooks, also I need high tech programming to calculate taxes for the federal and kanas for a s-corp as well as calulating EBITDA.  I need a place to download previous tax returns for EBITDA, too.

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only)

> *"now ask moonshot ai how to make a desktop icon, hook up hal to all widgets, sync data and verify they work with softdent and quickbooks, also I need high tech programming to calculate taxes for the federal and kanas for a s-corp as well as calulating EBITDA.  I need a place to download previous tax returns for EBITDA, too."*

**Interpretation:**  
- **(A)** Create a Windows desktop shortcut (.lnk) that launches NR2-Apex (hal-10290) via the existing `StartProgram.bat`.  
- **(B)** Wire HAL neural core (`/api/hal/evaluate-query`) into every Apex widget instrument (hbar/donut/bullet/waterfall/scrubber) so each can "Ask HAL" with context.  
- **(C)** Harden the SoftDent + QuickBooks import sync (document inbox → HAL) and provide a verification checklist proving end-to-end data flow.  
- **(D)** Extend the existing `tax_engine.py` (S-corp federal + Kansas "kanas" planning) with high-touch Apex UI integration—distinguishing import-backed book numbers vs. planning estimates vs. CPA-filed returns.  
- **(E)** Build EBITDA calculation (practice-normalized) from QB/SoftDent imports with owner add-backs, surfaced in a dedicated instrument.  
- **(F)** Add a local document repository for previous tax returns (upload/list/download) to provide historical context for EBITDA trends.

**Status:** CONSULT ONLY. No files will be modified until operator validates T0 and explicitly approves proceed at each gate.

---

## 1. Desktop Icon (Windows launch)

**Goal:** Double-click shortcut → `StartProgram.bat` → PowerShell → https://127.0.0.1:8765/

### Concrete Steps (Manual)
1. Right-click on `StartProgram.bat` (repo root) → **Send to → Desktop (create shortcut)**.
2. Right-click the new shortcut → **Properties**:
   - *Target:* `C:\Path\To\NewRidgeFinancial2\StartProgram.bat` (adjust to your repo root).
   - *Start in:* `C:\Path\To\NewRidgeFinancial2` (critical so PowerShell finds `scripts\`).
   - *Icon:* Browse to `NewRidgeFinancial2\site\favicon.ico` (or leave default).
   - *Run:* Normal window.
3. **Advanced** (optional): Check "Run as administrator" only if your PowerShell execution policy requires it; NR2 itself does not need elevation for localhost:8765.

### Optional Deliverable (PowerShell)
```powershell
# CONSULT ONLY — DO NOT RUN until operator approves T1
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$Home\Desktop\NewRidge Financial 2.0.lnk")
$Shortcut.TargetPath = "C:\Path\To\NewRidgeFinancial2\StartProgram.bat"
$Shortcut.WorkingDirectory = "C:\Path\To\NewRidgeFinancial2"
$Shortcut.IconLocation = "C:\Path\To\NewRidgeFinancial2\site\favicon.ico"
$Shortcut.Description = "Launch NR2-Apex (hal-10290)"
$Shortcut.Save()
```
**MUST:** Update paths to actual repo root.  
**NICE:** Pin to taskbar after first launch.

---

## 2. Hook HAL to All Widgets

**Architecture:** Extend `apex-hal-bridge` with a per-widget "Ask HAL" affordance that POSTs a context packet to `/api/hal/evaluate-query`.

### Widget Coverage (hal-10290 Inventory)
| Instrument | Page(s) | HAL Action | Context Payload |
|------------|---------|------------|-----------------|
| `provider-production` (hbar) | Financial, SoftDent | explain_variance | `{provider_id, production_amt, period, prior_period_amt}` |
| `expense-categories` (hbar) | QuickBooks | trend_analysis | `{account_name, ytd_amt, budget_amt (null if none)}` |
| `payer-mix` (donut) | Financial, Office Mgr | composition_alert | `{payer_type, percentage, threshold_breach}` |
| `collection-efficiency` (bullet) | Financial, A/R | metric_interpretation | `{actual_pct, target_range, aging_bucket}` |
| `insurance-vs-patient` (stacked-bar) | Financial, Claims | reconciliation_check | `{insurance_amt, patient_amt, outstanding_ar}` |
| `ar-aging-flow` (waterfall) | A/R | walk_explanation | `{bucket_name, amount, is_adjustment}` |
| `period-horizon` (scrubber) | Financial, Taxes | forecast_query | `{selected_period, book_net_income (imported)}` |

### Contract Schema (per widget)
```json
{
  "widget_id": "string",
  "page_route": "financial|softdent|quickbooks|ar|taxes|office-mgr",
  "ask_hal_action": "explain_variance|trend_analysis|composition_alert|metric_interpretation|reconciliation_check|walk_explanation|forecast_query",
  "context": {
    "data_source": "softdent|quickbooks|manual_input",
    "import_timestamp": "ISO8601|null",
    "metrics": {
      "label": "string",
      "value": "number|null",
      "unit": "currency|percent|count"
    },
    "threshold_state": "green|amber|red|null"
  },
  "operator_question": "string (free text from widget input)"
}
```

**Implementation:** Add `ApexHalBridge.attachWidget(widgetEl, pageRoute)` in `apex-core.js` that injects a small "🜂 Ask HAL" button on each instrument card. Click → populates context from `data-apex-widget-id` and opens HAL drawer pre-seeded.

---

## 3. Sync SoftDent + QuickBooks + Verification

**Sync Path (Existing):**  
`Sync-HAL-Imports.ps1` (or Direct-First mode) → `app_data/nr2/document_inbox/{softdent,quickbooks}/` → `/api/sync-documents` → `import_loader.py` → Apex widgets.

### Verification Checklist

**SoftDent Sections (Source of Truth)**
- [ ] **Export Files Present:** `SD_Production_*.csv`, `SD_AR_Aging_*.csv`, `SD_Payer_Mix_*.csv` in inbox (or direct-first path).
- [ ] **Parse Integrity:** `import_loader.py` reads provider names without Unicode errors; production dollars parse as float (empty/null accepted, never 0.01 demos).
- [ ] **HAL Bridge:** `/api/apex/widgets/softdent` returns 200 with `instruments` array; `last_import_iso` within 24h of actual export time.
- [ ] **Apex Smoke:** Financial page shows "Last import load: [timestamp]" footer; no amber "Stale imports" banner.

**QuickBooks Sections**
- [ ] **Export Files Present:** `QB_ProfitLoss_*.csv` (or `.iif`), `QB_ChartOfAccounts_*.csv` in inbox.
- [ ] **Net Income Line:** `tax_engine.py` can extract `Ordinary Business Income` or user maps account "Net Income" to bridge.
- [ ] **Expense Breakdown:** `expense-categories` hbar renders accounts >$0; empty accounts omitted (not zero-filled).
- [ ] **Apex Smoke:** QuickBooks page loads without red "Import error" banner; waterfall (if used) shows buckets labeled "Current" and "30-60" etc.

**End-to-End Proof**
1. Run `Sync-HAL-Imports.ps1` manually; confirm exit code 0.
2. Click Apex **Sync** button (triggers `/api/sync-documents`).
3. Verify `import-manifest.json` updated with `lastSyncEpoch`.
4. Open HAL Command Center → query "What is the latest SoftDent production?" → HAL cites correct import timestamp and provider totals (or states "imports empty" if none).

**Failure Modes**
- **Missing Export:** Upstream SoftDent/QB export not run; HAL shows empty state (honest).
- **Stale Data:** `last_import_iso` > 48h; Apex shows amber banner.
- **Parse Mismatch:** Column headers changed; `import_loader.py` logs warning to `.local_logs/nr2/import_warnings.log`.

---

## 4. Federal + Kansas S-Corp Tax Programming (high-tech)

**Extend:** `NewRidgeFinancial2/tax_engine.py` (existing planning engine) + new Apex endpoint.

### High-Touch Features
1. **Live Bridge:** `/api/tax/calculate-planning` accepts:
   - `book_net_income` (auto-filled from QB import or manual override).
   - `modeled_officer_w2` (defaulted via `default_modeled_w2()` or user override).
   - `ebitda_add_backs` (from §179, depreciation, owner discretionary).
   - `tax_year` (default 2025).

2. **Kansas Specifics:**  
   - Rate: 5.7% (from existing `KANSAS_PLANNING_RATE`).  
   - Pass-through entity tax (PTET) checkbox (Kansas SB 15 elective) — **SHOULD** phase if Kansas enacts PTE tax for S-corps (currently planning only).

3. **Federal Specifics:**  
   - Rate: 32% (existing `FEDERAL_PLANNING_RATE`).  
   - QBI deduction estimation (20% of qualified business income) — **NICE** to add as toggle.

4. **UI Integration (Taxes Page):**
   - Use existing `period-horizon` scrubber to select tax year/quarter.
   - Display:
     - Book Income (imported, labeled "QB Import").
     - Adjusted Ordinary Income (after bridge).
     - Federal Tax (planning).
     - Kansas Tax (planning).
     - Quarterly Estimates (Q1-Q4 breakdown).
   - **Labeling:** Large banner: **"TAX PLANNING ESTIMATES — REQUIRES CPA REVIEW BEFORE FILING"**.

### Honesty Rules
- Never display "Tax Due" as a final number; always prefix "Planning Estimate".
- If QB import missing, disable auto-calc; show "Import QuickBooks data to enable tax estimate".

---

## 5. EBITDA Calculation

**Formula (Practice/Owner-Normalized):**
```
EBITDA = 
  QB Net Income (Ordinary Business Income)
  + Interest Expense (from QB chart of accounts)
  + Taxes (federal income tax paid by entity — usually $0 for S-corp pass-through, but state PTE tax if elected)
  + Depreciation & Amortization (from QB or SoftDent equipment schedules)
  + Owner Add-Backs (officer salary above market rate, discretionary personal expenses run through practice)
```

**Implementation:**
- **Source:** `tax_engine.py` already accepts `ebitda_add_backs`.
- **Widget:** New `ebitda-waterfall` on Financial page (type: waterfall) showing:
  1. Start: Net Income (QB)
  2. Add: Depreciation (QB or manual)
  3. Add: Interest (QB)
  4. Add: Owner Salary Adjustment (SoftDent payroll vs. market rate)
  5. End: Owner-Normalized EBITDA
- **Input Method:** "Adjustments" panel next to widget where operator enters add-backs (stored in `local_store.py`, not posted to QB).

**Honesty:**
- If Depreciation not found in QB import, field shows "N/A — enter manually".
- EBITDA labeled as "Management Calculation — Not GAAP Financial Statements".

---

## 6. Previous Tax Returns Download Place

**Location:** Extend Documents page with a **Tax Library** section.

**Storage Layout (Local Filesystem):**
```
app_data/nr2/document_library/
  tax_returns/
    2024/
      federal/
        Form_1120S_2024.pdf
        K-1_2024.pdf
      kansas/
        Form_K-120S_2024.pdf
    2023/
      federal/
        ...
```

**API Contract:**
- `GET /api/documents/tax-returns` → list years and jurisdictions.
- `GET /api/documents/tax-returns/2024/federal/Form_1120S_2024.pdf` → download (stream from local disk).
- `POST /api/documents/tax-returns/upload` (operator-only) → save to appropriate year/jurisdiction folder.

**UI (Apex):**
- New tab "Tax Library" on Documents page.
- Table: Year | Jurisdiction | Filed Date (manual entry) | Download icon.
- Upload button (local file picker) → moves into structured folder.

**EBITDA Context:**  
HAL can reference these when asked "Compare 2024 vs 2023 EBITDA factors" — HAL reads the PDF text (if OCR'd) or uses stored metadata; no invented figures.

---

## 7. Moonshot Spec Deliverables (paste-ready, CONSULT ONLY)

**File A: `scripts/Create-DesktopShortcut.ps1`**
```powershell
# CONSULT ONLY — DO NOT APPLY until operator approves
param([string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path)
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\NR2 Apex (hal-10290).lnk")
$Shortcut.TargetPath = "$RepoRoot\StartProgram.bat"
$Shortcut.WorkingDirectory = $RepoRoot
$Shortcut.IconLocation = "$RepoRoot\site\favicon.ico,0"
$Shortcut.Description = "Launch NewRidge Financial 2.0 (Apex hal-10290)"
$Shortcut.Save()
Write-Host "Shortcut created on Desktop" -ForegroundColor Green
```

**File B: `apex-hal-widget-bridge.js` (snippet to inject)**
```javascript
// CONSULT ONLY — extends apex-core.js
const ApexHalWidget = {
  attach(instrumentEl, {page, widgetId, dataSource}) {
    const btn = document.createElement('button');
    btn.className = 'apex-hal-ask-btn';
    btn.textContent = '🜂 Ask HAL';
    btn.onclick = () => {
      const payload = {
        widget_id: widgetId,
        page_route: page,
        ask_hal_action: instrumentEl.dataset.halAction || 'explain_variance',
        context: {
          data_source: dataSource,
          import_timestamp: window.ApexApp?.lastImportIso || null,
          metrics: JSON.parse(instrumentEl.dataset.metrics || '{}'),
          threshold_state: instrumentEl.dataset.threshold || null
        },
        operator_question: '' // populated from prompt
      };
      window.ApexHalBridge.openDrawer(payload);
    };
    instrumentEl.querySelector('.apex-card-header').appendChild(btn);
  }
};
```

**File C: `tax_engine.py` extension (endpoint)**
```python
# CONSULT ONLY — add to NewRidgeFinancial2/tax_engine.py
from bottle import route, request, jsonify

@route('/api/tax/calculate-planning', method='POST')
def api_tax_calculate_planning():
    """
    High-tech S-corp tax planning endpoint.
    Expects JSON: {book_net_income: float|-null, modeled_officer_w2: int|null, ebitda_add_backs: float, tax_year: int}
    Returns: {federal_planning, kansas_planning, quarterly_estimates, disclaimer}
    """
    data = request.json
    result = build_tax_plan(
        book_net_income=data.get('book_net_income'),
        modeled_officer_w2=data.get('modeled_officer_w2'),
        ebitda_add_backs=data.get('ebitda_add_backs', 0.0),
        tax_year=data.get('tax_year', 2025)
    )
    result['disclaimer'] = "PLANNING ONLY — REQUIRES CPA REVIEW"
    return jsonify(result)
```

**File D: `app_data/nr2/document_library/tax_returns/README.txt`**
```
CONSULT ONLY — Directory structure for prior tax returns.
Place filed returns here manually:
  YYYY/federal/Form_1120S_YYYY.pdf
  YYYY/kansas/Form_K-120S_YYYY.pdf
Do not commit actual returns to git (add to .gitignore).
```

---

## 8. Implementation Phases (T0 validate → Tn) + Validation Gate

| Phase | Scope | Rank | Validation Gate (Operator must approve to proceed) |
|-------|-------|------|---------------------------------------------------|
| **T0** | Baseline audit of hal-10290 | MUST | Confirm current build runs; SoftDent/QB imports load (even if empty); no console errors in browser F12. |
| **T1** | Desktop shortcut (`Create-DesktopShortcut.ps1`) | MUST | Operator runs script; double-clicks new icon; NR2 launches to 127.0.0.1:8765 without error. |
| **T2** | HAL widget hooks (5 instrument types) | MUST | On Financial page, click "Ask HAL" on Production hbar; HAL drawer opens with context packet visible in Network tab; HAL responds with variance explanation (or "insufficient data"). |
| **T3** | Sync verification hardening | MUST | Run `Sync-HAL-Imports.ps1`; verify checklist (Section 3) passes; Apex shows green "Imports fresh" banner. |
| **T4** | Tax engine Apex integration + EBITDA widget | MUST | Taxes page shows scrubber; selecting Q1 2025 populates planning estimate; EBITDA waterfall calculates from QB net income + manual add-backs; labels show "Planning Only". |
| **T5** | Tax returns repository | SHOULD | Documents page shows "Tax Library"; operator manually copies one PDF to `2024/federal/`; appears in list; download succeeds. |

**Stop Criteria:**  
If T0 fails (imports broken), do not proceed to T3. Fix upstream first.  
If T4 produces tax numbers without CPA disclaimer, rollback immediately.

---

## 9. Risks, CPA Disclaimer & Rollback

**Financial Risk:**  
`tax_engine.py` uses **planning rates** (32% federal, 5.7% Kansas). Actual filing requires individual tax brackets, QBI phase-outs, basis limitations, and Kansas PTET elections. **Never use NR2 tax outputs for filing without CPA review.**

**Data Integrity Risk:**  
EBITDA add-backs are manually entered; operator could inflate practice value. HAL must flag when add-backs exceed 20% of net income (amber alert).

**Rollback Plan:**
- **T1 (Shortcut):** Delete `.lnk` from Desktop; revert to `StartProgram.bat` manual launch.
- **T2 (HAL Hooks):** Remove `ApexHalWidget.attach` calls from `apex-core.js`; widgets revert to static display.
- **T3 (Sync):** Disable `Sync-HAL-Imports.ps1` scheduled task; return to manual file drops.
- **T4 (Tax/EBITDA):** Set `TAX_PLANNING_UI_ENABLED=0` in `.env`; Taxes page hides calculator, shows "Contact CPA" placeholder.
- **T5 (Tax Returns):** Remove `tax_returns/` folder from document library; API routes return 404 (graceful degradation).

**Compliance Note:**  
All tax return PDFs remain local in `app_data/`; no OAuth to cloud tax prep services ( Drake, Lacerte, etc.) is implemented, per hard constraints.

**Awaiting operator approval to proceed with T0 validation.**