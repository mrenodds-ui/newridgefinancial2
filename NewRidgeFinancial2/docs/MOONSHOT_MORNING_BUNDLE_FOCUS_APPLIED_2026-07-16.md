# SoftDent morning-bundle focus harden — APPLIED

**Date:** 2026-07-16  
**Consult backlog:** `MOONSHOT_WHATS_NEXT_AFTER_CONTINUE_UNTIL_DONE_2026-07-16.md` item SoftDent morning-bundle  
**Operator:** continue

## Root cause (last close)

Morning Excel bundle failed with SoftDent still running:

- `Refusing SoftDent keys — foreground not SoftDent: 'NR2 Optical Bench…'`
- Select File Name path refused when SoftDent lost focus mid-dialog

Fallback `attest_only` kept period-close green (empty ≠ $0).

## Shipped

| Change | Where |
|--------|--------|
| Focus SoftDent even when already running | `ensure_softdent_ready_for_gui_export` |
| Always prep + re-focus between aging/register/collections | `softdent_export_morning_bundle` |
| Fail fast with `softdent_not_ready` if focus fails | same |
| Richer `morningBundle.detail` / ensure | `period_close_status` |
| Preserve `morningConfidence` on desk-smoke `?run=0` | `nr2_http_server` desk-smoke last |

## Validation

- `ensure_softdent_ready_for_gui_export` → `focused_main` while SoftDent running  
- Period-close unit tests pass  
- Desk smoke GREEN  

## Not run this pass

Full SoftDent GUI Excel aging/register/collections pull (interactive, long). Next Force Close / morning pull will exercise the hardened focus path.
