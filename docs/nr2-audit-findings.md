# NR2 dual-model audit findings (July 2026)

Consolidated from 12 sub-slice eval reports (`eval_section*_120b_70b_report.md`, gitignored) and follow-up code review. Raw model output is not committed; this file is the staff/engineering traceability summary.

## Status legend

| Status | Meaning |
|--------|---------|
| **Fixed** | Implemented and covered by tests/validators |
| **False positive** | Eval finding did not match code or was truncated context |
| **By design** | Intentional behavior; tests document the choice |
| **Open** | Not implemented or needs manual verification |

---

## Fixed

### Import pipeline and crashes
- Safe `source_mtime` when bridge/DB paths missing (`import_direct_pipeline.py`)
- Null guards in `buildSoftdentDashboard` / `buildFinancialDashboard` (`import-loader.js`)
- `toneClass` string coercion in page canvas panels
- JSON cache writes include `{rows, sourceFile, modifiedAt, sha256}`; manifest saved after bundle load
- Pipeline failures logged; `directPipelineError` on bundle
- Bridge fallback validation with `readSource: bridge-fallback` and `bridgeValidation` (`practice_source_access.py`)
- Period-sync upsert `mergeLog` + sync warnings (`softdent_dashboard_period_sync.py`, `import_sync.py`)
- Direct-first prefers upstream direct rows over fresher cache (`import_loader.py`)

### Collections and widget honesty (Design A)
- Pending collections → widget state `pending`, value `—`, status **DEGRADED** (not SUCCESS)
- `buildContractWidget` no longer upgrades FAILED → DEGRADED when fallback is SUCCESS
- Daysheet prod>0 + collections=0 not treated as reported zero (`softdent_dashboard_period_sync.py`)
- `buildFinancialDataQuality` exposes `overallPass`; month-end close and HAL commit validation enforce it
- Cross-source overview does not borrow SoftDent production for QuickBooks revenue

### Staff-facing canvas and diagnostics
- Import notices on Financial, SoftDent, QuickBooks, A/R, Claims, Documents, Library, Office Manager pages
- Bridge fallback downgrades `softdent.dashboard` diagnostics to **partial**
- Master chart `dataReady` + `formatForHal(feed)` includes **Ready now** per widget
- Financial data-quality tile uses `overallPass` and pending/missing flags (not green-on-import alone)

### Eval infrastructure
- 12 sub-slice focus bundles and dual-model batch runner (`scripts/run_nr2_dual_model_micro_eval.ps1`)
- Eval artifacts gitignored (`eval_section*.md`, `235b_*`)

---

## False positives

| Finding | Why |
|---------|-----|
| Missing `isPriorCalendarMonth` | Function exists in `import-loader.js` (~L385); focus bundle started too late |
| Kanban syntax error (2c1) | Truncated eval bundle; `canvasKanbanLanes` is valid |
| Empty 120B draft (2c2) | Treat 2c2 narrative findings as unverified |

---

## By design

| Behavior | Rationale |
|----------|-----------|
| `collectionsPending` → `healthy: true` in collection health | Pending = incomplete export, not hard failure; widget contract still degrades |
| HAL info (not warning) for pending collections in commit validation | Production can load before collections export |

---

## Open / manual follow-up

| Item | Notes |
|------|-------|
| Narratives canvas notice | Local draft workflow; lower traffic than claims/A/R |
| Taxes canvas notice | Tax engine has separate boundary; book data optional |
| Page-chrome / HAL page null guards (2c2) | Quick review passed; no crash paths found in `page-chrome.js` |
| Push + CI | Run after commits; workflow `.github/workflows/validate-nr2.yml` |

---

## Verification commands

From `NewRidgeFinancial2/`:

```powershell
python -m unittest discover -s . -p "test_*.py"
node test_import_loader_accounting.mjs
node test_import_diagnostics_node.mjs
node test_month_end_close.mjs
node validate-hal.mjs
node validate-pages.mjs
```

---

## Commit trail (main, July 2026)

1. `97ad3fe` — Widget/import honesty from dual-model audit (eval infra + core fixes)
2. `75184ca` — Import notices and quality gates (Financial/SoftDent/bridge diagnostics)
3. `f309473` — A/R notices, master chart readiness in HAL answers, direct-first preference
4. `7223fe6` — Claims notices and `.env.example` import policy comments
5. `cc9c22a` — Documents/Library/Office Manager notices + this doc
