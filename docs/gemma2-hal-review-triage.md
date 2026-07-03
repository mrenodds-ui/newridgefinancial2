# Gemma 2 HAL programming review — triage (July 2026)

Reports: `gemma2_hal_program_9b_report.md`, `gemma2_hal_program_27b_report.md` (gitignored).

Re-run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_gemma2_hal_program_eval.ps1 -Both
```

## Evaluation run (latest — July 3 2026)

| Check | Result |
|-------|--------|
| `validate-pages.mjs` | Passed |
| `validate-hal.mjs` | 26 suites passed |
| NR2 Python tests (12 modules, 46 tests) | Passed |
| Gemma 2 9B + 27B HAL review | Completed (15:19–15:30 UTC) |

### July 3 findings — triage

| Finding | Model | Verdict |
|---------|-------|---------|
| `monthlyRevenue !== 123456` assert (test-only) | 9B | **False positive** — intentional cross-source A/R policy test |
| `crossOverview.status !== "SUCCESS"` assert | 9B | **False positive** — same test block |
| `global.DesktopBridge` mutation in tests | 9B | **By design** — mocks restored after |
| "Add comments" on test fixtures | 9B | **Style / not a bug** |
| `bootStart < 3000` timeout brittleness | 27B | **Fixed** — raised to 5000ms with elapsed diagnostic |
| `syncStatus.ok` assumption | 27B | **Misread** — mock sets `ok: true`; assertion uses `.status` |
| `localModel` 60s timeout too short | 27B | **Config opinion** — not a confirmed bug |

No confirmed production bugs in this round.

## Original Gemma findings (9B + 27B) — triage

| Finding | Verdict |
|---------|---------|
| `halAutoRefreshCalled` not reset | **False positive** — test-only mock in `validate-hal.mjs` |
| `buildWidgetFeed` A/R nulling | **False positive** — handled by `enforceReceivablesArPolicy` |
| Globals `DesktopBridge` / `ImportCoordinator` | **By design** |
| Generic assert brittleness | **Partial** — structured message checks added where actionable |

## Gemma round 2 (post A/R fixes) — triage

| Finding | Verdict | Action |
|---------|---------|--------|
| Assert/schema validation (9B) | Low priority | Structured issue-message asserts for quality validation |
| Firewall string matching (9B) | Docs | Added `reason` to `hal-manager.json` `firewallExamples` |
| hal-models.json comments (9B) | Docs | Added `note` on `deep235b` lane |
| Missing `quality` metric (27B) | **Fixed** | `applyAccountingExcelCommitValidation` + widget degrade |
| Regex `overallPass failed` (27B) | **Fixed** | Exact message constants + structured assert |
| deep235b / firewallExamples docs (27B) | **Fixed** | See hal-models.json / hal-manager.json |

## Code fixes applied

### A/R honesty (page canvas + HAL summaries)

- `softdentGlanceStats`, `arKpis`, `softdentAgingBars`, `softdentResponsibilityDonut`
- `arTopClaimsTable`, `arFollowUpKanban`, `arCollectionsChart`
- `summarizeProgramSnapshot`, `formatSourceSystemGuide`

### Quality score validation (Gemma 27B)

- `hal-skills.js`: missing `financial.quality` → commit issue + `DEGRADED` overview widget
- `validate-hal.mjs`: regression tests for missing quality and exact `overallPass` message

### Import loader (pytest failure)

- `import_loader.py`: `_repo_relative()` — safe path recording when cache dir is outside repo root (temp test dirs)

### Documentation (Gemma low priority)

- `hal-manager.json`: firewall example `reason` fields
- `hal-models.json`: `deep235b` lane `note`

## Do not auto-fix from model output

- Architecture refactors without staff sign-off
- Findings citing symbols not present in the repo snapshot
