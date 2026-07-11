# HAL-Said Improve Fix — Applied (approve all)

**Date:** 2026-07-11  
**Build:** **hal-10470**  
**Consult:** `MOONSHOT_HAL_SAID_IMPROVE_FIX_CONSULT_2026-07-11.md`  
**Status:** All MUST / SHOULD / NICE items applied after operator “approve all”

## Shipped

| ID | Item | Where |
|---|---|---|
| 1.1 | Auto denial tasks → Steve (ERA + SoftDent scan) | `apex_hal_said_improve_pack.py` + ERA hook in `ingest_era_835` · HAL: “assign denials to Steve” |
| 1.2 | Clinical sign-off lane (Dr. Reno) | API + narratives/OM widgets · Approve/Reject buttons |
| 1.3 | EOB posting backlog | LocalStore backlog · Daily Huddle priorities · Mark posted |
| 2.1 | Carrier sync SoftDent/InsCo/xlsx → payer_reference | `scripts/sync_office_insurance_to_payer_reference.py` (staging default; `--apply` to promote) |
| 2.2 | Carrier label normalize | `normalize_softdent_label` · `GET /api/apex/hal/normalize-carrier` |
| 2.3 | Central payer contact update | `update_payer_field` · payer-contact-admin widget |
| 3.1 | Structured Remember form | `POST /api/apex/hal/remember-structured` · HAL page widget |
| 3.2 | Policy changelog | LocalStore + widget + API |
| 4.1 | Payer change alerts | `broadcast_payer_change` on sync/field update · Steve task when fee/eligibility |

## Honesty

- No SoftDent write-back (tasks / memories / backlog are NR2-local)
- Task titles use claim IDs only — never patient names
- Structured remember rejects SSN/DOB patterns
- HAL never submits claims to payers
- Payer sync writes **staging** first unless `--apply`

## Files

- `apex_hal_said_improve_pack.py` (new)
- `apex_program_improve_pack.py` (ERA post-hook + huddle extras)
- `apex_backend.py` (routes, board-actions, page widgets, BUILD_ID)
- `site/apex-core.js` (forms: remember, sign-off, EOB posted, payer admin)
- `scripts/sync_office_insurance_to_payer_reference.py` (new)
- `test_hal_said_improve_fix.py` (new)
- `nr2-build.json` / `site/nr2-build.json` / `site/sw.js` → **hal-10470**

## Ops

```text
# Preview payer sync (staging only)
python scripts/sync_office_insurance_to_payer_reference.py

# Promote after review
python scripts/sync_office_insurance_to_payer_reference.py --apply
```

HAL phrases:

- “assign denials to Steve”
- “show eob posting backlog”
- “open clinical sign-off queue”
- “request reno sign-off for claim …”
- “teach HAL” / structured remember widget

## Tests

`python -m pytest NewRidgeFinancial2/test_hal_said_improve_fix.py -q` → 11 passed
