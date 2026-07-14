# Moonshot HAL No Register Re-export Hardening — APPLIED (hal-10578)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_REGULAR_COLLECTIONS_2026-07-13.md`  
**Operator:** proceed  
**Status:** Applied (policy/guard only; no SoftDent write-back; no Register re-export; no ERA move/rename)  
**Build stamp:** kept `hal-10576` (package name hal-10578)

## Verdict shipped

When SoftDent Register Ins Plan is **$0** and Regular Collections are complete, DEF-001 / HAL now stamp `suggestedAction=era_835_procure` and **never** `re_export_register`. Explicit “re-export Register hoping Ins Plan > 0” asks are refused.

## What shipped

| Item | Detail |
|------|--------|
| Action tokens | `era_835_procure`, `collections_export`, `sync_imports`, `none`; forbidden `re_export_register` |
| Gap assess | Stamps `suggestedAction` + `forbidRegisterReexport` |
| Gap widget | Surfaces `suggestedAction`; ERA chips unchanged (no Register re-export chip) |
| HAL reply | Includes `suggestedAction=era_835_procure`; Regular Complete line when present |
| HAL refuse | `policy:forbid-register-reexport` for re-export / Ins Plan > 0 asks |
| Period refresh note | Softened: do not re-export hoping Ins Plan > 0 |

## Validation

| Gate | Result |
|------|--------|
| `suggestedAction` | `era_835_procure` (not `re_export_register`) |
| Widget message | Regular Collections: Complete · Insurance ERA Required |
| Unit `test_hal_no_register_reexport_suggestion_hal10578` | **PASS** |
| Related ERA / Regular suites | **PASS** |

```text
cd NewRidgeFinancial2
python -m unittest test_hal_no_register_reexport_suggestion_hal10578 test_era_835_honesty_ux_hal10571 test_regular_collections_def001_hal10577 -v
```

## Files

| File | Change |
|------|--------|
| `apex_softdent_hardening_pack.py` | suggestedAction helpers + gap/widget/reply stamps |
| `nr2_hal_gateway.py` | forbid-register-reexport policy + suggestedAction on DEF-001 |
| `apex_backend.py` | period-refresh note honesty |
| `test_hal_no_register_reexport_suggestion_hal10578.py` | NEW |
| `docs/MOONSHOT_WHATS_NEXT_AFTER_REGULAR_COLLECTIONS_2026-07-13.md` | consult |
| `docs/MOONSHOT_HAL_HARDENING_NO_REEXPORT_HAL10578.md` | NEW (this file) |

## Not done

- ERA-835 payer-portal procurement playbook (no in-repo SOPs)  
- BUILD_ID bump  
- Commit/push (await operator)
