# Moonshot AI — What's Next After OM Clinical Mini-Dossier (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_om_clinical_mini_consult.py`
**Shipped:** `4039bf4`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> continue

---

# Verdict (one sentence — THE next package)
Ship the **HAL "this patient" policy shortcut** to resolve bound patientContext when the user query references "this patient" or "about this patient" without requiring the SoftDent patient ID, completing the patient-context UX loop opened by the just-landed bind + auto-summarize commits.

## 0. Operator Intent (verbatim)
continue

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** HAL “this patient” chat shortcut (patient-context reference resolution)

**Why now:**  
- The LIVE AUDIT explicitly flags `"thisPatientShortcut": false`, confirming the gap exists despite the patient-context bind (`2cd6959`) being live.  
- Without this shortcut, users must still manually paste a SoftDent ID to ask HAL about the patient they just clicked in the Mon–Thu list or OM mini-dossier, negating the value of the newly shipped context-bind feature.  
- It is a discrete, low-risk policy-layer change that leverages existing RBAC and PHI-handling (hash/initials) already validated in the optical OM panel.

**Effort:** Small (1–2 days). Single policy resolver + prompt prefix injection; no new SoftDent schemas or UI widgets.

**REAL files:**  
- `NewRidgeFinancial2/site/nr2-optical-hal/hal_policy_router.py` (or equivalent chat policy handler in `nr2_http_server.py` if monolithic)  
- `NewRidgeFinancial2/site/nr2-optical-om/om_patient_dossier.py` (read existing `patientContext` session blob)  
- `NewRidgeFinancial2/site/nr2-optical-hal/patient_dossier.py` (context binding validation helper)  
- `NewRidgeFinancial2/desk_smoke.py` (extend smoke test to verify context resolution handshake)

**Validation gate:**  
1. OM clicks a patient → HAL panel opens with context bound.  
2. User types: *"What is the copay for this patient?"* (no ID provided).  
3. HAL responds using the bound context without prompting for SoftDent ID.  
4. Audit marker `"thisPatientShortcut": true` in next LIVE AUDIT.  
5. Desk smoke passes with `"patientContextResolution": "ok"`.

## 2. Why this beats the other candidates now
- **Beats Desk smoke extension (Candidate 2):** LIVE AUDIT shows current desk smoke is `"GREEN"` with zero failures; Force Close is a convenience, whereas the missing `"thisPatientShortcut"` is a functional gap blocking fluid OM workflow.  
- **Beats SoftDent/Trellis eligibility worklist (Candidate 3):** Batch helpers already exist; this is hardening, not unblocking. The HAL shortcut unblocks immediate daily usage of the Mon–Thu list → dossier → HAL flow just shipped.  
- **Beats Classic Apex 2B widget (Candidate 4):** Explicitly marked optional; restoring legacy UI does not advance the OM patient-track narrative established by the last four commits.

## 3. Runner-ups (2–3)
1. **Desk smoke extension with Force Close / beam proof** – Extend `desk_smoke.py` to cover OM Mon–Thu → dossier → HAL path and enable Force Close when beam hash drifts; defer until after HAL shortcut lands to avoid testing two variables at once.  
2. **SoftDent/Trellis tomorrow-insurance worklist hardening** – Nightly eligibility verify; valid but lower urgency because current SoftDent imports are `"fresh"` (see LIVE AUDIT) and batch helpers exist.  
3. **Classic Apex 2B thin weekly schedule widget** – Optional legacy restore; only revisit if OM staff explicitly request the old Apex view after using the new HAL-integrated flow.

## 4. What NOT to redo
- Mon–Thu list UI (already shipped `873b4c6` et al.).  
- OM mini-dossier base structure or its clinical notes/treatment estimates (already shipped `4039bf4`).  
- Claims integration (already shipped).  
- HAL patient-context API bind or auto-summarize logic (already shipped `2cd6959`).  
- SoftDent write-back (forbidden by constraint).  
- Any invented `src/integrations/` paths.

## 5. Acceptance criteria
- [ ] HAL chat parser recognizes “this patient”, “the patient”, “about this patient”, and “current patient” as context-dependent references.  
- [ ] When `patientContext` is bound in session, HAL injects the bound SoftDent ID + PHI hash into the tool call without user re-entry.  
- [ ] When `patientContext` is **null**, HAL politely asks for the patient ID (no hallucination).  
- [ ] RBAC preserved: user must still hold `read_patient_dossier` capability; audit log records the resolved ID.  
- [ ] `empty ≠ $0` rule respected in any summary output.  
- [ ] Desk smoke updated to assert that a “this patient” query returns a non-error response when context is preset.

## 6. Executive Summary (5 bullets)
- **Gap identified:** LIVE AUDIT flags `"thisPatientShortcut": false` despite fresh patient-context bind infrastructure.  
- **User impact:** Eliminates friction in the newly shipped OM workflow (Mon–Thu list → dossier → HAL) by removing the need to copy/paste patient IDs into chat.  
- **Scope:** Policy-layer only; no new SoftDent reads, no UI widgets, no write-back.  
- **Risk:** Low; leverages existing session state and PHI-handling; trivial to smoke-test.  
- **Next step:** Merge shortcut resolver, update desk smoke validation, flip audit marker to `true`.

## 7. Approval Checklist
- [ ] REAL paths verified: `nr2-optical-hal`, `nr2-optical-om`, `om_patient_dossier.py`, `desk_smoke.py` only.  
- [ ] No `src/integrations/` invented.  
- [ ] SoftDent remains READ-ONLY; empty ≠ $0 enforced.  
- [ ] PHI handling uses hash/initials per existing OM board standard.  
- [ ] Commit message references build `nr2-12043-hal-patient-summary` baseline.  
- [ ] Rollback plan: revert policy router change + session injection; no DB migration required.
