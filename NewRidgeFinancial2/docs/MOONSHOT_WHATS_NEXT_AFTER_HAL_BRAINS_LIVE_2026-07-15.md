# Moonshot AI — What's Next After HAL Brains Live Smoke (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Status:** ok
**Repo root:** `C:\Users\mreno\newridgefamilyfinancial`
**Prior:** `20d07a6` live route unblock · `nr2-12018-hal-brains`
**Script:** `scripts/run_moonshot_whats_next_after_hal_brains_live_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Harden the HAL money honesty gate immediately—force every monetary utterance to ground via live SoftDent/QB beams (or explicit UNAVAILABLE), eliminating hallucinated $35k/$48k mock values before any operational trust can be placed in the live chat.

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT (name, why now, effort, REAL files/ops, validation gate)
**Package:** HAL money honesty gate hardening (monetary grounding layer)  
**Why now:** HAL brains are LIVE (smoke green), but the “Total Functionability” audit identified monetary dishonesty as the critical blocker—HAL can currently hallucinate dollar amounts (e.g., $35,842, $48,100) instead of citing the live beams ($7,714 SoftDent AR, $78,399 QB revenue). Because NR2 is a financial program with shadow-pilot constraints, a chat that invents money is worse than a chat that refuses to answer. This is an OPS blocker (data truth > UX wiring).  
**Effort:** Medium (2–3 hours)—requires prompt engineering, tool-forcing logic, and response validation, no new infrastructure.  
**REAL files/ops:**
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\hal_brain_tools.py` — inject monetary tool policy (any query containing `$|dollar|revenue|AR|outstanding|balance` must route through `softdent-status` or `qb-summary` tools; refuse generative answers).
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\nr2_hal_gateway.py` — add pre-flight “money classifier” that rejects non-grounded monetary responses with 422 `money_honesty_violation` if live beam timestamp > 5 min stale.
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\hal_session_store.py` — append `moneyGrounded: true|false` and `beamTimestamp` to each turn JSONL for audit trail.
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\nr2_http_server.py` — ensure `/api/hal/chat` enforces tool-choice=required when money classifier triggers.
- `C:\Users\mreno\newridgefamilyfinancial\site\nr2-optical-page-hal.js` — render “$7,714 (SoftDent live 19:58)” vs “Unavailable (stale)” with red banner if HAL refuses due to missing beams.
**Validation gate:**
- Query “What is our AR?” → HAL must invoke `GET /api/hal/tools/softdent-status`, return “$7,714 outstanding (SoftDent, synced 2026-07-15T19:58Z)”, never a synthetic number.
- Query “How much revenue last month?” → HAL must invoke `qb-summary`, return “$78,399 (QB, synced 2026-07-15T19:59Z)”.
- If beams return `recordCount: 0` or 503, HAL must state “Financial data unavailable (source: SoftDent)” explicitly, never “$0”.
- No `$` symbols appear in HAL responses unless matched to a live beam value within the same session turn.

## 2. Why this beats the other candidates now
- **SoftDent GUI export E2E (#2):** Valuable, but export integrity depends on HAL first being honest about what it sees; if HAL lies about the pre-export AR balance, the consent model is compromised.
- **Reconciliation honesty (#3):** The reconciliation module is already dead (500) and marked UNAVAILABLE in the functionability audit; fixing it requires restoring the missing `apex_reconciliation_pack`, which is a larger CODE effort. Money honesty is a smaller, higher-leverage fix that prevents active harm while reconciliation remains offline.
- **Board-actions navigate (#4) / Optical subpage bind (#5):** Wiring navigation is moot if the “brain” driving the UI cannot be trusted with dollar figures; users will ignore HAL’s page suggestions if it hallucinates balances.
- **True token streaming (#6):** Smoke is green with buffered SSE; SSL adapter fix is a “nice to have” optimization, not a blocker. Monetary dishonesty is a trust blocker.

## 3. Runner-ups (2–3)
1. **SoftDent GUI export E2E from HAL consent** — Wire the `softdent_gui_export.py` trigger through the consent modal so office managers can refresh imports without leaving the HAL command center. (Deferred until money honesty is proven, otherwise HAL may consent to exports based on phantom data.)
2. **Reconciliation honesty — UNAVAILABLE vs pretend COHERENT** — Kill the 500-ing reconciliation endpoint or restore the real module; stop returning mock “COHERENT” status when the pack is missing. (Deferred because it requires deeper file restoration; money honesty is a quicker win with higher daily-ops impact.)
3. **Wire HAL board-actions navigate/director** — Allow HAL to open `/nr2-optical-softdent.html` or QB bench via `window.open` from the chat context. (Deferred because navigation without honest data is dangerous—HAL could open AR pages showing stale/mocked values.)

## 4. What NOT to redo
- **Brains greenfield:** Session store, multi-turn chat, SSE buffering, and rate-limit fixes are LIVE (smoke proved). Do not touch `hal_session_store.py` persistence logic or the SSE generator again.
- **Route unblocking:** `/api/hal/*` endpoints are registered and returning 200; do not restart the server or remap routes.
- **SoftDent write-back:** Still forbidden per build notes; do not enable POST write paths.
- **Apex SPA resurrection:** `hal-core`, `apex-core`, `app.js` remain removed; do not reintroduce legacy scripts.

## 5. Acceptance criteria
- [ ] HAL refuses to answer any query containing monetary terms (`$`, `USD`, `balance`, `outstanding`, `revenue`, `AR`, `AP`) unless the response includes a `tool_call` to `softdent-status` or `qb-summary` in that turn.
- [ ] HAL responses cite the exact live beam value ($7,714 / $78,399) with source and timestamp; no off-by-$1 hallucinations permitted.
- [ ] When beams report `hasData: false` or 503, HAL outputs explicit “Unavailable” text; empty sets are never rendered as `$0`.
- [ ] Session JSONL (`app_data/nr2/hal-sessions/*.jsonl`) contains `moneyGrounded: true` flag and `beamHash` for every turn involving currency.
- [ ] Optical page shows red “Stale data” banner if HAL response relies on beams older than 5 minutes.
- [ ] Browser automation test: Ask “What’s our AR?” → verify network tab shows `GET /api/hal/tools/softdent-status` before chat response completes.

## 6. Executive Summary (5 bullets)
- **Trust Blocker:** HAL brains are live but currently capable of hallucinating dollar amounts, violating financial software’s prime directive: never invent money.
- **Beam Grounding:** Force all monetary utterances through live SoftDent ($7,714) and QB ($78,399) tools; cache no longer than 5 minutes.
- **Explicit Unavailability:** Distinguish “data missing” from “zero dollars” in chat UI to prevent false financial decisions.
- **Audit Trail:** Append `moneyGrounded` boolean to every session turn JSONL for compliance shadow-pilot logs.
- **Prep for Export:** Once honesty is enforced, the consent-based SoftDent GUI export (runner-up #2) becomes safe to deploy because HAL will only propose exports based on verified live AR registers.

## 7. Approval Checklist
- [ ] Operator confirms monetary hallucination is the highest-risk live issue.
- [ ] SoftDent/QB beam endpoints confirmed stable (currently 17/19 sources fresh, 100% completeness).
- [ ] Path hygiene verified: all edits under `C:\Users\mreno\newridgefamilyfinancial`; no `C:\NewRidgeFamilyFinancial` references.
- [ ] Rollback plan: revert `hal_brain_tools.py` tool-forcing policy to previous permissive state if grounding causes excessive latency.
- [ ] Stakeholder aware: Office managers may see “Unavailable” more often until they sync SoftDent/QB, which is the desired honest behavior.
