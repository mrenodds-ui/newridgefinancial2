# Automated Export Instructions and Script Templates

## SoftDent Export

- The current bridge helper flow expects SoftDent exports to land in `C:\Users\mreno\SoftDentBridge\exports` with these filenames, then sync them into `SOFTDENT_IMPORT_DIR`:

```text
softdent_dashboard_data.json
softdent_claims_export.csv
softdent_clinical_notes_data.json
```

- If SoftDent supports command-line or scheduled exports, use templates like the following and keep the output filenames exact:

```powershell
# Example: Export SoftDent aggregate dashboard payload
Start-Process -FilePath "C:\Program Files\SoftDent\SoftDent.exe" -ArgumentList "/export:dashboard /output:C:\Users\mreno\SoftDentBridge\exports\softdent_dashboard_data.json"

# Example: Export SoftDent claims payload
Start-Process -FilePath "C:\Program Files\SoftDent\SoftDent.exe" -ArgumentList "/export:claims /output:C:\Users\mreno\SoftDentBridge\exports\softdent_claims_export.csv"

# Example: Export SoftDent clinical notes payload
Start-Process -FilePath "C:\Program Files\SoftDent\SoftDent.exe" -ArgumentList "/export:clinical_notes /output:C:\Users\mreno\SoftDentBridge\exports\softdent_clinical_notes_data.json"
```

- If only manual export is possible, export the files into `C:\Users\mreno\SoftDentBridge\exports` and then run `scripts\sync_softdent_bridge.ps1` from the dashboard repo. That script now copies them into the canonical `SOFTDENT_IMPORT_DIR` and refreshes the dashboard state.

### Additional Aggregate-Only Coverage Files

The canonical SoftDent import lane also accepts these aggregate-only report files directly into `SOFTDENT_IMPORT_DIR` or through `POST /softdent/import`. These files drive the dashboard's missing-report coverage matrix and should exclude PHI, raw ledger rows, patient identifiers, claim numbers, subscriber IDs, check numbers, account numbers, and procedure-level detail unless the filename below explicitly represents an approved aggregate export.

```text
outstanding_claims_by_company.csv
unsubmitted_claims.csv
insurance_income.csv
insurance_payment_distribution.csv
insurance_check_distribution.csv
treatment_plan_summary.csv
payment_plans.csv
```

- `outstanding_claims_by_company.csv`, `unsubmitted_claims.csv`, `insurance_income.csv`, `insurance_payment_distribution.csv`, and `insurance_check_distribution.csv` should be emitted as aggregate-only SoftDent coverage exports.
- `treatment_plan_summary.csv` and `payment_plans.csv` may also be satisfied by a supported treatment-plan/payment-plan entity report or a staged Database Extractor snapshot with aggregate count, amount, and status fields.

### Official Period Reports Required For Dashboard MTD/YTD Coverage

The bridge files above are not enough to satisfy the live financial summary's official-period validation. The current dashboard also checks for exact SoftDent accounting exports in `C:\SoftDentReportExports`, using `Reports > Accounting > Trans for a Period`, exported to CSV or TXT with the exact date range selected in SoftDent.

As of `2026-06-16`, the receipt at `C:\SoftDentFinancialExports\softdent_period_report_status.json` shows only a May report (`2026-05-01` through `2026-05-28`). To clear the current June warning, export these exact reports from SoftDent and place them under `C:\SoftDentReportExports`:

```text
Transactions for a Period: 06/01/2026 through 06/16/2026
Transactions for a Period: 01/01/2026 through 06/16/2026
Transactions for a Period: 01/01/2022 through 06/16/2026
```

Recommended filenames:

```text
transactions_for_period_2026-06-01_2026-06-16.csv
transactions_for_period_2026-01-01_2026-06-16.csv
transactions_for_period_2022-01-01_2026-06-16.csv
```

After exporting those files:

1. Place them in `C:\SoftDentReportExports`.
2. Run `C:\New folder\ops\softdent\automation\run_daily_softdent_refresh.ps1` or wait for the scheduled refresh.
3. Recheck `C:\SoftDentFinancialExports\softdent_period_report_status.json`.

The receipt generator at `C:\New folder\ops\softdent\periods\softdent_period_report_acquisition.py` is read-only. It scans existing exports and validates exact date ranges, but it does not generate missing SoftDent reports on its own.

- Canonical claims CSV columns:

```text
PatientName,MRN,ClaimId,ClaimStatus,Payer,Procedure,ServiceDate,DenialReason,ClaimAmount
```

- Canonical clinical notes JSON fields:

```text
PatientName,MRN,NoteDate,Provider,Procedure,ClinicalNote
```

## QuickBooks Export

- For QuickBooks Desktop, use the built-in export to Excel/CSV feature. If scripting is possible (e.g., via QuickBooks SDK or third-party tools), use a script like:

```powershell
# Example: Export QuickBooks report to CSV (replace with actual command if available)
# Requires QuickBooks SDK or third-party automation tool
# QBExport.exe --company "C:\Path\To\Company.qbw" --report "Profit and Loss" --output "C:\NewRidgeFamilyFinancial\app\data\imports\quickbooks\quickbooks_export.csv"
```

- If only manual export is possible, instruct users to export the required reports to:
  - `app/data/imports/quickbooks/`

- For the repo's recommended safety model, keep HAL read-only and use the Desktop architecture described in `docs/quickbooks_desktop_safe_architecture.md`.

## Scheduling (Optional)

- Use Windows Task Scheduler to run these scripts on a schedule for full automation.

---

## Next Steps

- Place exported files in `C:\Users\mreno\SoftDentBridge\exports`.
- Start `C:\Users\mreno\SoftDentBridge` if you want the bridge worker to stage them continuously.
- `scripts\refresh_from_softdent_and_verify.py` now syncs supported SoftDent and QuickBooks source files into the canonical import directories, refreshes pull-status state, and then recomputes the live financial summary.
- Direct operator uploads can also use `POST /softdent/import` or `POST /quickbooks/import` to write canonical import files immediately.
- HAL review uploads can use `POST /api/hal9000/staged-imports`; only approved `quickbooks_*.csv` staged files are picked up on the next refresh.
