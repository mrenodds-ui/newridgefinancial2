# HAL Import Automation

This folder automates HAL's read-only import lane for SoftDent and QuickBooks export files.

## Defaults

- SoftDent source: `C:\Users\mreno\SoftDentBridge\exports`
- QuickBooks source: `C:\Users\mreno\QuickBooksExports`
- SoftDent destination: `C:\NewRidgeFamilyFinancial\app\data\imports\softdent`
- QuickBooks destination: `C:\NewRidgeFamilyFinancial\app\data\imports\quickbooks`

Override sources with:

```powershell
$env:NR2_SOFTDENT_EXPORT_SOURCE = "D:\Path\To\SoftDentExports"
$env:NR2_QUICKBOOKS_EXPORT_SOURCE = "D:\Path\To\QuickBooksExports"
```

Override HAL import destinations with `SOFTDENT_IMPORT_DIR` or `QUICKBOOKS_IMPORT_DIR`.

## Run Once

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\import-automation\Sync-HAL-Imports.ps1
```

## Seed Starter Import Files

If QuickBooks or SoftDent A/R widgets are empty and no live exports exist yet, copy the tracked read-only samples into HAL's import folders:

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\import-automation\Seed-HAL-Import-Samples.ps1
```

Use `-Force` to overwrite existing destination files.

## Watch Continuously

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\import-automation\Sync-HAL-Imports.ps1 -Watch
```

## Register Scheduled Task

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\import-automation\Register-HAL-Import-Automation.ps1
```

This registers `New Ridge HAL Import Sync` to run every 5 minutes.

## Safety Boundary

The automation only copies approved export files into HAL's local import folders.
It never writes to SoftDent, QuickBooks, payers, clearinghouses, or external services.
