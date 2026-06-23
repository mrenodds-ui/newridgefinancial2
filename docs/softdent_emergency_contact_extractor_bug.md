# SoftDent Emergency Contact Extractor Bug

## Summary

The local dashboard refresh pipeline is healthy, but the live Sensei SoftDent transaction feed is still absent. The clearest upstream defect currently visible is a repeated `ExtractEC` failure in the Sensei Gateway Client when reading the SoftDent emergency-contact table.

The observed exception is:

```text
System.InvalidOperationException: The data is NULL at ordinal 23. This method can't be called on NULL values. Check using IsDBNull before calling.
at Client.Service.DataAdapters.SoftDent.ExtractorHelper.ExtractEC(JObject jPatient, String patId)
```

## Exact Field

The SoftDent emergency-contact extractor query is in [C:/ProgramData/Sensei Gateway Client/DataAdapters/SoftDent/Scripts/Extraction/EmergencyContact.sqlite](C:/ProgramData/Sensei%20Gateway%20Client/DataAdapters/SoftDent/Scripts/Extraction/EmergencyContact.sqlite#L1):

```text
SELECT * FROM PatientEmergencyContact WHERE [LegacyKey] = @legacyKey
```

The SoftDent local table definition is in [C:/ProgramData/Sensei Gateway Client/DataAdapters/SoftDent/Scripts/PrepareLocalDB/Tables/PatientEmergencyContact.sqlite](C:/ProgramData/Sensei%20Gateway%20Client/DataAdapters/SoftDent/Scripts/PrepareLocalDB/Tables/PatientEmergencyContact.sqlite#L1).

Column ordinal `23` in that schema is:

```text
SoftDentEmergencyContactTextBoxValue
```

That makes the most likely root cause:

```text
ExtractEC is calling GetString(23) against PatientEmergencyContact.SoftDentEmergencyContactTextBoxValue when that column is NULL.
```

## Operational Evidence

- A fresh local 45-minute refresh completed successfully on 2026-06-16.
- The regenerated import report still requested `appointments`, `patients`, and `transactions`.
- The transaction diagnostic still showed `file_count = 0`, `rows_seen = 0`, `rows_mappable = 0`.
- The incremental extraction state still showed `source = sqlite-export`, `transactions = 0`, `collections = 0`.

## Sensei Runtime Evidence

- Emergency-contact extractor errors recurred for hours instead of causing a full local service stop.
- SignalR reconnected after those errors, which suggests a degrading record-level extractor bug rather than a total client crash.
- After the late-day check window, there were still emergency-contact extractor errors and zero transaction mentions.

## Impact

- The local dashboard/import pipeline is working.
- The program is correctly surfacing `READY_WAITING_ON_SOURCE_DATA` instead of inventing missing transaction data.
- The live Sensei transaction entity is still not being emitted to the local DataSync path.
- The emergency-contact extractor defect is a concrete upstream SoftDent/Sensei bug that may be degrading or short-circuiting broader extraction behavior.

## Requested Vendor Action

1. Confirm whether `PatientEmergencyContact.SoftDentEmergencyContactTextBoxValue` is allowed to be `NULL` in supported SoftDent data.
2. Make `ExtractEC` null-safe for ordinal `23`, ideally with `IsDBNull(23)` or SQL-side `COALESCE`.
3. Confirm whether this extractor failure can block or degrade transaction entity emission for the same tenant session.

## Local Recheck Command

Run the repo diagnostic script to regenerate the same conclusion from current files:

```powershell
C:\NewRidgeFamilyFinancial\.venv\Scripts\python.exe C:\NewRidgeFamilyFinancial\scripts\check_softdent_emergency_contact_extractor.py
```