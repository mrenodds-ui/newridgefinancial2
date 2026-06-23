# SoftDent Issue Timeline Report

## Scope

This report summarizes the accessible SoftDent / Sensei Gateway Client logs in this workspace and turns them into a dated incident timeline.

The available evidence starts in March 2026. No January or February log files were found in the accessible folders. The first setup-like artifacts appear on 2026-03-12, the first real extractor failure log appears on 2026-03-18, and the most detailed runtime failures appear in the 2026-06-17 client log.

## Evidence Sources

- [March 18 extractor log](C:/ProgramData/Sensei%20Gateway%20Client/DataAdapters/SoftDent/CSD_DataExtractor_18_0_2026-03-18.log)
- [April 3 extractor log](C:/ProgramData/Sensei%20Gateway%20Client/DataAdapters/SoftDent/CSD_DataExtractor_18_0_2026-04-03.log)
- [June 17 client log](C:/ProgramData/Sensei%20Gateway%20Client/Logs/Sensei%20Gateway%20Client_20260617.jsonl)
- [Emergency contact extractor bug note](softdent_emergency_contact_extractor_bug.md)

## Executive Summary

The failure pattern evolves in three phases:

1. March 12 start-up / seeding state: the local bridge exists, but no failure log is visible yet.
2. March 18 through April 3: the extractor repeatedly fails before meaningful data extraction because the SoftDent database path cannot be resolved.
3. June 17: the client is alive enough to process messages, reconnect SignalR, and run writeback, but it begins failing on emergency-contact rows with a null-field exception at ordinal 23, then later ordinal 24, while queue and service-lifecycle errors continue around it.

### Concise Summary

The logs point to brittle integration work rather than sabotage. March and April show repeated SoftDent database-path resolution failures that block extraction at startup, and June shows live runtime instability with SignalR reconnects, queue and service lifecycle failures, and repeated emergency-contact crashes caused by nullable fields being read as strings at ordinals 23 and 24. The pattern is consistent with defective implementation and weak runtime handling, not intentional disruption.

## Detailed Timeline

### 2026-03-12: Initial bridge state

What is visible:

- Bridge artifacts exist in the local SoftDent working area.
- Reference and seed-style files are present, but no operational failure log is visible for this date.

What this means:

- The integration appears to have been in an initial setup or seed state.
- There is no evidence in the accessible folders of a March 12 extraction failure yet.

### 2026-03-18 16:52: First real extractor failure window

The extractor log shows 27 separate start blocks on this date.

Representative startup sequence:

- Started Data Extractor on 03/18/2026 at 16:52
- Command Prompt Argument: entitytype=appointment
- Command Prompt Argument: daysbefore=-1
- Command Prompt Argument: daysafter=-1
- Command Prompt Argument: dbpath=c:\softdent
- DBPath - c:\softdent is NOT valid
- Command Prompt Argument: tenantid=0000950863
- Calling InitializeSoftdent()
- starting to parse config file
- Reading DB path from Registry

Observed failure chain:

- The tool tries to use `c:\softdent` from the command line, but rejects it as invalid.
- It falls back to registry lookup.
- The registry lookup for `Software\InfoSoft\SoftDent\SD_PATHS` fails.
- `LocalDirectory` and `WorkingDirectory` under `SOFTWARE\Wow6432Node\PWInc\SoftDent\AppSuite` are queried, but both paths are rejected because `C:\SoftDent\SoftDent.SYS` is not valid.
- The extractor stops with `Error: DB path is not set, Could not proceed further!!!`
- It then emits `Error 161: 'The specified path is invalid.`

Entity types attempted in the March 18 log:

- appointment
- patient
- insco

Impact:

- No useful extraction can proceed.
- The bridge is blocked at environment/configuration resolution, before record-level data handling.

### 2026-04-03 06:52 to 06:54: Same failure, broader entity coverage

The April log shows 90 extractor start blocks on this date.

Representative startup sequence is the same as March 18:

- Started Data Extractor on 04/03/2026 at 06:54
- entitytype=appointment
- dbpath=c:\softdent
- DBPath - c:\softdent is NOT valid
- Reading DB path from Registry
- registry lookups fail
- `C:\SoftDent\SoftDent.SYS` is not valid
- `Error: DB path is not set, Could not proceed further!!!`
- `Error 161: 'The specified path is invalid.`

Entity types attempted in the April 3 log:

