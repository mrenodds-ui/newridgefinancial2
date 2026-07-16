# SoftDent Print Preview harden + Trellis withBenefits smoke — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_NR2_12071_2026-07-16.md`  
**Operator:** continue  
**Build:** `nr2-12072-preview-harden-benefits-smoke`

## Correction vs Moonshot gate

Moonshot asked for `morningBundle.ok=true` via Print Preview. **Rejected honestly:** money beams require SoftDent Excel drops (`moneyBeamIngest` + path). Excel remains SoftDent-greyed → `attest_only` + empty ≠ `$0`. Preview is visual-only.

Root cause from attended bundle: all three reports returned `ok` with `printPreviewOpen=false` and **Date Wizard** left open — Preview path ignored Date Wizard / as-of aging.

## Package 1 — SoftDent Print Preview harden

| Change | File |
|--------|------|
| Detect **Date Wizard** / Report Setup | `softdent_gui_export.py` `_find_softdent_report_setup_dialog` |
| Fill as_of (aging) vs range; OK into Preview | `_fill_softdent_report_setup` |
| Collections win32 Practice Management paths on Preview | `open_report_print_preview` |
| `ok` only when `printPreviewOpen` and setup not stuck | `open_report_print_preview` + `softdent_export` |
| MDI titles for aging/collections/register | `softdent_report_preview_visible` |
| Menu map note | `softdent_gui_menu_map.json` |

Never File · never Printer · SoftDent write-back forbidden.

## Package 2 — Wire withBenefits into desk-smoke

`desk_smoke.morningConfidence.trellisBenefits` carries `patients` / `withBenefits` / `statusOnly` (counts only, no $). Informational — does not flip Force Close.

## Validation

- Unit: `test_softdent_gui_export`, `test_trellis_tomorrow_panel`
- Live SoftDent Preview re-run: optional attended; money beams still blocked until SoftDent enables Excel
- Restart NR2 for build stamp + smoke field

## Explicitly not done

- Flip `morningBundle.ok` without Excel
- Invent SoftDent Excel / File paths
- Flip `forceCloseAvailable`
