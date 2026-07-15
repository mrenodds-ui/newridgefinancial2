# Moonshot AI — whole computer help for NR2 (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Endpoint:** https://api.moonshot.ai/v1/chat/completions
**Status:** ok
**Build:** `nr2-12017-optical-ops`
**Repo root:** `C:\Users\mreno\newridgefamilyfinancial`
**Inventory:** `.local_logs/moonshot_financial_eval/machine_inventory_for_moonshot.json`
**Script:** `scripts/run_moonshot_whole_computer_help_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> have moonshot ai look at my entire computer and see if anything would help this program - report

---

# Verdict — what on this computer helps NR2 most

## 0. Operator Intent (verbatim)
> have moonshot ai look at my entire computer and see if anything would help this program - report

## 1. Host snapshot (what is actually here that matters)
- **Canonical repo**: `C:\Users\mreno\newridgefamilyfinancial` (live NR2-12017-optical-ops)
- **SoftDent**: Installed at `C:\SoftDent`, running process `SDWIN`, Start Menu shortcut `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\CS SoftDent Software\CS SoftDent Software.lnk` (target `C:\SoftDent\SDWIN.EXE`, WorkingDirectory `C:\SoftDent`)
- **Export drop zones**: `C:\SoftDentReportExports` (41 files, latest 2026-07-15), `C:\SoftDentFinancialExports` (analytics.db 177MB, 3,080 files)
- **Document inbox**: `C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\document_inbox` (manifest.json + softdent/quickbooks subdirs)
- **SideNotes package**: `C:\SoftDent\HAL-SideNotes-Workstation` (watcher scripts, config.json, vdb_reader.py)
- **Local LLM**: Ollama 0.32.0 installed at `C:\Users\mreno\AppData\Local\Programs\Ollama` with 4 models (hal-local:30b-a3b, hal-local:32b, qwen3 variants, ~76GB total)
- **OCR**: Tesseract 5.4.0 installed at `C:\Program Files\Tesseract-OCR\tesseract.exe` (not on PATH)
- **QB Integration**: QuickBooks Pro 2024 running (`QBW.exe`, `QBDBMgrN`), ODBC DSN "QuickBooks Data QRemote" present
- **SQL**: SQL Server 2025 Express instance `MSSQL17.SQLEXPRESS`
- **Scheduled Tasks**: 14 NR2-related tasks in "Ready" state (not currently executing)
- **Stale data**: QB revenue/P&L (1,482 min old), SoftDent claims/production (1,486 min old)

## 2. Top opportunities ranked (MUST / SHOULD / NICE)

### MUST
| Asset | How it helps NR2 | Concrete next step | Risk |
|-------|------------------|-------------------|------|
| **Scheduled Tasks** (14 tasks in "Ready" state: `New Ridge 45 Minute SoftDent Refresh`, `New Ridge QuickBooks SDK Refresh`, `New Ridge HAL Import Sync`, `New Ridge SoftDent Daily GUI Pull 5PM`, `NR2_Import_Cron`) | Current import readiness shows 8 stale datasets (critical: QB revenue/P&L; warning: SoftDent claims/production). Tasks appear configured but idle. | Open Task Scheduler, verify Next Run Time is within 24h; manually trigger `New Ridge HAL Import Sync` and `New Ridge QuickBooks SDK Refresh` to clear 1,482-minute staleness. Check that `NR2_Import_Cron` triggers every 45 min as named. | If tasks fail silently, HAL continues operating on 24+ hour old financials; verify Task History tab for last successful run. |
| **Tesseract OCR** at `C:\Program Files\Tesseract-OCR\tesseract.exe` | Document inbox processing requires OCR for scanned EOBs/ERA; currently installed but `toolsOnPath.tesseract` is null (not on PATH). | Add `C:\Program Files\Tesseract-OCR` to system PATH or configure NR2 `TESSERACT_CMD` env var to absolute path; test with `tesseract --version` from repo root. | Without OCR wiring, document ingestion pipeline cannot extract text from image-based ERA attachments. |
| **SoftDent Export Folders** (`C:\SoftDentReportExports`, `C:\SoftDentFinancialExports`) | Master reports (Register, Collections, Daysheet, Aging) export to these paths per SoftDent doctrine; current exports show 2026-07-15 aging but 2026-07-14 register/transactions. | Launch SoftDent via Start Menu shortcut → Output Options → Excel/Preview (never Printer) → export Register for period 2026-07-01 to current date → save to `C:\SoftDentReportExports` to unblock stale production dataset. | Do not write to `C:\SoftDent\*.dat` directly; ensure exports use Excel/Preview prompts only. |

### SHOULD
| Asset | How it helps NR2 | Concrete next step | Risk |
|-------|------------------|-------------------|------|
| **Ollama local models** (`hal-local:30b-a3b`, `hal-local:32b`, `qwen3` variants) at `C:\Users\mreno\.ollama\models` | 76GB of local LLM capacity available for on-premise inference (PHI stays local); can power HAL narrative generation without cloud HAL (currently disabled: `cloudHal.enabled: false`). | Configure NR2 to use local Ollama endpoint (`http://localhost:11434`) with model `hal-local:30b-a3b` for operational summaries; verify in `app_data/nr2/config` or env vars. Ensure Ollama service starts via `C:\Users\mreno\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\Ollama.lnk`. | Large models consume RAM; ensure 18-20GB per model load does not starve QB/SoftDent SQL processes. |
| **HAL-SideNotes-Workstation** at `C:\SoftDent\HAL-SideNotes-Workstation` | Real-time SoftDent side-car watcher (`sidenotes_watcher.py`, `vdb_reader.py`) can stream operational events to HAL without polling; includes `Start-HAL-SideNotes.bat`. | Execute `Start-HAL-SideNotes.bat` to activate watcher; verify `watcher_state.json` updates when SoftDent records change; configure NR2 to read from SideNotes socket/file instead of full ODBC polls. | If SoftDent is locked or SDWIN restarted, watcher may lose hook; requires restart. |
| **SQL Server 2025 Express** (`MSSQL17.SQLEXPRESS`) | Could host staging tables for SoftDent analytics instead of flat files; ODBC drivers 11/17/18 already installed. | Create database `NR2_Staging` on SQLEXPRESS; configure NR2 to use ODBC connection string `DRIVER={ODBC Driver 18 for SQL Server};SERVER=.\SQLEXPRESS;...` for intermediate analytics storage (optional migration from sqlite analytics.db). | Requires backup/maintenance; do not migrate until current flat-file pipeline is stable. |

