# Moonshot REC-008 Batch Narratives — APPLIED

**Date:** 2026-07-11  
**Consults:** Expert SE REC-008; `MOONSHOT_WHATS_NEXT_AVOID_GITHUB_2026-07-12.md`  
**Operator:** do what moonshot wants (avoid GitHub)  

## Goal

Select multiple denied/open claims → generate appeal drafts with shared context → bulk print packet (browser PDF). No SoftDent write-back. Empty clinical notes stay empty.

## Applied (real Apex paths — not fictional `hal/modules/...`)

| Piece | Where |
|-------|--------|
| Seed helper + shared context + max 20 | `apex_program_improve_pack.py` |
| `narrative_batch_generate` | `apex_backend.py` — loops `narrative_insurance_generate`, audits via `record_claim_action`, builds print packet |
| Routes | `POST /api/apex/narratives/batch-seed`, `POST /api/apex/narratives/batch-generate` |
| Batch UI | `apex-core.js` — Consent + Batch Generate on batch-selector; workbench batch action generates |
| Narratives page | `apex-narratives.js` — `applySeed` shows all batch drafts |
| Tests | `test_rec008_batch_narratives.py` |

## Honesty / consent

- `operatorConsent` required
- Draft footer still says human review before payer submit
- No invented dollars; missing claim → per-id error in results

## Validate

1. Restart NR2 / hard-refresh Apex  
2. Claims → batch selector: check claims, check Consent, **Batch Generate**  
3. Packet tab opens; Narratives page lists each draft  
4. `python -m unittest test_rec008_batch_narratives -q`
