# NR2 Pilot Operator Runbook

**New Ridge Family Financial 2.0** — print this page for front-desk and office-manager staff.

---

## Daily start (2 minutes)

1. Double-click **`StartProgram.bat`** at the repo root.
2. Browser opens **`https://127.0.0.1:8765/`** — accept the local certificate warning once if prompted.
3. Confirm the **import traffic banner** is green or amber (not red).
4. In HAL, run **Staff handoff summary** or **Run readiness check** if starting a new shift.

---

## Shadow mode rules (first 30 days)

| Do | Do not |
|----|--------|
| Compare NR2 A/R and claims to SoftDent daily | Let NR2 be the only system of record yet |
| Review ERA match cards (👍 correct / 👎 wrong) | Auto-post without office-manager approval |
| Acknowledge HAL alert toasts | Disable TLS or bind to LAN |
| Log issues in your normal practice workflow | Share the browser tab with non-staff |

**HAL is a Level 1 assistant** — licensed office manager signs off on all postings and write-offs.

---

## Import freshness

- **Green / fresh** — financial work allowed.
- **Amber** — refresh imports soon; HAL may warn on financial questions.
- **Red / stale (>24h)** — posting blocked; click **Force Refresh** or run import sync before billing work.

---

## End of shift (3 minutes)

1. Open HAL transparency panel → **Clock out shift** (generates handoff report).
2. Review open ERA matches and alert toasts.
3. Close the NR2 browser tab (single-tab policy).

---

## Weekly checks (office manager)

```powershell
py -3.14 NewRidgeFinancial2\scripts\validate_production_readiness.py
```

All required checks should pass. Optional: QB and Twilio checks until those integrations are enabled.

Verify **`app_data\nr2\nr2_financial_mutations.log`** has entries for any test postings or write-offs.

---

## One-time IT setup (already done on this workstation)

```powershell
pip install sqlcipher3 keyring bottle APScheduler requests cryptography
powershell -File NewRidgeFinancial2\scripts\setup_localhost_tls.ps1
```

TLS files live in **`app_data\nr2\tls\`**. Dev-only bypass (not for production): `NR2_ALLOW_HTTP=1`.

---

## If something breaks

| Symptom | Action |
|---------|--------|
| App won't start — TLS error | Re-run `setup_localhost_tls.ps1` |
| Red import banner | Run import sync; confirm SoftDent/QB export paths in `.env` |
| HAL won't answer financial questions | Check import level; refresh imports |
| Database error on start | Restore from latest `app_data\nr2\backups\` copy |
| Second browser tab warning | Close extra tabs; use one NR2 tab only |

**Stop server:** `StopNewRidgeFinancial2.bat`

---

## Emergency contacts

- **Practice owner / dentist** — approve write-offs over $250 (dual approval with office manager).
- **IT** — certificate, SQLCipher, loopback bind issues.

---

*Build: hal-10025 · Pilot: CONDITIONAL APPROVE · Moonshot must-fix items implemented.*

---

## Phase 2 — Supervised pilot (days 31–60)

**Enable once shadow-mode Week 1 checks pass.**

```powershell
powershell -File NewRidgeFinancial2\scripts\Start-Pilot-Phase2.ps1
py -3.14 NewRidgeFinancial2\scripts\validate_supervised_pilot.py
```

| Capability | Operator rule |
|------------|----------------|
| **Alert toasts + morning routine** | Acknowledge alerts; review autonomous tick log weekly |
| **ERA auto-match** | Every match gets 👍/👎; no batch approve without review |
| **Posting queue** | Office manager approves each queue item; HAL never auto-posts |
| **Import automation** | Scheduled sync every 5 min (after Phase 2 setup script) |
| **QB read-only** | Optional — set `NR2_QBO_CLIENT_ID` / secret for sync only |

Copy `NewRidgeFinancial2/docs/examples/workstation_role.json.example` to  
`app_data/nr2/workstation_role.json` if not created by the setup script.

**Still not system of record** until Phase 3 — keep reconciling to SoftDent daily.

---

## Phase 3 — Production cutover (days 61+)

**Enable only after Phase 2 supervised pilot completes** and the office manager attests import accuracy.

Moonshot operational criteria (no dedicated Moonshot code file — implemented from batch5 validator patterns + financial report):

- **30+ days** shadow compare to SoftDent (`NR2_PILOT_MIN_SHADOW_DAYS`, default 30)
- **30+ days** supervised posting with human sign-off (`NR2_PILOT_MIN_SUPERVISED_DAYS`)
- Phase 2 validator passing
- Signed **`app_data/nr2/pilot_cutover.json`** (see `docs/examples/pilot_cutover_attestation.json.example`)

```powershell
powershell -File NewRidgeFinancial2\scripts\Start-Pilot-Phase3.ps1
py -3.14 NewRidgeFinancial2\scripts\validate_cutover_readiness.py
```

| Capability | Operator rule |
|------------|----------------|
| **System of record** | NR2 is primary for A/R and posting on this workstation |
| **Export approved postings** | Unlocked only in cutover phase |
| **SoftDent** | Keep read-only exports for backup until leadership signs off on full retirement |
| **Rollback** | Set `NR2_PILOT_PHASE=supervised` and restore from `app_data\nr2\backups\` if mismatch |

**Pilot phase env (optional):** `NR2_PILOT_PHASE=shadow|supervised|cutover` overrides `app_data/nr2/pilot_phase.json`.

Phase 1 setup (records shadow start):

```powershell
powershell -File NewRidgeFinancial2\scripts\Start-Pilot-Phase1.ps1
```

Dev-only bypass of day counters: `NR2_PILOT_SKIP_DAY_CHECKS=1` (not for production cutover).