### NICE
| Asset | How it helps NR2 | Concrete next step | Risk |
|-------|------------------|-------------------|------|
| **Git/GitHub Desktop** (`C:\Program Files\Git\cmd\git.exe`, GitHub Desktop installed) | Version control for `newridgefamilyfinancial` repo; currently no evidence of dirty working tree but desktop shortcuts suggest manual bat file usage. | Use GitHub Desktop to visualize changes to `app_data/nr2` configs; commit any local modifications to avoid loss during backup rotations. | Low risk; purely hygiene. |
| **Sensei Gateway Client** (v8.0.0.326) | Already installed; alternative data lane to SoftDent proprietary exports if properly licensed and configured. | Verify Sensei DataSync folders (`C:\SoftDent\DataSync`) are populated with JSON extracts; if Sensei is active, NR2 could consume `SDExtractor_JSON` output as secondary validation source. | Sensei extracts may not match SoftDent GUI Register totals exactly; use only for operational detail, not period-close. |
| **Disk E:** (6.4TB free) | Large storage for long-term export archives; currently hosting `E:\NewRidgeFamilyFinancial` (likely backup). | Repurpose `E:\` as dedicated archive for `C:\SoftDentFinancialExports\_derived_archive` and `C:\SoftDentReportExports\_history` to prevent C: drive bloat (currently 595GB used of 1.8TB). | Ensure backup scripts do not confuse E: copy with canonical C: repo. |

## 3. Already wired / leave alone (so we do not thrash)
- **QuickBooks Pro 2024**: Running (`QBW.exe`, `QBDBMgrN`), ODBC DSN configured; leave READ-only posture intact.
- **SoftDent Start Menu shortcut**: `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\CS SoftDent Software\CS SoftDent Software.lnk` is the documented launch path; continue using this (never bare `SDWIN.EXE`).
- **Analytics DB**: `C:\SoftDentFinancialExports\softdent_financial_analytics.db` (177MB) is actively written (journal file present); do not move or compact during business hours.
- **Python 3.11/Node.js**: Runtime dependencies present; leave PATH as-is.
- **Document inbox structure**: `app_data/nr2/document_inbox` with softdent/quickbooks subdirs is the canonical drop zone; maintain current layout.

## 4. Stale / risky / ignore (duplicate repos, old diagnostics, backup traps)
| Item | Issue | Action |
|------|-------|--------|
| **Desktop diagnostic files** (`SoftDent_Diagnostic_20260326_*.txt`, `softdent_helper_check.txt`, `softdent_live_components.txt`, `softdent_server_check.txt`) | Stale (March 2026), may confuse operators about current system state. | Delete or archive to `C:\SoftDentFinancialExports\_stale_archive`. |
| **NewRidgePortal-legacy-archive-20260418** on Desktop | 52-file legacy Apex SPA archive (pre-nr2-optical); contradicts doctrine "do not recommend restoring legacy Apex SPA". | Ignore; do not restore. If space needed, move to `F:\` backup drive. |
| **Duplicate repo copies** (`D:\NewRidgeDashboard`, `E:\NewRidgeFamilyFinancial`, `F:\NewRidgeFamilyFinancial_FullBackup_20260710_162639`, `F:\NewRidgeFinancial2_Backup_*`) | Risk of editing wrong codebase or importing stale data from backup drives. | Treat as read-only backups; never launch NR2 from these paths. If sync needed, use `robocopy` from C: to F: only, not reverse. |
| **G:\softdent** | Unknown SoftDent copy on external/removable-style drive; may be outdated mirror. | Ignore unless proven to be current; do not configure NR2 to read from G:. |
| **Downloads PDFs** (`SoftDent_Expert_Witness_Final.pdf`, `SoftDent_Courtroom_Grade_Report.pdf`, etc.) | Courtroom/expert witness reports from June 2026; not operational assets. | Leave in Downloads; do not move to NR2 inbox. |
| **C:\SoftDent\exports** (empty) | SoftDent's default export folder is unused; NR2 uses `C:\SoftDentReportExports`. | Ignore; do not delete (SoftDent may default here if config reset). |

## 5. SoftDent + QB + Sensei + SideNotes + OCR + SQL Express matrix

| System | Status | Integration Path | NR2 Usage |
|--------|--------|------------------|-----------|
| **SoftDent** | Running (SDWIN) | Start Menu shortcut → GUI → Excel/Preview exports → `C:\SoftDentReportExports` | Master reports (Register, Aging, Daysheet) for period-close |
| **QuickBooks 2024** | Running (QBW, QBDBMgrN) | ODBC DSN "QuickBooks Data QRemote" + SDK | Revenue, P&L, Expenses, AR (currently stale, needs refresh task) |
| **Sensei Gateway** | Installed v8.0.0.326 | `C:\SoftDent\DataSync\SDExtractor_JSON` | Optional operational detail (procedures, claims); not primary for period-close |
| **SideNotes** | Present but unknown state | `C:\SoftDent\HAL-SideNotes-Workstation\sidenotes_watcher.py` | Real-time event stream if activated via `Start-HAL-SideNotes.bat` |
| **OCR (Tesseract)** | Installed but not on PATH | `C:\Program Files\Tesseract-OCR\tesseract.exe` | Document inbox text extraction (must wire PATH or env var) |
| **SQL Express 2025** | Installed, instance SQLEXPRESS | ODBC Driver 18 | Optional staging database; currently unused by NR2 |

## 6. Scheduled-task posture (enable / audit / leave)

| Task Name | State | Posture | Notes |
|-----------|-------|---------|-------|
| `New Ridge 45 Minute SoftDent Refresh` | Ready | **Audit** | Verify last run time; if >45 min ago, trigger manually to clear staleness. |
| `New Ridge HAL Document Source Sync` | Ready | **Audit** | Required for document inbox processing. |
| `New Ridge HAL Full Practice Pull` | Ready | **Audit** | Heavyweight pull; ensure it runs nightly, not during business hours. |
| `New Ridge HAL Import Sync` | Ready | **Enable/Trigger** | Critical path for QB/SoftDent freshness; appears stalled (data 1,482 min old). |
| `New Ridge HAL Model Warmup` | Ready | **Leave** | Pre-loads Ollama models; safe to keep. |
| `New Ridge NR2 Program` | Ready | **Leave** | Likely main service wrapper. |
| `New Ridge QuickBooks SDK Refresh` | Ready | **Enable/Trigger** | Critical for QB revenue/P&L; trigger immediately to clear critical staleness. |
| `New Ridge SoftDent Daily GUI Pull 5PM` | Ready | **Audit** | Ensure 5PM trigger aligns with business close; verify it targets `C:\SoftDentReportExports`. |
| `New Ridge SoftDent Export Watcher` | Ready | **Leave** | Monitors export folder for new files. |
| `NewRidgePortal-ServerAutoStart` | Ready | **Leave** | Legacy name but may be required for service boot. |
| `NR2 Workstation` | Ready | **Leave** | Workstation mode launcher. |
| `NR2_Import_Cron` | Ready | **Audit** | Verify schedule (should be frequent, e.g., 15-30 min) and that it actually fires. |
| `NR2_Monthly_Audit` | Ready | **Leave** | Monthly reconciliation task. |
| `PortalImportWatchdog` | Ready | **Audit** | Ensure it monitors correct path (`document_inbox`), not legacy portal path. |

**Action**: All tasks show "Ready" (idle). The critical staleness (QB revenue/P&L, SoftDent claims/production) indicates they are not firing or failing silently. **Audit Task History** for each; manually trigger `New Ridge QuickBooks SDK Refresh` and `New Ridge 45 Minute SoftDent Refresh` immediately to restore data freshness.

## 7. Executive Summary (7 bullets)
1. **Critical data staleness**: QB revenue/P&L and SoftDent claims/production are 24+ hours stale; scheduled tasks are configured but idle—manual trigger or task repair required immediately.
2. **Tesseract OCR is orphaned**: Installed at `C:\Program Files\Tesseract-OCR\tesseract.exe` but not on PATH; wire it to enable document inbox processing.
3. **SideNotes watcher dormant**: Real-time SoftDent integration package exists at `C:\SoftDent\HAL-SideNotes-Workstation` but may not be running; launch via `Start-HAL-SideNotes.bat` to reduce polling load.
4. **Local LLM ready**: 76GB of Ollama models (hal-local, qwen3) available for PHI-safe local inference; configure NR2 to use `http://localhost:11434` for narrative features.
5. **Export discipline maintained**: SoftDent exports correctly routing to `C:\SoftDentReportExports` (latest aging 2026-07-15), but register/transactions lagging (2026-07-14); need fresh Excel export via Start Menu shortcut.
6. **Backup trap risk**: Multiple repo copies on D:, E:, F: drives could be mistaken for live code; canonical is `C:\Users\mreno\newridgefamilyfinancial` only.
7. **No new vendors needed**: All assets to clear current blockers (stale data, OCR, real-time feeds) exist on host; prioritize wiring existing Tesseract, SideNotes, and Ollama over new installations.

## 8. Approval Checklist
- [ ] Operator confirms scheduled task history (no silent failures)
- [ ] Tesseract PATH configuration tested (`tesseract --version` from repo root)
- [ ] SideNotes watcher started (`Start-HAL-SideNotes.bat` executed, `watcher_state.json` updating)
- [ ] Fresh SoftDent Register export generated (Excel/Preview only) to `C:\SoftDentReportExports` today
- [ ] QuickBooks SDK refresh triggered manually to clear 1,482-minute staleness
- [ ] Ollama local endpoint tested (if HAL cloud remains disabled)
- [ ] Backup drives D:/E:/F: verified read-only (no accidental edits)
