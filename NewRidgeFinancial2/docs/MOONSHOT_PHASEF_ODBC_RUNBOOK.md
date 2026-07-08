# Moonshot Phase F — SoftDent ODBC Deep Extract Runbook

**Build:** `hal-10095`  
**Scope:** Optional read-only SQL Server extract into `sd_*` SQLite tables (patients, procedures, payments, claims, appointments, providers, adjustments).

## When to use ODBC

Use the ODBC lane when you need **patient-level depth**, live appointments, or claim rows beyond what daysheet/CSV exports provide. The JSON/daysheet fallback lane remains sufficient for daily collections and production widgets when ODBC is not configured.

## Prerequisites (operator + IT)

1. **Read-only SQL login** on the SoftDent SQL Server instance (no INSERT/UPDATE/DELETE).
2. **64-bit ODBC System DSN** on the NR2 host (`ODBC Data Source Administrator (64-bit)`).
   - Driver: **ODBC Driver 17 or 18 for SQL Server**
   - DSN name example: `SoftDentReadOnly`
3. **Firewall** — NR2 PC must reach SQL Server port (typically 1433) from the financial hub machine.
4. **Python pyodbc** — included in NR2 Python environment; verify with `py -3.14 -c "import pyodbc"`.

## Step F1 — Configure DSN

Set in repo `.env` or system environment (never commit passwords to git):

```env
SOFTDENT_ODBC_DSN=SoftDentReadOnly
SOFTDENT_ODBC_USER=nr2_reader
SOFTDENT_ODBC_PASSWORD=<secret>
NR2_CONSENT_EXECUTOR=1
```

Alternate DSN env key: `NR2_SOFTDENT_ODBC_DSN`.

## Step F2 — Schema discovery

From repo root:

```powershell
cd NewRidgeFinancial2
py -3.14 scripts/discover_softdent_odbc_schema.py
```

Output is saved to `app_data/nr2/softdent_schema_discovery.json` (override with `--out` or `NR2_SOFTDENT_SCHEMA_DISCOVERY`).

Review `columnSamples` and adjust table/column names in the suggested queries before copying to `.env`.

## Step F3 — Per-table SQL queries

Copy `suggestedEnv` lines from discovery output into `.env`. Example keys:

| Env var | Target table |
|---------|----------------|
| `SOFTDENT_ODBC_PATIENTS_QUERY` | `sd_patients` |
| `SOFTDENT_ODBC_PROCEDURES_QUERY` | `sd_procedures` |
| `SOFTDENT_ODBC_PAYMENTS_QUERY` | `sd_payments` |
| `SOFTDENT_ODBC_CLAIMS_QUERY` | `sd_claims` |
| `SOFTDENT_ODBC_APPOINTMENTS_QUERY` | `sd_appointments` |
| `SOFTDENT_ODBC_PROVIDERS_QUERY` | `sd_providers` |
| `SOFTDENT_ODBC_ADJUSTMENTS_QUERY` | `sd_adjustments` |

Queries must be **SELECT only**. Column aliases should match NR2 expectations (`patient_id`, `proc_date`, `ada_code`, etc.) — see `softdent_odbc_extract.py` `_populate_from_odbc()`.

## Step F4 — Run extract

**Workstation (8766):** Sync tab → **Sync SoftDent**

**API (8765 loopback):**

```http
POST /api/admin/extract-softdent-odbc
Content-Type: application/json

{"force": true}
```

Requires `NR2_CONSENT_EXECUTOR=1`.

**Automatic:** `import_sync.py` calls `ensure_softdent_odbc_fresh()` during import refresh.

## Step F5 — Verify

```powershell
py -3.14 -c "from softdent_odbc_extract import read_extract_status; import json; print(json.dumps(read_extract_status(), indent=2))"
```

Expect:

- `lastMode`: `odbc` when SQL lane succeeded (or `json-fallback` when using exports only)
- `populatedTables`: ≥ 3 for healthy lane
- `tableCounts.sd_patients`, `sd_appointments`, `sd_claims` > 0 when ODBC queries configured

**UI:** SoftDent page shows **sd_* extract** strip; workstation Sync footer shows table count.

**HAL:** Ask *"SoftDent ODBC extract status"* — uses `softdent_extract_status` tool.

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `odbc_not_configured` | DSN env unset | Set `SOFTDENT_ODBC_DSN` |
| `odbc_queries_not_configured` | DSN ok, no SQL | Run discovery, set `SOFTDENT_ODBC_*_QUERY` |
| `odbc_connect_failed` | Network/credentials | Test DSN in ODBC admin; verify firewall |
| `consent_executor_disabled` | Safety gate | Set `NR2_CONSENT_EXECUTOR=1` |
| `json-fallback` with DSN set | Query/table mismatch | Fix SQL using `columnSamples` |
| pyodbc missing | Python env | Reinstall NR2 Python deps |

## Security notes

- Use a **read-only** SQL principal; NR2 never writes to SoftDent via ODBC extract.
- Store credentials in system env or Windows Credential Manager — not in the repository.
- ODBC extract is consent-gated; workstation sync buttons stay disabled when `NR2_CONSENT_EXECUTOR=0`.

## Related files

| File | Role |
|------|------|
| `softdent_odbc_extract.py` | Extract orchestration, sd_* schema, fallback lane |
| `scripts/discover_softdent_odbc_schema.py` | Schema discovery + query templates |
| `import_sync.py` | Auto refresh during import |
| `GET /api/softdent/odbc-status` | Status for UI and HAL |
| `POST /api/admin/extract-softdent-odbc` | Manual/consent-gated extract |
