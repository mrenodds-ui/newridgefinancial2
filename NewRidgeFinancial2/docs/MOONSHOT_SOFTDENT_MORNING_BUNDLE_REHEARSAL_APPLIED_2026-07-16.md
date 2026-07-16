# SoftDent morning Excel bundle rehearsal — APPLIED (harden; live export still blocked)

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_RESTART_PROOF_2026-07-16.md`  
**Operator:** continue  
**Package:** SoftDent GUI morning Excel bundle (`softdent_export_morning_bundle`)

## Live result

SoftDent was running and signed on. Full morning bundle + aging-only rehearsals **did not land Excel files**. Failures seen:

- Chrome **Claim Management** stole foreground mid-run (`Refusing SoftDent keys — foreground not SoftDent`)
- 64-bit `menu_select` → `ElementNotEnabled` (expected; SoftDent is 32-bit)
- After Output Options: Report Setup / Select File Name / Excel SaveCopyAs intermittent

`periodCloseStatus.morningBundle.ok` remains **false** (`attest_only` fallback). Empty ≠ `$0` preserved (no invented dollars).

## Shipped hardenings (real paths)

| Change | File |
|--------|------|
| Reclaim SoftDent focus from Chrome/Edge/Cursor (not AMD) | `softdent_gui_export.py` |
| F10-first for aging/register/collections/transactions; Practice Management branch `r→p` for collections | `softdent_gui_export.py` |
| Aging Report Setup uses **as-of** date (not start/end range) | `softdent_gui_export.py` |
| Recognize `AG*.XLS` SoftDent Excel stems | `softdent_gui_export.py` |
| Select File Name empty-path retry | `softdent_gui_export.py` |
| `prepare_softdent_for_next_report` between morning-bundle reports | `hal_brain_tools.py` |
| Menu map note: collections under Practice Management; close Chrome during bundle | `softdent_gui_menu_map.json` |
| Unit: reclaimable focus titles | `test_softdent_gui_export.py` |

## Operator action to finish rehearsal

1. Close or background **Claim Management** Chrome tab/window.
2. Leave SoftDent main foreground (no Optical Bench steal).
3. Say **continue** / **approve** for an attended morning-bundle re-run (aging → register → collections → Excel only, never Printer).

## Explicitly not done

- Flip `forceCloseAvailable` on MATCH
- Invent SoftDent export folders / `$0` from empty
- Classic Apex 2B

**Code track closed for this pass.** Live `morningBundle.ok=true` needs attended SoftDent.
