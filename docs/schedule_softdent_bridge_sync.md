# Schedule SoftDent Bridge Sync Every 30 Minutes

1. Open Task Scheduler (Win+R → `taskschd.msc`).
2. Click "Create Task..."
3. Name: `SoftDent Bridge Sync`
4. Security: Run whether user is logged on or not
5. Triggers tab: New → Begin the task: On a schedule
   - Settings: Daily
   - Repeat task every: 30 minutes
   - For a duration of: Indefinitely
6. Actions tab: New → Action: Start a program
   - Program/script: `powershell.exe`
   - Add arguments: `-ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\scripts\scheduled_softdent_bridge_sync.ps1"`
7. Conditions tab: Uncheck "Start the task only if the computer is on AC power" if desired.
8. OK, enter your password if prompted.

The script will run every 30 minutes, copy any of the expected dashboard, claims, and clinical-note exports from `C:\Users\mreno\SoftDentBridge\exports` into the canonical `SOFTDENT_IMPORT_DIR` location, and then trigger the refresh pipeline.

---

You can test by placing one or more of the required export files in `C:\Users\mreno\SoftDentBridge\exports` and running the script manually or waiting for the next scheduled run.
