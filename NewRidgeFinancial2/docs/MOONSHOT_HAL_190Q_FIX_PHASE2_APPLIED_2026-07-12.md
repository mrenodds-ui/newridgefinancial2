# Moonshot HAL 190Q Fix — Phase 2 APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_HAL_190Q_WHATS_NEXT_2026-07-12.md` / `MOONSHOT_HAL_190Q_FIX_CONSULT_2026-07-12.md`  
**Operator:** proceed  

## Goal

Raise deliverable rate on steps/path/how-to asks by enforcing structured output (JSON schema → numbered steps + caution), with markdown fallback and UI render that preserves lists.

## Applied (real paths)

| Piece | Where |
|-------|--------|
| `is_deliverable_request` + JSON schema + markdown normalize | `nr2_hal_gateway.py` |
| Ollama `format` schema on deliverable asks | `call_ollama_chat` / `evaluate_query` / stream |
| SSE aggregates deliverable replies before emit | `evaluate_query_sse_frames` |
| Scoring aligns with gateway intent + numbered lists | `scripts/hal_eval_scoring.py` |
| Client JSON→steps + preserve markdown | `hal-core.js` (`isDeliverableRequest`, `formatStructuredDeliverable`, `polishChatReply`) |
| Agent finalize preserve lists | `hal-agent.js` (`renderStructuredDeliverable`) |
| Step / caution HTML | `app.js` `formatHalMessageHtml` + `styles.css` |
| Tests | `test_nr2_hal_local_policy.py`, `scripts/test_hal_eval_scoring.py` |

## Honesty

- Structured outputs still forbid invented dollars, CARC meanings, PHI, and fictional paths  
- Caution field used for read-only / consent reminders  
- Empty ≠ $0 inherited from Phase 1  

## Not in this phase

- Phase 3 streaming TTFT polish beyond deliverable SSE aggregate  
- Live full 190Q re-run (optional after this lands)  

## Validate

1. `python -m unittest test_nr2_hal_local_policy -q` (from `NewRidgeFinancial2/`)  
2. `python -m unittest test_hal_eval_scoring -q` (from `scripts/`)  
3. Ask HAL: “What are the next steps to reconcile deposits?” → numbered steps + optional Caution  
