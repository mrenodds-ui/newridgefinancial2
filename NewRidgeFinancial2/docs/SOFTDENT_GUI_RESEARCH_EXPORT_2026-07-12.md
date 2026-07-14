# SoftDent GUI export research (Carestream CS SoftDent)

**Date:** 2026-07-12  
**Sources:** Carestream SoftDent Help (OH_DE1010), keystroke reference, Accounting/Register/Daysheet/Aging/Trans job aids  
**Practice build:** CS SoftDent Software v19.1.4  

## Official report flow (all accounting reports)

1. **Reports → Accounting → \<report\>**  
2. **Output Options** window appears  
3. Choose output (**Excel** for NR2 ingest — not Printer) → **OK**  
4. **Setup** window (Register Setup / Daysheet / Aging / Trans…) → dates, provider **999** = all → **OK**  
5. If Excel: SoftDent prompts for save path (short 8.3 paths work: `C:\SOFTDE~1\…`)

### Phase-1 menu paths (Carestream)

| Report | Menu path |
|--------|-----------|
| Register for a Period | Reports → Accounting → Registers → Period |
| Daysheet | Reports → Accounting → Daysheet |
| Transactions for a Period | Reports → Accounting → Trans for a Period |
| Account Aging | Reports → Accounting → Account Aging |

Register Excel export is officially supported for Daily / Monthly / Yearly / Period / Cumulative / Summary.

## Why we see “Waiting for printer connection…”

Output Options includes **Printer**. If Printer is selected (or Enter hits default Printer), SoftDent talks to the Windows default printer. When that printer is offline, SoftDent shows **Waiting for printer connection…** with **Cancel**.

**Rule:** Always select **Excel** before OK. If a printer wait appears → **Cancel** (Alt+C / Cancel button) — never leave SoftDent spinning on a dead printer.

## Keyboard rules (Carestream + this workstation)

| Key | SoftDent behavior (docs) | Our rule |
|-----|--------------------------|----------|
| Enter | OK | Use for OK on SoftDent dialogs |
| Esc | Closes a *window* | Do **not** send Esc on SoftDent main (can prompt quit); OK to Cancel printer dialogs via Cancel/Alt+C instead |
| Tab / Shift+Tab | Next / previous field | Use in Setup / Save |
| Space | Check/uncheck | Use for checkboxes |
| Alt+F4 | Exits SoftDent | Forbidden in automation |
| Alt+R | Reports menu (soft accel) | **Forbidden on this PC** — AMD Adrenalin Instant Replay steals Alt+R |
| F10 | Windows menu bar | Prefer SoftDent menu click or SC_KEYMENU to SoftDent hwnd |

Carestream documents many Ctrl shortcuts for Lists/Scheduler/Chart — **none** open Register/Daysheet; those are menu-only.

## Interaction policy for NR2 automation

- Launch SoftDent only via desktop/Programs shortcut (`CS SoftDent Software.lnk`, includes `-sus`).  
- Sign On: keyboard type user/password → Enter (mouse OK on SoftDent Login controls only).  
- Drive menus with **keyboard and/or mouse**, but **only SoftDent-owned windows** (SDWIN PID).  
- Never click/focus AMD / Radeon / other apps.  
- SoftDent v19 uses a classic Win32 `HMENU`: UIA only sees the top bar; use SoftDent `menu_select("Reports->Accounting->Registers->Period")` (or F10+letters).  
- **Output Options:** same click pattern for both paths:  
  - **Excel** prompt → **Enter** → file save → NR2 parses.  
  - **Print Preview** prompt → **Enter** → SoftDent preview → go to the **last page** for exact totals (visual read).  
- Never leave **Printer** selected.  
- Prefer Register Excel for period production/collections/Ins Plan when SoftDent reports those labels.  
- Fallback: F10 / SoftDent-local menu keys (not global Alt+R).  
- After any report: sweep printer dialogs and cancel them.

### Verified v19.1.4 menu paths (this PC)

| Report | Win32 menu_select path |
|--------|------------------------|
| Register Period | `Reports->Accounting->Registers->Period` |
| Daysheet | `Reports->Accounting->Daysheet` |
| Trans for a Period | `Reports->Accounting->Trans for a Period` |
| Account Aging | `Reports->Accounting->Account Aging` |
| Collections Summary | `Reports->Practice Management->Collection Reports->Summary` |

## Data accuracy note

Final **Daysheet** updates `RCVTOT.DAT`. Register receivables totals need that file current. NR2 still treats Ins Plan $0 honestly (no invented split).

## References

- https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/DayRegRpt.htm  
- https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/RegstrRpt.htm  
- https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/Daysheet.htm  
- https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/ActAgeRp.htm  
- https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/KystrkSht.htm  
- Trans for a Period job aid PDF (Carestream `SD_Trans_for_a_Period_JA_FINAL.pdf`)  
