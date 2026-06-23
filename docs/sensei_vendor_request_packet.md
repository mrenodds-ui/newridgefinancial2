# Sensei Vendor Request Packet

Use this packet when sending a formal request to the Sensei or Carestream vendor about the current gateway installation.

## Purpose

This request asks the vendor to explain and document the actual behavior of the installed Sensei Gateway product on the local machine, including:

- outbound data collection
- inbound import or writeback behavior
- cloud connectivity
- enabled entities
- transaction feed expectations
- error handling
- compliance documentation

## Local Evidence Summary

The following was observed locally on the machine running Sensei Gateway:

- The Sensei client is cloud-connected and configured with remote Azure endpoints for `SyncAgentApi` and `IngressApi`.
- The local service stages data under `C:\ProgramData\Sensei Gateway Client\DataSync\0000950863`.
- Observed staged entity folders include `patient`, `appointment`, `insco`, `dentist`, `location`, `ada`, and `Reference`.
- The injector config includes these entities: `Patient`, `Location`, `Appointment`, `Dentist`, `Provider`, `Pharmacy`, `User`, `Ada`, `Transaction`, and `Pnotes`.
- Local inbound import folders exist under `C:\SoftDent\DataSync\SDInjector_JSON\ImportedFiles\0000950863`.
- Imported JSON files were observed for at least `patient` and `appointment` entities.
- A writeback template exists for `PatientEmergencyContact` updates.
- Injector logs recorded successful patient-related writeback or import activity.
- The outbound DataSync path did not show live `transaction` entity emission during inspection, even though `Transaction` is enabled in config.
- Current extractor logs also show emergency-contact extraction failures involving a nullable field in `PatientEmergencyContact`.

## Formal Questions For The Vendor

### Product Scope

1. Is the currently installed Sensei Gateway product intended to operate as a bidirectional integration, not only a read-only export utility?
2. Which installed features are read-only, and which features can write data back into SoftDent?
3. Which entities are enabled by default in this deployment, and which are optional?

### Data Collection

1. What exact data elements are collected from SoftDent for these entities:
   - patient
   - appointment
   - insurance or responsible party
   - dentist or provider
   - notes or `Pnotes`
   - transaction
2. Does the product collect only changed records, or can it collect full reference or historical data sets?
3. What determines when outbound sync occurs?

### Writeback / Import

1. What exact entities can be written back into SoftDent in this deployment?
2. What business workflows trigger inbound writeback or injector imports?
3. Is patient-related writeback expected in the current deployment?
4. Is appointment-related writeback expected in the current deployment?
5. Is emergency-contact writeback expected in the current deployment?
6. Is transaction writeback supported, enabled, or expected in the current deployment?

### Cloud and Hosting

1. What cloud services receive outbound data from this installation?
2. What cloud services can send work or writeback instructions to this installation?
3. What sub-processors or hosting providers are involved?
4. Where is the data stored geographically, and for how long?

### Logging and Error Handling

1. Please explain the purpose of the local injector import path under `C:\SoftDent\DataSync\SDInjector_JSON\ImportedFiles\0000950863`.
2. Please explain the purpose of the writeback gateway database under `C:\SoftDent\writeback_gateway\softdent_writeback_gateway.db`.
3. Please explain the duplicate-key errors observed in the injector log and whether they indicate failed writes, retries, or duplicate inbound payloads.
4. Please explain whether the emergency-contact extractor failure can interfere with broader entity extraction or transaction feed emission.
5. Please confirm whether Sensei, Kodak, or Carestream received telemetry, alerts, exception reports, support logs, cloud-ingress records, or other server-side records showing the emergency-contact extractor failures beginning at least 2026-05-18 and continuing through 2026-06-17.
6. Please confirm whether the successful SignalR connections and Azure Service Bus session activity shown in the local logs included transmission of client-side exception telemetry for the emergency-contact extractor failures involving `System.InvalidOperationException: The data is NULL at ordinal 23` and later ordinal 24.
7. Please confirm whether your backend systems generated any acknowledgment, alert, telemetry record, support ticket, engineering ticket, incident record, retry record, or error-ingestion record for those extractor failures.
8. If so, when was the issue first visible on the vendor side?
9. Was a support ticket, engineering ticket, incident, or defect record created for this failure pattern?
10. Was any patch, configuration change, update, or deployment made to address it?
11. Has the emergency-contact extractor defect been fully resolved?
12. During the failure period, was any patient, appointment, emergency contact, transaction, billing, or other PHI partially staged, transmitted, retried, rejected, or written back?
13. Does the practice need to take any corrective or validation steps to confirm data integrity after the failure period?

### Transaction Feed

1. `Transaction` is enabled in config, but no live transaction entity emission was observed in the local DataSync path. Is that expected?
2. If not expected, what condition prevents live transaction emission for this tenant?
3. Does transaction data travel by a different channel than the entity folders inspected locally?

### Compliance and Authorization

1. Please provide the current data-flow description for this product.
2. Please confirm whether the product requires a BAA or equivalent privacy agreement for this deployment.
3. Please confirm whether the current deployment should be documented as cloud-connected and bidirectional.
4. Please provide documentation describing how the practice can disable writeback while preserving read-only export or sync behavior.

## Specific Defect To Escalate

The current extractor error appears to be:

```text
System.InvalidOperationException: The data is NULL at ordinal 23.
```

Local schema review indicates ordinal `23` maps to:

```text
PatientEmergencyContact.SoftDentEmergencyContactTextBoxValue
```

The vendor should confirm whether `ExtractEC` needs a null-safe fix such as `IsDBNull` handling or SQL-side `COALESCE`.

## Requested Vendor Deliverables

Ask the vendor to provide all of the following in writing:

- a statement of whether this deployment is bidirectional
- a list of all collected data categories
- a list of all writable entities
- a data-flow diagram or narrative
- hosting and sub-processor details
- expected transaction-feed behavior
- explanation of the duplicate-key injector errors
- explanation of the emergency-contact extractor failure
- confirmation of whether successful SignalR and Azure Service Bus activity included transmission of exception telemetry for the emergency-contact failures
- confirmation of whether server-side telemetry or support records captured the emergency-contact failures from at least 2026-05-18 through 2026-06-17
- confirmation of when the defect was first known internally, whether an incident or defect record was created, and what fix or mitigation was deployed
- confirmation of whether the defect is fully resolved and whether post-incident data validation is required
- steps to disable writeback if desired
- any required compliance or privacy documents tied to this deployment

## Internal Use Note

This packet is based on direct local inspection of config files, staging paths, logs, and injector artifacts present on the machine. It does not rely only on vendor marketing or assumptions.
