# NR2 Office Workstation — Install Package

Drop this folder on each operatory / front-desk PC. It runs **Send Message**, **Ask HAL**, and **desktop popups** without installing the full financial app.

## Requirements

- Windows 10/11 x64
- **SideNotesIM** installed (for local message history + popups)
- Network access to the **HAL hub PC** (Start Program, port **8765**)
- **Python 3.11+** on the PC *only if* the package was built without a bundled `python\` folder — Setup will create one automatically

## Install (each workstation)

1. Copy **`NR2-Office-Workstation.zip`** to the PC and extract to e.g. `C:\NR2-Workstation\`.
2. Double-click **`Install.bat`**.
3. Enter:
   - **Station** — `Room 1`, `Frontdesk 1`, etc. (must match SideNotes)
   - **HAL hub URL** — e.g. `http://192.168.1.50:8765` (the Start Program PC on your LAN)
4. Setup creates `.env`, desktop + startup shortcuts, and starts the workstation in the background.

Popups appear in the lower-right without opening the messenger window.

## Daily use

- **Desktop → NR2 Workstation** — open Send Message / Ask HAL
- App also auto-starts at sign-in (startup shortcut) unless you used `-NoStartup` during setup

## Silent / scripted install

```powershell
powershell -ExecutionPolicy Bypass -File Setup-Workstation.ps1 `
  -Station "Room 4" `
  -HalHubUrl "http://192.168.1.50:8765" `
  -Quiet
```

Add `-NoStartup` to skip the auto-start shortcut.

## Build the zip (hub / dev PC)

From the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-nr2-workstation-package.ps1
```

Output:

- `dist\NR2-Office-Workstation\` — folder to copy
- `dist\NR2-Office-Workstation.zip` — hand out to each desk

## Uninstall

1. Delete startup shortcut: Win+R → `shell:startup` → remove **NR2 Workstation.lnk**
2. Delete desktop shortcut
3. Delete the install folder (e.g. `C:\NR2-Workstation\`)

## Logs

`logs\nr2-workstation.out.log` and `logs\nr2-workstation.err.log` in the install folder.
