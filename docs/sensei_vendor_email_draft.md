# Draft Email To Sensei Vendor

Subject: Request for Written Clarification on Sensei Gateway Data Flow, Writeback Scope, and Current Errors

Hello,

We reviewed the currently installed Sensei Gateway client on our local machine and need written clarification about its real data flow, writeback scope, and current runtime behavior.

Our local inspection shows that the installed client appears to be more than a read-only export bridge. We observed:

- cloud-connected SyncAgent and Ingress endpoints
- local outbound staging of multiple SoftDent-related entities
- local inbound injector import folders for at least patient and appointment entities
- writeback templates for emergency-contact related records
- injector log evidence of at least some patient-related writeback or import activity
- current extractor and injector errors that need explanation

We need written answers to the questions in [docs/sensei_vendor_request_packet.md](c:/NewRidgeFamilyFinancial/docs/sensei_vendor_request_packet.md), especially the following:

1. Is this deployment bidirectional?
2. What exact data elements are collected?
3. What exact entities can be written back into SoftDent?
4. Why is `Transaction` enabled in config while no live transaction entity emission is appearing in the local DataSync tree?
5. What is the purpose of the local injector import path and writeback gateway path?
6. Can the emergency-contact extractor failure degrade broader extraction behavior?
7. How can writeback be disabled while preserving read-only export or sync behavior?

We also need a response to the current extractor defect:

```text
System.InvalidOperationException: The data is NULL at ordinal 23.
```

Local schema review indicates ordinal `23` maps to:

```text
PatientEmergencyContact.SoftDentEmergencyContactTextBoxValue
```

Please confirm whether the extractor should be handling this field as nullable and whether a product fix is required.

We also need written clarification about vendor-side awareness and handling of these failures. Our local logs indicate that the Sensei Gateway client was cloud-connected while these failures were occurring, and that the same emergency-contact NULL-field defect persisted across multiple daily log windows from at least 2026-05-18 through 2026-06-17.

The logs show confirmed two-way transport with vendor-hosted services, including successful SignalR connections and live Azure Service Bus session behavior. However, they do not show explicit application-level acknowledgment that the emergency-contact extractor exceptions themselves were received, ingested, reviewed, or acted on by the vendor.

Please confirm whether Sensei, Kodak, or Carestream received telemetry, alerts, exception reports, support logs, cloud-ingress records, or other server-side records showing these emergency-contact extractor failures during that period.

Please specifically confirm whether the successful SignalR connections and Azure Service Bus session activity shown in the local logs included transmission of client-side exception telemetry, including the emergency-contact extractor failures involving `System.InvalidOperationException: The data is NULL at ordinal 23` and later ordinal 24.

Please also confirm whether your backend systems generated any acknowledgment, alert, telemetry record, support ticket, engineering ticket, incident record, retry record, or error-ingestion record for those extractor failures.

Please also confirm:

1. whether Sensei received telemetry or server-side notice of these failures
2. when Sensei first became aware of the emergency-contact extractor defect
3. whether a support ticket, engineering ticket, incident, or defect record was created
4. whether any patch, configuration change, update, or deployment was made to address it
5. whether the defect has been fully resolved
6. whether any patient, appointment, emergency contact, transaction, billing, or other PHI was partially staged, transmitted, retried, rejected, or written back during the failure period
7. whether the practice needs to take any corrective or validation steps to confirm data integrity

Please respond with:

- written confirmation of whether this deployment is read-only or bidirectional
- a clear list of collected and writable data categories
- hosting and sub-processor details
- expected transaction-feed behavior for this deployment
- explanation of the observed extractor and injector errors
- confirmation of whether successful SignalR and Azure Service Bus activity included transmission of exception telemetry for the emergency-contact failures
- confirmation of whether server-side telemetry or support records captured these failures
- confirmation of when the defect was first known internally and what corrective action was taken
- confirmation of whether the defect is resolved and whether local data validation is required
- documentation for disabling writeback if desired
- any relevant BAA, compliance, or data-flow documentation for this integration

Thank you.
