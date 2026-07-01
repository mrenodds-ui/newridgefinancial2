# NewRidgeFinancial 2.0

Active program: **NewRidgeFinancial 2.0** — a single-window **pywebview desktop app**.

- No React/Vite runtime
- No FastAPI backend
- No localhost HTTP server
- Local SQLite + import cache only

Legacy code under `_legacy/` and `frontend/` is reference only.

## Run

Double-click:

```text
StartProgram.bat
```

Or:

```powershell
scripts\start_program.ps1
```

(`StartNewRidgeFinancial2.bat` is an alias to the same launcher.)

The launcher loads repo-root `.env` when present, then starts `NewRidgeFinancial2/desktop_app.py`.

## Stop

```text
StopProgram.bat
```

(`StopNewRidgeFinancial2.bat` is an alias.)

(`StopDashboard.bat` only kills old port listeners — it does not stop the desktop app.)

## Import data

Live SoftDent / QuickBooks exports sync into the NR2 document-inbox cache:

```text
app_data/nr2/document_inbox/softdent/
app_data/nr2/document_inbox/quickbooks/
```

Sync authority: `NewRidgeFinancial2/import_sync.py`  
Automation: `NewRidgeFinancial2/import-automation/Sync-HAL-Imports.ps1`  
Documents sync: `NewRidgeFinancial2/import-automation/Sync-HAL-Document-Sources.ps1`  
Pre-flight: `NewRidgeFinancial2/import-automation/Verify-HAL-Readiness.ps1`

Legacy `app/data/imports/` is migrated automatically on first sync.  
Legacy `scripts/sync_softdent_bridge.ps1` is **retired**.

## Layout

| Path | Role |
|------|------|
| `NewRidgeFinancial2/desktop_app.py` | Desktop launcher |
| `NewRidgeFinancial2/import_sync.py` | Export → import cache sync |
| `NewRidgeFinancial2/import_loader.py` | Import cache reader |
| `app_data/nr2/document_inbox/` | Canonical import cache (gitignored under `app_data/`) |
| `app_data/nr2/` | Desktop SQLite state |

See `NewRidgeFinancial2/README.md` for page/HAL details.
