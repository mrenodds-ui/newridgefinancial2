# NR2 Workstation + SideNotes + HAL Hub — Plan & Report

**Document type:** Operational plan and situation report  
**Date:** 2026-07-08  
**Build baseline:** `hal-10096`  
**Program:** NewRidgeFinancial 2.0 — Office messaging with HAL as central hub  
**Practice:** New Ridge Family Dental (solo)  
**Authoring:** Synthesized from Moonshot consultations, hal-10095 codebase audit, operator request  
**Related:** `MOONSHOT_WORKSTATION_SIDENOTES_2026-07-08.md`, `MOONSHOT_WORKSTATION_PLAN_COMPARISON_2026-07-08.md`, `MOONSHOT_PHASE5_HUB_PROTOCOL.md`

**Hub reload:** `https://127.0.0.1:8765/?v=hal-10096&__nr2_purge=1`  
**Workstation:** Desktop app via `StartWorkstation.bat` (pywebview on port 8766 — not a browser tab)

---

## Moonshot reconciliation (2026-07-08)

Moonshot **CONDITIONAL APPROVE (~90%)** on this plan. Corrections applied:

| Moonshot correction | Plan change |
|---------------------|-------------|
| Pilot **3 desks** before all 10 | H4 split → **H4a pilot** (hub + 2 rooms), **H4b remaining 7** |
| H1 is operator sign-off first | hal-10096 = watcher hardening + automated W1/W3/W4/W6/W7/W8 |
| Defer H3 until W2 popup PASS | H3 unchanged but marked **blocked on pilot W2** |
| Hub URL ping at install | `Setup-Workstation.ps1` → `Test-HalHubUrl` |
| Station name validation | `Test-StationName` against canonical list |

**Merged Moonshot roadmap:** hal-10096 (sign-off + watcher) → hal-10097–98 (popup stack) → hal-10099 (history, after pilot) → hal-10100 (pilot 3 desks) → hal-10101 (remaining desks).

See full comparison: `docs/MOONSHOT_WORKSTATION_PLAN_COMPARISON_2026-07-08.md`

---

## hal-10096 delivered (this build)

| Item | File(s) | Status |
|------|---------|--------|
| Watcher health in status API | `sidenotes_bridge.py` `sidenotes_watcher_health()` | ✅ |
| Watcher auto-restart supervisor | `sidenotes_bridge.py` `ensure_sidenotes_watcher()`, `workstation_app.py` | ✅ |
| Bridge live / offline in UI | `workstation-page.js`, `app.js`, `styles.css` | ✅ |
| HAL hub ping at install | `workstation-deploy/Setup-Workstation.ps1` | ✅ |
| Automated sign-off W1/W3/W4/W6–W8 | `scripts/run-moonshot-workstation-signoff.mjs` | ✅ |
| Manual W2/W5 | Operator — popup + kill/restart test | ☐ pending |

---

## Executive summary

New Ridge Financial 2.0 has the **correct architecture** for office messaging: **HAL on 8765 is the intelligence hub**, **NR2 Workstation on 8766 is the desk client**, and **SideNotesIM remains the VistaDB transport** during transition. Workstation already exceeds SideNotes on Ask HAL, message templates, hub broadcast, and KPI mirror — but **does not yet replace SideNotes** for daily staff use until popup reliability, watcher health, and hub sign-off are proven on every operatory PC.

### Verdict (Moonshot)

| Area | Status |
|------|--------|
| HAL-as-hub architecture | **APPROVE** — keep 8765 as system of record for HAL + metadata |
| Workstation program direction | **CONDITIONAL APPROVE** — not daily-primary until parity proven |
| SideNotes compatibility model | **APPROVE** — dual-run; bridge via `sidenotes-helper` |
| Compliance (no IM text on 8765) | **MANDATORY** — metadata only on financial screen |

### Strategic goal

Make NR2 Workstation **feel as fast and reliable as SideNotesIM** for room-to-room messaging and popups, while HAL on the hub PC gains **office-wide awareness** (broadcast badges, hero metrics, Ask HAL routing) without exposing SideNotes message bodies on the financial screen.

