# HAL SideNotes — Workstation Package

Drop this folder on each workstation to let HAL monitor SideNotesIM across the
whole office network. It reads only **routing metadata** (sender, recipient,
date/time, unread flag) — **never the message body**.

## What's in here

- `py32/` — bundled 32-bit Python runtime (needed for the SideNotesIM VistaDB engine)
- `sidenotes_watcher.py`, `vdb_reader.py`, `announcer.py` — the watcher
- `config.json` — settings (written for this station by the installer)
- `Install.bat` — **run this once** to set up this workstation
- `Setup-Station.ps1` — the guided setup the installer calls
- `Start-HAL-SideNotes.bat` — starts the watcher

## Requirements

- Windows
- **SideNotesIM installed** on the workstation (provides the VistaDB COM engine)
- Network access to the shared SoftDent hub:
  `C:\softdent\HAL-SideNotes-Workstation\data`
  (or the same folder through a UNC share such as
  `\\SERVER\softdent\HAL-SideNotes-Workstation\data`)

## Install (per workstation)

1. Copy this whole folder somewhere local, e.g. `C:\HAL-SideNotes\`.
2. Double-click **`Install.bat`**.
3. Answer two prompts:
   - **Station** — pick this computer's SideNotesIM station name
     (Server, Room 2, Room 3, Room 4, Room 5, Frontdesk 1, Frontdesk 2,
     Office Manager), or type a custom one.
   - **Shared data folder** — press Enter to use
     `C:\softdent\HAL-SideNotes-Workstation\data`, or type the UNC path that
     reaches the same shared folder.
4. It writes `config.json`, creates a **Desktop** shortcut and a **Startup**
   shortcut (auto-start at sign-in), and offers to start the watcher now.

That's it. Each station publishes `sidenotes-inbox-<station>.json` into
`C:\softdent\HAL-SideNotes-Workstation\data`, and HAL merges all stations into
one live monitor from that hub.

## Silent / scripted install

```powershell
powershell -ExecutionPolicy Bypass -File Setup-Station.ps1 `
  -Station "Room 4" `
  -SharedDataFolder "C:\softdent\HAL-SideNotes-Workstation\data" `
  -Quiet
```

Add `-NoStartup` to skip the auto-start shortcut.

## Station name must match

HAL merges these exact station files:

`sidenotes-inbox-server.json`, `-room-2`, `-room-3`, `-room-4`, `-room-5`,
`-frontdesk-1`, `-frontdesk-2`, `-office-manager`.

So set the station to one of: **Server, Room 2, Room 3, Room 4, Room 5,
Frontdesk 1, Frontdesk 2, Office Manager**. (Custom names work too, but then
add the matching file name to HAL's merge list in `site/app.js`.)

## Privacy

The watcher never opens the message text column (`dMessage`). Only sender,
recipient, message id, date/time, and the unread flag are read, and only those
fields are written to the inbox JSON. HAL announces the **sender only**.

## Stopping / uninstalling

- Stop: close the watcher window (or press Ctrl+C). Bell mute is restored on exit.
- Remove from startup: delete `HAL SideNotes.lnk` from
  `shell:startup` (Win+R → `shell:startup`).
- Uninstall: delete the folder and the two shortcuts.
