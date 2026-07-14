# Moonshot HAL 190Q Fix — Phase 4 APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_WHY_ERRORS_2026-07-12.md`  
**Operator:** proceed  

## Goal

Close known-code CARC/CAS hallucination by serving curated whitelist briefs (25 CARC + 10 CAS) from lookup; unknown codes hard-refuse with no model fallback.

## Applied (real paths)

| Piece | Where |
|-------|--------|
| `CARC_BRIEFS` (25) + `CAS_BRIEFS` (10) + lookup/refuse helpers | `era835_parser.py` |
| HAL summary injects known briefs; unknown → refuse note | `era835_parser.summarize_835_for_hal` |
| ERA pack injects briefs on list/ingest; absent → refuse | `apex_era835_pack.py` |
| `try_local_policy_reply` consults whitelist before LLM | `nr2_hal_gateway.py` |
| Monospace/code-styled CARC brief render | `site/hal-core.js` (+ Apex DOM hook) |
| Tests | `test_carc_whitelist.py` |

## Honesty

- Briefs cite CMS X12 835 plain language only; no PHI; no invented dollars  
- Empty ≠ $0 preserved on patient-responsibility Staff Action lines  
- Unknown codes: `I cannot interpret this code; escalate to posting supervisor.`  
- CO-45 exact map text: `Contractual obligation; do not bill patient.`  

## Not in this phase

- Live full 190Q re-run (recommended after this lands)  
- Collections/Daysheet export gap  
- SoftDent write-back  

## Validate

1. `python -m unittest test_carc_whitelist -q` (from `NewRidgeFinancial2/`)  
2. `python -m unittest test_nr2_hal_local_policy -q`  
3. Ask HAL “What is CARC 45?” → whitelist brief (monospace in Apex chat)  
4. Ask HAL “What does CARC XX-99 mean?” → posting-supervisor refusal  
