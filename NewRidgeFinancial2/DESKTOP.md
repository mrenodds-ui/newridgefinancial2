# NewRidgeFinancial 2.0 — Browser App

Browser-based mission-control program for staff pages and HAL. The UI loads from `site/` over loopback HTTP at **http://127.0.0.1:8765/**.

> **NR2 Workstation** (operatory messaging, popups) is a separate **desktop-only** app on port 8766. This guide is for the financial / Start Program browser app only.

## Launch (staff)

1. Double-click **Start Program** (`StartProgram.bat` at repo root).
2. Your default browser opens **http://127.0.0.1:8765/** automatically.
3. Do not open `site/index.html` directly as a `file://` page for daily work.
4. After git pull or schema changes, close the browser tab and run Start Program again.

## Verify the correct build loaded

| Check | Expected |
|-------|----------|
| Browser tab title | `NewRidgeFinancial 2.0 (hal-XX)` |
| Sidebar footer | `Design hal-XX` |
| Navigation | Grouped sections: Overview, Clinical, Revenue, Operations |
| Financial page | Colored hero, filter pills, insight strip |

If boot fails, the page shows an error screen instead of silently falling back to the old layout.

## Developers

### Bump build version (after schema or shell changes)

```powershell
node scripts/bump-nr2-build.mjs hal-95
cd NewRidgeFinancial2
node validate-pages.mjs
node validate-hal.mjs
```

Or auto-increment: `node scripts/bump-nr2-build.mjs`

Updates: `nr2-build.json`, `site/nr2-build.json`, `site/moonshot-page-registry.js`, all `?v=` tags in `site/index.html`.

### Validate before launch

Start Program runs validators automatically. To skip (emergency only):

```powershell
powershell -File scripts/start_program.ps1 -SkipValidation
```

Manual:

```powershell
powershell -File scripts/Invoke-NR2Validators.ps1
```

### Desktop shortcuts

Refresh canonical shortcuts:

```powershell
powershell -File scripts/Refresh-NR2-DesktopShortcut.ps1
```

Audit all NR2-related shortcuts:

```powershell
powershell -File scripts/Audit-NR2-DesktopShortcuts.ps1 -VerboseLinks
powershell -File scripts/Audit-NR2-DesktopShortcuts.ps1 -FixShortcuts
```

### Architecture

```
StartProgram.bat
  → scripts/start_program.ps1
  → scripts/start_nr2_browser.ps1   (port 8765, stops prior PID, runs validators)
  → NewRidgeFinancial2/browser_app.py
      → loopback HTTP → site/index.html
          → moonshot-page-registry.js + nr2-moonshot-mockup-chrome.js (canonical shell)
          → desktop-boot.js (boot gate)
          → app.js
```

Build manifest: `NewRidgeFinancial2/nr2-build.json`  
Local SQLite state: `app_data/nr2/`

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Old flat pages, no hero | Stale shortcut or zombie process | Kill pythonw on 8765, run Audit script, Refresh shortcuts |
| Boot error: mixed versions | Hand-edited index.html | Run bump script or fix all `?v=` tags |
| Server/JS version mismatch | Server not restarted after bump | Close tab, run Start Program again |
| "Page not found" | Wrong launcher or backup folder copy | Confirm shortcut targets repo `StartProgram.bat` |
| NR2 server offline banner | Server not running | Run StartProgram.bat |

Legacy React mockup in `frontend/` is dev-only and is **not** the production program.
