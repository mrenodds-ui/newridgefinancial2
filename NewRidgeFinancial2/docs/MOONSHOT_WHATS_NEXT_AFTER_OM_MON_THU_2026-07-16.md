# Moonshot AI — What's Next After OM Mon–Thu Patient List (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_om_mon_thu_consult.py`
**Shipped:** `2310d0d` · `16197d2` · `873b4c6`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> continue

---

# Verdict
**HAL patient hash handoff → real set_patient_context / dossier summarize tool** (completes the 873b4c6 prefill into a live HAL tool loop).

## 0. Operator Intent (verbatim)
continue

## 1. Recommended NEXT
- **Name:** HAL Patient Context Set + Dossier Summarize Tool (Optical OM → HAL loop completion)
- **Why now:** Commit 873b4c6 shipped the “Ask HAL” handoff with patientHash *prefill*; the LIVE AUDIT shows build `nr2-12043-hal-patient-summary` thematically centered on HAL summarization, the local HAL hub is live (`192.168.50.244:8765`), and the Office Manager role carries `read_patient_dossier`. Converting the draft-prefill into a real `set_patient_context` + `summarize_dossier` tool call closes the loop while PHI/hash controls are already in place.
- **Effort:** Medium (1–2 sessions) — tool schema, HAL bridge handler, optical page callback, audit hook.
- **REAL files:**
  - `NewRidgeFinancial2/site/nr2-optical-page-hal.html` / `.js` (extend handoff from prefill to context set)
  - `nr2_hal_tools.py` (or equivalent) — new `summarize_patient_dossier` tool definition
  - `nr2_api_hal.py` — `POST /api/hal/set-patient-context` (RBAC-scoped, hashes PHI)
  - `nr2_audit_logger.py` — leverage existing `hal-patient-context` audit endpoint
  - `nr2-optical-page-office-manager.js` — mini-dossier “Ask HAL” button triggers context set instead of draft compose
- **Validation gate:** 
  1. Mini dossier click → HAL sidebar opens with patient context pre-set (not just text in chat box).
  2. HAL can invoke `summarize_dossier` and receive SoftDent mini-dossier JSON (claims + estimates) without additional auth prompts.
  3. Audit record written with `patient_hash`, `tool_name`, `timestamp`, `role=office_manager`.
  4. Green laser remains true (no SoftDent write-back).

## 2. Why this beats the other candidates now
- **Beats Classic Apex 2B:** Audit shows `opticalOmHasWeekly: true` — the OM already has a working weekly view in optical; restoring the legacy Classic pack is technical debt cleanup, not forward value, and the constraint marks it optional unless “clearly highest value,” which it is not while HAL integration is mid-flight.
- **Beats Deepen OM patient context (local tools):** The build stamp and just-shipped commits indicate the product momentum is on *HAL-assisted* analysis, not local UI depth. Adding local clinical notes now would fragment the UX and duplicate effort once HAL summarization is live.
- **Beats SoftDent/Trellis worklist:** “Uncommitted nearby” is speculative; the HAL loop is already 80% wired (prefill exists) and delivers immediate Shadow-phase value for the OM role.
- **Beats Desk smoke:** Smoke is QA hygiene, not a capability package; the audit shows green lasers (`blockingCount: 0`, `level: fresh`), indicating the current optical track is stable enough to extend rather than pause.

## 3. Runner-ups
1. **Deepen OM patient context (clinical notes + treatment estimate local tools)** — Good incremental value, but defer until HAL summarization is proven; avoids building local UI that HAL may replace.
2. **Desk smoke: Force Close / beam proof one-shot** — Schedule for the end of the HAL track; validate the full Mon-Thu → Dossier → HAL flow before calling the milestone done.
3. **Classic Apex OM weekly widget restore (2B)** — Only if optical HAL adoption fails or Classic users escalate; otherwise keep stripped to reduce maintenance surface.

## 4. What NOT to redo
- Optical Mon–Thu list view, provider filter, or print CSS (already shipped 2310d0d/16197d2).
- Mini dossier panel structure or SoftDent claims embed (already shipped).
- HAL prefill draft composition (already shipped 873b4c6) — this package *upgrades* it to real context, not redoing it.
- SoftDent write-back (remains forbidden; stay READ-ONLY).

## 5. Acceptance criteria
- [ ] Clicking “Ask HAL” in the mini dossier calls `set_patient_context` with hashed patient identifier; HAL sidebar opens with context banner showing patient initials/hash.
- [ ] HAL tool `summarize_patient_dossier` available in local tool registry; returns dossier summary (appointments, claims, estimates) respecting `empty≠$0` rules.
- [ ] Audit entry persisted via existing `POST /api/audit/hal-patient-context` with `action_type=context_set` or `tool_call`.
- [ ] No PHI in URL or client storage; only hash/initials transmitted.
- [ ] Regression test: Mon–Thu list still loads <2s; provider filter still functions; print CSS unaffected.
- [ ] Validation run against live SoftDent snapshot (fresh as of audit timestamp `2026-07-16T11:38:xx`).

## 6. Executive Summary (5 bullets)
- **Completes the arc:** Converts the 873b4c6 “draft prefill” into a live, auditable HAL context loop, delivering on the `nr2-12043-hal-patient-summary` build theme.
- **Leverages live infrastructure:** Uses existing local HAL hub (`192.168.50.244:8765`), RBAC capabilities (`read_patient_dossier`), and fresh SoftDent snapshots (green laser).
- **Shadow-phase safe:** Read-only, hashed PHI, local-only (cloud HAL disabled per audit), fitting the `shadow` pilot constraints.
- **Immediate OM value:** Office Managers can ask natural-language questions about the selected patient’s financial/clinical snapshot without copying data manually.
- **Thin scope:** Focuses strictly on the handoff bridge and one summarize tool; avoids Classic Apex restoration or local UI bloat.

## 7. Approval Checklist
- [ ] HAL hub token rotation not required (existing token valid).
- [ ] SoftDent schema freeze acknowledged (read-only contract respected).
- [ ] RBAC matrix updated (new tool permission mapped to `office_manager` role).
- [ ] Privacy review: hash algorithm matches existing `patientHash` compose logic (SHA-256 + salt).
- [ ] Rollback plan: Feature flag `hal_patient_context` can disable new handoff, reverting to prefill-only behavior.
- [ ] Documentation: Update NR2 runbook “Optical OM → HAL Workflow” section.
