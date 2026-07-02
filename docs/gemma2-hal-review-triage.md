# Gemma 2 HAL programming review — triage (July 2026)

Reports: `gemma2_hal_program_9b_report.md`, `gemma2_hal_program_27b_report.md` (gitignored).

Re-run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_gemma2_hal_program_eval.ps1 -Both
```

Apply the same evidence bar as the dual-model audit: **file + line or validator assertion required** before changing production code.

## 9B report triage

| Finding | Verdict | Evidence |
|---------|---------|----------|
| `halAutoRefreshCalled` not reset | **False positive** | Symbol exists only in `validate-hal.mjs` (test mock, lines 1295–1318). Not in `NewRidgeFinancial2/site/`. Model confused validator harness with production code. |
| Globals `DesktopBridge` / `ImportCoordinator` | **By design** | Intentional pywebview desktop bridge in `hal-proactive.js` with `Services` / `ImportCoordinator` / `DesktopBridge` fallbacks. Standard NR2 architecture. |
| Generic `assert` messages in validators | **Low priority** | Many asserts already include descriptive messages (e.g. lines 804–805). Some short labels remain (`"toggle check"`) — cosmetic only. |

## 27B report triage

| Finding | Verdict | Evidence |
|---------|---------|----------|
| `buildWidgetFeed` fails to null `patientBalanceTotal` when A/R unavailable | **False positive (widget feed)** | `buildWidgetFeed` ends with `enforceReceivablesArPolicy(feed, arAvailable)` which nulls both `accountsReceivableTotal` and `patientBalanceTotal` (`hal-skills.js` 2384–2404). Covered by `validate-hal.mjs` 801–806. |
| Missing `HalProactive` unit tests | **Overstated** | `validate-hal.mjs` 1286–1316 exercises `buildProactiveBriefing`, `runAutonomousPlacement`, routing, and refresh behavior. Not a dedicated test file, but not untested. |
| `halAutoRefreshCalled` not reset in `runAutonomousPlacement` | **False positive** | Same as 9B — test-only variable in validator, not production state. |

## Related real issue (not in Gemma reports, found during verification)

| Issue | Verdict | Status |
|-------|---------|--------|
| SoftDent page canvas may show unverified A/R via `sd.hero` fallback | **Fixed** | `softdentGlanceStats()` uses widget-feed `patientBalanceTotal` only. |
| Stale `dashboards.ar.kpis` / SoftDent aging / responsibility charts bypass widget feed | **Fixed** | `arKpis()`, `softdentAgingBars()`, `softdentResponsibilityDonut()` require verified-A/R widget `SUCCESS`. |
| HAL program snapshot / source guide show stale `sd.hero` or `ar.kpis` | **Fixed** | `summarizeProgramSnapshot()` and `formatSourceSystemGuide()` gate on verified A/R. |
| A/R claims table shows per-claim `outstanding` without verified export | **Fixed** | `arTopClaimsTable()` masks outstanding unless `arOutstandingClaims` widget is `SUCCESS`. |
| A/R follow-up kanban / collections chart show claim or trend amounts without verified export | **Fixed** | `arFollowUpKanban()` omits claim amounts; `arCollectionsChart()` requires `arAgingAndCollections` `SUCCESS`. |

## Recommended next steps

1. **Do not fix** `halAutoRefreshCalled` or refactor globals based on Gemma output alone.
2. ~~**Optional fix:** Remove `sd.hero` fallback in `softdentGlanceStats()`~~ **Done.**
3. ~~**Optional test:** Add `validate-hal.mjs` assertion for page canvas A/R honesty~~ **Done.**

## Do not auto-fix from model output

- Architecture refactors (remove globals, rewrite agent loop) without staff sign-off.
- Findings that cite symbols or files not present in the repo snapshot.
