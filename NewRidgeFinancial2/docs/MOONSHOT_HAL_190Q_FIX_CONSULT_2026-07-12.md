# Moonshot AI — HAL 190Q Fix Plan (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Source eval:** `MOONSHOT_HAL_190Q_REPORT_2026-07-12.md` / `HAL_190Q_EVAL_2026-07-12.json`  
**Script:** `scripts/run_moonshot_hal_190q_fix_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot how to fix the 190 questons issues and report

---

# Verdict
HAL is technically stable but operationally broken: 74% of responses ignore format constraints, latency exceeds 50 seconds, and the evaluation rubric misidentifies compliant read-only refusals as failures, requiring immediate gateway validation layers and scoring recalibration.

## 0. Operator Intent (verbatim)
ask moonshot how to fix the 190 questons issues and report

## 1. Problem Diagnosis (ranked; blunt)
1. **Brevity Constraint Ignorance (P0)**: The 32B model generates verbose prose despite explicit sentence limits because `nr2_hal_gateway.py` lacks post-generation validation; 73.7% quality failures stem directly from unenforced output constraints.
2. **Scoring Rubric Mismatch on Read-Only (P0)**: `scripts/hal_eval_scoring.py` uses literal string matching for "read-only" while the gateway returns policy-compliant phrases like "cannot post" or "I am not able to modify," causing 75% false-negative compliance scores despite correct local-policy enforcement.
3. **Deliverable Structure Absence (P1)**: No structured output schema is enforced for "steps/paths" requests, resulting in narrative text instead of actionable lists or decision matrices.
4. **Latency Architecture (P1)**: 32B Q4_K_M averages 53s due to synchronous blocking calls without streaming; hardware (R9700) is sufficient but UX is unacceptable for interactive staff workflows.
5. **Speculative Code Invention (P2)**: Unknown CARC codes trigger hallucinated interpretations instead of hard refusals or escalations.

## 2. Fix Package (ordered phases)

### Phase 1: Constraint Enforcement & Scoring Alignment (Days 1-2)
**Goal**: Raise quality pass rate to >85% and read-only OK to 100% by fixing validation and scoring logic.  
**Why**: Current 26.3% quality and 25% read-only rates are blocking production release; these are logic errors, not model capability issues.  
**Effort**: Low (code changes only, no model retraining).  
**REAL Files**:
- `NewRidgeFinancial2/nr2_hal_gateway.py`: Add `validate_constraint_compliance()` post-generation filter in `clean_gateway_text()` to detect sentence count violations (split by period + space, count <= limit) and trigger regeneration with penalty prompt.
- `scripts/hal_eval_scoring.py`: Modify `has_read_only_mention()` to accept regex pattern `(read[- ]?only|cannot (post|modify|write)|I am not able to|local-policy blocks)` instead of literal "read-only".  
**Validation Gate**: Run 190Q eval subset (n=20) and verify quality pass >85%, read-only OK = 100% on previously failed cases.

### Phase 2: Structured Deliverables (Days 3-4)
**Goal**: Achieve >70% deliverable rate by forcing structured output for action-oriented queries.  
**Why**: Staff requests for "steps/paths" require machine-readable or bulleted deliverables, not prose.  
**Effort**: Medium (prompt engineering + JSON mode).  
**REAL Files**:
- `NewRidgeFinancial2/nr2_hal_gateway.py`: In `evaluate_query()`, detect deliverable intent (keywords: "steps", "path", "how to", "procedure") and set `format: json` in `call_ollama_chat()` options with schema `{"steps": [], "caution": ""}`; add fallback to markdown list if JSON fails.
- `NewRidgeFinancial2/nr2_hal_gateway.py`: Add `is_deliverable_request()` helper using keyword matching before model call.  
**Validation Gate**: Deliverable rate >70% on 50-question test set containing explicit "provide steps" queries.

### Phase 3: Latency Mitigation via Streaming (Days 5-7)
**Goal**: Reduce perceived latency to <2s time-to-first-token (TTFT) while maintaining total generation time; reduce avg latency to <15s for short queries.  
**Why**: 53s blocking calls break staff workflow continuity.  
**Effort**: Medium (SSE implementation).  
**REAL Files**:
- `NewRidgeFinancial2/nr2_hal_gateway.py`: Modify `call_ollama_chat()` to use `stream: true` in Ollama options; accumulate chunks in buffer while yielding SSE events.
- `NewRidgeFinancial2/site/hal-core.js`: Update SSE handler to render tokens as they arrive instead of waiting for full response (verify `hal-agent.js` for `EventSource` handling).
- `NewRidgeFinancial2/nr2_hal_gateway.py`: Verify integration with existing `keep_alive` optimization (already shipped in `apex_hal_cache_warm_pack.py`).  
**Validation Gate**: 95th percentile TTFT <2s; avg latency <15s on chat8b lane subset (n=50).

### Phase 4: CARC Code Safety Hardening (Days 8-10)
**Goal**: Eliminate hallucinated interpretations of unknown codes; achieve 0% speculative invention.  
**Why**: Financial/insurance codes require high precision; "possible interpretation" is liability risk.  
**Effort**: Low (lookup table + prompt adjustment).  
**REAL Files**:
- `NewRidgeFinancial2/nr2_hal_gateway.py`: Add `known_carc_codes` set in `try_local_policy_reply()`; if query matches CARC pattern and code not in set, return standard refusal: "This code is not in my governed memory. Escalate to admin." Do not route to 32B for speculation.
- `NewRidgeFinancial2/nr2_hal_gateway.py`: Update system prompt template to include instruction: "If asked about unknown codes, state you do not know and stop. Do not speculate."  
**Validation Gate**: 100% refusal rate on unknown CARC codes in test set (n=10).

## 3. What NOT to redo (already shipped / traps)
- **Do not load 8B model concurrently**: Lane labels are routing aliases only; loading 8B alongside 32B on R9700 risks OOM and provides minimal latency gain for the complexity.
- **Do not retrain or fine-tune**: Issues are inference-time constraint violations, not model knowledge gaps; 32B Q4_K_M has sufficient capability.
- **Do not modify `apex_hal_cache_warm_pack.py`**: Keep-alive logic already shipped and operational.
- **Do not add new rubric criteria**: Fix existing scoring logic rather than expanding the evaluation surface.
- **Do not invent financial figures**: Maintain existing policy against speculative dollar amounts (empty ≠ $0).

## 4. Acceptance Scorecard Targets (post-fix)
| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| Quality Pass Rate | 26.3% | ≥85% | Phase 1 constraint validator |
| Deliverable Rate | 27.9% | ≥75% | Phase 2 structured output |
| Read-Only OK Rate | 25.0% | 100% | Phase 1 rubric regex fix |
| Avg Latency (All) | 52.8s | <15s | Phase 3 streaming |
| Consent OK Rate | 75.0% | 100% | Phase 1 hardening |
| Yes/No Lead Rate | 90.9% | ≥95% | Phase 1 brevity enforcement |
| CoT Leak Rate | 0.0% | 0.0% | Maintain (no changes) |
| Technical Success | 100% | 100% | Maintain |

## 5. Executive Summary
- **Root Cause**: The system answers correctly but ignores format constraints and uses a misaligned evaluation rubric that penalizes compliant policy language.
- **Quick Wins**: Post-generation sentence counting and regex-based read-only detection will lift quality from 26% to >85% within 48 hours.
- **Latency Reality**: 32B Q4_K_M on R9700 cannot sub-10s without streaming; implement SSE to fix perceived performance without hardware changes.
- **Safety Gap**: Unknown CARC codes require a lookup gate to prevent speculative financial liability.
- **Risk**: Delaying Phase 1 fixes leaves the system unfit for staff use due to unactionable verbose responses and false compliance failures.

## 6. Approval checklist
- [ ] Confirm no 8B model loading (maintain 32B single-model architecture)
- [ ] Verify `scripts/hal_eval_scoring.py` regex changes cover "cannot post" variants
- [ ] Validate `nr2_hal_gateway.py` sentence split logic handles abbreviations (e.g., "Dr.", "No.")
- [ ] Confirm SSE implementation in `hal-core.js` does not break existing voice/SSE multiplexing
- [ ] Review CARC code whitelist approach with compliance team
- [ ] Schedule 190Q re-run within 48 hours of Phase 1 deployment