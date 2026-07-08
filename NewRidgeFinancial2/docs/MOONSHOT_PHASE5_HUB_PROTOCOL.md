# Moonshot Phase 5 — SideNotes Hub Broadcast Protocol

**Date:** 2026-07-07  
**Build:** `hal-10090`  
**Ports:** Workstation `8766` → Financial HAL `8765`

## Implementation status (hal-10090)

- `hal_hub.hub_notify_access_ok()` — validates `Origin` (8766 / `NR2_HUB_ORIGIN`) **and** `X-Hub-Token`
- `hal_hub.hub_last_broadcast_access_ok()` — validates `X-Hub-Token` on GET
- `nr2_http_server._lan_hal_hub_access_ok()` — routes hub APIs through the checks above
- Hero metrics mirror: financial hub `POST /api/hub/notify` with `kind: "hero-metrics"` → workstation polls `GET /api/hub/last-broadcast` (Tier S3)

## Manual sign-off (operator)

1. Start 8765 (`StartProgram.bat`) and 8766 (`StartWorkstation.bat`)
2. On 8766, send office message with target **Everyone**
3. Within ~15s, 8765 HAL SideNotes panel shows **OFFICE BROADCAST** badge — **no message body**
4. Load Financial page on 8765 — 8766 workstation shows hero KPI mirror strip when present

## Purpose

When a workstation posts an office-wide message (targets `all` / `everyone`), the HAL Command Center on port 8765 shows an **OFFICE BROADCAST** badge on the SideNotes monitor. Message **text is never shown** on 8765 for routing-only compliance — only metadata (sender, time, channel).

## Endpoints (8765 / shared `nr2_http_server.py`)

| Method | Path | Role |
|--------|------|------|
| `POST` | `/api/hub/notify` | Record a broadcast signal (metadata only) |
| `GET` | `/api/hub/last-broadcast` | Poll latest broadcast for HAL badge |
| `GET` | `/api/hub/status` | Workstation reachability + last broadcast (8765 poll) |

## Authentication (Moonshot blocker — required)

| Header | Required | Notes |
|--------|----------|-------|
| `X-Hub-Token` | **Yes** on GET and POST | Shared secret from `GET /api/app-info` → `hubToken` |
| `Origin` | **Yes** on POST `/api/hub/notify` | Must be workstation origin (`127.0.0.1:8766` / `localhost:8766`) or `NR2_HUB_ORIGIN` |

Token resolution (`hal_hub.py`):

1. `NR2_HUB_TOKEN` environment variable (operator override)
2. Else persisted file `app_data/nr2/hub_token.txt` (auto-generated on first use)

Clients store token as `window.NR2_HUB_TOKEN` after `/api/app-info` (see `desktop-bridge.js`, `app.js ensureHubToken()`).

## POST `/api/hub/notify`

```json
{
  "from": "Front Desk",
  "target": "all",
  "channel": "office",
  "at": "2026-07-07T22:00:00.000Z"
}
```

Headers:

```
Origin: http://127.0.0.1:8766
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

Returns broadcast fields when present; `{ "ok": true }` when none.

## Workstation flow (8766)

1. User sends office message with target **Everyone** / `all`.
2. `postOfficeChannelMessage()` routes via `HalHubClient.submitToHalHub` or `OfficeHub.appendMessage`.
3. On success, `notifyHubBroadcastAfterOfficeSend()` POSTs to `8765/api/hub/notify` via `HalHubClient.notifyHubBroadcast` with `Origin` + `X-Hub-Token`.
4. Full message still flows through `/api/office-channel` or `/api/hal-hub/inbound` — hub notify is **metadata only**.

## HAL flow (8765)

1. `ensureHubToken()` loads `hubToken` from `/api/app-info`.
2. `refreshOfficeChannel()` polls office channel and calls `refreshHubBroadcastBadge()` with `X-Hub-Token`.
3. Badge reads `GET /api/hub/last-broadcast` → sets `window.__NR2_HUB_BROADCAST`.
4. `HalPage.hubBroadcastBadgeHtml()` renders **OFFICE BROADCAST** in SideNotes monitor heads.
5. `patchHubBroadcastBadgeDom()` updates badge without full HAL re-render.

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

## Implementation map

| File | Responsibility |
|------|----------------|
| `hal_hub.py` | Token, origin validation, broadcast state |
| `nr2_http_server.py` | REST routes, CORS, `hubToken` in app-info |
| `site/hal-hub-client.js` | `X-Hub-Token` on cross-port hub fetch |
| `site/app.js` | `ensureHubToken`, notify after send, poll + DOM patch |
| `site/hal-page.js` | Badge HTML in SideNotes monitor |
| `import_loader.py` / `operatory_schedule.json` | Canonical operatory export |
