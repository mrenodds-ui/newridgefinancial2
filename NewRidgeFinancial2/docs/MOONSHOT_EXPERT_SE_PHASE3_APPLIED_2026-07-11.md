# Moonshot Expert SE Program Recommendations — Phase 3 Applied

**Date:** 2026-07-11  
**Build:** **hal-10501**  
**Consult:** `MOONSHOT_EXPERT_SE_PROGRAM_RECOMMENDATIONS_CONSULT_2026-07-11.md`  
**Prior:** Phase 1 + Phase 2 applied docs  
**Status:** Phase 3 applied per operator proceed (no deviation)

## Applied

| ID | Fix | Status |
|----|-----|--------|
| **REC-005** | Restore `POST /api/apex/claims/era-ingest`; CAS parse (`CO-45`) in `era835_parser`; store/copy `denialCode` onto ERA Matched kanban cards | Done |
| **REC-006** | Restore claims workbench getTemplate (Narrative / Note / Callback); restore `GET/POST /api/apex/claims/actions` (audit-log only, no SoftDent write-back) | Done |
| **REC-007** | Widget stub fast-path (`warming: true`) + background `_fill=True` cache fill; client re-polls while warming; flag `NR2_WIDGETS_STUB_FASTPATH` (default ON) | Done |

## Files

- `era835_parser.py` — CAS → `denialCode` / `casCodes`
- `apex_program_improve_pack.py` — ingest + `apply_era_to_kanban_columns` denial stamp
- `apex_backend.py` — claims/actions + era-ingest routes (before `<claim_id>`); stub fast-path
- `site/apex-core.js` — workbench template restored from `d03f31c`; warming re-poll
- `test_expert_se_phase3.py` — CAS / denial / stub gates
- Build **hal-10500 → hal-10501**

## Validation

```text
python -m unittest test_expert_se_phase3 test_expert_se_phase2 -q
```

| Gate | Result |
|------|--------|
| CAS `CO-45` on parse | Pass |
| ERA Matched card gets `denialCode` | Pass |
| Stub returns `warming` then fill builds | Pass |

## Full Expert SE plan status

| Phase | Status |
|-------|--------|
| 1 — Gate split + Ready/Import Degraded + legacy task | Applied (hal-10499) |
| 2 — Threaded HAL verify + import health chips + monitor | Applied (hal-10500) |
| 3 — ERA CAS + card actions + stub fast-path | Applied (hal-10501) |
| NICE REC-008/009 | Not applied (optional) |

## Honesty

- Card actions are **NR2-local audit only** — no SoftDent write-back
- Stub widgets show empty/warming — never invented dollars
- Money/PHI reads still require fresh imports (Phase 1 gate)
