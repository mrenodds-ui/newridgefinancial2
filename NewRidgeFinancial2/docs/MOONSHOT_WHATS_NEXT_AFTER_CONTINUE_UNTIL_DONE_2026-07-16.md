# Moonshot AI — What's Next After Continue-Until-Done (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_continue_until_done_consult.py`
**Shipped:** `82aa59e` continue-until-done closed
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> continue

---

# Verdict
Restart NR2 server to load the new Trellis routes and prove HTTP 200 on `trellis_tomorrow` before proceeding to SoftDent morning-bundle rehearsal.

## 0. Operator Intent (verbatim)
continue

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Package:** `NR2-12071-TRELLIS-HTTP-PROOF`  
**Why now:** LIVE AUDIT shows `trellisTomorrow.error: "HTTPError"` and `ok: null`. The build notes explicitly state *"Restart NR2 server to load new routes"* (82aa59e). Until the server restarts, the new Trellis tomorrow-insurance endpoint is unreachable, desk smoke cannot validate HTTP GREEN, and `morningConfidence` remains unpopulated. This is a deployment blocker, not a code defect.  
**Effort:** Low (operational restart + verification; zero code changes).  
**REAL files:**  
- `C:\Users\mreno\newridgefamilyfinancial\server.py` (or `app.py` / `main.py` entry point) — restart target  
- `routes/trellis.py` — new route module requiring load  
- `services/desk_smoke.py` — validation consumer  
- `app_data/nr2/office/` — Hub data path (per audit)  
**Validation gate:**  
1. `trellisTomorrow.ok === true`  
2. `trellisTomorrow.error === null`  
3. `deskSmokeRun.status === "GREEN"` **and** `deskProof === "MATCH"` **and** HTTP layer returns 200 (not just Python-level OK)  
4. `morningConfidence` field populates (non-null)  

## 2. Ordered backlog AFTER #1 (2–4 items)
1. **SoftDent GUI Morning Excel Bundle Rehearsal** (`NR2-12072-SOFTDENT-MORNING-BUNDLE`)  
   - Shadow-run the period-close morning bundle export via SoftDent GUI (read-only).  
   - Validate `periodCloseStatus.morningBundle` transitions from `null` to a valid path/hash.  
   - Confirm `emptyNotZero` remains `true` throughout.  

2. **Period-Close Excel Path Hardening** (`NR2-12073-PERIOD-CLOSE-EXCEL-PATH`)  
   - Harden the desktop report-pull logic for SoftDent → Excel → NR2 ingestion.  
   - Ensure PHI initials+hash masking on board views before Excel generation.  

3. **Desk Smoke: Trellis Tomorrow HTTP Resilience** (`NR2-12074-TRELLIS-RESILIENCE`)  
   - Add retry/backoff for Trellis HTTP calls (if not already present) to prevent transient `HTTPError` from failing desk smoke.  

4. **Classic Apex 2B Weekly Widget** (`NR2-12075-APEX-2B-WIDGET`) — *Optional, only if audit after #1–3 shows gap.*  

## 3. Why this beats the other candidates now
- **Candidate #2 (SoftDent morning bundle):** Cannot be validated end-to-end while the Trellis HTTP layer is failing; desk smoke will remain incomplete.  
- **Candidate #3 (Classic Apex):** No audit evidence of missing widget; Trellis HTTP error is a hard blocker.  
- **Candidate #4 (SoftDent report-pull):** Depends on stable period-close status, which depends on functioning Trellis tomorrow data for insurance validation.  
- **Candidate #5 (HAL BlueNote):** Audit shows no voice/ducking gaps; HAL Hub is reachable (`halHubUrl` responsive).  

## 4. What NOT to redo
- OM schedule enrich (already shipped).  
- Trellis huddle logic (already shipped).  
- This-patient shortcut coverage (already shipped).  
- PushEngage scorer or embeds (already shipped; AVOID rule active).  
- Flip `forceCloseAvailable` to `true` on GREEN+MATCH (must stay laser-gated by design).  

## 5. Acceptance criteria
- [ ] NR2 server restarted and new routes loaded (commit 82aa59e active).  
- [ ] `GET /api/trellis/tomorrow` (or equivalent) returns HTTP 200 with JSON payload.  
- [ ] `trellisTomorrow.hasData` is boolean (not null).  
- [ ] `deskSmokeRun` shows `status: "GREEN"`, `deskProof: "MATCH"`, and no `error`.  
- [ ] `morningConfidence` field is populated (number or object, not null).  
- [ ] `forceCloseAvailable` remains `false` (laser-gate preserved).  

## 6. Executive Summary (5 bullets)
- **Deployment Blocker:** LIVE AUDIT confirms `trellisTomorrow` throws `HTTPError` because new routes are not loaded; server restart is required to activate commit 82aa59e.  
- **Zero Code Change:** This package is purely operational (restart + smoke test); no Python or JS modifications.  
- **Validation Chain:** Fixing HTTP 200 unblocks `morningConfidence` calculation and validates the desk smoke “HTTP GREEN” requirement.  
- **SoftDent Next:** Once Trellis HTTP is proven, the immediate follow-on is the SoftDent morning-bundle rehearsal (period-close shadow day).  
- **Laser-Gate Preserved:** Force Close remains unavailable (`forceCloseAvailable: false`) until explicit business rules (outside GREEN+MATCH) are met.  

## 7. Approval Checklist
- [ ] Operator confirms NR2 server restart executed.  
- [ ] Operator confirms `trellisTomorrow` endpoint returns HTTP 200 (checked via browser/curl or desk smoke).  
- [ ] Operator verifies `deskSmokeRun.status === "GREEN"` post-restart.  
- [ ] Operator confirms `morningConfidence` is no longer null.  
- [ ] Operator approves proceeding to `NR2-12072-SOFTDENT-MORNING-BUNDLE`.
