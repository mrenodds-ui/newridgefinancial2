# SoftDent morning Excel bundle — ATTENDED re-run APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_TRELLIS_BENEFITS_2026-07-16.md`  
**Operator:** approve  
**Package:** Attended SoftDent morning Excel bundle (`softdent_export_morning_bundle`)

## Prep

- Minimized Chrome **NR2 Optical · Claims** (Claim Management focus thief)
- SoftDent v19.1.4 already running, signed on, focused
- `ensure_softdent_ready_for_gui_export` → `ok: true`

## Live result (~205s)

| Report | Navigation | Output Options | Money ingest path |
|--------|------------|----------------|-------------------|
| aging | OK (F10 after 64-bit `menu_select` ElementNotEnabled) | **Excel greyed out** → Print Preview | no `.xls` drop |
| register | OK | Excel greyed out → Print Preview | no `.xls` drop |
| collections | OK | Excel greyed out → Print Preview | no `.xls` drop |

Summary log: `.local_logs/morning_bundle_attended_2026-07-16.json`

```json
{
  "ok": false,
  "agingOk": false,
  "okCount": 3,
  "failed": [],
  "paths": [],
  "error": "softdent_excel_disabled",
  "excelDisabled": true,
  "emptyNotZero": true
}
```

`periodCloseStatus.morningBundle.ok` remains **false** (`attest_only`). Empty ≠ `$0` preserved — no invented dollars from Print Preview.

Latest files under `C:\SoftDentReportExports` are still **2026-07-15** (no new Excel today).

## What worked

- Attended focus prep (Claims Chrome minimized)
- Full aging → register → collections sequence without mid-run focus steal
- Hard rule honored: Excel or Print Preview only — **never Printer / never File**
- When Excel disabled, automation correctly fell back to Print Preview and did not invent money beams

## Blocker (operator SoftDent config)

SoftDent **Output Options → Excel is disabled/greyed** on this workstation. Until Excel is enabled in SoftDent (license / report output setup), money-beam morning bundle cannot go GREEN.

## Explicitly not done

- Flip `forceCloseAvailable` on MATCH
- Invent SoftDent Excel drops / `$0` from empty preview
- Classic Apex 2B
- Redo Trellis benefits / OM schedule / this-patient

## Operator next

1. In SoftDent, enable **Excel** on Output Options (not File, not Printer).
2. Say **approve** / **continue** for another attended morning-bundle run.
3. Tonight 10:10 PM Trellis `--verify` still fills ClearCoverage benefits independently.
