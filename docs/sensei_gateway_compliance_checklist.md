# Sensei Gateway Compliance Checklist

Use this checklist to decide whether the current Sensei Gateway setup is documented, authorized, and compliant with your practice requirements.

## Vendor Agreement

- Confirm there is a signed agreement with the Sensei or Carestream vendor covering this integration.
- Confirm the agreement describes the product as cloud-connected if that is how it operates.
- Confirm the agreement covers bidirectional sync or writeback behavior, not only read-only export.
- Confirm the agreement identifies the services or sub-processors involved in hosting or transport.

## HIPAA / Privacy Paperwork

- Confirm there is a current Business Associate Agreement if PHI is involved.
- Confirm the BAA covers both outbound sync and inbound writeback functions.
- Confirm the BAA covers the actual categories of data observed locally: patient, appointment, insurance, provider, notes, and related reference data.
- Confirm retention, breach notification, and subcontractor obligations are defined.

## Data Flow Documentation

- Document the local service name and executable path.
- Document the local tenant staging path under `C:\ProgramData\Sensei Gateway Client\DataSync\0000950863`.
- Document the injector import path under `C:\SoftDent\DataSync\SDInjector_JSON\ImportedFiles\0000950863`.
- Document the writeback gateway database path under `C:\SoftDent\writeback_gateway\softdent_writeback_gateway.db`.
- Document the configured cloud endpoints from the local appsettings file.
- Document which entities are enabled in extractor and injector config.

## Minimum Necessary Review

- Verify the practice intended to expose patient data.
- Verify the practice intended to expose appointment data.
- Verify the practice intended to expose insurance and responsible-party data.
- Verify the practice intended to expose notes if `Pnotes` is enabled.
- Verify the practice intended to enable writeback for patient or emergency-contact related records.
- Verify `Transaction` capability is expected, even if live transaction emission is not currently present.

## Writeback Governance

- Confirm who approved inbound writeback behavior.
- Confirm which entities are allowed to be written back into SoftDent.
- Confirm there is a rollback or recovery plan for bad imports.
- Confirm duplicate-key or mapping failures are monitored.
- Confirm writeback actions are audited and attributable.

## Security Controls

- Confirm only authorized vendor or integration services can submit inbound payloads.
- Confirm access to the local Sensei and SoftDent staging folders is restricted.
- Confirm service accounts and Windows permissions are documented.
- Confirm TLS endpoint ownership and certificate chain are acceptable to the practice.
- Confirm antivirus, EDR, and backup policies include these staging and log paths.

## Operational Monitoring

- Review Sensei service logs regularly for queue, extractor, and writeback failures.
- Review injector logs for duplicate-key and import errors.
- Review quarantine folders for rejected inbound payloads.
- Review whether staged patient and appointment imports are expected business behavior.
- Review whether any transaction or notes imports are appearing unexpectedly.

## Policy Alignment

- Confirm the privacy notice given to patients matches the real vendor data flow.
- Confirm internal staff understand this is not only a passive export process.
- Confirm leadership understands the system is cloud-connected and bidirectional.
- Confirm incident response procedures cover vendor sync failures or erroneous writebacks.

## Questions To Send The Vendor

- What exact data elements are collected from SoftDent?
- Which data elements are written back into SoftDent?
- Which entities are enabled by default versus optional?
- What cloud services receive this data?
- Where is the data stored, and for how long?
- What triggers outbound sync?
- What triggers inbound writeback?
- How are failed or duplicate writes handled?
- How can the practice disable writeback while keeping read-only sync?
- Is `Transaction` expected to emit live in this deployment, and if not, why is it configured?

## Local Evidence Already Observed

- Multiple staged entity folders exist under the Sensei DataSync tenant path.
- The injector config includes `Patient`, `Appointment`, `Transaction`, and `Pnotes`.
- Imported patient and appointment JSON files exist under the injector import path.
- The emergency-contact writeback template targets the SoftDent `PatientEmergencyContact` table.
- Injector logs showed patient-related writeback/import activity and duplicate-key errors.

## Decision Threshold

If any of these are missing, the practice should treat the current setup as under-documented and potentially non-compliant until resolved:

- signed vendor agreement
- BAA or equivalent required privacy agreement
- written approval for bidirectional writeback
- documented data-flow inventory
- clear monitoring and rollback process