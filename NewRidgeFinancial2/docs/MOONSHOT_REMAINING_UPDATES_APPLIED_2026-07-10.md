# Moonshot remaining updates — applied

**Date:** 2026-07-10  
**Build:** **hal-10280** (prior pack: hal-10270)

## Scope (deferred items from flash / starship / widget consults)

| Item | Source | Status |
|------|--------|--------|
| Perspective grid floor | Flashy presentation | Applied — `.apex-grid-floor` + CSS; removed under `prefers-reduced-motion` |
| Fuller page-change glitch | Flashy presentation | Applied — `ApexMotion.flashStage()` on nav |
| Bottom OPS ticker | Starship bridge | Applied — `#apex-ticker-bottom` + dual-track `apex-ticker.js` |
| Local QB categorize (V4) | Widget ideas | Applied — `build_categorize_assist` + `type: "categorize"` UI |
| Categorize empty on live import | Operator follow-up | **Fixed at 10280** — retargeted to `expenseCategories` (Category/Amount/Scope); leaf labels; boundary-safe keywords |

## 10280 categorize fix

Live QB import shape uses `expenseCategories` (8 YTD rows), not memo transaction lines. Period-total `expenses` rows have no Memo/Description.

- Prefer `expenseCategories`; skip period-total rollups
- Display leaf label from hierarchical Category paths (`… · Payroll Expenses`)
- Keyword rules with short-key boundaries (`lab` ∉ `Labor`)
- Amounts only from import; never posts to QuickBooks
- Honest empty when no category/memo lines exist

## Files touched

- `site/index.html` — grid floor, bottom ticker, build assets
- `site/apex-ticker.js` — top + bottom tracks
- `site/apex-motion-helper.js` — `flashStage`
- `site/apex-chrome-flash.css` — grid floor, bottom ticker, glitch
- `site/apex-bridge.css` — categorize instrument styles
- `site/apex-core.js` — categorize template + size
- `apex_backend.py` — categorize assist + BUILD_ID
- `nr2_browser_security.py` — apex ticker/hal/narratives read prefixes
- `nr2-build.json` / `site/nr2-build.json`

## Honesty

- Categorize assist uses **local keyword rules only**; amounts only when present on import; never posts to QuickBooks.
- Empty states remain honest when no expense categories/memos exist.