### Top outcomes (30-day horizon)

1. **Hub broadcast signed off** — Everyone send on 8766 → OFFICE BROADCAST badge on 8765 within 15s.
2. **Popup parity on 3+ desks** — Incoming message balloon with messenger window closed.
3. **Watcher health visible** — Every workstation shows SideNotes bridge online; auto-restart on failure.
4. **Workstation package deployed** — All rooms + front desk on `NR2-Office-Workstation.zip` with correct hub URL.
5. **Dual-run stable for 2 weeks** — Staff use NR2 shortcut daily; SideNotesIM stays installed as fallback.

### Estimated effort (solo operator/developer)

| Phase | Theme | Builds | Calendar |
|-------|-------|--------|----------|
| H1 | Hub sign-off + watcher hardening | hal-10096 | Week 1 ✅ code |
| H2 | Popup + watcher reliability | hal-10097–98 | Week 1–2 |
| H3 | History UX + send polish *(after pilot W2 PASS)* | hal-10099 | Week 2–3 |
| H4a | **Pilot deploy — 3 desks** (Moonshot) | hal-10100 | Week 3 |
| H4b | Remaining 7 desks | hal-10101 | Week 4 |
| H5 | Prove parity (operator) | — | Weeks 4–6 |

---

## Part I — Situation report (as-is)

### 1.1 Three-layer office stack

```
┌─────────────────────────────────────────────────────────────────┐
│  HAL HUB PC — Start Program (8765)                              │
│  Financial cockpit · HAL chat · SideNotes monitor (metadata)    │
│  hal_hub.py · office channel · hub token · SAPI on hub PC       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ LAN: NR2_HAL_HUB_URL
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Room 1 (8766) │   │ Room 2 (8766) │   │ Frontdesk     │
│ pywebview app │   │ pywebview app │   │ (8766)        │
│ Send · Ask HAL│   │ popups        │   │               │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
              SideNotesIM.exe + history.vdb (VistaDB)
              sidenotes-helper (32-bit py32) — read/send bridge
```

### 1.2 Component inventory

| Component | Port / path | Key files | Function |
|-----------|-------------|-----------|----------|
| **Financial + HAL** | 8765 | `browser_app.py`, `hal-page.js`, `app.js` | Owner cockpit, HAL agent, staff sidenotes metadata |
| **Office Workstation** | 8766 | `workstation_app.py`, `workstation-page.js` | Send Message, Ask HAL, desktop popups |
| **HAL hub** | 8765 API | `hal_hub.py`, `hal-hub-client.js` | Inbound queue, office channel, broadcast state, token |
| **SideNotes bridge** | helper | `sidenotes_bridge.py`, `sidenotes-hub.js` | 32-bit CLI → VistaDB read/send |
| **SideNotes watcher** | background | `sidenotes_watcher.py` | Metadata → `sidenotes-inbox.json` |
| **Popup watchers** | background | `sidenotes_popup_watcher.py`, `hub_message_watcher.py` | vdb + hub → desktop balloon |
| **Workstation package** | deploy | `workstation-deploy/`, `build-nr2-workstation-package.ps1` | Per-desk install zip |

### 1.3 What works today (hal-10095)

