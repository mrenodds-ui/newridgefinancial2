# SoftDent on the web — operator manual + office report

**Date:** 2026-07-13  
**Practice SoftDent:** CS SoftDent Software **v19.1.4** (desktop)  
**NR2 web:** `https://127.0.0.1:8765/` → SoftDent page / `#softdent` / `#softdent/ops`

---

## 1. What “SoftDent on the web” means

| Layer | What it is | Manual / how to use |
|-------|------------|---------------------|
| **SoftDent product Help (vendor web)** | Carestream/Sensei **online Help** for SoftDent windows, reports, shortcuts | Inside SoftDent: **Help → SoftDent Help**, or press **F1**. Web Help portal: [Carestream SoftDent Help – Using Online Help](https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/DE1055_SD_Wkbk/Using_Online_Help.htm) |
| **SoftDent training / support portal** | Support + training library (Sensei) | [SoftDent Support](https://gosensei.com/softdent-support/) · CDI / Resource Library after login |
| **Tutorial (safe practice)** | SoftDent demo DB | Start → SoftDent Software → Tutorial → SoftDent Tutorial ([Tutorial help](https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/Tutorial.htm)) |
| **NR2 “SoftDent on the web”** | Apex **SoftDent** page in the browser — widgets only. Does **not** replace SoftDent UI | Open NR2 → SoftDent nav. Dollars come from **desktop SoftDent exports**, then Sync |

**Important:** SoftDent Practice Management for this office is the **desktop Win32 app**, not a Carestream cloud SoftDent browser client. The “web” surface you use day-to-day for SoftDent **money widgets** is **NR2 Apex**. SoftDent’s own online Help is the vendor manual for the desktop product.

---

## 2. Official SoftDent Help (web) — how to get the manual

1. Launch SoftDent via **CS SoftDent Software.lnk** (`-sus`).
2. Sign On **COMPUTE** / **computer**.
3. Menu: **Help → SoftDent Help**  
   Or press **F1** on any SoftDent window (context help).
4. In Help: **Contents** (browse by feature) or **Search**.
5. Print a topic: **Ctrl+P**.

Support / more docs: [gosensei.com/softdent-support](https://gosensei.com/softdent-support/) → online documentation / resource library / Carestream Dental Institute.

Selected Carestream report job aids used by this office:

| Topic | SoftDent Help URL |
|-------|-------------------|
| Using Online Help | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/DE1055_SD_Wkbk/Using_Online_Help.htm |
| Tutorial | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/Tutorial.htm |
| Register report | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/RegstrRpt.htm |
| Daysheet | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/Daysheet.htm |
| Account Aging | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/ActAgeRp.htm |
| Trans for a Period (PDF job aid) | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/assets/docs/SD_Trans_for_a_Period_JA_FINAL.pdf |
| Account Transactions list | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/ActTxLst.htm |
| Install guide (PDF) | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/DE2000_SDConfig/PDFs/DE1000_SD_InstallGde.pdf |

---

## 3. SoftDent → NR2 web (how widgets get SoftDent data)

```
SoftDent desktop (Excel or Print Preview — never Printer)
   → save / land under C:\SoftDentReportExports  (or SoftDentFinancialExports)
   → NR2 Sync / refresh_softdent_period_imports
   → https://127.0.0.1:8765 SoftDent / Financial / Claims / A/R widgets
```

Widgets **never** open SoftDent menus by themselves. Staff or automation export first; then the web page reads imports.

### Hard rules (this office)

- Launch: **CS SoftDent Software.lnk** only — never bare `SDWIN.EXE`
- Sign On: **COMPUTE** / **computer**
- Output Options: **Excel** or **Print Preview** — **never Printer** (Cancel printer wait with Alt+C)
- Never **Esc** on SoftDent main (quit prompt)
- SoftDent is **32-bit** — prefer F10 menus if UIA fails
- Empty ≠ `$0` — NR2 will not invent SoftDent dollars

### Phase-1 money reports (desktop → web)

| SoftDent menu | Output | Lands in | NR2 web use |
|---------------|--------|----------|-------------|
| Reports → Accounting → Registers → Period | Excel | `C:\SoftDentReportExports` | Production / collections / Ins Plan honesty |
| Reports → Accounting → Daysheet | Excel | same | Daysheet totals / DEF-001 diagnostics |
| Reports → Accounting → Account Aging | Excel | same | A/R aging widgets (`softdent.ar`) |
| Reports → Accounting → Trans for a Period (Format **1**) | Excel | same | Account tx / ledger |
| Reports → Practice Management → Collection Reports → Summary | Excel when offered | same | Collections summary |
| Reports → … → Insurance Income | **Print Preview only** on v19.1.4 | visual audit | Does **not** create gold CSV lines |

After export: open NR2 SoftDent page → Sync / Refresh (or wait for background sync).

Automated pull (same rules):  
`python scripts\run_softdent_money_widget_pull.py --reports aging,register,daysheet,collections`

---

## 4. NR2 SoftDent web page (what you see)

| Surface | URL hash | Purpose |
|---------|----------|---------|
| SoftDent Overview | `#softdent` | Zero-scroll keep set (vitals, gauge, gold drop OPS, trends, …) |
| SoftDent Ops | `#softdent/ops` | Overflow widgets (gaps, gold pipeline, catalogs, dossier, …) |
| Register / Schedule subpages | `#softdent/register`, `#softdent/schedule` | Sub-nav detail |

Gold drop widget stays on Overview because OPS/Print Preview must stay visible. Many gap tiles live under **Ops** after demote (`hal-10612`+).

---

## 5. Report — current SoftDent↔web status (2026-07-13)

| Check | Status |
|-------|--------|
| SoftDent desktop launch / Sign On playbook documented | OK |
| Vendor web Help available (F1 / Help → SoftDent Help) | OK — Carestream portal |
| Account Aging Excel → NR2 A/R softGap freshness | Cleared on **hal-10613** after OPS pull |
| Register Ins Plan Collections | SoftDent truth often **$0** → `ERA_835_REQUIRED` until real ERA `.835` |
| Insurance Income → Gold CSV | **GOLD_CSV_MISSING** — Print Preview ≠ gold line-item file |
| Claims denial / eligibility fields | Often missing or “Awaiting insurance…” — not denial codes |
| NR2 SoftDent page fills from import cache | Warming until sync/fill completes |

### Honesty residual (cannot be fixed by inventing data)

1. Drop real payer **ERA 835** under `C:\SoftDentFinancialExports\era` → Sync  
2. Carestream gold **line-item CSV** (if/when Excel unlocked) → SoftDentFinancialExports → Sync  
3. SoftDent schedule export with **elig/ben** fields for verification matrix  

---

## 6. Related in-repo manuals

| Doc | Content |
|-----|---------|
| `docs/SOFTDENT_WIDGET_DATA_PATHS_2026-07-12.md` | Widget → SoftDent source map |
| `docs/SOFTDENT_GUI_RESEARCH_EXPORT_2026-07-12.md` | Desktop menus, Output Options, keyboard |
| `docs/SOFTDENT_ACCOUNT_TX_EXCEL_WEB_VALIDATE_2026-07-12.md` | Trans for a Period Excel + web validation |
| `docs/SOFTDENT_SIGNON_PROGRAM_WIRING_2026-07-12.md` | Sign On wiring |
| `.cursor/rules/softdent-desktop-gui.mdc` | Always-on SoftDent OPS hard rules |

---

## 7. Executive summary

- SoftDent’s **product manual on the web** = Carestream SoftDent Help (**Help → SoftDent Help** / **F1** / Carestream Help URLs above).  
- SoftDent’s **money truth for NR2 web** = **desktop SoftDent Excel/Print Preview** → export folder → Sync → Apex SoftDent page.  
- SoftDent itself here is **not** a browser PMS; NR2 is the web dashboard that displays SoftDent imports.  
- Gold CSV + ERA remain OPS/procurement gaps — Print Preview and empty fields stay honest (empty ≠ `$0`).
