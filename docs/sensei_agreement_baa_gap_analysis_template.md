# Sensei Agreement And BAA Gap Analysis Template

Use this worksheet to compare your signed Sensei or Carestream agreement and any BAA against the local machine evidence already documented in this repo.

Related evidence documents:

- [docs/sensei_gateway_risk_summary.md](c:/NewRidgeFamilyFinancial/docs/sensei_gateway_risk_summary.md)
- [docs/sensei_gateway_compliance_checklist.md](c:/NewRidgeFamilyFinancial/docs/sensei_gateway_compliance_checklist.md)
- [docs/sensei_vendor_request_packet.md](c:/NewRidgeFamilyFinancial/docs/sensei_vendor_request_packet.md)
- [docs/softdent_emergency_contact_extractor_bug.md](c:/NewRidgeFamilyFinancial/docs/softdent_emergency_contact_extractor_bug.md)

## Status Scale

- `match`: the signed document clearly covers the observed behavior
- `partial`: the document touches the area but does not clearly cover the observed behavior
- `gap`: the document does not appear to cover the observed behavior
- `unknown`: the needed language was not found yet

## Local Evidence Baseline

Observed on the machine:

- Sensei is cloud-connected through remote Azure-hosted endpoints.
- Sensei stages outbound data under `C:\ProgramData\Sensei Gateway Client\DataSync\0000950863`.
- Observed staged data categories include patient, appointment, insurance, provider or dentist, ADA or reference, and location-related data.
- Injector config includes `Patient`, `Appointment`, `Transaction`, and `Pnotes` among other entities.
- Local inbound JSON import folders exist under `C:\SoftDent\DataSync\SDInjector_JSON\ImportedFiles\0000950863`.
- Imported patient and appointment JSONs were observed locally.
- Emergency-contact writeback templates exist.
- Injector logs showed patient-related writeback or import success and duplicate-key errors.
- Live transaction emission was not observed in the outbound DataSync tree despite `Transaction` being enabled in config.

## Gap Analysis Entries

Copy and complete one block for each topic.

### Cloud connectivity

- Observed local behavior: Sensei connects to remote vendor Azure endpoints.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Bidirectional scope

- Observed local behavior: Product appears to support both outbound sync and inbound writeback.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Read-only vs writeback

- Observed local behavior: Local install is not limited to passive export behavior.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Patient data

- Observed local behavior: Patient staging and patient import files observed.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Appointment data

- Observed local behavior: Appointment staging and appointment import files observed.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Insurance or responsible party data

- Observed local behavior: Insurance-related staging and injector log references observed.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Provider or dentist data

- Observed local behavior: Provider or dentist-related config and staged folders observed.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Notes or `Pnotes` capability

- Observed local behavior: `Pnotes` appears in injector config.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Transaction capability

- Observed local behavior: `Transaction` appears in config even though live emission was not observed.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Writeback authorization

- Observed local behavior: Emergency-contact writeback template and patient import success observed.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Hosting or subprocessors

- Observed local behavior: Vendor services appear Azure-hosted.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Geographic storage or transfer

- Observed local behavior: Cloud hosting implied, storage location not locally documented.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Retention policy

- Observed local behavior: Not locally documented.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Breach notification obligations

- Observed local behavior: Not locally documented.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Auditability

- Observed local behavior: Some logs exist locally, but contract scope unknown.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

### Disable writeback option

- Observed local behavior: No local contract language available yet.
- Agreement language found:
- BAA language found:
- Status: `match | partial | gap | unknown`
- Notes:

## Specific Clauses To Look For In The Signed Agreement

- wording that the product is cloud-connected or vendor-hosted
- wording that the product can transmit data off the local machine
- wording that the product can receive instructions, jobs, updates, or writeback payloads
- wording that the product is bidirectional or supports import, sync-back, or update workflows
- wording that names the actual data categories handled
- wording that names any subprocessors or hosting providers
- wording that explains how writeback can be disabled or constrained

## Specific Clauses To Look For In The BAA

- definitions of PHI categories covered by the service
- permitted uses and disclosures matching the observed data flow
- subcontractor or downstream processor coverage
- storage, transport, and security controls for cloud-connected workflows
- breach notice and incident handling language
- restrictions or conditions on inbound modifications or writeback workflows

## Red Flags

Treat any of the following as a likely contract or BAA gap:

- the signed paperwork describes the product as read-only, but local evidence shows writeback capability
- the paperwork describes the product as local-only, but local evidence shows cloud connectivity
- the paperwork omits patient or appointment data categories that are clearly staged locally
- the BAA does not appear to cover bidirectional import or writeback behavior
- the paperwork does not explain hosting, subprocessors, or data flow destinations

## Decision Summary

After reviewing the actual agreement and BAA, fill this in:

- Agreement status: `match | partial | gap | unknown`
- BAA status: `match | partial | gap | unknown`
- Highest-risk mismatch found:
- Immediate action required:
- Vendor clarification still needed:

## Next Step Once Documents Are Available

Paste or place the signed agreement and BAA text into the workspace, then compare each clause against this worksheet and the evidence documents listed above.
