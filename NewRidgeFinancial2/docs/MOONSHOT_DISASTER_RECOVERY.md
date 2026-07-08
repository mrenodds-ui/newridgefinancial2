# Moonshot Disaster Recovery (hal-10073+)

Restore NR2 from a scheduled SQLite backup when the primary database is corrupt or missing.

## When to use

- NR2 fails to start with SQLite errors
- Import sync repeatedly corrupts `nr2.db`
- Operator intentionally rolled back after a bad import

## Prerequisites

- Stop NR2 (`StartProgram.bat` window closed; no process on ports 8765/8766)
- Backups in `app_data/nr2/backups/` from `backup_db.py` (7-day rotation)

## Restore procedure

1. **Stop the program** — close the desktop app and workstation; confirm nothing listens on 8765/8766.
2. **Locate backup** — pick the newest `nr2_YYYYMMDD_HHMMSS.db` under `app_data/nr2/backups/`.
3. **Preserve the damaged file** (optional) — rename current `app_data/nr2/nr2.db` to `nr2.db.broken`.
4. **Copy backup** — copy the chosen backup over `app_data/nr2/nr2.db`.
5. **Restart** — run `StartProgram.bat`; reload `https://127.0.0.1:8765/?v=hal-10074&__nr2_purge=1`.
6. **Refresh imports** — from Financial or QuickBooks page, trigger **Refresh Data** or QB sync if figures look stale.

## CPA / support exports

- CPA packets: `app_data/nr2/cpa_exports/` (regenerated on demand)
- Support bundles: `app_data/nr2/support_bundles/` (diagnostics only; no PHI)

## What is not restored

- In-flight HAL chat (session-only)
- Uncommitted browser localStorage (purge with `__nr2_purge=1` if schema drift)

## Verification

```powershell
cd NewRidgeFinancial2
py -3.14 -m pytest test_backup_db.py -q
node validate-hal.mjs
```

Expected: backup tests pass; HAL validation 103+ suites pass.
