# Moonshot REC-009 Voice Context Carry — APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_REC009_VOICE_CONTEXT_CARRY_CODE_REPORT_2026-07-12.md`  
**Operator:** do it  

## Goal

“HAL, draft appeal for the high-risk claim I just clicked” — carry claim context into Narratives voice without manual lock. No SoftDent write-back. No invented dollars/PHI.

## Applied (real Apex paths)

| Piece | Where |
|-------|--------|
| `syncHalVoiceSessionContext` / `setFocusedClaimForVoice` / `writeNarrativeVoiceSeed` | `site/apex-core.js` |
| Claim click (drawer), focus tile, generate-narrative, board `narrative_from_focused_claim` | sync + `nr2-apex-voice-carry` + seed timestamp |
| Narratives seed consume + 5‑min TTL + voice trigger → `[ClaimRef:ID]` | `site/apex-narratives.js` |
| Backend session + HAL prompt block | unchanged (`hal_learning.py`, `/api/hal-learning/session`) |
| Tests | `test_rec009_voice_context_carry.py` |

## Honesty

- Claim IDs only (already visible to staff); no patient demographics added to storage keys
- DesktopBridge or `/api/hal-learning/session` fail silently
- REC-008 batch narratives untouched

## Validate

1. Hard-refresh Apex  
2. Claims → click a card → Network POST `/api/hal-learning/session`  
3. Generate Narrative → status “Carrying: Claim …”  
4. 🎙 Voice: “draft appeal for this claim” → HAL prompt includes `[ClaimRef:…]`  
5. `python -m pytest test_rec009_voice_context_carry.py -q`
