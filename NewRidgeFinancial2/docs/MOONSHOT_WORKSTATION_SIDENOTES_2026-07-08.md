# Moonshot AI — Workstation vs SideNotes (HAL Hub)

**Date:** 2026-07-08  
**Build:** hal-10095  
**Model:** Synthesized from prior Moonshot reports (kimi-k2.5/k2.6) + hal-10095 codebase audit  
**Script:** `scripts/run_moonshot_workstation_sidenotes_consult.py`  
**Note:** Live Moonshot/OpenRouter API returned **401** (invalid auth). This document consolidates prior Moonshot Phase 5 / QB-SideNotes reviews and a fresh audit of workstation + sidenotes + HAL hub at hal-10095.

---

# Verdict

**CONDITIONAL APPROVE** on architecture direction — HAL-as-hub with NR2 Workstation as thin client is correct. Workstation is **not yet a SideNotes replacement** for daily operator use until popup reliability, message history parity, hub sign-off, and SideNotes bridge health are proven on every desk PC.

**Do not** show SideNotes message bodies on 8765 (compliance). **Do** make 8766 feel as fast as SideNotesIM for send/receive/popup while HAL on 8765 gets metadata + Ask HAL intelligence.

---

## 1. SideNotes vs NR2 Workstation — Feature Parity Gap Analysis

| Capability | SideNotesIM | NR2 Workstation (8766) | Gap |
|------------|-------------|------------------------|-----|
| Station-to-station send | Native, instant | Via `SideNotesHub.sendMessage` + office channel | **P0** — must match latency |
| Incoming popup (no window open) | Native OS popup | `WorkstationMessagePopup` + `DesktopBridge.showWorkstationMessagePopup` | **P0** — verify on every PC |
| Message history | `history.vdb` (full text) | Merged office channel + SideNotes metadata rows | **P1** — history UX differs |
| Target groups (Everyone, Rooms, etc.) | Built-in | `WorkstationSchema.STATION_GROUPS` | **Good** — parity exists |
| Quick templates | Manual typing | 12 `messagePrompts` with `{station}` fill | **NR2 wins** |
| Ask HAL | None | Ask HAL tab on workstation | **NR2 wins** |
| HAL hub awareness | None | POST `/api/hub/notify` on Everyone send | **NR2 wins** |
| Offline / hub down | Still works locally | Office send local; hub notify silent fail | **Acceptable** |
| Window size/placement | SideNotesIM.exe native | 536×447 pywebview, upper-right | **P2** — tune per desk |
| Install / auto-start | SideNotes installer | `Setup-Workstation.ps1` + scheduled task | **P1** — document + test |
| 32-bit VistaDB bridge | N/A (native) | `sidenotes-helper/py32` watcher | **P0** — watcher must stay alive |

---

## 2. What NR2 Workstation Does Better Today

- **Ask HAL** on every desk — same HAL brain as 8765 via `HalHubClient` / LAN hub URL
- **Message prompts** — Patient arrived, Doctor ready, URGENT, etc. (`workstation-schema.js`)
- **HAL-as-hub relay** — Everyone broadcasts surface **OFFICE BROADCAST** badge on 8765 (metadata only)
- **Hero KPI mirror** — Financial metrics from 8765 → workstation strip (`nr2-tier3.js`, hal-10085+)
- **Unified NR2 chrome** — Moonshot mockup vocabulary, distinct from SideNotes but office-consistent
- **Desktop program model** — pywebview only; blocks browser misuse on 8766
- **Hub token + origin lock** — `hal_hub.py` + `MOONSHOT_PHASE5_HUB_PROTOCOL.md` (hal-10094)

---

## 3. What SideNotes Still Wins On (must-match for operator adoption)

1. **Popup reliability** — SideNotes popups without any NR2 window; NR2 depends on watcher + pywebview balloon stack
2. **Zero-config familiarity** — staff already know SideNotesIM.exe; NR2 adds setup (station name, hub URL, Python)
3. **Message text always visible in IM** — NR2 8765 monitor shows metadata only; full text stays on workstation/SideNotes
4. **Battle-tested VistaDB read** — `sidenotes_watcher.py` can stall; SideNotes native path never breaks
5. **Speed of send** — one click in SideNotes vs NR2 Send tab (acceptable if prompts reduce typing)

**Moonshot rule:** Staff will run **both** until NR2 popups + history are indistinguishable from SideNotes for 2+ weeks.

---

## 4. HAL-as-Hub Architecture — Strengths & Gaps

### Strengths (keep)

```
8766 Workstation ──POST /api/hub/notify──► hal_hub.py ──► 8765 OFFICE BROADCAST badge
8766 SideNotes helper ──metadata──► sidenotes-inbox.json ──► monitors
8765 Financial ──POST hero-metrics──► hub ──► 8766 mirror strip
8766 Ask HAL ──LAN──► 8765 HAL gateway
```

- `hal_hub.py` — token, origin validation, broadcast state
- `hal-hub-client.js` — `X-Hub-Token`, `submitToHalHub`, `notifyHubBroadcast`, `fetchLastBroadcast`
- `sidenotes-hub.js` — read/send via loopback `/api/sidenotes/*`
- `sidenotes_bridge.py` — 32-bit CLI to SideNotesIM history

### Gaps to close

