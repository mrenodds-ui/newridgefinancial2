# Moonshot AI — Program Suggestion After SoftDent Morning Bundle (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Status:** ok
**Repo root:** `C:\Users\mreno\newridgefamilyfinancial`
**Prior:** `a753f31` SoftDent morning bundle · `c5de424` beamHash desk proof
**Script:** `scripts/run_moonshot_program_after_morning_bundle_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> what do you suggest for program — then: run it through moonshot. Agent proposal: after SoftDent morning bundle + beamHash proof + Force Close + OPS alerts, prioritize desk confidence: ship a short desk smoke loop (close status, money-beams + dataBeamHash, Force Close availability, VERIFY BEAM MATCH) before more SoftDent GUI hardening, BlueNote send, or QB consent UX. Watch one real morning next.

---

# Verdict: Ship the desk smoke script to validate close status, money-beam integrity with dataBeamHash, Force Close availability, and VERIFY BEAM match before expanding GUI surface or adding BlueNote/QB features.

## 0. Operator Intent (verbatim)
what do you suggest for program — then: run it through moonshot. Agent proposal: after SoftDent morning bundle + beamHash proof + Force Close + OPS alerts, prioritize desk confidence: ship a short desk smoke loop (close status, money-beams + dataBeamHash, Force Close availability, VERIFY BEAM MATCH) before more SoftDent GUI hardening, BlueNote send, or QB consent UX. Watch one real morning next.

## 1. Recommended NEXT (name, why now, effort, REAL files/ops, validation gate)

**Package:** Desk Smoke Script / Confidence Loop

**Why now:** Shadow mode activated yesterday (`systemOfRecord: false` as of 2026-07-15T21:10:23Z). The desk now operates without historical safety nets and requires automated, continuous proof that the close pipeline, money beams, and Force Close escape hatch are functional. LIVE AUDIT exposes a concrete honesty gap: `beamVerify` returns HTTP 404 despite the `beamVerifyRoute: true` code marker and c5de424 "formal beamHash desk proof" shipping notice—the hash verification mechanism is currently unreachable. A smoke script forces this fix and prevents regression before QB consent or BlueNote features increase system complexity.

**Effort:** Low (2–3 hours) — Python health loop, JSONL logging, HAL hub status badge.

**REAL files/ops:**
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\desk_smoke.py` (new; validates close pipeline)
- `C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\ops\desk_smoke_log.jsonl` (runtime; structured results)
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\nr2_http_server.py` (add `GET /api/health/desk-smoke` or wire to existing hub)
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\site\nr2-optical-pages-hub.js` (surface "DESK SMOKE: GREEN/RED" badge with timestamp)
- Validates against LIVE AUDIT data:
  - `periodCloseStatus` (completed/beamHash 887abf908c98136e)
  - `moneyBeams` (SoftDent $7,714 + QB $78,399, beamHash adb651d7f098ab17)
  - `dataBeamHash` presence and consistency between close logs
  - `GET /api/hal/tools/beam-verify` (currently 404—must fix to pass)
  - Force Close availability bit (laser red/stalled vs healthy green)

**Validation gate:** Script exits 0 with hash match and 200 OK on beam-verify; exits 1 with mismatch, missing dataBeamHash, or 404 on verify endpoint. HAL hub displays last smoke timestamp and status color.

## 2. Why this beats the other candidates now (explicitly address the agent proposal)

