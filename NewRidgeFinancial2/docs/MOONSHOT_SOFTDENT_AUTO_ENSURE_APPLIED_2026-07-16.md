# SoftDent Auto-Ensure for Autonomous HAL (APPLIED)

**Date:** 2026-07-16  
**Build:** `nr2-12041-softdent-auto-ensure`  
**Prior:** `nr2-12040-hal-autonomous`  
**Operator:** next

## Why

HAL autonomy still failed when SoftDent wasn’t already open (`softdent_gui_unreachable`). Morning / HAL / Force Close paths need SoftDent desktop before Excel pulls.

## What shipped

1. **`ensure_softdent_ready_for_gui_export`** in `softdent_gui_export.py` — launches via **CS SoftDent Software.lnk** (`-sus`) + Sign On, never bare `SDWIN.EXE`
2. **`softdent_export` / `export_report_by_id` / morning bundle** — call ensure when main window is down
3. **Autonomous tick** — ensure SoftDent before Force Close when lasers are red

## Doctrine unchanged

- SoftDent write-back forbidden
- Excel / Print Preview only
- empty ≠ $0
- Select File Name keeps SoftDent’s folder (never SoftDentReportExports)

## Validation

- Unit: ensure already-running / launch path / export ensure call
- Live: restart NR2; with SoftDent closed, HAL SoftDent export or morning tick should launch + sign on then pull
