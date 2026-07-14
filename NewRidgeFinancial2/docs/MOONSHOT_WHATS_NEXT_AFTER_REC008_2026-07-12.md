# Moonshot AI — What's Next After REC-008 (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Script:** `scripts/run_moonshot_whats_next_after_rec008_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

**Constraint:** avoid GitHub / PR for now.

---

# Verdict
Close REC-009 voice context carry locally to complete the Expert SE loop and eliminate HAL's conversational amnesia between voice turns.

## 0. Intent
Finish the only remaining Expert SE NICE item (REC-009) so HAL maintains entity continuity across multi-turn voice sessions in the Apex staff UI without requiring GitHub operations.

## 1. Already Done (do not redo)
- REC-008 batch claim narratives (consent, batch-seed/batch-generate APIs, workbench Batch Generate, browser print/PDF packet)
- Expert SE Phases 1–3, compact pages, import gate harden, inbox sync coherence
- Zero-scroll widgets (hal-10561)
- HAL GPU pin → qwen3:32b (hal-local:32b)
- Deterministic import-gap replies naming for `quickbooks.payroll` + `quickbooks.ap`

## 2. Recommended NEXT — REC-009 Voice Context Carry (Local-Only)
**Goal:** Persist HAL voice session context (entities, intents, last action) across browser refreshes and consecutive voice turns so the operator does not have to re-seed patient/claim IDs.

**Why now:** It is the sole "Open NICE" from Expert SE; removes the last UX friction in live HAL voice; requires zero external auth or PR workflows.

**Effort:** Small (client-side state bridge + minor HAL surface patch).

**Files:**
- `NewRidgeFinancial2/site/apex-hal-voice.js` (or existing `apex-*.js` voice surface) – context serialization
- `NewRidgeFinancial2/apex_backend.py` – lightweight `/voice/session` endpoint for ephemeral state if client-side storage is insufficient
- `NewRidgeFinancial2/apex_program_improve_pack.py` – context carry logic and validation hooks

**Validation gate:**
- Voice turns 1→2→3 retain references (e.g., "the patient we just discussed") without re-prompting
- Survives browser refresh; no PII leaked to localStorage keys; qwen3:32b receives consistent context window

## 3. Runner-up options (max 3)
1. **QB Payroll/AP File Export Ingestion** – Drop-zone handler in `site/apex-inbox.js` to auto-parse QuickBooks payroll/AP exports into the inbox (completes the optional missing piece).
2. **gitignore Hygiene** – Add `site/index.pre-apex.html` to `.gitignore` and purge from index (cleanup, zero risk).
3. **HAL Voice Cold-Start Cache** – Local Ollama model keep-alive tweak in `apex_backend.py` to prevent qwen3:32b unload between voice sessions (performance polish).

## 4. Approval checklist
- [ ] Voice context persists across 3+ turns and a browser refresh without GitHub push
- [ ] `apex_backend.py` session handlers log only hashed session IDs (no PHI)
- [ ] Zero-scroll widgets remain functional after voice surface changes
- [ ] No `gh auth`, `git push`, or PR creation required during implementation