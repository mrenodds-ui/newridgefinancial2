# Moonshot DEF-001 Regular Collections Ingest — APPLIED (hal-10577)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_JULY_INSPLAN_OPS_2026-07-13.md`  
**Operator:** proceed  
**Status:** Applied (read-only Register parse/ingest; Ins Plan $0 truth; no SoftDent write-back; no ERA move/rename)  
**Build stamp:** kept `hal-10576` (package name hal-10577; no cache-bust required for period JSON)

## Verdict shipped

SoftDent-labeled **Regular Collections $30,626.42** from `REG202607.XLS` is now the July patient side on DEF-001. Ins Plan stays **$0.00**. Gap/widget: **Regular Collections: Complete** · **Insurance Collections: ERA Required**.

## What shipped

| Item | Detail |
|------|--------|
| Register parse | Regular label → `patient` / `regularCollections` even when Ins Plan = $0 |
| Flags | `regularCollectionsReported`, `registerInsPlanZero`; both labels ⇒ not `collectionsFormatRequired` |
| Inbox scan | Matches SoftDent short names `REG\d{6}`; env export root is exclusive when set |
| Period merge | Preserve split/Regular flags on prior; max Regular across sources (stale CSV cannot clobber XLS) |
| Gap / widget | `ERA_835_REQUIRED`; message distinguishes Regular complete vs ERA for insurance |
| Live ingest | `force_reimport` → July `patient=30626.42`, `insurance=0.0` |

## Live validation

| Gate | Result |
|------|--------|
| `REG202607.XLS` Regular | **$30,626.42** |
| Ins Plan | **$0.00** (not invented) |
| `gap.patient` | **30626.42** (was 0.0) |
| Widget | `Regular Collections: Complete ($30,626.42) · Insurance Collections: ERA Required · 2026-07` |
| `collectionsGapCode` | `ERA_835_REQUIRED` |
| Unit tests | **13/13 PASS** (`test_regular_collections_def001_hal10577`, register xls, ERA honesty) |

```text
cd NewRidgeFinancial2
python -m unittest test_regular_collections_def001_hal10577 test_softdent_register_xls_hal10566 test_era_835_honesty_ux_hal10571 -v
```

## Files

| File | Change |
|------|--------|
| `softdent_practice_exports.py` | Regular → patient when Ins Plan $0; honesty flags |
| `softdent_dashboard_period_sync.py` | prior/split flags; max Regular; no false collapse |
| `apex_softdent_hardening_pack.py` | gap/widget Regular vs ERA; `REG\d{6}` inbox; env-exclusive roots |
| `test_regular_collections_def001_hal10577.py` | NEW |
| `test_softdent_register_xls_hal10566.py` | Ins Plan $0 + Regular expectations |
| `test_era_835_honesty_ux_hal10571.py` | format-required cleared on ERA honesty path |
| `docs/MOONSHOT_WHATS_NEXT_AFTER_JULY_INSPLAN_OPS_2026-07-13.md` | consult |
| `docs/MOONSHOT_REGULAR_COLLECTIONS_DEF001_APPLIED_2026-07-13.md` | NEW (this file) |

## Not done

- ERA-835 procurement / first drop  
- BUILD_ID bump to hal-10577 (optional cache stamp)  
- Commit/push (await operator)  
- Stale July CSV cleanup under `C:\SoftDentReportExports` (merge prefers XLS Regular max)
