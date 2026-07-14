# SoftDent Daily Master GUI Pull — APPLIED

**Date:** 2026-07-12  
**Status:** Applied  
**Build lane:** hal-10566 + GUI master pull  

## What this is

Daily SoftDent **UI** orchestrator: launch/Sign On → Phase-1 report catalog → `C:\SoftDentReportExports` → existing refresh. Scheduled **5:00 PM interactive** (logged-on desktop only).

| Piece | Path |
|-------|------|
| Menu map | `NewRidgeFinancial2/softdent_gui_menu_map.json` |
| Drivers | `NewRidgeFinancial2/softdent_gui_export.py` |
| Master CLI | `scripts/run_softdent_daily_master_pull.py` |
| Ops wrapper | `C:\New folder\ops\softdent\automation\run_softdent_daily_gui_pull.ps1` |
| Task installer | `C:\New folder\ops\softdent\tasks\install_softdent_daily_gui_pull_task.ps1` |
| Status | `C:\SoftDentFinancialExports\softdent_daily_gui_pull_status.json` |

## Phase 1 reports

register, collections, transactions, daysheet, aging (MTD / as-of).

## Usage

```powershell
# Dry-run (no SoftDent UI)
.\.venv\Scripts\python.exe scripts\run_softdent_daily_master_pull.py --dry-run

# Live MTD pull (SoftDent must be usable on this desktop)
.\.venv\Scripts\python.exe scripts\run_softdent_daily_master_pull.py --start 2026-07-01 --end 2026-07-12

# Install 5 PM interactive task
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\New folder\ops\softdent\tasks\install_softdent_daily_gui_pull_task.ps1"
```

## Validation (2026-07-12)

| Check | Result |
|-------|--------|
| Unit tests `test_softdent_gui_export` | **PASS** (3) |
| `--dry-run` master pull | **PASS** — status written to `C:\SoftDentFinancialExports\softdent_daily_gui_pull_status.json` |
| Task `New Ridge SoftDent Daily GUI Pull 5PM` | **Installed** — Interactive, daily 17:00 |
| Live SoftDent Phase-1 GUI export | **Deferred** — SDWIN not running at validate time; run master pull when SoftDent is signed on |

## Safety

- Password only in gitignored `.env` — never in status JSON / HAL payloads  
- SoftDent read-only report export — no write-back, no invented Ins/Patient dollars  
- AM 5:15 refresh stays ingest-only; GUI pull is separate interactive 5 PM task  
