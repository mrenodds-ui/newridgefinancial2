# NewRidgeFinancial 2.0

Single-window desktop mission-control program for New Ridge Family Financial.

The legacy program in `_legacy/` is for reference only and is not used here.

## Run

Double-click `StartNewRidgeFinancial2.bat` (repo root), or run:

```powershell
scripts\start_nr2_1966.ps1
```

The launcher opens one desktop app window. It does not start a localhost
server and does not open Chrome.

## Files

```
NewRidgeFinancial2/
  desktop_app.py     single-window pywebview app launcher
  local_store.py     local SQLite state store
  site/
    index.html        desktop app shell
    styles.css        mission-control shell styling
    app.js            internal routing and local app state
    page-views.js     real client-side screens for program pages
    hal-page.js       real HAL Command Center screen
    desktop-bridge.js local file + SQLite bridge
```

## Stop

`StopNewRidgeFinancial2.bat`