| Capability | Evidence | Status |
|------------|----------|--------|
| Workstation desktop shell | `workstation_app.py` pywebview, browser blocked | ✅ Implemented |
| Station groups (Everyone, Rooms, etc.) | `workstation-schema.js` `STATION_GROUPS` | ✅ Implemented |
| 12 message prompt templates | `workstation-schema.js` `messagePrompts` | ✅ Implemented |
| SideNotes send via bridge | `sidenotes-hub.js` → `/api/sidenotes/send` | ✅ Implemented |
| Office channel + hub inbound | `app.js` `postOfficeChannelMessage` | ✅ Implemented |
| Hub broadcast notify | `notifyHubBroadcastAfterOfficeSend` → `HalHubClient.notifyHubBroadcast` | ✅ Implemented |
| Hub token + origin lock | `hal_hub.py`, `MOONSHOT_PHASE5_HUB_PROTOCOL.md` | ✅ hal-10094 |
| Hero KPI mirror 8765→8766 | `nr2-tier3.js` `publishHeroMetrics` / `pollHeroMirror` | ✅ hal-10085+ |
| Desktop popups (3 paths) | SideNotes vdb watcher, hub watcher, in-app toast | ✅ Implemented — **needs sign-off** |
| Ask HAL on workstation | `workstation-page.js` Ask HAL tab | ✅ Implemented |
| SideNotes window size match | 536×447 in schema + `workstation_app.py` | ✅ Implemented |
| Auto-start at sign-in | `Register-NR2WorkstationStartup.ps1` | ✅ Package exists |

### 1.4 What is not proven

| Gap | Impact | Priority |
|-----|--------|----------|
| Manual 8766→8765 broadcast test not recorded | HAL hub unawareness risk | **P0** |
| Popup reliability unverified on operatory PCs | Staff stay on SideNotesIM | **P0** |
| Watcher stall / no auto-restart | Silent messaging failure | **P0** |
| History UX differs from SideNotes | Adoption friction | **P1** |
| Workstation not deployed to all desks | Dual-run incomplete | **P1** |
| Ask HAL LAN routing untested on remote desk | Empty responses at rooms | **P1** |

---

## Part II — Feature parity analysis

### 2.1 SideNotes vs NR2 Workstation

| Capability | SideNotesIM | NR2 Workstation | Winner | Gap action |
|------------|-------------|-----------------|--------|------------|
| Station-to-station send | Native | `SideNotesHub` + office channel | Tie | Match latency (P0) |
| Popup without opening window | Native OS | pywebview balloon + watchers | SideNotes | Sign-off every desk (P0) |
| Message history (full text) | `history.vdb` | Merged channel + metadata | SideNotes | Unified history tab (P1) |
| Target groups | Built-in | `STATION_GROUPS` | Tie | — |
| Quick templates | None | 12 prompts | **NR2** | — |
| Ask HAL | None | Ask HAL tab | **NR2** | Route via hub LAN (P1) |
| HAL hub broadcast badge | None | `/api/hub/notify` | **NR2** | Sign-off (P0) |
| Hero KPI mirror | None | 8765→8766 strip | **NR2** | — |
| Zero setup | Installed years ago | Station + hub URL + zip | SideNotes | Package + docs (P1) |
| Offline when hub down | Works | Local send OK; hub notify fails silent | SideNotes | Acceptable |

### 2.2 NR2 advantages to preserve (do not regress)

1. **Ask HAL** on every desk — routes to same HAL brain as 8765.
2. **Message prompts** — reduce typing for common operatory phrases.
3. **OFFICE BROADCAST badge** on HAL command center (metadata only — compliance).
4. **Hero metrics mirror** — financial KPIs visible at chairside without opening 8765.
5. **Desktop-only 8766** — prevents staff opening workstation in browser by mistake.
6. **Hub security** — `X-Hub-Token` + origin lock on cross-port calls.

### 2.3 SideNotes advantages to match (adoption blockers)

1. **Popup always works** — no dependency on NR2 window state.
2. **Instant familiarity** — one app, no hub URL configuration.
3. **Full text in IM** — staff read messages in SideNotesIM without opening NR2.
4. **Watcher-free native path** — VistaDB inside SideNotes process.

**Moonshot adoption rule:** Run both apps until NR2 popups + send are indistinguishable from SideNotes for **14 consecutive business days**.

---

## Part III — Target architecture (HAL as hub)

### 3.1 Message flows

**A — Room-to-room (operatory messaging)**

```
Staff types on 8766 → SideNotesHub.sendMessage → sidenotes_cli (32-bit)
    → SideNotesIM history.vdb → recipient SideNotesIM popup (legacy)
    → sidenotes_popup_watcher → WorkstationMessagePopup (NR2 balloon)
    → office channel append (hal_hub.py) for hub metadata
```