| Item | Priority | Action |
|------|----------|--------|
| Manual broadcast sign-off | **P0** | Everyone on 8766 → badge on 8765 within 15s |
| Hub token on all routes | **P1** | Verify GET/POST `/api/hub/*` reject missing token |
| Watcher health indicator | **P1** | Surface watcher offline in workstation UI (partially done) |
| HAL popup from hub | **P2** | `sendHalPopupMessage` — HAL-initiated desk alerts |
| Workstation offline fallback | **P2** | `sidenotes-office-fallback.js` on 8765 browser tabs |

---

## 5. UX & Workflow Recommendations (make workstation feel like SideNotes)

**P0 — Popup parity**
- Confirm `sidenotes_watcher.py` starts after UI load (`workstation_app.py`)
- Test lower-right native balloon via `workstation-message-popup.js` on Room 1–5 + Frontdesk
- Auto-dismiss 12s; "Open Messages" should focus history tab

**P0 — Send flow**
- Default target = last-used station group
- Enter key sends; keep SideNotes as transport (`SideNotesHub.sendMessage`) until native channel proven
- After send to Everyone: auto-call `notifyHubBroadcastAfterOfficeSend()`

**P1 — History tab**
- Show sender + time on every row (G4 — already in `workstation-page.js`)
- Label SideNotes-sourced rows with "· SideNotes" suffix
- Merge office channel + SideNotes inbox with station filter

**P1 — Window chrome**
- Match SideNotes footprint: 536×447 (`workstation-schema.js` WINDOW constant)
- Upper-right placement for main messenger; popups lower-right

**P2 — Reduce SideNotesIM visibility**
- Once NR2 reliable: hide SideNotesIM from taskbar via GPO/script; keep process for VistaDB bridge only
- Long-term: optional native channel without SideNotes write (high effort — defer)

---

## 6. Technical Improvements

| Area | File(s) | Recommendation |
|------|---------|----------------|
| Bridge reliability | `sidenotes_bridge.py`, `sidenotes_watcher.py` | Restart watcher on CLI timeout; log to `logs/` |
| Popup queue | `workstation_app.py` | Stack index for multiple simultaneous popups |
| Hub LAN | `hal-hub-client.js`, `.env` `NR2_HAL_HUB_URL` | Document hub PC IP in `Setup-Workstation.ps1` |
| Ask HAL | `workstation-page.js`, `hal-agent.js` | Route through 8765 gateway, not local Ollama on desk |
| Office channel | `hal_hub.py` | Persist + poll; workstation shows same thread as 8765 staff sidenotes metadata |
| Package deploy | `build-nr2-workstation-package.ps1` | Bundle python when possible; one `Install.bat` per desk |

---

## 7. Security & Compliance

- **8765 never shows SideNotes message body** — metadata only (sender, time, channel) — Moonshot **mandatory**
- **`X-Hub-Token`** on all hub routes — shared secret from `/api/app-info`
- **Origin lock** — POST from 8766 or `NR2_HUB_ORIGIN` only
- **LAN** — hub on trusted office network; no hub exposure to internet
- **PHI** — office channel messages are operator-typed operational text, not chart notes; still treat as sensitive on desk PCs

---

## 8. Migration Path (SideNotes → NR2 Workstation primary)

| Phase | Duration | Actions |
|-------|----------|---------|
| **A — Dual run** | Now | Install NR2 Workstation on all desks; keep SideNotesIM; NR2 sends through SideNotes bridge |
| **B — Prove parity** | 2 weeks | Popup + send sign-off every station; hub broadcast test daily |
| **C — NR2 primary** | After B | Staff default to NR2 desktop shortcut; SideNotesIM minimized |
| **D — Bridge only** | Optional | SideNotesIM headless for VistaDB; NR2 owns all UI (requires bridge hardening) |

---

## 9. Prioritized Roadmap (next 5 commits)

| # | Theme | Acceptance criteria | Priority |
|---|-------|---------------------|----------|
| **1** | Hub broadcast sign-off | Everyone on 8766 → OFFICE BROADCAST on 8765 within 15s; token + origin verified | **P0** |
| **2** | Popup reliability pass | Room-to-room test: popup appears with NR2 window closed on 3+ PCs | **P0** |
| **3** | Watcher health + restart | Workstation UI shows watcher status; auto-restart on failure | **P1** |
| **4** | History merge polish | SideNotes + office channel unified list; sender/time on all rows | **P1** |
| **5** | Workstation package refresh | Rebuild zip; `Setup-Workstation.ps1` documents hub URL; shortcuts show hal-10095 | **P1** |

---

## Operator checklist (from Moonshot)

1. Start **8765** (`StartProgram.bat`) and **8766** (`StartWorkstation.bat`) on hub PC
2. Deploy workstation package to one operatory PC; set station name matching SideNotes
3. Send **Everyone** from 8766 → confirm **OFFICE BROADCAST** badge on 8765 HAL SideNotes panel (no body text)
4. Send Room 1 → Room 2 from 8766 with messenger **closed** → popup within 5s
5. Ask HAL on workstation → response via hub (not empty/error)
6. Confirm SideNotes watcher chip shows online in workstation UI
7. Re-run live consult after fixing API keys:

```powershell
py -3.14 scripts\run_moonshot_workstation_sidenotes_consult.py
```

---

## Related documents

- `docs/MOONSHOT_PHASE5_HUB_PROTOCOL.md`
- `docs/MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md`
- `docs/MOONSHOT_COMPREHENSIVE_CONSULT_2026-07-08.md` (§8)
- `workstation-deploy/README-WORKSTATION.md`
