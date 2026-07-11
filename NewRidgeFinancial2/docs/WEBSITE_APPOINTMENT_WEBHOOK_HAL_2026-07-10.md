# Website appointment webhook → HAL (2026-07-10)

Gravity Forms form #1 on `/patient-information/scheduling/` posts appointment requests into NR2 so HAL/front desk see them as sidenotes.

## Live tunnel (this PC)

Quick tunnel is running via Cloudflare → local webhook-only relay on **127.0.0.1:8777** (not full NR2 :8765).

| Item | Value |
|------|--------|
| Webhook URL | See `.local_logs/website_webhook/public_url.txt` (changes if tunnel restarts) |
| Header | `X-NR2-Webhook-Secret: <secret>` |
| Secret file | `app_data/nr2/website_webhook_secret.txt` (gitignored) |
| Start | `NewRidgeFinancial2/scripts/Start-Website-Webhook-Tunnel.ps1` |
| Stop | `NewRidgeFinancial2/scripts/Stop-Website-Webhook-Tunnel.ps1` |
| Logs | `.local_logs/website_webhook/` |

**Verified 2026-07-10:** public POST through trycloudflare.com returned `ok: true` and created a HAL sidenote (`WEB APPT REQUEST: …`).

Note: this office PC’s default DNS may not resolve `*.trycloudflare.com`; Gravity Forms’ servers use public DNS and can reach the URL. Keep the start script / cloudflared process running or the URL dies.

## Flow

1. Patient submits **Request Appointment** (Gravity Forms #1).
2. Gravity Forms **Webhook** POSTs JSON (or form fields) to the tunnel URL.
3. Relay stores the lead in SQLite (`website_leads`) and inserts a local sidenote (`source=website`).
4. HAL sidenotes bridge loads `/api/sidenotes/local` → note appears as **WEB APPT REQUEST: …**

## Auth

Secret is auto-generated into `app_data/nr2/website_webhook_secret.txt` by the start script / relay.

Send the same value as header `X-NR2-Webhook-Secret` (preferred).

## Gravity Forms setup (needs PBHS — admin is locked)

WP user cannot open `gf_edit_forms` (403). Ask RevenueWell/PBHS to add a webhook on **form 1**:

1. Request URL: contents of `.local_logs/website_webhook/public_url.txt`
2. Method: **POST**
3. Format: **JSON**
4. Custom header: `X-NR2-Webhook-Secret` = contents of `app_data/nr2/website_webhook_secret.txt`
5. Include entry fields (name, email, phone, interest, time, day, hear-about, comments)

## Operator APIs (via NR2 :8765 when running)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/website-leads?status=open` | Open leads |
| GET | `/api/website-leads?status=all` | All leads |
| POST | `/api/website-leads/{id}/handled` | Mark handled |

## Sample payload

```json
{
  "entry_id": "123",
  "form_id": "1",
  "Your Name": "Jane Doe",
  "Your E-mail Address": "jane@example.com",
  "Your Phone Number": "316-555-0100",
  "I am interested in": "Scheduling Appointment",
  "Best Time for Appointment": "Morning",
  "Preferred Day of Week": "T",
  "How did you hear about us?": "Friend/Family",
  "Comments/Questions": "New patient"
}
```