**B — Everyone broadcast (office-wide)**

```
8766 Send target=Everyone → postOfficeChannelMessage
    → notifyHubBroadcastAfterOfficeSend → POST 8765 /api/hub/notify
    → hal_hub.record_hub_broadcast (metadata only, no text)
    → 8765 HalPage hubBroadcastBadgeHtml → OFFICE BROADCAST
```

**C — Ask HAL (workstation → hub)**

```
8766 Ask HAL tab → HalHubClient / HAL gateway on 8765 (NR2_HAL_HUB_URL)
    → hal-agent.js on hub PC → Ollama hal-chat:8b
    → response returned to workstation UI
```

**D — Hero mirror (hub → workstations)**

```
8765 Financial page load → NR2Tier3.publishHeroMetrics → POST /api/hub/notify kind=hero-metrics
    → 8766 pollHeroMirror → KPI strip on workstation
```

### 3.2 Compliance boundary (non-negotiable)

| Surface | Message body | Allowed |
|---------|--------------|---------|
| SideNotesIM.exe | Full text | Yes — local desk |
| NR2 Workstation 8766 | Full text | Yes — operator typed |
| HAL financial 8765 | **Metadata only** | Sender, time, channel, badge |
| HAL chat / Ask HAL | Operational Q&A | Yes — not patient chart paste |

### 3.3 Background services on each workstation (`workstation_app.py`)

| Service | Env flag | Starts after UI |
|---------|----------|-----------------|
| SideNotes metadata watcher | `NR2_SIDENOTES_WATCHER=1` | Yes — deferred thread |
| SideNotes popup watcher | `NR2_SIDENOTES_POPUP_WATCHER=1` | Yes |
| Hub popup watcher | always (hub URL) | Yes — polls 8765 inbound |

---

## Part IV — Implementation plan

### Phase H1 — Hub sign-off & security (hal-10096)

**Goal:** Prove 8766→8765 broadcast path; document operator procedure.

| Task | File(s) | Acceptance |
|------|---------|------------|
| Verify `X-Hub-Token` on GET/POST `/api/hub/*` | `hal_hub.py`, `nr2_http_server.py` | 403 without token |
| Confirm origin lock for 8766 POST | `hal_hub.hub_notify_access_ok` | Non-8766 origin rejected |
| Record manual broadcast test | `docs/OPERATOR_PILOT_RUNBOOK.md` or sign-off log | PASS written |
| Extend sign-off script hub checks | `scripts/run-moonshot-operator-signoff.mjs` | Automated #5 PASS when servers up |

**Operator test (required before closing H1):**

1. Start 8765 + 8766 on hub PC.
2. On 8766, send message target **Everyone**.
3. Within 15s, 8765 HAL SideNotes panel shows **OFFICE BROADCAST** — no message body.
4. DevTools: `window.__NR2_HUB_BROADCAST` populated.

---

### Phase H2 — Popup & watcher reliability (hal-10097–98)

**Goal:** Popups appear with messenger closed on 3+ PCs; watcher self-heals.

| Task | File(s) | Acceptance |
|------|---------|------------|
| Watcher health chip always visible | `workstation-page.js` | Shows online/offline |
| Auto-restart watcher on CLI timeout | `sidenotes_bridge.py`, `workstation_app.py` | Restart within 30s of failure |
| Log watcher events | `logs/nr2-workstation.err.log` | PID start/stop/restart lines |
| Popup stack for simultaneous messages | `workstation_app.py` `_popup_lower_right_pos` | 2+ popups don't overlap |
| Hub popup watcher LAN test | `hub_message_watcher.py` | Remote desk receives hub-originated popup |

**Build hal-10097:** Watcher restart + health UI  
**Build hal-10098:** Popup stack + logging

**Operator test (required before closing H2):**

1. Hub PC + Room 1 + Room 2 workstations running; messenger **closed** on Room 2.
2. Room 1 sends to Room 2 → balloon within 5s on Room 2.
3. Kill sidenotes watcher → UI shows offline → auto-restart within 30s.
4. Repeat on Frontdesk 1.

