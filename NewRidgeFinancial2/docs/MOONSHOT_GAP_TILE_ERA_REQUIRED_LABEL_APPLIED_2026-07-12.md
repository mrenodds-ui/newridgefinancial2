# Gap-Tile Honesty Label Polish — APPLIED (hal-10572)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_IMPORT_HYGIENE_2026-07-12.md`  
**Operator:** proceed  
**Build:** **hal-10572**

## What shipped

| Item | Detail |
|------|--------|
| Visible gap code | Prefer `collectionsGapCode` / Register Ins Plan $0 → **`ERA_835_REQUIRED`** on tile message |
| ERA enrich | When `registerInsPlanZero`, keep `gapCode=ERA_835_REQUIRED`; ERA presence stays on `eraGapCode=ERA_835_AVAILABLE` |
| Hint | Explicit “Do not re-export Register hoping Ins Plan > 0” |
| HAL chips | `ERA-835 path` / Collections gap / Sync — no Re-export Register CTA |
| Helper | `display_collections_gap_code()` |

## Validation

```text
cd NewRidgeFinancial2
python -m unittest test_gap_tile_era_required_label_hal10572 test_era_835_honesty_ux_hal10571 test_apex_softdent_era_s1 -v
```

| Gate | Result |
|------|--------|
| Widget `emptyMessage` / `message` = `ERA_835_REQUIRED` | **PASS** |
| Not primary `ERA_835_AVAILABLE` | **PASS** |
| Do-not-re-export hint | **PASS** |
| Pending+ERA still `gapCode=ERA_835_AVAILABLE` (non–Ins-Plan-zero) | **PASS** |
| No invented insurance $ | **PASS** |

## Files

| File | Change |
|------|--------|
| `apex_softdent_hardening_pack.py` | `display_collections_gap_code`, widget/chips/alert |
| `apex_softdent_era_pack.py` | Preserve REQUIRED on enrich; honesty fixHint |
| `apex_backend.py` + `nr2-build.json` + site assets | BUILD_ID **hal-10572** |
| `test_gap_tile_era_required_label_hal10572.py` | NEW |

## Not done

- Real ERA-835 inbox ingest  
- Collections Summary Excel-temp  
- Inventing QB payroll/AP rows  
- Re-export July Register  

## Live re-verify (operator proceed 2026-07-12 ~22:48Z)

Restarted `browser_app.py` onto **hal-10572** (was still serving stale 10571 process). Synced leftover `site/index.html` + `site/workstation/index.html` cache-bust stamps `hal-10571` → `hal-10572`.

| Gate | Result |
|------|--------|
| `GET /api/apex/hal/collections-gap` → `gapCode=ERA_835_REQUIRED` (= `collectionsGapCode`) | **PASS** |
| `eraGapCode` remains `ERA_835_AVAILABLE` (ERA presence only) | **PASS** |
| Financial widget message `ERA_835_REQUIRED · 2026-07` | **PASS** (browser + API) |
| Do-not-re-export honesty hint visible | **PASS** |
| HAL chips: ERA-835 path / Collections gap / Sync imports | **PASS** |
| UI badge `hal-10572 · bridge` | **PASS** |
| Unit tests `test_gap_tile_era_required_label_hal10572` | **PASS** |
