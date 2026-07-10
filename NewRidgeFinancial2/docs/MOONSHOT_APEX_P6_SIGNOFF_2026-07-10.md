# NR2-Apex Bridge — P6 Production Hardening & Operator Sign-Off

**Date:** 2026-07-10  
**Build:** `hal-10240`  
**Epoch:** `nr2-apex`  
**Mode:** starship bridge (sidebar + ticker + fixed mosaic + interactive narratives)

## Delivered (P0 → P6 + Starship S1–S5)

| Phase | Result |
|-------|--------|
| P0 Wipe | Mockup/moonshot retired from load path; backup + Rollback-Apex-P0.ps1 |
| P1–P3 | Apex shell, tokens, widget engine, backend feeds |
| P4 | All 11 pages real-data widgets |
| P5 | Silent refresh, HAL status panel, print packets |
| Starship | Fixed mosaic, sidebar, ticker, interactive narratives |
| **P6** | Ticker 10s cache, Mute Ticker, responsive mosaic, Rollback-Apex-Bridge.ps1, this sign-off |

## Operator checklist

- [ ] Hard-refresh https://127.0.0.1:8765/ shows `hal-10240` in sidebar
- [ ] Ticker scrolls; **Mute Ticker** pauses motion
- [ ] Sidebar navigates all 11 pages
- [ ] Financial mosaic widgets are fixed-size (not elongated full-width bars)
- [ ] Narratives opens 3-pane composer (not KPI stubs)
- [ ] HAL page keeps right-rail chat
- [ ] Sync / Print icons work
- [ ] No invented dollar amounts on empty imports

## Rollback

```powershell
powershell -ExecutionPolicy Bypass -File NewRidgeFinancial2\scripts\Rollback-Apex-Bridge.ps1
```

Full pre-Apex wipe rollback (nuclear):

```powershell
powershell -ExecutionPolicy Bypass -File NewRidgeFinancial2\scripts\Rollback-Apex-P0.ps1
```

## API surface (bridge)

- `GET /api/apex/widgets/<page>`
- `GET /api/apex/ticker` (10s server cache)
- `GET /api/apex/hal/status`
- `POST /api/apex/sync/trigger`
- `POST /api/apex/print/view` → packet URL
- `GET /api/apex/narratives/structure`
- `POST /api/apex/narratives/generate`
- `POST /api/apex/narratives/print-packet`

## Sign-off

Operator approval closes the Moonshot redesign + starship bridge track for this build.

Reply **SIGNED OFF** when the checklist above is acceptable, or list defects to fix.