---

### Phase H3 — History & send UX polish (hal-10099)

**Goal:** History tab feels like SideNotes inbox; send is one-keystroke fast.

| Task | File(s) | Acceptance |
|------|---------|------------|
| Unified history: office channel + SideNotes | `workstation-page.js` | Single sorted list |
| Sender + time on every row | `workstation-page.js` | G4 complete |
| SideNotes source label | `" · SideNotes"` suffix on bridged rows | Visible |
| Remember last target group | localStorage or station config | Default on open |
| Enter to send | send form handler | Works in message tab |

---

### Phase H4a — Pilot deploy (hal-10100) — Moonshot: 3 desks only

**Goal:** Prove messaging on hub PC workstation + two operatories before wider rollout.

| Pilot desk | Station | Role |
|------------|---------|------|
| Hub PC | Frontdesk 1 or Office Manager | HAL hub + workstation |
| Operatory A | Room 1 | Popup test |
| Operatory B | Room 2 | Popup test |

**Exit:** W1–W3 PASS for 7 consecutive business days → proceed H4b.

---

### Phase H4b — Remaining desks (hal-10101)

**Goal:** Deploy to Frontdesk 2, Rooms 3–5, Office Manager, Darkroom, Server after pilot week clean.

| Task | Acceptance |
|------|------------|
| Rebuild zip at hal-10101 | `dist/NR2-Office-Workstation.zip` |
| Roll out 7 remaining stations | All rows in station checklist checked |
| Document LAN firewall | Inbound TCP 8765 from office subnet on hub PC |

---

### Phase H4 — Package deploy (superseded by H4a/H4b)

~~Deploy all 10 stations in one step~~ — **replaced by Moonshot pilot-first model above.**

**Station checklist:**

| Station | SideNotes name | NR2 installed | Hub URL | Popup test |
|---------|----------------|---------------|---------|------------|
| Frontdesk 1 | Frontdesk 1 | ☐ | ☐ | ☐ |
| Frontdesk 2 | Frontdesk 2 | ☐ | ☐ | ☐ |
| Room 1 | Room 1 | ☐ | ☐ | ☐ |
| Room 2 | Room 2 | ☐ | ☐ | ☐ |
| Room 3 | Room 3 | ☐ | ☐ | ☐ |
| Room 4 | Room 4 | ☐ | ☐ | ☐ |
| Room 5 | Room 5 | ☐ | ☐ | ☐ |
| Office Manager | Office Manager | ☐ | ☐ | ☐ |
| Darkroom | Darkroom | ☐ | ☐ | ☐ |
| Server | Server | ☐ | ☐ | ☐ |

---

### Phase H5 — Prove parity (operator, no code)

**Goal:** 14 business days dual-run without SideNotes-only fallback.

| Week | Action |
|------|--------|
| 1 | Staff trained: NR2 shortcut primary, SideNotesIM fallback |
| 1–2 | Daily hub broadcast test (Everyone → badge) |
| 2 | Ask HAL used at least once per day per front desk |
| 3 | Zero popup failures logged |
| 4 | Operator sign-off: "NR2 primary" |

**Exit criteria for SideNotes-minimized mode:**

- [ ] All 10 stations popup PASS
- [ ] Hub broadcast PASS 14/14 days
- [ ] No watcher offline > 5 min without auto-recovery
- [ ] Staff prefer NR2 prompts over SideNotes typing (informal poll)

---

## Part V — Operator procedures

### 5.1 Hub PC (daily)

```powershell
# Start financial + HAL hub
C:\NewRidgeFamilyFinancial\StartProgram.bat
```

Confirm: `https://127.0.0.1:8765` loads; HAL chat responds.

### 5.2 Workstation PC (daily — automatic)

Workstation auto-starts at sign-in via scheduled task. Manual open:

```
Desktop → NR2 Workstation
```

**Do not** open `http://127.0.0.1:8766` in a browser.

