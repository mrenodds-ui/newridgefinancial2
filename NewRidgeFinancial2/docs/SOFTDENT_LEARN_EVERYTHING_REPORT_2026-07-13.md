# SoftDent — Learn-Everything Report (this office + Carestream Help)

**Date:** 2026-07-13  
**Scope:** Everything NR2 / HAL / OPS currently knows about how SoftDent **runs** and **pulls reports** on this PC, plus what Carestream’s online Help teaches for those reports.  
**Practice build:** CS SoftDent Software **v19.1.4** (desktop Win32).  
**Honesty:** This is **not** “every SoftDent feature on Earth.” It is the complete **program + office** SoftDent knowledge base as of this date. SoftDent’s full vendor manual remains **Help → SoftDent Help** / **F1**.

---

## Executive verdict

| Question | Answer |
|----------|--------|
| Do we know how SoftDent launches, signs on, and pulls the reports NR2 needs? | **Yes — deeply** |
| Do we know every SoftDent report SoftDent can print? | **No** |
| Is SoftDent itself a web browser PMS here? | **No** — desktop app; NR2 Apex is the web dashboard |
| Can SoftDent dollars be inventedish when reports fail? | **No** — empty ≠ `$0` |

---

## 1. How SoftDent runs (desktop)

### Launch
1. Start Menu / Desktop: **CS SoftDent Software.lnk**  
2. Working directory `C:\SoftDent`, arguments **`-sus`**  
3. **Never** bare `SDWIN.EXE`

### Sign On
| Field | Value |
|-------|--------|
| User | **COMPUTE** (or `SOFTDENT_SIGNON_USER`) |
| Password | **computer** lowercase (or `SOFTDENT_SIGNON_PASSWORD`; code forces `.lower()`) |

Never Esc on SoftDent **main** (quit prompt). Prefer keyboard F10 menus when 64-bit UI Automation fails (`ElementNotEnabled` — SoftDent is 32-bit).

### Access doctrine (NR2)
- **Period-close money truth** = SoftDent **desktop Excel** exports  
- **Fast ops detail** (schedule/util) = Sensei / `sd_*` / ODBC lane — do not invent dollars from DB when desktop Register disagrees  

Code: `softdent_signon.py`, rule `.cursor/rules/softdent-desktop-gui.mdc`.

---

## 2. Universal SoftDent report flow (Carestream + this PC)

Every accounting-style report follows the same shell:

1. **Reports → … → \<report\>**  
2. **Output Options** window  
3. Choose **Excel** or **Print Preview** → Enter/OK — **never Printer**  
4. **Setup** (dates, doctor **999** = all, options) → OK  
5. If Excel: Save / SoftDent may open temp `SDWIN*.csv` in Excel → **SaveCopyAs** to `C:\SoftDentReportExports`  
6. If Print Preview: page through → **last page** for totals (page 1 alone is often incomplete)

### Printer hang
If Output Options defaults to **Printer**, SoftDent shows **Waiting for printer connection…**  
→ **Cancel** (Alt+C). Never leave SoftDent spinning on an offline printer.

### Keyboard pitfalls (this workstation)
| Key | Rule |
|-----|------|
| Esc | SoftDent main = quit — **forbidden** |
| Alt+R | Stolen by AMD Adrenalin Instant Replay — **forbidden** for Reports |
| F10 | Preferred SoftDent menu access |
| Alt+F4 | Exits SoftDent — forbidden in automation |

---

## 3. Every report NR2 automates (GUI catalog)

Source of truth: `NewRidgeFinancial2/softdent_gui_menu_map.json` + `softdent_gui_export.py`.

### Phase 1 — required money / ops Excel (daily / money pull)

| `report_id` | SoftDent menu | Output | Land-as name | Proven? |
|-------------|----------------|--------|--------------|---------|
| **register** | Reports → Accounting → Registers → Period | Excel | `register_for_period_{start}_{end}.xls` / `REG{yy}{mm}` | **Yes** |
| **collections** | Reports → Practice Management → Collection Reports → Summary | Excel or Preview | `collections_for_period_{start}_{end}.xls` | Flaky |
| **transactions** | Reports → Accounting → Trans for a Period | Excel (Format **1** = List Each Transaction Separately) | `transactions_for_period_*.xls` / TXN* | Partial |
| **daysheet** | Reports → Accounting → Daysheet | Excel | `daysheet.xls` / `DAY*` | Flaky (Printer traps) |
| **aging** | Reports → Accounting → Account Aging | Excel | `account_aging.xls` / `AGE*` | **Yes** (recent pulls) |

**phase1_order:** `register → collections → transactions → daysheet → aging`

### Phase 2 — optional / Print-Preview–heavy

