# SoftDent GUI Sign On — program + HAL wiring (no secrets in git)

**Date:** 2026-07-12  

## SoftDent data-access doctrine (whole program)

**Hybrid (measured on this workstation):**

| Need | Better path | Why |
|------|-------------|-----|
| Period financial totals (prod/collections/Ins Plan) | **Desktop SoftDent Excel** | Source of truth — complete correct SoftDent figures; ODBC not configured here for live extract |
| Patients / procedures / claims / payments lists | **Database / Sensei / `sd_*`** | Much faster (~ms) when tables are populated |
| Visual confirmation | **Desktop Print Preview** | Click Preview → Enter → **last page** for totals |

1. **Financial close / master reports** → SoftDent desktop (Sign On → Output Options → **Excel** → Enter → save → NR2 parse).  
2. **Operational detail** → DB/Sensei/`sd_*` when populated (fast).  
3. **Do not** promote DB to period-close primary until a side-by-side matches SoftDent Register.  
4. **HARD RULE:** Output Options = **Excel** prompt or **Print Preview** prompt only — **never** click **Printer**.  
5. **Never** invent dollars or SoftDent write-back.

Constant: `SOFTDENT_DATA_ACCESS_DOCTRINE` in `softdent_signon.py` (also on HAL status / Sign On API).

## Master report list (program knowledge)

| Artifact | Role |
|----------|------|
| `NewRidgeFinancial2/softdent_master_reports.json` | Canonical list of what NR2 needs + DB vs GUI |
| `NewRidgeFinancial2/softdent_master_reports.py` | `verify_master_reports()` + HAL summary |
| `NewRidgeFinancial2/softdent_gui_menu_map.json` | SoftDent UI menu paths / Excel stems for GUI pulls |
| `scripts/run_softdent_daily_master_pull.py` | Master GUI orchestrator; `--verify-only` audits the list |

### Master reports

| Id | Preferred | Output Options | When DB cannot supply |
|----|-----------|----------------|------------------------|
| `sd_odbc_core` | Database (`sd_*`) | DB | Sensei/ODBC extract first |
| `register` | GUI | Excel (prefer) / Preview | Click Excel→Enter; or Preview→Enter + **last page** |
| `collections` | GUI | Excel + Preview (verified) | Click Excel→Enter; or Preview→Enter + **last page** |
| `transactions` | GUI (DB assist) | Excel / Preview | Click Excel→Enter; Preview last page if visual |
| `daysheet` | GUI | Excel + Preview (verified) | Click Excel→Enter; Preview last page if visual |
| `aging` | GUI (DB assist) | Excel + Preview (verified) | Click Excel→Enter; Preview last page if visual |
| `writeoff_totals` | GUI (DB assist) | Excel + Preview (verified) | Click Excel→Enter; Preview last page if visual |

## How to get data (live validated 2026-07-12)

Ran `scripts/validate_softdent_report_howto.py` → **7/7 PASS**  
Log: `C:\SoftDentFinancialExports\softdent_report_howto_validation.json`

| Report | Preferred how | Steps |
|--------|---------------|-------|
| `sd_odbc_core` | Database | Sensei / ODBC / `sd_*` when populated |
| `register` | **Excel** (also Preview) | Menu → click **Excel** → Enter → Setup → save → refresh |
| `collections` | **Excel** (also Preview) | Same; never Printer |
| `transactions` | **Excel** (also Preview) | Same |
| `daysheet` | **Excel** (also Preview) | Same |
| `aging` | **Excel** (also Preview) | Same |
| `writeoff_totals` | **Excel** (also Preview) | Same |

**HARD RULE:** Output Options = **Excel** or **Print Preview** only — never **Printer**. Preview path: last page for exact totals.

Verify:

```text
python -m softdent_master_reports --start 2026-07-01 --end 2026-07-12
python scripts/run_softdent_daily_master_pull.py --verify-only --start 2026-07-01 --end 2026-07-12
```

## How Sign On credentials are known

SoftDent GUI Sign On credentials are **only** in environment variables:

| Key | Purpose |
|-----|---------|
| `SOFTDENT_SIGNON_USER` | SoftDent Sign On user id (typically `COMPUTE`) |
| `SOFTDENT_SIGNON_PASSWORD` | SoftDent Sign On password |
| `SOFTDENT_GUI_USER` / `SOFTDENT_GUI_PASSWORD` | Aliases |

Loaded from process/User env and local gitignored `.env` (`C:\New folder\.env`, `NewRidgeFinancial2\.env`).

| Location | Purpose |
|----------|---------|
| `NewRidgeFinancial2/softdent_signon.py` | Resolver + UI assist + data-access doctrine |
| `NewRidgeFinancial2/softdent_odbc_extract.py` | Database / ODBC extract lane (preferred when reachable) |
| `NewRidgeFinancial2/softdent_gui_export.py` | UI export helpers for DB-unreachable reports |
| `scripts/run_softdent_safe_period_export.py` | Safe orchestrator (no password in stdout) |
| `refresh_softdent_period_imports` | Step `softdent_signon` (never echoes password) |

## SoftDent Sign On identity

- **User:** `COMPUTE` (SoftDent Sign On / Change Login)  
- **Password:** stored only in local env / `.env` — **not** in git, HAL replies, or docs  

## HAL surfaces

| Surface | Behavior |
|---------|----------|
| Local policy | Sign On password / “data not in database” → env keys + UI-only doctrine (never prints password) |
| LLM context | `compile_softdent_signon_guidance` injects Sign On + data-access rule |
| HAL status | `softdentSignOn` + `dataAccessDoctrine` + `masterReports` on `/api/apex/hal/status` |
| API | `GET /api/apex/hal/softdent-signon` |
| HAL tool | `softdent_signon_status` in `hal-agent.js` |
| Export playbook | DB first; else Sign On + UI export |
| Services | `fetchSoftdentSignOnStatus` in `site/services.js` |

## Ask HAL

- How does SoftDent Sign On work?
- Where is the SoftDent Sign On password?
- How do I get SoftDent data that cannot be reached by the database?
- What SoftDent reports does the master program need?
- SoftDent login credentials

## Usage

```text
python NewRidgeFinancial2/softdent_signon.py
python -m softdent_master_reports --require-inbox --start 2026-07-01 --end 2026-07-12
python scripts/run_softdent_safe_period_export.py --start 2026-07-01 --end 2026-07-12
```

Or ask HAL / Refresh SoftDent period — step `softdent_signon` confirms `passwordConfigured` + assist result.

## Security

- Do not commit `.env`  
- Do not paste the password into Moonshot docs or chat  
- HAL must not echo the password value  
- Rotate if this value was shared in chat logs  
- Sign-on assist uses `force_change_login=False` by default (no Change Login spam when already signed in)