### 5.3 First-time desk install

```powershell
# On hub/dev PC — build package
powershell -ExecutionPolicy Bypass -File scripts\build-nr2-workstation-package.ps1

# Copy dist\NR2-Office-Workstation.zip to desk PC, extract, run Install.bat
# Or silent:
powershell -ExecutionPolicy Bypass -File Setup-Workstation.ps1 `
  -Station "Room 4" `
  -HalHubUrl "http://192.168.1.50:8765" `
  -Quiet
```

### 5.4 Troubleshooting

| Symptom | Check | Fix |
|---------|-------|-----|
| No popup | `logs/nr2-workstation.err.log` | Restart NR2 Workstation; verify SideNotesIM running |
| Watcher offline chip | SideNotes watcher PID | `run-sidenotes-helper.bat` or restart workstation |
| Ask HAL empty | `NR2_HAL_HUB_URL` in desk `.env` | Point to hub PC IP:8765; re-run Setup or fix `.env`; hub must be running at install for ping |
| No OFFICE BROADCAST on 8765 | Hub token, both servers up | `ensureHubToken()`; resend Everyone from 8766 |
| Hub 403 | Token mismatch | Restart 8765; reload workstation |

---

## Part VI — Test & sign-off matrix

### 6.1 Automated

```powershell
node scripts\run-moonshot-workstation-signoff.mjs
```

Also (when 8765 + 8766 running): `node NewRidgeFinancial2\scripts\run-moonshot-operator-signoff.mjs` (#5 hub).

### 6.2 Manual (record in `.local_logs/moonshot_financial_eval/`)

| # | Test | Pass criteria |
|---|------|---------------|
| W1 | Everyone broadcast | Badge on 8765 ≤15s; no body text |
| W2 | Room→room popup | Balloon ≤5s; messenger closed |
| W3 | Ask HAL remote desk | Response from hub; not timeout |
| W4 | Hero mirror | KPI strip on 8766 after 8765 financial load |
| W5 | Watcher recovery | Offline chip → auto online ≤30s |
| W6 | Hub token reject | POST /api/hub/notify without token → 403 |
| W7 | SideNotes send parity | Message appears in SideNotesIM history |
| W8 | Dual popup paths | Both SideNotes vdb and hub inbound trigger balloon |

### 6.3 Sign-off record template

```markdown
# Workstation HAL Hub Sign-off
**Date:** YYYY-MM-DD
**Build:** hal-10xxx
**Operator:** ___________

| Test | Result | Notes |
|------|--------|-------|
| W1 | PASS/FAIL | |
| W2 | PASS/FAIL | |
...
```

---

## Part VII — Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| WS1 | SideNotes watcher stalls on VistaDB lock | Medium | High | Auto-restart; log PID; H2 |
| WS2 | Hub PC offline — desks lose Ask HAL | Medium | Medium | Local error message; SideNotes still works |
| WS3 | Wrong `NR2_HAL_HUB_URL` on desk | High | Medium | Setup script validation; README |
| WS4 | Staff ignore NR2, stay on SideNotes | Medium | High | Prompts + Ask HAL value; training |
| WS5 | Popup blocked by Windows focus | Low | Medium | pywebview always-on-top; test Win10/11 |
| WS6 | 32-bit py32 helper missing on desk | Low | High | Bundle python in zip; Install.bat check |
| WS7 | PHI on 8765 screen | Low | Critical | Metadata-only enforced in `hal_hub.py` |
| WS8 | LAN firewall blocks 8765 | Medium | Medium | Document inbound rule for office subnet |

---

## Part VIII — Commit roadmap summary

| Build | Phase | Deliverable |
|-------|-------|-------------|
| **hal-10096** | H1 | ✅ Watcher supervisor, health UI, hub ping, sign-off script |
| **hal-10097** | H2 | Watcher logging + popup stack polish |
| **hal-10098** | H2 | Popup stack + watcher logging |
| **hal-10099** | H3 | History merge + send UX *(after pilot W2)* |
| **hal-10100** | H4a | Pilot package — **3 desks** |
| **hal-10101** | H4b | Remaining 7 desks |

### Parallel work (not blocking workstation)

These remain in the main NR2 plan (`MOONSHOT_DETAIL_PLAN_REPORT_2026-07-08.md`) and run on the hub PC independently:

- SoftDent payment/adjustment fix (Phase B)
- Claims narrative assist (Phase D)
- QuickBooks empty states (Phase E)

Workstation phases **H1–H4** can proceed in parallel with hub data work.

---

## Part IX — Migration timeline

```
Now ────────────── Week 2 ────────────── Week 4 ────────────── Week 6+
 │                    │                    │                    │
 ▼                    ▼                    ▼                    ▼
