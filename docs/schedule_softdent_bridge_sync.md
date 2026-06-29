# Schedule HAL Import Sync

Use the NR2 import automation scripts. The retired `scheduled_softdent_bridge_sync.ps1` and related legacy bridge scripts must not be used.

## One-time setup (Task Scheduler)

1. Open Task Scheduler (`Win+R` → `taskschd.msc`).
2. Create Task → Name: `New Ridge HAL Import Sync`
3. Triggers: repeat every 5 minutes (or your preferred interval).
4. Action: Start a program
   - Program: `powershell.exe`
   - Arguments:
     ```
     -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\import-automation\Sync-HAL-Imports.ps1"
     ```
5. Optional: pass explicit source overrides (otherwise `.env` is loaded automatically):
   ```
   -File "...\Sync-HAL-Imports.ps1" -SoftDentSource "D:\exports\softdent" -QuickBooksSource "D:\exports\quickbooks"
   ```

Or register via:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\import-automation\Register-HAL-Import-Automation.ps1"
```

## Manual verification (read-only)

```powershell
powershell -ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\import-automation\Sync-HAL-Imports.ps1"
python C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\import_sync.py
node C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\validate-hal.mjs
node C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\validate-pages.mjs
```

## Authority

- **Sync script:** `NewRidgeFinancial2/import-automation/Sync-HAL-Imports.ps1`
- **Python authority:** `NewRidgeFinancial2/import_sync.py`
- **Import cache:** `app/data/imports/` (gitignored)

Sync copies and transforms export files only. It never writes to SoftDent or QuickBooks.

## Retired scripts (do not use)

- `scripts/scheduled_softdent_bridge_sync.ps1`
- `scripts/sync_softdent_bridge.ps1`
- `scripts/watch_softdent_bridge.ps1`
