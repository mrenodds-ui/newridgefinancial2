# SoftDent account transactions → Excel (web + live validation)

**Date:** 2026-07-12  
**Source of truth:** SoftDent desktop UI (not DB/`sd_*`)

## Learned from Carestream SoftDent Help

### A) All patients / period (Excel-documented)

Carestream job aid [Running the Transactions for a Period Report](https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/assets/docs/SD_Trans_for_a_Period_JA_FINAL.pdf):

1. **Reports → Accounting → Trans for a Period**
2. **Output Options** → choose output → OK  
3. Set dates + format (**List Each Transaction Separately** for line-level)  
4. OK  

Excel is a normal Output Options choice on this practice’s SoftDent v19.1.4.

### B) One account (Account Transaction tab)

Carestream [Account Transactions List options](https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/ActTxLst.htm):

1. Open account (**F3** / **Ctrl+A** List Account) or patient (**F5**)
2. **Transactions** → Account Mode (Account Transaction view)
3. **Print Transactions** → Output Options (Excel if offered)

### Keys (Carestream)

| Key | Action |
|-----|--------|
| F3 | Account search |
| F5 | Patient search |
| Ctrl+A | List → Account |

Sign On: **COMPUTE** / **computer** (keyboard or mouse). Never **Printer**. Never Esc on SoftDent main.

Launch SoftDent only via **CS SoftDent Software.lnk** (not bare `SDWIN.EXE`).

SoftDent Excel often opens a temp `%LOCALAPPDATA%\Temp\SDWIN*.csv` in Excel — copy/SaveCopyAs into `C:\SoftDentReportExports`.

## HAL

Playbook is injected when staff ask about SoftDent account/patient transactions / Trans for a Period / Excel export:

- `format_softdent_account_tx_excel_hal_reply()` in `softdent_signon.py`
- LLM context via `compile_softdent_signon_guidance`
- Local policy via `nr2_hal_gateway.try_local_policy_reply` (intent `policy:softdent-signon-env`)

## Live validation (this PC — SoftDent v19.1.4)

| Check | Result |
|-------|--------|
| SoftDent path opens Output Options | **PASS** |
| Excel button present | **PASS** — Printer, Print Preview, File, Excel, … |
| Excel selected (not Printer) | **PASS** |
| Transactions For A Period setup appears | **PASS** — Start/End dates, Format **1 = List Each Transaction Separately**, Doctors 999, **Show Notes in Excel** |
| SoftDent opens Excel workbook | **PASS** — window `SDWIN3 - Excel` from temp `SDWIN3.csv` |
| Saved into NR2 inbox | **PASS** — `C:\SoftDentReportExports\TXN260201.xls` (~286 KB, 1736 rows) |
| Donna Nickel in export | See validation JSON `hasDonnaNickel` / `donnaLines` |

Log: `C:\SoftDentFinancialExports\softdent_account_tx_excel_validation.json`  
Export: `C:\SoftDentReportExports\TXN260201.xls`

**Note:** SoftDent Excel output often skips “Select File Name” and opens Excel on a temp CSV (`%LOCALAPPDATA%\Temp\SDWIN*.csv`). Automation should `SaveCopyAs` into `C:\SoftDentReportExports`.

## Ops fix for save path

SoftDent **System → Printing Preferences → Default Path for Excel Files** → `C:\SoftDentReportExports` (short: `C:\SOFTDE~1`).
