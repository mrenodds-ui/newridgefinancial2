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