- ada
- appointment
- appointmenttype
- dentist
- insco
- location
- patient

Interpretation:

- The integration has expanded the set of entity types it is trying to process.
- The environment issue still blocks every run before any meaningful extraction is completed.
- This is still a start-up/configuration failure, not yet the later runtime null-field failure.

### 2026-06-17 10:06 to 10:48: Runtime is alive, but transport and service lifecycle begin failing

The June 17 client log starts with a SignalR reconnect cycle:

- 10:06:24 AM: SignalR connection state changes from True to False
- 10:06:24 AM: SignalR disconnected. Will attempt to reconnect in 00:00:06.
- 10:06:30 AM: Attempting to connect to SignalR service.
- 10:06:32 AM: SignalR service connected.
- 10:06:32 AM: SignalR connection state changes from False to True

Then the client begins failing on message intake:

- 10:06:50 AM: Failed to read message from agent command queue.

At 10:48, service-level retries appear:

- 10:48:55 AM: WriteBackService retry attempt 1 in 00:00:03 because the message processor is already running and must be stopped first.
- 10:48:58 AM: Failed to acquire connection state lock during close event.
- 10:48:58 AM: SyncAgentService retry attempt 1 in 00:00:06 because the IServiceProvider has already been disposed.

Interpretation:

- The client is not fully down.
- It is reconnecting and processing, but its queue and service lifecycle management are unstable.
- These are infrastructure/runtime issues separate from the later data-row null problem.

### 2026-06-17 11:00 to 11:16: Emergency-contact null-field failures begin

The first record-level emergency-contact errors appear here.

Observed errors:

- 11:00:12 AM: Error creating Emergency Contact for `579276` in customer `0000950863`
- 11:10:12 AM: Error creating Emergency Contact for `574696` in customer `0000950863`
- 11:10:12 AM: Error creating Emergency Contact for `577616` in customer `0000950863`
- 11:10:12 AM: Error creating Emergency Contact for `578765` in customer `0000950863`
- 11:10:12 AM: Error creating Emergency Contact for `578855` in customer `0000950863`
- 11:16:12 AM: Error creating Emergency Contact for `579801` in customer `0000950863`

From the detailed exception payload, the root cause is:

- `System.InvalidOperationException: The data is NULL at ordinal 23`
- `Client.Service.DataAdapters.SoftDent.ExtractorHelper.ExtractEC`
- `Microsoft.Data.Sqlite.SqliteDataReader.GetString(Int32 ordinal)`

Meaning:

- The extractor is reading a field as a non-null string.
- The underlying SQLite value is NULL.
- The code is not guarding with `IsDBNull` before `GetString`.

### 2026-06-17 11:45 to 11:52: Queue failures recur

The runtime degrades again later in the morning:

- 11:45:47 AM: SignalR disconnected. Will attempt to reconnect in 00:00:05.
- 11:46:32 AM: Failed to read message from agent command queue.
- 11:46:32 AM: Failed to read message from write-back queue.
- 11:52:56 AM: WriteBackService retry attempt 1 in 00:00:02 because the message processor is already running and must be stopped first.
- 11:52:58 AM: Failed to acquire connection state lock during close event.
- 11:52:58 AM: SyncAgentService retry attempt 1 in 00:00:08 because the IServiceProvider has already been disposed.

Interpretation:

- The system is cycling between reconnects, queue failures, and service retries.
- This suggests instability in the messaging / writeback layer, not a one-off exception.

### 2026-06-17 11:58 to 15:28: Emergency-contact failures continue, and the null shifts from ordinal 23 to ordinal 24

Later in the day, emergency-contact extraction keeps failing on more records.

Observed record errors:

- 11:58:05 AM: Error creating Emergency Contact for `437501`
- 11:58:05 AM: Error creating Emergency Contact for `579875`
- 12:00:05 PM: Error creating Emergency Contact for `580350`
- 12:00:05 PM: Error creating Emergency Contact for `580359`
- 12:49:05 PM: Error creating Emergency Contact for `579868`
- 12:59:05 PM: Error creating Emergency Contact for `580019`
- 1:03:05 PM: Error creating Emergency Contact for `578490`
- 1:05:05 PM: Error creating Emergency Contact for `437501`
- 1:13:05 PM: Error creating Emergency Contact for `580262`
- 1:15:04 PM: Error creating Emergency Contact for `579274`
- 1:29:05 PM: Error creating Emergency Contact for `577913`
- 1:44:05 PM: Error creating Emergency Contact for `437501`
- 1:54:05 PM: Error creating Emergency Contact for `580157`
- 2:02:05 PM: Error creating Emergency Contact for `577913`
- 2:06:05 PM: Error creating Emergency Contact for `579274`
- 2:10:05 PM: Error creating Emergency Contact for `579868`
- 3:18:06 PM: Error creating Emergency Contact for `580350`
- 3:26:07 PM: Error creating Emergency Contact for `580157`
- 3:28:05 PM: Error creating Emergency Contact for `580157`

