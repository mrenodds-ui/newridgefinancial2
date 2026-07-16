# Moonshot AI — What's Next After HAL Patient Context (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_hal_patient_context_consult.py`
**Shipped:** `2cd6959`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> continue

---

# Verdict
Ship the **Desk smoke extension with Force Close / beam proof** to close the data-integrity loop on the HAL patient-context workflow and enable OM attestation for shadow-mode financial reconciliation.

## 0. Operator Intent (verbatim)
continue

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Package:** Desk smoke extension: Mon–Thu list → patient-context bind → HAL summarize → Force Close / beam proof  
**Why now:**  
- LIVE AUDIT flags `forceCloseAvailable: false` despite `deskProof: MATCH`, leaving the shadow-mode financial close incomplete.  
- The just-shipped patient-context bind (2cd6959) creates a 30-minute HAL session window; without Force Close, the OM cannot attest “I’ve reviewed this patient’s dossier vs. SoftDent source-of-truth” which blocks supervised-mode promotion.  
- Required for the `empty ≠ $0` constraint validation (financial mode requires explicit zero vs. null handling before close).  

**Effort:** Medium (2–3 days)  
- Beam-hash diff logic (SoftDent ↔ NR2 cached dossier)  
- Force Close API endpoint (`POST /api/desk/force-close`) with RBAC (`write_posting`)  
- OM UI “Force Close / Beam Proof” button in mini-dossier footer (enabled only when `deskProof === 'MATCH'`)  
- Audit trail table `desk_close_attestations` (patient_id, beam_hash, closed_by, closed_at)  

**REAL files to touch:**  
- `routes/desk_smoke.py` – extend `/api/desk/smoke-check` to return `forceCloseEligible` boolean  
- `routes/force_close.py` – new endpoint, idempotent close with hash lock  
- `services/beam_validator.py` – compare SoftDent live row checksum vs. NR2 cached dossier checksum  
- `components/om/MiniDossier.tsx` – add “Force Close” button and attestation checkbox  
- `policies/hal/patient_context_policy.py` – inject `beam_status` into HAL context so HAL can report “Patient dossier is clean / dirty”  

**Validation gate:**  
1. OM opens Mon–Thu list → clicks patient → mini-dossier loads → HAL auto-summarizes.  
2. “Force Close” button appears only if beam hash matches; clicking it writes attestation row.  
3. `GET /api/desk/force-close-status` returns `closed: true` and HAL chat shows “This patient is force-closed for today.”  
4. Attempting close on hash-mismatch patient returns 409 with diff payload (SoftDent $X vs. NR2 $Y).

## 2. Why this beats the other candidates now
- **Deepen mini-dossier (clinical notes):** NR2 is `financialOnly` mode; clinical notes are out-of-scope for the current pilot and would require new SoftDent readers not yet validated for PHI hashing.  
- **SoftDent/Trellis eligibility worklist:** Marked “dirty/untracked” in prior notes; requires batch path hardening that risks destabilizing the fresh 12043 build.  
- **HAL “this patient” chat shortcut:** Nice UX polish, but the LIVE AUDIT shows the context bind is already functional (`set_patient_context: true`); Force Close is the missing compliance piece for shadow-mode exit criteria.  
- **Classic Apex 2B:** Fallback only if HAL adoption fails; HAL adoption is green (`green: true`).

## 3. Runner-ups (2–3)
1. **HAL “this patient” chat shortcut (Candidate 5)** – Immediate follow-on after Force Close ships; enables implicit patient references in HAL policy replies (“What’s the balance for **this patient**?”) using the bound 30m TTL context.  
2. **SoftDent/Trellis tomorrow-insurance worklist (Candidate 3)** – Required for next-day financial clearance, but blocked until Force Close proves the beam integrity of today’s data.  
3. **Deepen OM mini-dossier – treatment estimate only (subset of Candidate 1)** – Financially relevant (treatment $ estimate), but secondary to proving today’s closed ledger.

## 4. What NOT to redo
- Mon–Thu appointment list UI/UX (already shipped).  
- Mini-dossier base layout or claims list (already shipped).  
- `POST /api/hal/patient-context` binding logic or 30m TTL session handling (already shipped).  
- HAL auto-summarize trigger on patient open (already shipped).  
- SoftDent write-back (remains forbidden; read-only enforced).

## 5. Acceptance criteria
- [ ] `forceCloseAvailable` flips to `true` in LIVE AUDIT when beam hash matches.  
- [ ] OM can Force Close a patient in ≤2 clicks from the mini-dossier.  
- [ ] Closed patient shows visual lock icon; HAL chat prefix updates to “[CLOSED] Patient Name”.  
- [ ] Audit log captures who closed, when, and the beam hash.  
- [ ] Attempting modification of a Force-Closed patient by non-admin returns 403.  
- [ ] “Empty ≠ $0” validation runs pre-close (null vs. zero explicit check).  

## 6. Executive Summary (5 bullets)
- **Shadow-mode compliance:** Force Close is the final gate for the OM to attest “I’ve reviewed this patient’s financial dossier against SoftDent,” satisfying 30-day shadow pilot exit criteria.  
- **Beam integrity:** Hash-level proof (SoftDent ↔ NR2) prevents drift during the 30m HAL session window.  
- **Financial safety:** Explicit handling of `empty ≠ $0` ensures null balances are not interpreted as zero dollars during close.  
- **Non-blocking UX:** Force Close button appears only when data is clean; dirty data shows diff modal instead.  
- **HAL readiness:** Prepares the patient-context session for conversational shortcuts (runner-up #5) by finalizing the state machine (Open → Bound → Summarized → Closed).

## 7. Approval Checklist
- [ ] Security review of `/api/desk/force-close` (RBAC `write_posting`, CSRF token validation).  
- [ ] Privacy confirm: No PHI in beam hash (use HMAC-SHA256 of SoftDent record IDs + balance values only).  
- [ ] Database migration for `desk_close_attestations` table (encrypted at rest).  
- [ ] OM training brief: “Green laser = Force Close available; Red laser = reconcile first.”  
- [ ] Rollback plan: If Force Close corrupts, disable via feature flag `FORCE_CLOSE_ENABLED=false`.
