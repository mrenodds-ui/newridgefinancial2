# Voice-to-Narrative + Payer Appeal Templates — Applied

**Date:** 2026-07-10  
**Build:** **hal-10360**  
**Status:** NICE items from claims/narratives consult — coded

## Voice-to-narrative

- HAL parses: `dictate findings: …`, `append to insurance: …`, `replace notes with: …`
- Board action `narrative_append` → opens Narratives and writes into the section
- Narratives page **🎙 Voice** button (Web Speech API) → routes through HAL dictate
- Words are operator speech/text only — HAL does not invent clinical findings

## Payer-specific appeal templates

Built-in (operator-overridable via LocalStore `nr2:v2:narratives:payer-templates`):

| Template | Match |
|----------|--------|
| Delta Dental | delta |
| Guardian | guardian |
| MetLife | metlife |
| Blue Cross Blue Shield | bcbs / blue cross |
| Generic Payer | fallback |

- Placeholders: `{{claimId}}`, `{{patientName}}`, `{{dos}}`, `{{clinicalNotes}}`, `{{procedures}}`, `{{denialClause}}`, etc.
- Narratives UI: payer template dropdown; auto-resolve from selected payer on Generate
- APIs: `GET/POST /api/apex/narratives/payer-templates`

## Files

- `apex_claims_narratives_pack.py` — templates, voice parse, appeal render
- `apex_backend.py` — HAL voice narrative, routes, structure includes templates
- `site/apex-narratives.js` — Voice button + template select + `applyVoiceText`
- `site/apex-core.js` — `narrative_append` board action