The exception pattern changes later in the day:

- Earlier batch: ordinal 23
- Later batch: ordinal 24

Interpretation:

- The extractor is hitting more than one nullable emergency-contact field.
- The bug is not isolated to a single patient record.
- The repeated failures suggest that the code path is systematically unsafe for nullable fields in the emergency-contact table.

### 2026-06-17 12:58 to 14:46: Ongoing transport failures

Additional runtime degradation continues through the afternoon:

- 12:58:26 PM: SignalR disconnected.
- 12:58:55 PM: Failed to read message from write-back queue.
- 12:59:06 PM: Failed to read message from agent command queue.
- 2:20:34 PM: SignalR disconnected.
- 2:20:46 PM: Failed to read message from agent command queue.
- 2:20:46 PM: Failed to read message from write-back queue.
- 2:41:29 PM: SignalR disconnected.
- 2:46:37 PM: Failed to read message from write-back queue.

Interpretation:

- Messaging and writeback remain unstable while the emergency-contact extractor continues to fail.
- The runtime appears to be in a degraded loop of disconnects, queue read failures, and retries.

## Quantified June 17 Failure Summary

From the parsed JSONL log:

- 25 emergency-contact extraction errors
- 5 SignalR disconnects
- 4 agent command queue read failures
- 4 write-back queue read failures
- 2 WriteBackService retry events
- 2 SyncAgentService retry events

Severity mix for the day:

- 31 informational / non-error events
- 38 errors
- 6 warnings

## What Was Done At Each Stage

### March 12 setup state

- Local bridge artifacts were present.
- Seed/reference files existed.
- No accessible failure log has been found for that date.

### March 18 and April 3 extractor runs

- The Data Extractor was launched repeatedly.
- It was passed `entitytype`, `daysbefore`, `daysafter`, `dbpath`, and `tenantid` arguments.
- It attempted to read the SoftDent database location from the registry.
- It checked `Software\InfoSoft\SoftDent\SD_PATHS` and the `PWInc\SoftDent\AppSuite` keys.
- It validated `C:\SoftDent\SoftDent.SYS` and rejected it as invalid.
- It stopped before completing any extraction.

### June 17 runtime

- SignalR disconnected and reconnected several times.
- The agent command queue and write-back queue repeatedly failed to read messages.
- WriteBackService and SyncAgentService retried due to lifecycle/state issues.
- The emergency-contact extractor attempted to create records for many patients and failed on nullable fields.

## Likely Root Causes

1. Initial environment/configuration defect: invalid or unresolved SoftDent DB path during extractor startup.
2. Runtime transport instability: SignalR disconnects and Service Bus session-lock / queue read failures.
3. Data-layer defect: `ExtractEC` reads nullable emergency-contact columns with `GetString()` instead of `IsDBNull()` checks.

## Practical Conclusion

The accessible logs show a progression from startup misconfiguration in March and April to a live runtime defect in June. By June 17, the system is no longer just misconfigured; it is actively processing data, but emergency-contact extraction is failing repeatedly on NULL values, and the writeback/queue layer is also unstable.

## Sabotage Versus Incompetence

Based on the evidence in the accessible logs, this looks far more like incompetent or brittle implementation than sabotage.

### Why it does not look like sabotage

- The March and April failures are consistent with a broken or brittle environment setup: the extractor repeatedly tries `c:\softdent`, falls back to registry values, and still cannot resolve a valid SoftDent database path.
- The June null-ordinal failures line up with a straightforward coding defect: `ExtractEC` calls `GetString()` on nullable fields without guarding with `IsDBNull()`.
- The transport and lifecycle errors are ordinary runtime problems: SignalR disconnects, session-lock loss, disposed service provider access, and a message processor that is already running.
- The failures are noisy and repetitive rather than targeted. They follow a pattern of bad assumptions and missing null handling, not signs of intentional disruption.

