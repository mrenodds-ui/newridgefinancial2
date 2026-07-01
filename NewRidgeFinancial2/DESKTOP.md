# NewRidgeFinancial 2.0 Desktop

Single-window pywebview app for staff pages and HAL. The UI loads from `site/` over loopback HTTP (not `file://`).

## Launch (staff)

1. Use **Start Program** on the desktop (`StartProgram.bat`).
2. Do not open `site/index.html` directly in a browser for daily work.
3. After git pull or schema changes, close the NR2 window and launch Start Program again.

## Verify the correct build loaded

| Check | Expected |
|-------|----------|
| Window title | `NewRidgeFinancial 2.0 (hal-XX)` |
| Sidebar footer | `Design hal-XX` |
| Navigation | Grouped sections: Overview, Clinical, Revenue, Operations |
| Financial page | Colored hero, filter pills, insight strip |

If boot fails, the app shows an error screen instead of silently falling back to the old layout.

## Developers

### Bump build version (after schema or shell changes)

```powershell
node scripts/bump-nr2-build.mjs hal-95
cd NewRidgeFinancial2
node validate-pages.mjs
node validate-hal.mjs
```

Or auto-increment: `node scripts/bump-nr2-build.mjs`

Updates: `nr2-build.json`, `site/nr2-build.json`, `site/page-schema.js`, all `?v=` tags in `site/index.html`.

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
  → scripts/start_nr2_desktop.ps1   (port 8765, stops prior PID, runs validators)
  → NewRidgeFinancial2/desktop_app.py
      → loopback HTTP → site/index.html
          → page-schema.js + page-chrome.js (canonical shell)
          → desktop-boot.js (boot gate)
          → app.js
```

Build manifest: `NewRidgeFinancial2/nr2-build.json`  
WebView profile (per schema): `app_data/nr2/webview/hal-XX/`

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Old flat pages, no hero | Stale shortcut or zombie process | Kill pythonw, run Audit script, Refresh shortcuts |
| Boot error: mixed versions | Hand-edited index.html | Run bump script or fix all `?v=` tags |
| Python/JS version mismatch | Desktop not restarted after bump | Close window, Start Program again |
| "Page not found" | Wrong launcher or backup folder copy | Confirm shortcut targets repo `StartProgram.bat` |

Legacy React mockup in `frontend/` is dev-only and is **not** the desktop app.
