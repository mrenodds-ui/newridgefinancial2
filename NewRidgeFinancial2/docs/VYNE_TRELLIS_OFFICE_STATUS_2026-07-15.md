# Vyne Trellis — office status (this workstation)

**Date:** 2026-07-15  
**Scope:** Locate Trellis / confirm Sync-or-RES / map SoftDent ECS → Vyne payer IDs for HAL.

## Confirmed on this PC

| Item | Status |
|------|--------|
| Trellis web UI | **https://app.vynetrellis.com** (ClaimListener `claimSiteUrl`) |
| Vyne Api Service | **Running** · Auto · `C:\Users\Public\RES\RESPrinter\VyneApiService.exe` |
| Vyne File Service | **Running** · Auto · `C:\Users\Public\RES\RESPrinter\VyneFileService.exe` |
| RES / Renaissance stack | `C:\Users\Public\RES` (DOTR print capture + ClaimListener + plugins) |
| SoftDent claim watch | `PluginsREPPlugin.ini` → watch `C:\SOFTDENT\*.REP` · **ENABLED=True** |
| SoftDent classic eLink | Present but **misconfigured / dead** (Practice Name/Id/Password unset since ~2015–2021) |
| Vyne Sync desktop installer | **Not found** on this box (Sync is usually on the PMS **server**) |
| “Vyne Claims” printer | **Not currently installed** among Windows printers |
| Prior Trellis login proof | `C:\Users\Public\RES\vyne_after_login.png`, `vyne_eligibility.png` (2026-03-22) |
| CustomerId (VdpSharedSettings) | `30617` |

## How claims leave SoftDent here

SoftDent writes/prints claim traffic into the **RES/Vyne** path (`.REP` watch on `C:\SOFTDENT` + DOTR forms capture), which talks to Vyne Trellis / RSS endpoints (`rl7.rss-llc.com`, `*.vynetrellis.com`). This is the Renaissance → Vyne Trellis lineage, not bare SoftDent eLink.

## HAL / NR2 payer map (done this session)

1. Re-imported office list `NewRidgeFinancial2/data/imports/vyne_payers.json` (182 rows) into `data/tesia_payer_list.json` → **226** payers total.
2. Ran `softdent_tesia_join` (exact ECS/Vyne IDs only):
   - **105** exact SoftDent ↔ Tesia/Vyne matches
   - **0** new ECS IDs needed in Tesia list
   - **32** SoftDent carriers with no ECS-like ID
   - Kansas samples stamped: `CDKS1` (Delta KS), `47163` (BCBS KS), `47171` (BCBS KC), `RLHA1` (Renaissance)
3. Report: `NewRidgeFinancial2/data/softdent_tesia_join_report.json`

HAL already routes `vyne` / clearinghouse payer-ID asks through this list.

## Staff login

1. Browser → https://app.vynetrellis.com  
2. Eligibility / Appointments per office SOP (`Desktop\…\docs\VYNE-STAFF-WORKFLOW.md` in legacy archive).  
3. Support: dentalvendorsupport@vynedental.com · 866-712-9584  

## Gaps / follow-ups

- Confirm whether **Vyne Sync** lives on the SoftDent **server** (not this workstation).
- Reinstall or enable **Vyne Claims** printer if SoftDent claim print path stalls.
- Legacy portal insurance pull failed earlier with `VYNE_INSURANCE_PULL_FOLDER not configured` — optional if Trellis + RES already cover eligibility.
- Do **not** commit RES cert passwords from `VyneApiService.exe.config` into git.