| `report_id` | SoftDent menu | Output on v19.1.4 | NR2 role |
|-------------|----------------|-------------------|----------|
| **writeoff_totals** | Practice Management → Insurance Reports → Writeoff Totals | **Print Preview only** | Visual write-off totals |
| **insurance_payment_distribution** | Accounting → Insurance Payment Distribution | **Print Preview only** | Distribution view (may lack ADA lines) |
| **insurance_payment_analysis** | Practice Management → Insurance Reports → **Insurance Income** | **Print Preview only** | Gold candidate — **does not create gold CSV lines** |
| **production_by_ada_code** | Practice Management → Production Reports → Production by ADA Code | Excel or Preview | SoftDent CODE rollups (`PRODBYADA.xls`) — **not** InsCo×ADA gold payments |

### Carestream Help — what these reports contain

**Register** ([RegstrRpt.htm](https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/RegstrRpt.htm)):  
Daily / Monthly / Yearly / Period / Cumulative / Summary — receivables + production, patients seen/new, charges/adjustments/collections, averages.

**Account Aging** ([ActAgeRp.htm](https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/ActAgeRp.htm)):  
Aged balances; Ins Amt; Current / 30 / 60 / 90; Outstanding Insurance Breakdown; Total (Net 30). Carestream warns: Aging defaults exclude some accounts — **do not equate Aging totals to Daysheet receivables** without matching include options.

Daysheet / Trans Help URLs: see §8.

---

## 4. How pulls are run (scripts)

| Script | What it does |
|--------|----------------|
| `scripts/run_softdent_money_widget_pull.py` | Sign On → Register/Daysheet/Aging/Collections → refresh → Register↔daysheet drift check |
| `scripts/run_softdent_daily_master_pull.py` | Full Phase-1 daily GUI pull (+ status JSON) |
| `scripts/run_softdent_daily_gui_pull.ps1` | Scheduled wrapper (~5 PM interactive session) |
| `scripts/automate_softdent_register_period_export.py` | Register only |
| `scripts/automate_softdent_collections_period_export.py` | Collections only |
| `scripts/validate_softdent_account_tx_excel.py` (+ continue/proceed/finish) | Trans-for-a-Period Excel chain |
| `scripts/run_softdent_master_learn.py` / `probe_softdent_master_report_modes.py` | Learn/probe Output Options modes |

Status JSON often under `C:\SoftDentFinancialExports\` (`softdent_money_widget_pull_status.json`, daily pull status).

### Observed live failure modes (learned)
1. Daysheet → SoftDent opened **Printer** wait → pull aborted (correct refuse)  
2. Collections → no Save dialog / no SDWIN workbook for SaveCopyAs  
3. SoftDentExportReports mirror copy → PermissionError (non-blocking if ReportExports lands)  
4. 64-bit Python automating 32-bit SoftDent → pywinauto warning (still works with caveats)

---

## 5. After SoftDent: how data becomes NR2 web

```
SoftDent UI export
  → C:\SoftDentReportExports   (Excel/CSV from GUI)
  → C:\SoftDentFinancialExports  (status, gold CSV drop, era\, learn JSON)
  → import_sync / refresh_softdent_period_imports
       ├─ Account Aging → softdent_ar_aging.csv (softGap uses file mtime; hal-10613 retouches when OPS export newer)
       ├─ Register/Daysheet → dashboard period rows / daysheet_totals
       └─ Claims/procedures/schedule CSVs → bundle.softdent.*
  → https://127.0.0.1:8765 SoftDent / Financial / Claims / A/R widgets
