# Browser Smoke — ERA-835 Honesty UX + Widgets NICE + TXN Ledger (hal-10571)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ERA835_HONESTY_2026-07-12.md`  
**Operator:** proceed (after widgets-NICE OPS ask — Register re-export skipped; Ins Plan $0 already SoftDent truth)  
**Build:** **hal-10571**  
**URL:** `https://127.0.0.1:8765/`

## Why not SoftDent Register re-export
July Register already present (`register_for_period_2026-07-01_2026-07-12.xls`, Ins Plan $0). Moonshot ERA honesty (197efe8) forbids re-export hoping Ins Plan > 0. Proceeded with the post–hal-10571 smoke gate instead.

## Hotfix required to unblock smoke
Import watcher called `load_import_bundle(..., read_only=True)` but the loader has no such kwarg → mass quarantine (`import_read_forbidden` / 75% completeness).

| File | Fix |
|------|-----|
| `apex_import_watcher_pack.py` | Drop invalid `read_only=True`; `sync=False` is the read-only path |

Also released 50 `read_only`-caused quarantine items back to inbox and restarted `browser_app.py`.

## Acceptance gates

| Gate | Result |
|------|--------|
| Hard refresh loads **hal-10571** | **PASS** (badge + `/nr2-build.json`) |
| `collectionsGapCode=ERA_835_REQUIRED` | **PASS** (`/api/apex/hal/collections-gap`) |
| Honesty hint / “do not re-export Register…” | **PASS** (gap `fixHint` + `issues[]`) |
| No “Re-export Register” remedial CTA | **PASS** (HAL chips = Collections gap / Refresh period / Sync only) |
| Widgets NICE: pareto / tax-calendar / timeline-lanes | **PASS** (A/R+Claims / Taxes / Claims) |
| TXN ledger surface | **PASS** (SoftDent `data-table` ledger after warm) |
| `eraStub.mode=stub` | **PASS** (local stub; inbox roots empty) |

## Widget counts (post-warm)

| Page | Widgets | Notable types |
|------|---------|----------------|
| financial | 36 | `radial-gauge`, collections gap strip, pareto |
| softdent | 18 | `patient-dossier-card`, ledger `data-table` |
| ar | 13 | `pareto-chart`, `collection-task-list`, gauge |
| claims | 18 | `pareto-chart`, `timeline-lanes` |
| taxes | 9 | `tax-calendar`, `data-table` |

## Notes
- Gap strip **message** still shows `ERA_835_AVAILABLE · 2026-07` (outer `gapCode`); nested `collectionsGapCode` is `ERA_835_REQUIRED` — honesty path is correct.
- Browser HAL POST `/api/apex/hal/orchestrate` returns `browser_mutation_forbidden` without mutation token; gap API + local policy cover the phrase gate.
- SoftDent desktop remained logged in; no Register re-export run during smoke.

## Re-verify (operator proceed 2026-07-12 ~22:25Z)

Live re-check after Moonshot consult `MOONSHOT_WHATS_NEXT_AFTER_ERA835_HONESTY_2026-07-12.md` → **proceed**.

| Gate | Result |
|------|--------|
| `/nr2-build.json` / UI badge **hal-10571** | **PASS** |
| `GET /api/apex/hal/collections-gap` → `collectionsGapCode=ERA_835_REQUIRED`, `registerInsPlanZero=true`, `collectionsExportRequired=false` | **PASS** |
| Honesty `fixHint` + issues “do not re-export Register hoping Ins Plan > 0” | **PASS** |
| HAL chips = Collections gap / Refresh SoftDent period / Sync imports (no Re-export Register) | **PASS** |
| Financial gap strip visible in browser (Ins Plan $0 → ERA-835) | **PASS** |
| Widgets NICE: financial=36 (pareto), ar=13 (pareto), claims=18 (timeline-lanes), taxes=9 (tax-calendar), softdent=18 (ledger) | **PASS** |
| TXN ledger `softdent-transaction-ledger` status=ok (25 rows in widget payload) | **PASS** |
| `stub_era835_ingestion_path()` → `mode=stub`, `readOnly=true`, `existingRoots=[]` | **PASS** |

No SoftDent Register re-export. Quarantine UI may still list pre-hotfix `read_only` failures; watcher fix is in `2439197`.
