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
Restart NR2 server to load nr2-12070 routes, then prove Trellis tomorrow-insurance HTTP 200 and validate desk smoke remains GREEN with appointments-range emitting apptTimeColumn.

## 0. Operator Intent (verbatim)
continue

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Package:** NR2-12071-RESTART-ROUTE-PROOF  
**Why now:** The LIVE AUDIT shows `trellisTomorrow.error: "HTTPError"` and the build notes explicitly state *"Restart NR2 server to load new routes"*. Commit 82aa59e deployed the Trellis tomorrow-insurance endpoint and the appointments-range fix (always emit `apptTimeColumn`), but the runtime is still serving the old route table. Until the process restarts, the new `/api/trellis/tomorrow` handler is unreachable, desk smoke cannot validate the HTTP path, and the morning bundle pipeline cannot initialize.

**Effort:** 15 min (process restart + 3 validation curls).

**REAL files (known NR2 layout):**
- `C:\Users\mreno\newridgefamilyfinancial\app.py` (or `server.py` / `main.py` — the ASGI/WSGI entrypoint)
- `C:\Users\mreno\newridgefamilyfinancial\routes\trellis.py` (new tomorrow-insurance handler)
- `C:\Users\mreno\newridgefamilyfinancial\services\desk_smoke.py` (HTTP probe logic)
- `C:\Users\mreno\newridgefamilyfinancial\services\appointments_range.py` (apptTimeColumn emitter)

**Validation gate (must pass before proceeding):**
1. `GET /api/trellis/tomorrow` returns HTTP 200 with JSON payload containing `targetDate`, `total`, `hasData` (not HTTPError).
2. Desk smoke run shows `status: "GREEN"`, `deskProof: "MATCH"`, `forceCloseAvailable: false` (laser-gated).
3. `appointmentsRange.apptTimeColumn` is non-null (populated with time strings or empty array `[]`, never missing key).
4. No 500s in `NR2.log` post-restart.

## 2. Ordered backlog AFTER #1 (2–4 items)
1. **NR2-12072-SOFTDENT-MORNING-BUNDLE** — Rehearse SoftDent GUI morning Excel export (`softdent_export_morning_bundle`) and populate `periodCloseStatus.morningBundle` with the shadow-day run. Harden the desktop report-pull path so the Excel parser handles null cells as `emptyNotZero` (not `$0`).  
   *Files:* `services/softdent_export.py`, `services/period_close.py`, `utils/excel_parser.py`.

2. **NR2-12073-APEX-2B-WEEKLY-WIDGET** — Classic Apex 2B weekly widget (optional; only if post-restart audit shows widget gap). Low priority unless OM dashboard reports missing weekly rollup.  
   *Files:* `widgets/apex_2b.py`, `routes/widgets.py`.

3. **NR2-12074-EXCEL-PATH-HARDENING** — Defensive parsing for period-close Excel paths (schema validation, PHI hash on initials, temp file cleanup).  
   *Files:* `services/excel_import.py`, `services/phi_hasher.py`.

4. **NR2-12075-HAL-BLUENOTE-DUCKING** — HAL BlueNote voice/ducking follow-on only if LIVE AUDIT after #1 shows `cloudHal.enabled: true` and voice gap exists. Currently disabled; defer.  
   *Files:* `services/hal_voice.py`, `config/hal.yaml`.

## 3. Why this beats the other candidates now
- **Candidate 2 (SoftDent GUI bundle):** Cannot succeed while the server returns HTTPError on the Trellis probe; the morning bundle depends on the same route table that is currently stale. Restart is a prerequisite.
- **Candidate 3 (Apex 2B):** Widget data is secondary to core financial pipeline stability; audit shows no widget blocking errors.
- **Candidate 4 (Excel hardening):** Belongs after the bundle rehearsal (NR2-12072) so we have real Excel files to harden against.
- **Candidate 5 (HAL BlueNote):** `cloudHal.enabled` is `false` in LIVE AUDIT; no gap exists today.
- **Candidate 6 (Other):** No other gaps are blocking; the HTTPError is the only red flag.

## 4. What NOT to redo
- OM schedule enrich (already shipped in nr2-12070).
- Trellis huddle data model (already on main).
- This-patient shortcut logic (already covered, `thisPatientShortcutCovered: true`).
- PushEngage scorer or embeds (hygiene already applied; AVOID rule active).
- Flip `forceCloseAvailable` to `true` on GREEN+MATCH (must remain laser-gated by design; keep `false` unless red lasers fire).

## 5. Acceptance criteria
- [ ] Server process terminated and restarted; new PID in logs.
- [ ] `trellisTomorrow.ok === true` and `error === null` in LIVE AUDIT.
- [ ] `trellisTomorrow.total` is a number (≥ 0) and `targetDate` is ISO date string.
- [ ] `appointmentsRange.apptTimeColumn` is present (array) even when `hasData === false`.
- [ ] `deskSmokeLast.morningConfidence` is non-null after first morning run post-restart.
- [ ] No regressions: `periodCloseStatus.status` remains `"completed"`, `alignmentLasers.green` stays `true`.
- [ ] `softdent` sources remain `fresh` (lastSyncAt within 5 min of restart).

## 6. Executive Summary (5 bullets)
- **Restart Required:** Build nr2-12070 added new HTTP routes (Trellis tomorrow, appointments-range fix) that are not loaded until the server restarts; current HTTPError proves the route is unreachable.
- **Validation Before Bundle:** Morning bundle and period-close shadow runs depend on valid HTTP probes; restart must precede SoftDent Excel rehearsal.
- **Laser-Gate Intact:** Force Close remains unavailable (`forceCloseAvailable: false`) by design; do not bypass even when desk smoke is GREEN.
- **SoftDent Read-Only:** All exports remain read-only; empty cells will map to `emptyNotZero`, not `$0`, in the upcoming bundle package.
- **Sequential Safety:** NR2-12071 validates the runtime; NR2-12072 exercises the business logic; NR2-12073+ are optimizations deferred until the pipeline is proven stable.

## 7. Approval Checklist
- [ ] Operator acknowledges server restart is required to load nr2-12070 routes.
- [ ] Backup or shadow copy of `app_data/nr2/office` verified before restart.
- [ ] Maintenance window communicated to OM desk (brief interruption expected).
- [ ] Validation gates for NR2-12071 documented and ready to execute post-restart.
- [ ] Next package (NR2-12072) held in backlog until gate #1 passes.
