# IT checklist — SoftDent read-only ODBC for Gold CSV (optional lane)

**When:** Carestream confirms SQL table/column names for insurance payment *lines*, or discovery finds them.  
**Not:** inventing InsCo×ADA paid rows from `sd_payments` / DaySheet / Print Preview.

## Blockers on this host (2026-07-13)

- `SOFTDENT_ODBC_DSN` / `NR2_SOFTDENT_ODBC_DSN` = **unset**
- `NR2_CONSENT_EXECUTOR` = **unset**
- Drivers present: ODBC Driver 17/18 for SQL Server (and others)

## Steps

1. Create **64-bit System DSN** (e.g. `SoftDentReadOnly`) → SoftDent SQL instance, **read-only** login.
2. Set env (do not commit secrets):

```env
SOFTDENT_ODBC_DSN=SoftDentReadOnly
SOFTDENT_ODBC_USER=nr2_reader
SOFTDENT_ODBC_PASSWORD=<secret>
NR2_CONSENT_EXECUTOR=1
```

3. Discover schema:

```powershell
cd C:\NewRidgeFamilyFinancial\NewRidgeFinancial2
C:\NewRidgeFamilyFinancial\.venv\Scripts\python.exe scripts\discover_softdent_odbc_schema.py
```

4. Find tables/views with **carrier + ADA/CDT + paid amount** at line grain (Carestream-named). Export CSV with headers matching NR2 gold aliases (`Insurance Company`, `Procedure Code`, `Paid Amount`, …).
5. Save as `C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv` → Apex Sync / gold-era-settlement run.
6. Gate: `paymentLines>0`, `settlementMatrixReady=true`, `inventedGold=false`.

See also: `docs/MOONSHOT_PHASEF_ODBC_RUNBOOK.md`, `docs/CARESTREAM_SUPPORT_TICKET_GOLD_CSV_2026-07-13.md`.
