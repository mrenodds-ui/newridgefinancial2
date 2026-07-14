# SoftDent widget data paths (how widgets get data)

**Date:** 2026-07-12  
**Doctrine:** Hybrid — SoftDent **desktop Excel** is source of truth for period financial totals; **database / Sensei / `sd_*`** is faster for operational detail.

## Canonical flow

```
SoftDent desktop UI (Sign On → Output Options → Excel → Enter → save)
  → C:\SoftDentReportExports  (+ SoftDentFinancialExports)
  → refresh_softdent_period_imports / import_sync
       ├─ Register/Daysheet Excel → period stubs / daysheet_totals
       ├─ sync_dashboard_period_rows → softdent.dashboard periods
       └─ claims/AR/procedures CSV → bundle.softdent.*
  → load_import_bundle()
  → Apex widget builders (Financial / SoftDent / A/R / Claims / OM)

Parallel (ops, not period-close $):
Sensei / ODBC → sd_* sqlite → schedule / util / dossier widgets
```

Widgets **never** call SoftDent UI directly. Desktop path is export → inbox → refresh → bundle.

## Source key

| Source | Meaning |
|--------|---------|
| `desktop_excel` | SoftDentReportExports Register `.xls` (and related desktop dumps) driving gap/guidance |
| `analytics_db` | Dashboard period rows after Excel/CSV promote (`daysheet_totals`, period sync) |
| `inbox_csv` | SoftDent document inbox CSV/JSON (`claims`, `ar`, `procedures`, …) |
| `sd_sqlite` | SoftDent operational `sd_*` tables (Sensei/ODBC) |
| `sensei` | Sensei Gateway / operatory chairs / schedule exports |
| `mix` | SoftDent + QuickBooks (or other) join |
| `computed` | Diagnostics / guidance derived from imports |

## Primary SoftDent widgets

| Widget id | Label | Source | How |
|-----------|-------|--------|-----|
| softdent-collections-gap | Collections Gap (DEF-001) | desktop_excel | Inbox scan + dashboard period; honest gap until Ins Plan split |
| financial-vital-signs | Vital Signs | analytics_db | Latest dashboard production/collections |
| financial-dual-trend | Prod/Collections trend | analytics_db | Dashboard period sparks |
| ins-patient-split | Ins/Patient Split | analytics_db | Register Excel → insurance/patient on period row |
| payer-donut | Payer Mix | inbox_csv | Claims by Payer (else Ins/Patient fallback) |
| collection-bullet | Collection Efficiency | analytics_db | collections ÷ production |
| ar-aging-chart | A/R Aging | inbox_csv | Account Aging export buckets |
| provider-hbar | Provider Production | inbox_csv | procedures by provider |
| softdent-production-gap | Production Import | inbox_csv | procedures/production inbox |
| softdent-aging-gap | Patient Aging | inbox_csv | aging / softdent.ar |
| softdent-scheduling-gap | Scheduling | sensei | operatory / chairs |
| sd-vitals-strip | SoftDent Vitals | analytics_db | dashboard + SoftDent sections |
| sd-prod-trend | Production Trend | analytics_db | ≥2 dashboard production points |
| operatory-util-board | Operatory Board | sd_sqlite | sd_appointments preferred |
| weekly-schedule-list | Weekly Schedule | sd_sqlite | sd_appointments |
| provider-util-7d | Provider Util 7d | sd_sqlite | appointment counts (not $) |
| claims-* suite | Claims RCM | inbox_csv | SoftDent claims / claimStatus |
| sd-register-table | Register table | inbox_csv | procedures/register/transactions |
| period-dual-trend | Period comparison | analytics_db | MoM dashboard periods |
| production-vs-payroll | Production vs Payroll | mix | SoftDent prod × QB payroll |
| reconciliation-status | Reconciliation | mix | SoftDent × QB variance |
| c0-import-guidance | CPA import guidance | desktop_excel | Points at Register → inbox → refresh |

## Practical rule

| Widget need | Path to use |
|-------------|-------------|
| Correct period $ (prod/collections/Ins Plan) | Desktop SoftDent **Excel** → refresh → analytics dashboard widgets |
| Claims / AR buckets / procedure charts | SoftDent **CSV/JSON inbox** (often from desktop exports) |
| Today’s schedule / util | **`sd_*` / Sensei** (fast DB lane) |

Live learn log for Output Options: `C:\SoftDentFinancialExports\softdent_master_report_learn.json`  
Path comparison: `scripts/compare_softdent_desktop_vs_db.py`

## Validation (2026-07-12)

Ran `scripts/validate_softdent_widget_data_paths.py` → **7/7 PASS**  
Log: `C:\SoftDentFinancialExports\softdent_widget_path_validation.json`

| Claim | Result |
|-------|--------|
| Period $ depends on desktop Register Excel in SoftDentReportExports | PASS (July XLS parses) |
| Collections gap reads live bundle + inbox | PASS |
| Analytics dashboard / gap explains July money KPIs | PASS |
| OM/schedule can use populated `sd_*` | PASS |
| Claims/AR/procedure inbox exports present | PASS |
| Ins/Patient, payer, collection-bullet builders wired | PASS |
| Register parse honesty (Ins Plan $0 ⇒ format required) | PASS |
