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

## Rehearsal (2026-07-16)

Ran `softdent_export_morning_bundle(days=30)` after focus harden (~5 min):

| Report | Result |
|--------|--------|
| aging | Fail — Output Options closed unexpectedly before OK (4/4) |
| register | Fail — Output Options / Select File Name; FG stolen by File Explorer |
| collections | Fail — FG stolen by Notepad / Select File Name had no SoftDent folder |

Ensure prep succeeded (`focused_main`). Mid-dialog thieves still break SoftDent Excel automation. Attest-only fallback remains correct (empty ≠ $0).

**Operator tip for next Force Close / morning pull:** close File Explorer and editor windows over SoftDent; leave SoftDent Output Options → Excel only (never Printer).

## Not closed

`morningBundle.ok=true` still requires a clean SoftDent desktop session for the three Excel reports.
