# SoftDent safe GUI export kit — APPLIED (hal-10566)

**Date:** 2026-07-12  
**Status:** Applied  
**Build:** hal-10566  

## What this is

Read-only SoftDent GUI assist for Sign On + Register/Collections period Excel export into `C:\SoftDentReportExports`.

| Piece | Path |
|-------|------|
| Sign On resolver | `NewRidgeFinancial2/softdent_signon.py` |
| Export helpers | `NewRidgeFinancial2/softdent_gui_export.py` |
| Safe orchestrator | `scripts/run_softdent_safe_period_export.py` |
| Register CLI | `scripts/automate_softdent_register_period_export.py` |
| Collections CLI | `scripts/automate_softdent_collections_period_export.py` |

## Safety rules

- Password only in local gitignored `.env` (`SOFTDENT_SIGNON_USER` / `SOFTDENT_SIGNON_PASSWORD`)
- Never committed, never printed in HAL refresh payloads, never written into Moonshot docs
- SoftDent **read-only** report export — no SoftDent write-back / no invented dollars
- Sign-on assist does **not** open Change Login when SoftDent main window is already up (`force_change_login=False`)

## Usage

```powershell
# Status / ensure signed on (no password in output)
.\.venv\Scripts\python.exe NewRidgeFinancial2\softdent_signon.py

# Register + Collections for open month
.\.venv\Scripts\python.exe scripts\run_softdent_safe_period_export.py --start 2026-07-01 --end 2026-07-12

# Collections menu keys differ by SoftDent build:
$env:SOFTDENT_COLLECTIONS_MENU_KEYS = "c"
```

Then Refresh SoftDent period (HAL) or call `refresh_softdent_period_imports()`.

## Honesty

July Register may still show **Ins Plan Collections = $0.00**. Export automation cannot invent a split; `collectionsFormatRequired` stays until SoftDent reports a real Ins Plan side.

## Rotate

If the SoftDent password was pasted into chat, change it in SoftDent and update local `.env` only.