- **Agrees with agent on priority:** Desk confidence and operational visibility supersede new feature work while in shadow mode. The agent correctly identifies that verifying Force Close availability and beam integrity is prerequisite to safe morning operations.
- **Addresses concrete honesty gap:** LIVE AUDIT shows `beamVerify: { "error": "HTTPError", "msg": "HTTP Error 404: Not Found" }`. The "formal beamHash desk proof" shipped in c5de424 is non-functional. A smoke script surfaces this immediately and provides a failing test that gates the fix, rather than discovering the gap during a live close.
- **Option 2 (laser-stall timer):** Already shipped in 0874a03 (period-close OPS alerts for blocked/stalled/Force Close). LIVE AUDIT shows lasers green (`"red": false, "green": true`); additional timer refinement is premature optimization.
- **Option 3 (SoftDent GUI harden):** LIVE AUDIT shows morning bundle functioning (SoftDent aging/register/collections all fresh, 17/19 sources connected). No failures observed. The agent correctly defers this pending "one real morning" observation—smoke script enables that observation with telemetry.
- **Option 4/5 (QB consent UX / BlueNote send):** Both require trusted shadow money first. QB AP/Payroll are stale (1662 min) but optional; BlueNote has no programmatic send API. Smoke script establishes hub trust before tackling these.
- **Option 6 (alternate LIVE AUDIT fix):** While the beamVerify 404 could be a standalone hotfix, the smoke script provides higher value by ensuring the fix works and preventing regression across all close pipeline components.

## 3. Runner-ups (2–3)

1. **Hotfix beamVerify 404:** Required for smoke script to pass, but insufficient alone. Ship as part of the smoke package, not a separate program.
2. **Wire QB sync consent UX:** QB AP/Payroll datasets are stale (optional severity). Useful for completeness, but lower priority than verifying the close pipeline that just entered shadow mode.
3. **Expand morning SoftDent pull:** Already completed (aging + register + collections). No evidence of failure in LIVE AUDIT to justify immediate GUI hardening.

## 4. What NOT to redo

- Do not rebuild SoftDent export logic (morning bundle stable per LIVE AUDIT freshness timestamps).
- Do not implement BlueNote outbound network send (no API exposed; hub remains the lane per prior docs).
- Do not add new SoftDent report IDs until smoke script validates current 3-report bundle integrity.
- Do not touch `C:\NewRidgeFamilyFinancial` (invalid root exists per LIVE AUDIT; path hygiene requires `C:\Users\mreno\newridgefamilyfinancial` only).
- Do not write-back to SoftDent (doctrine remains: Excel/Print Preview only, empty ≠ $0).

## 5. Acceptance criteria

- [ ] Smoke script executable via CLI and HAL Hub "DESK SMOKE" button.
- [ ] Validates `periodCloseStatus` matches `moneyBeams` totals (SoftDent $7,714 + QB $78,399).
- [ ] Validates `dataBeamHash` present in close logs and matches live beam hash.
- [ ] `GET /api/hal/tools/beam-verify` returns 200 with matching hash (fix 404 regression first).
- [ ] Force Close availability bit correctly reflects laser state (available only when red/stalled/blocked).
- [ ] Writes structured JSONL to `app_data/nr2/ops/desk_smoke_log.jsonl` with timestamp, status, and any hash mismatches.
- [ ] HAL hub displays last smoke status (green/red) and timestamp; red status triggers OPS alert.
- [ ] Script runs without error against real morning bundle (aging + register + collections) before closing this package.

## 6. Executive Summary (5 bullets)

- Shadow mode is live (`systemOfRecord: false`); desk operates without historical safety net as of 2026-07-15.
- LIVE AUDIT reveals `beamVerify` endpoint returns 404 despite shipping in c5de424—hash verification is currently broken, creating a concrete honesty gap.
- Agent’s desk smoke proposal correctly prioritizes operational confidence over BlueNote send, QB consent, or additional SoftDent GUI work.
- Smoke script will immediately surface the 404, force the fix, and provide continuous validation that money beams and close hashes remain consistent.
- Defer QB consent UX and BlueNote send until smoke passes consistently for one real morning with full 3-report pull.

## 7. Approval Checklist

- [ ] Operator confirms: Shadow mode requires automated desk confidence before expanding feature surface.
- [ ] Operator acknowledges: `beamVerify` 404 must be fixed for smoke script to pass (concrete CODE gap identified).
- [ ] Operator accepts: "Watch one real morning" follows smoke deployment, using smoke logs as telemetry.
- [ ] Path hygiene acknowledged: All operations restricted to `C:\Users\mreno\newridgefamilyfinancial`; invalid root `C:\NewRidgeFamilyFinancial` remains untouched.
