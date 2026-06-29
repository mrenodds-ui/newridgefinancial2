# HAL SideNotes Watcher

A small **local** helper that lets HAL announce incoming **SideNotesIM** messages
out loud, and (optionally) suppress the SideNotesIM bell so HAL's voice is the
alert.

It watches the SideNotesIM message database (`history.vdb`) for newly-arrived
messages and, for each one:

- **announces the sender** via the Windows voice — e.g. _"New message from Room 4."_
- optionally **mutes the SideNotesIM bell** (per-app audio mute — reversible, no admin)
- writes a small JSON "inbox" that the HAL screen reads to show a live feed

## Privacy / PHI

The helper **never reads the message body** (`dMessage`). It only reads routing
metadata — sender, recipient, message id, date/time, and the unread flag — and
everything stays on this machine. Nothing is sent over the network. HAL
announces only the **sender** and the words _"new message"_, never the contents.

## How it works

SideNotesIM stores history in a legacy **VistaDB 2.1.7** file. There is no SQL
driver for it; the helper drives the vendor's 32-bit COM engine
(`VistaDBCOM20.DLL`) that ships with SideNotesIM. Because that engine is 32-bit
and in-process, the helper runs under a bundled **32-bit Python** (`py32/`).

To avoid ever locking the database SideNotesIM has open, each read is taken from
a transient copy of `history.vdb`.

```
SideNotesIM  ──writes──►  %APPDATA%\SideNotesIM\history.vdb
                                  │  (file change detected)
                                  ▼
                 sidenotes_watcher.py  ──reads routing only──►  VistaDB COM engine
                                  │
              ┌──────────────────────────────┼────────────────────┐
              ▼                              ▼                     ▼
   SAPI -> processed HAL WAV          mute bell (opt)     site/data/sidenotes-inbox.json
 "Good afternoon... from X"                                  (HAL reads this)
```

## Run it

Double-click **`run-sidenotes-helper.bat`**, or from a terminal:

```
py32\python.exe sidenotes_watcher.py
```

Leave it running. Press **Ctrl+C** to stop (this also restores the bell if it
was muted). On startup it baselines to the current newest message, so existing
history is **not** re-announced.

## Configuration — `config.json`

| Key | Default | Meaning |
| --- | --- | --- |
| `historyPath` | _(auto)_ | Path to `history.vdb`; blank = `%APPDATA%\SideNotesIM\history.vdb` |
| `simDir` | `C:\Program Files (x86)\SideNotesIM` | SideNotesIM install dir (holds the COM engine) |
| `myStation` | `Server` | This computer's SideNotesIM station name; its own outgoing messages are not announced |
| `pollSeconds` | `2.0` | How often the file is checked for changes |
| `announce` | `true` | Speak announcements |
| `voiceStyle` | `hal9000` | Voice preset: `hal9000` (slow, calm HAL 9000 style) or blank for default |
| `announceVaried` | `true` | Randomly vary the announcement wording each time (sender only; message text is never spoken) |
| `announceVariants` / `announceBroadcastVariants` | `[]` | Optional custom phrasing pools (use `{sender}`); blank = built-in HAL phrasings |
| `stationPeople` | office map | Maps SideNotes stations to staff names for announcements, e.g. Room 2 -> Mayci |
| `processedAudio` | `true` | Render speech to WAV, then locally lower/slow/smooth/compress it for a closer HAL tone |
| `announceTemplate` | HAL-style direct message phrase | Spoken text for direct messages |
| `announceBroadcastTemplate` | HAL-style broadcast phrase | Spoken text for "Everyone" messages |
| `announceScope` | `to_me_or_everyone` | `to_me_or_everyone` or `all` |
| `suppressBell` | `true` | Mute the SideNotesIM bell while running (restored on exit) |
| `duckMusic` | `true` | Lower background music during each announcement, then restore |
| `duckMusicProcesses` | `["Pandora.exe"]` | App executables to duck (add `msedge.exe` / `chrome.exe` for Pandora in a browser) |
| `duckMusicLevel` | `0.14` | Music volume while HAL is speaking (0.0–1.0; `0.14` ≈ 14%) |
| `voiceHint` | `""` | Substring to pick a voice (e.g. `Zira`); blank = default |
| `voiceRate` / `voiceVolume` | `-6` / `90` | SAPI rate (-10..10) and volume (0..100), before HAL WAV processing |
| `inboxPath` | _(auto)_ | Where the HAL inbox JSON is written |
| `inboxMax` | `50` | Max recent messages kept in the inbox |

> To stop muting the SideNotesIM bell, set `"suppressBell": false`.

Current staff-name map:

- `Room 2` -> `Mayci`
- `Room 3`, `Room 4`, `Room 5` -> `Nicole`
- `Frontdesk 1`, `Frontdesk 2` -> `Andrea and Jeannie`
- `Office Manager` -> `Steve`

## In HAL

The HAL screen's **SIDENOTESIM MONITOR** panel (in the SOURCE INTAKE card) shows
`LIVE`/`OFFLINE`, whether voice and bell-mute are on, **HAL 9000 voice** mode,
and the most recent senders. Use **TEST VOICE** in that panel to hear the
in-app HAL voice. HAL chat replies (short ones) are also spoken in the same style.

## First-time setup (already done on this machine)

The bundled `py32/` 32-bit Python has `comtypes`, `pycaw`, and `psutil`
installed. To recreate it elsewhere:

1. Download `python-3.12.x-embed-win32.zip`, extract to `py32/`.
2. In `py32/python312._pth`, uncomment `import site`.
3. `py32\python.exe get-pip.py`
4. `py32\python.exe -m pip install comtypes pycaw psutil`

SideNotesIM must be installed (provides the VistaDB COM engine), and .NET-free
native VistaDB 2.x runs against the system's installed runtimes.
