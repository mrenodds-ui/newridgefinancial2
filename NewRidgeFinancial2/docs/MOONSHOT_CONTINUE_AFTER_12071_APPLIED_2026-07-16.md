# Continue after nr2-12071/12072 — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_NR2_12071_2026-07-16.md`  
**Operator:** continue  
**Live build:** `nr2-12072-preview-harden-benefits-smoke`

## What Moonshot asked vs what we applied

| Moonshot #1 | Reality |
|-------------|---------|
| Harden Print Preview so `morningBundle.ok=true` | **Rejected as stated.** Print Preview ≠ money-beam Excel ingest (`moneyBeamIngest=false` when `excelDisabled`). Flipping `morningBundle.ok` from Preview would invent money capability. |
| Preview Date Wizard / collections F10 | **Already on main** as `bd435ae` (nr2-12072) |

## Applied this continue

1. **Restarted NR2 browser** (`start_nr2_browser.ps1 -Restart`) — live `assetVersion` = `nr2-12072-preview-harden-benefits-smoke`
2. **Synced** `site/nr2-build.json` to match package stamp (was stuck on 12070)
3. **Desk smoke proof** `?run=1` → GREEN / MATCH / `forceCloseAvailable=false`
4. **`morningConfidence.trellisBenefits`** live:
   - patients 28 · withBenefits 0 · statusOnly 28 (honest until tonight’s ClearCoverage scrape)
5. **Aging probe** still `excelDisabled=true` → Print Preview only · no Excel path
6. **HAL teach** — SoftDent Excel enablement operator checklist line in `softdent_report_pull.py`

## Still blocked (operator SoftDent)

Enable SoftDent Output Options **Excel**, then say **approve** for morning money-bundle re-run.

## Explicitly not done

- Flip `morningBundle.ok` from Print Preview alone
- Flip `forceCloseAvailable`
- Invent Excel drops / `$0`
- Invent `hal_softdent_teach.json` (consult path — does not exist; teach lives in `softdent_report_pull.py`)