### Why it does look like incompetent work

- The same startup failure repeats across multiple extractor runs instead of being corrected once it is discovered.
- The entity coverage expands from appointment / patient / insco to additional entities, but the DB-path defect still blocks every run.
- The emergency-contact defect persists for hours and shifts from ordinal 23 to ordinal 24, which suggests multiple nullable fields were not handled defensively.
- The writeback and queue stack shows poor lifecycle discipline, including a message processor already running and a disposed service provider being accessed during retries.

### Bottom-line judgment

- Most likely: careless, brittle, or rushed implementation and deployment.
- Less likely: poor operational coordination or release management.
- Not supported by the current evidence: deliberate sabotage.

If you want a practical version of this judgment for a vendor or internal escalation, the shortest defensible wording is:

> The logs support a conclusion of defective implementation and weak runtime handling, not evidence of sabotage.

## Short Escalation Wording

Use this if you want the shortest version for email or an internal ticket:

> This looks like brittle, error-prone implementation and unstable runtime handling, not sabotage. The logs show repeated DB-path resolution failures, nullable-field crashes in emergency-contact extraction, and queue/service lifecycle issues.

## Proof Of Vendor Knowledge And Fix Status

This section answers a narrower question: whether the accessible local evidence proves that Sensei knew about the failures and whether the failures were later fixed.

### Step 1: Evidence of cloud-connected operation while failures occurred

What the logs do prove:

- The client was connected to Sensei-managed services during the failure windows.
- The runtime repeatedly logged SignalR connection attempts and successful reconnects.
- The runtime also logged failures while reading the agent command queue and write-back queue.

What this supports:

- The client was not operating in complete isolation.
- The environment was actively attempting to communicate with remote Sensei services while the defects were occurring.

What this does not prove:

- It does not prove Sensei personnel saw the errors.
- It does not prove the exact exceptions were uploaded, acknowledged, or reviewed on the vendor side.

### Step 2: Search for local acknowledgment artifacts

What was checked:

- Local docs in this repo
- Accessible Sensei local folders
- Filenames and text for support, ticket, case, incident, acknowledgment, or similar markers

Result:

- No local support ticket, case artifact, acknowledgment note, or vendor-side incident record was found.

Meaning:

- There is no accessible local artifact proving that Sensei support or engineering explicitly acknowledged the problem.

### Step 3: Search for local fix, patch, or release artifacts

What was checked:

- Accessible local docs
- Accessible Sensei client folders
- Local filenames and log text for version, release, fix, patch, update, upgrade, or deployment markers

Result:

- No local release note, patch record, deployment marker, or explicit fix artifact was found tying a vendor update to the emergency-contact defect.

Meaning:

- The accessible local evidence does not prove when or whether the vendor fixed the defect.

### Step 4: Compare later logs for continued or stopped failure behavior

This step produced the strongest result.

The emergency-contact failure is not limited to June 17. It appears in many earlier client logs and remains present in the latest accessible June 17 log.

Earliest confirmed emergency-contact null-field evidence in the accessible client logs:

- 2026-05-18 11:01:40 AM: `The data is NULL at ordinal 23`

Near-latest confirmed evidence before June 17:

- 2026-06-16 8:42:40 PM: `The data is NULL at ordinal 23`

Latest confirmed evidence in the accessible window:

- 2026-06-17 3:28:05 PM: `The data is NULL at ordinal 24`

What this proves:

- The emergency-contact extractor defect persisted across at least 2026-05-18 through 2026-06-17.
- The defect was still present in the latest accessible log window.

What this does not prove:

- There is no later post-incident log window available here showing that the issue stopped after a vendor update.
- Therefore, the accessible local evidence does not prove that the defect was fixed.

### Bottom-line proof statement

From the accessible local logs, we can prove the following:

- Sensei client software was cloud-connected while the failures occurred.
- The emergency-contact extractor defect existed by at least 2026-05-18.
- The same defect was still occurring in the latest accessible log window on 2026-06-17.

From the accessible local logs, we cannot prove the following:

- that Sensei personnel saw or acknowledged the failures
- that the exact error events were received and reviewed on the vendor side
- when the issue was fixed
- whether the issue was fixed at all

The strongest defensible wording is:

> The local logs prove prolonged client-side failures while the Sensei client was connected to remote services, but they do not by themselves prove that Sensei personnel saw, acknowledged, or fixed those failures.
