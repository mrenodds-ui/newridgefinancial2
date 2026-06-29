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
StartNewRidgeFinancial2.bat
```

Or:

```powershell
scripts\start_nr2_1966.ps1
```

The launcher loads repo-root `.env` when present, then starts `NewRidgeFinancial2/desktop_app.py`.

## Stop

```text
StopNewRidgeFinancial2.bat
```

(`StopDashboard.bat` only kills old port listeners — it does not stop the desktop app.)

## Import data

Live SoftDent / QuickBooks exports sync into:

```text
app/data/imports/softdent/
app/data/imports/quickbooks/
```

Sync authority: `NewRidgeFinancial2/import_sync.py`  
Automation: `NewRidgeFinancial2/import-automation/Sync-HAL-Imports.ps1`

Legacy `scripts/sync_softdent_bridge.ps1` is **retired**.

## Layout

| Path | Role |
|------|------|
| `NewRidgeFinancial2/desktop_app.py` | Desktop launcher |
| `NewRidgeFinancial2/import_sync.py` | Export → import cache sync |
| `NewRidgeFinancial2/import_loader.py` | Import cache reader |
| `app/data/imports/` | Canonical import cache (gitignored) |
| `app_data/nr2/` | Desktop SQLite state |

See `NewRidgeFinancial2/README.md` for page/HAL details.