Dual-run          H1+H2 complete       All desks deployed     NR2 primary
SideNotes + NR2   Popup sign-off       H3+H4 complete         SideNotes minimized
Hub sign-off      3+ desks PASS        Daily broadcast        (bridge only)
```

| Milestone | Target date | Owner |
|-----------|-------------|-------|
| H1 hub broadcast PASS | Week 1 | Developer + operator |
| H2 popup PASS (3 desks) | Week 2 | Operator |
| All 10 stations installed | Week 4 | Operator |
| 14-day dual-run complete | Week 6 | Operator |
| NR2 primary declaration | Week 7 | Operator |

---

## Part X — Related documents & scripts

| Document / script | Purpose |
|-------------------|---------|
| `docs/MOONSHOT_WORKSTATION_SIDENOTES_2026-07-08.md` | Moonshot consultation summary |
| `docs/MOONSHOT_PHASE5_HUB_PROTOCOL.md` | Hub API spec (token, notify, broadcast) |
| `docs/MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md` | Prior Moonshot SideNotes review |
| `docs/MOONSHOT_DETAIL_PLAN_REPORT_2026-07-08.md` | Full NR2 post-ceiling plan (data + HAL) |
| `workstation-deploy/README-WORKSTATION.md` | Desk install guide |
| `scripts/run_moonshot_workstation_sidenotes_consult.py` | Re-run Moonshot consult (fix API keys first) |
| `scripts/build-nr2-workstation-package.ps1` | Build deploy zip |
| `scripts/run-moonshot-operator-signoff.mjs` | Automated sign-off |

---

## Appendix A — Key code references

| Concern | Location |
|---------|----------|
| Workstation schema + stations | `site/workstation/workstation-schema.js` |
| Send + history UI | `site/workstation-page.js` |
| SideNotes bridge JS | `site/sidenotes-hub.js` |
| Hub client (token, notify) | `site/hal-hub-client.js` |
| Office send + broadcast | `site/app.js` `postOfficeChannelMessage`, `notifyHubBroadcastAfterOfficeSend` |
| Desktop popups | `site/workstation-message-popup.js`, `workstation_app.py` |
| Background watchers | `workstation_app.py` `_start_background_services` |
| Hub backend | `hal_hub.py` |
| 32-bit CLI bridge | `sidenotes_bridge.py`, `sidenotes-helper/sidenotes_cli.py` |

---

## Appendix B — Environment variables (workstation desk)

| Variable | Example | Purpose |
|----------|---------|---------|
| `NR2_HAL_HUB_URL` | `http://192.168.1.50:8765` | Hub PC on LAN |
| `NR2_SIDENOTES_MY_STATION` | `Room 3` | Must match SideNotes station name |
| `NR2_SIDENOTES_WATCHER` | `1` | Enable metadata watcher |
| `NR2_SIDENOTES_POPUP_WATCHER` | `1` | Enable vdb popup watcher |
| `NR2_WORKSTATION_START_HIDDEN` | `1` | Start minimized at sign-in |
| `NR2_HUB_TOKEN` | (auto) | Override hub token if needed |

---

**Next action:** Run `node scripts\run-moonshot-workstation-signoff.mjs` with 8765+8766 up, then complete manual **W2** (popup) and **W5** (watcher kill/recovery) on pilot desks.
