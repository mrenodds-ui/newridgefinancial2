# HAL nightly Trellis dental insurance verification (Mon–Thu 10pm)

## What HAL learned
Night-before SoftDent schedule → Vyne Trellis **Add Patient → Verify** for the next clinical day (Mon–Thu chairs).

## Schedule
| Lane | When | What |
|------|------|------|
| APScheduler `nr2-trellis-verify` | Mon–Thu **22:00** local (while NR2 runs) | Build worklist + pending; upsert HAL work item |
| Windows Task Scheduler | Mon–Thu **10:00 PM** interactive | Same + headed Playwright Verify (`--verify`) |

Thu night targets **Monday** (skips Fri–Sun). Mon–Wed nights target the next calendar day.

## Credentials
Gitignored `.env.vyne.local`:
```
VYNE_AUTOMATION_USERNAME=mrenodds@hotmail.com
VYNE_AUTOMATION_PASSWORD=Wichita4589$
```
Never Emporia. Batch refuses Emporia autofill.

## Enable UI verify in APScheduler
Set user/process env `NR2_TRELLIS_VERIFY=1` (Task Scheduler script already passes `--verify`).

## Manual
```powershell
.\.venv\Scripts\python.exe scripts\run_trellis_nightly_verify.py --force
.\.venv\Scripts\python.exe scripts\run_trellis_nightly_verify.py --force --verify
# or
POST /api/scheduler/insurance-verify-run  {"force": true, "runVerify": true}
```

Install Task Scheduler:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_trellis_nightly_verify_task.ps1
```

## Outputs
`app_data/nr2/vyne_pulls/tomorrow_trellis_{add_worklist,pending_batch,verify_results}_YYYY-MM-DD.json`

## HAL chat
Ask: “nightly Trellis verify” / “10pm insurance verification” → `policy:trellis-nightly-verify`.
