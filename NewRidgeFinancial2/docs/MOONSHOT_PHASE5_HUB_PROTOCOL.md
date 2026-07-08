# Moonshot Phase 5 — SideNotes Hub Broadcast Protocol

**Date:** 2026-07-07  
**Build:** `hal-10094`  
**Ports:** Workstation `8766` → Financial HAL `8765`

## Implementation status (hal-10094)

- `hal_hub.hub_notify_access_ok()` — validates `X-Hub-Token` first; then `Origin` (8766 / `NR2_HUB_ORIGIN`) **or** loopback `8765` hero-metrics POST from the financial hub
- `hal_hub.hub_last_broadcast_access_ok()` — validates `X-Hub-Token` on GET
- `nr2_http_server._lan_hal_hub_access_ok()` — routes hub APIs through the checks above
- Hero metrics mirror: financial hub `POST /api/hub/notify` with `kind: "hero-metrics"` + token → workstation polls `GET /api/hub/last-broadcast` on **8765** via `HalHubClient.fetchLastBroadcast()` (Tier S3)
- Broadcast metadata never includes message body text (`record_hub_broadcast` strips `text`)

## Manual sign-off (operator)

1. Start 8765 (`StartProgram.bat`) and 8766 (`StartWorkstation.bat`)
2. On 8766, send office message with target **Everyone**
3. Within ~15s, 8765 HAL SideNotes panel shows **OFFICE BROADCAST** badge — **no message body**
4. Load Financial page on 8765 — 8766 workstation shows hero KPI mirror strip within ~15s when metrics are present

## Purpose

When a workstation posts an office-wide message (targets `all` / `everyone`), the HAL Command Center on port 8765 shows an **OFFICE BROADCAST** badge on the SideNotes monitor. Message **text is never shown** on 8765 for routing-only compliance — only metadata (sender, time, channel).

## Endpoints (8765 / shared `nr2_http_server.py`)

| Method | Path | Role |
|--------|------|------|
| `POST` | `/api/hub/notify` | Record a broadcast signal (metadata only) |
| `GET` | `/api/hub/last-broadcast` | Poll latest broadcast for HAL badge / hero mirror |
| `GET` | `/api/hub/status` | Workstation reachability + last broadcast (8765 poll) |

## Authentication (Moonshot blocker — required)

| Header | Required | Notes |
|--------|----------|-------|
| `X-Hub-Token` | **Yes** on GET and POST | Shared secret from `GET /api/app-info` → `hubToken` |
| `Origin` | **Yes** on POST from 8766 | Workstation origin (`127.0.0.1:8766` / `localhost:8766`) or `NR2_HUB_ORIGIN` |
| Loopback 8765 | Hero metrics only | Financial hub may POST from `127.0.0.1:8765` with valid token (no 8766 Origin) |

POST without `X-Hub-Token` → **403**.

Token resolution (`hal_hub.py`):

1. `NR2_HUB_TOKEN` environment variable (operator override)
2. Else persisted file `app_data/nr2/hub_token.txt` (auto-generated on first use)

Clients store token as `window.NR2_HUB_TOKEN` after `/api/app-info` (see `desktop-bridge.js`, `app.js ensureHubToken()`).

## POST `/api/hub/notify`

Office broadcast (8766):

```json
{
  "from": "Front Desk",
  "target": "all",
  "channel": "office",
  "at": "2026-07-07T22:00:00.000Z"
}
```

Hero metrics (8765 loopback):

```json
{
  "kind": "hero-metrics",
  "from": "Financial8765",
  "target": "workstation",
  "pageId": "financial",
  "heroMetrics": [{ "label": "Collections", "value": "$42k", "hint": "MTD" }],
  "at": "2026-07-07T22:00:00.000Z"
}
```

Headers (workstation):

```
Origin: http://127.0.0.1:8766
X-Hub-Token: <hubToken from app-info>
Content-Type: application/json
```

Headers (financial hero publish):

```
X-Hub-Token: <hubToken from app-info>
Content-Type: application/json
```

Response:

```json
{
  "ok": true,
  "at": "2026-07-07T22:00:00.000Z",
  "from": "Front Desk",
  "channel": "office",
  "target": "all"
}
```

## GET `/api/hub/last-broadcast`

Headers:

```
X-Hub-Token: <hubToken from app-info>
```

Returns broadcast fields when present; `{ "ok": true }` when none. Workstation fetches **8765** (not 8766) — broadcast state lives in the financial hub process.

## Workstation flow (8766)

1. User sends office message with target **Everyone** / `all`.
2. `postOfficeChannelMessage()` routes via `HalHubClient.submitToHalHub` or `OfficeHub.appendMessage`.
3. On success, `notifyHubBroadcastAfterOfficeSend()` POSTs to `8765/api/hub/notify` via `HalHubClient.notifyHubBroadcast` with `Origin` + `X-Hub-Token`.
4. Full message still flows through `/api/office-channel` or `/api/hal-hub/inbound` — hub notify is **metadata only**.
5. SideNotes message list shows sender + time on each row; popups show `from` label (G4).

## HAL flow (8765)

1. `ensureHubToken()` loads `hubToken` from `/api/app-info`.
2. `refreshOfficeChannel()` polls office channel and calls `refreshHubBroadcastBadge()` with `X-Hub-Token`.
3. Badge reads `GET /api/hub/last-broadcast` → sets `window.__NR2_HUB_BROADCAST`.
4. `HalPage.hubBroadcastBadgeHtml()` renders **OFFICE BROADCAST** in SideNotes monitor heads.
5. `patchHubBroadcastBadgeDom()` updates badge without full HAL re-render.
6. `NR2Tier3.publishHeroMetrics()` POSTs hero KPIs with hub token after financial page load.

## SoftDent operatory data contract (Moonshot blocker)

Canonical export: `app_data/nr2/document_inbox/softdent/operatory_schedule.json`

```json
{
  "operatoryChairs": [
    {
      "name": "Op 1",
      "slots": [{ "time": "9:00 AM", "patient": "Smith", "procedure": "Prophy", "tone": "default" }]
    }
  ]
}
```

UI reads **only** `softdent.operatoryChairs` from the dedicated operatory export — no fallback field chain.

## Offline behavior

| Scenario | Expected |
|----------|----------|
| 8765 down, 8766 sends | Office send may succeed locally; hub notify fails silently; no 8765 errors |
| 8765 up, no broadcasts | Badge hidden; poll returns `{ ok: true }` |
| Missing / invalid hub token | 403 on hub routes; badge stays hidden |

## Operator manual sign-off

See `.local_logs/moonshot_financial_eval/OPERATOR_SIGNOFF_QB_SOFTDENT_SIDENOTES_2026-07-07.md`.

Automated Phase G checks: `node scripts/run-moonshot-operator-signoff.mjs` (#5 live, #15–17 offline).

## Implementation map

| File | Responsibility |
|------|----------------|
| `hal_hub.py` | Token, origin validation, broadcast state |
| `nr2_http_server.py` | REST routes, CORS, `hubToken` in app-info, `_lan_hal_hub_access_ok()` |
| `site/hal-hub-client.js` | `X-Hub-Token` on cross-port hub fetch; `fetchLastBroadcast()` |
| `site/nr2-tier3.js` | `publishHeroMetrics`, `pollHeroMirror` (8765 poll) |
| `site/app.js` | `ensureHubToken`, notify after send, poll + DOM patch |
| `site/hal-page.js` | Badge HTML in SideNotes monitor |
| `site/workstation-page.js` | SideNotes sender/time in message rows |
| `import_loader.py` / `operatory_schedule.json` | Canonical operatory export |