```

**NR2 SoftDent page does not drive SoftDent menus.** Staff or scripts export first; Sync second.

Parallel (not period-close $): Sensei Gateway / `sd_*` for schedule/util.

---

## 6. SoftDent money honesty map (learned hard truths)

| Fact | Meaning for pulls / widgets |
|------|-----------------------------|
| Register **Ins Plan Collections = $0** is often SoftDent ground truth | Do **not** re-export Register hoping Ins Plan becomes > 0 |
| Regular Collections carry most patient pay | Ins/Patient split stays empty when insurance ≤ 0 and patient-only |
| Gap code **`ERA_835_REQUIRED`** | Need real payer `.835` under `C:\SoftDentFinancialExports\era` — SoftDent menu Excel cannot invent remits |
| Gap code **`GOLD_CSV_MISSING`** | Insurance Income Print Preview ≠ gold InsCo×ADA payment lines; need Carestream line-item CSV/`insurance_payments_YYYYMMDD.csv` |
| Claims `DenialReason` = “Awaiting insurance response” | **Not** a denial code — denial-pareto correctly stays empty |
| Aging ≠ Daysheet A/R | Carestream: different account include rules |

---

## 7. HAL SoftDent knowledge (program replies)

| Helper / policy | Teaches staff |
|-----------------|---------------|
| `format_softdent_signon_hal_reply` | Launch + Sign On (never prints password) |
| `format_softdent_widget_path_hal_reply` | Excel → ReportExports → refresh |
| `format_softdent_account_tx_excel_hal_reply` | Trans for a Period / Format 1 |
| `format_softdent_data_access_hal_reply` | Desktop vs DB doctrine |
| `format_master_reports_hal_reply` | Master financial-close catalog |
| Gateway policies | gold-csv-drop, print-preview-audit, outstanding-claims, ERA inbox, InsCo×ADA |

`config/hal_policy.yaml`: never fabricate SoftDent import data; no SoftDent write-back from HAL.

---

## 8. Official Carestream SoftDent Help (web)

| Topic | URL |
|-------|-----|
| Using Online Help | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/DE1055_SD_Wkbk/Using_Online_Help.htm |
| Tutorial | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/Tutorial.htm |
| Register reports | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/RegstrRpt.htm |
| Daysheet | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/Daysheet.htm |
| Daily Register | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/DayRegRpt.htm |
| Account Aging | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/ActAgeRp.htm |
| Account Transactions list | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/ActTxLst.htm |
| Trans for a Period (PDF) | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/assets/docs/SD_Trans_for_a_Period_JA_FINAL.pdf |
| Keystroke sheet | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/OH_DE1010/KystrkSht.htm |
| Install guide (PDF) | https://help.carestreamdental.com/rh/web/server/SoftDent/projects_responsive/DE2000_SDConfig/PDFs/DE1000_SD_InstallGde.pdf |
| Sensei SoftDent Support | https://gosensei.com/softdent-support/ |

**Inside SoftDent:** Help → SoftDent Help, or **F1**.

Note: `support.carestreamdental.com` has been DNS-dead in recent OPS notes — prefer Sensei / help.carestreamdental.com.

---

## 9. What we still do *not* know (honest residual)

1. ~~Full SoftDent product feature matrix~~ → **encoded** in `softdent_product_kb.json` (2040 Help TOC topics + 13 report categories). Full topic *prose* remains in local CHM / F1, not verbatim in git.  
2. Guaranteed Excel path for Insurance Income / Writeoff on v19.1.4 (product limitation — Preview only)  
3. Reliable Collections/Daysheet automation every run (Printer/Save dialog flakes remain)  
4. SoftDent ODBC table maps for gold until Carestream/IT documents them  
5. Live payer ERA portals (Delta/MetLife/Availity download menus) — OPS files, not SoftDent menu catalog  

Program entry points: `softdent_product_kb.py`, HAL `policy:softdent-product-kb`, `GET /api/apex/hal/softdent-kb`, doc `docs/SOFTDENT_FULL_PRODUCT_KB_2026-07-13.md`.

---

## 10. Canonical in-repo SoftDent learning shelf

| Doc | What it teaches |
|-----|-----------------|
| `docs/SOFTDENT_LEARN_EVERYTHING_REPORT_2026-07-13.md` | **This report** |
| `docs/SOFTDENT_FULL_PRODUCT_KB_2026-07-13.md` | Full SoftDent product KB wiring |
| `softdent_product_kb.json` / `softdent_product_kb.py` | Program-readable SoftDent Help TOC + report catalog |
| `docs/SOFTDENT_WEB_MANUAL_AND_REPORT_2026-07-13.md` | SoftDent Help vs NR2 SoftDent web page |
| `docs/SOFTDENT_GUI_RESEARCH_EXPORT_2026-07-12.md` | Menus, Output Options, keyboard |
| `docs/SOFTDENT_WIDGET_DATA_PATHS_2026-07-12.md` | Widget → SoftDent source |
| `docs/SOFTDENT_ACCOUNT_TX_EXCEL_WEB_VALIDATE_2026-07-12.md` | Trans Excel live validation |
| `docs/SOFTDENT_SIGNON_PROGRAM_WIRING_2026-07-12.md` | Sign On env wiring |
| `softdent_gui_menu_map.json` | Machine report catalog |
| `.cursor/rules/softdent-desktop-gui.mdc` | Always-on hard rules |

---

## 11. One-page operator cheat sheet

```
1. Launch CS SoftDent Software.lnk (-sus)
2. Sign On COMPUTE / computer
3. Reports → <report> → Output Options → Excel (or Print Preview) → Enter
4. Setup dates / doctor 999 → OK
5. Save / SaveCopyAs → C:\SoftDentReportExports
6. If Printer wait → Cancel (Alt+C)
7. NR2 https://127.0.0.1:8765 → SoftDent → Sync
8. Never invent $0 to fill empty widgets
```

**Automated equivalent:**  
`python scripts\run_softdent_money_widget_pull.py --reports register,daysheet,aging,collections`

---

## 12. Closing

NR2 and this agent now have a **complete learned map** of SoftDent **run + pull-report** behavior for this office’s money/ops close cycle, grounded in Carestream Help + live automation catalogs + OPS failures. SoftDent as a whole dental PMS still has surfaces outside that map; for those, use SoftDent’s own Web Help (**F1**).
