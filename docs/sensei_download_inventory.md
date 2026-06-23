# Sensei Download And Import Inventory

This document separates what was proven from local machine evidence from what only appears to be supported by configuration.

## Bottom Line

The installed Sensei Gateway pathway appears able to both send and receive practice data.

What is strongest from the evidence is not a full list of every field transferred, but a clear split between:

- entities that were directly evidenced as imported or written back
- entities that were configured or staged but not proven imported in this session
- entities that appear expected but were specifically missing during inspection

## Bucket 1: Proven Imported Or Written Back

These categories had direct local evidence of inbound import files, writeback templates, or log-confirmed activity.

### Patient

Evidence:

- imported patient JSON files were observed under `C:\SoftDent\DataSync\SDInjector_JSON\ImportedFiles\0000950863`
- injector logs recorded successful patient-related writeback or import activity
- risk summary and vendor packet both document patient import evidence
- sampled imported patient JSON field names included contact, demographic, responsible-party, emergency-contact, and medical-history fields

Confidence: high

### Appointment

Evidence:

- imported appointment JSON files were observed under `C:\SoftDent\DataSync\SDInjector_JSON\ImportedFiles\0000950863`
- local docs record appointment import evidence
- sampled imported appointment JSON field names included confirmation status and confirmation note fields

Confidence: high

### Emergency contact related data

Evidence:

- local writeback template targets the `PatientEmergencyContact` table
- extractor failure was tied to `PatientEmergencyContact.SoftDentEmergencyContactTextBoxValue`
- this proves the emergency-contact pathway is active in the installed product surface

Confidence: high for pathway presence, medium for confirmed successful inbound writeback

## Bucket 2: Configured Or Staged, But Not Proven Imported In This Session

These categories were present in config files, staged folders, or local product structure, but I did not prove an actual inbound download or writeback event for each one.

### Insurance or responsible party related data

Evidence:

- staged entity folders included `insco`
- injector log references involved insurance policies and responsible-party related updates

Confidence: medium

### Dentist or provider data

Evidence:

- staged folders included `dentist`
- injector config included `Dentist` and `Provider`

Confidence: medium

### Location data

Evidence:

- staged folders included `location`
- injector config included `Location`

Confidence: medium

### ADA or reference data

Evidence:

- staged folders included `ada` and `Reference`
- injector config included `Ada`

Confidence: medium

### Notes or `Pnotes`

Evidence:

- injector config included `Pnotes`
- extractor config included `Pnotes`
- no note-related files or folders were found in the inspected DataSync, injector import, adapter, or log paths
- no direct imported notes payload was proven during inspection

Confidence: high that notes capability is configured, low that notes were actually downloaded or imported in the inspected paths

### User or pharmacy related data

Evidence:

- injector config included `User` and `Pharmacy`
- no direct imported payload was proven during inspection

Confidence: low

## Bucket 3: Expected Or Enabled, But Missing During Inspection

These categories appear supported by the installed config, but the live evidence checked during this session did not show them moving through the inspected local path.

### Transaction

Evidence:

- injector config included `Transaction`
- vendor packet and risk summary both note that `Transaction` is enabled in config
- the outbound DataSync path did not show live `transaction` entity emission during inspection
- the local import report showed zero transaction files, zero rows seen, and zero rows mappable

Confidence: high that transaction capability exists in config, high that live transaction transfer was not observed in the inspected path

## Best Current Answer To “What Are They Downloading?”

The most defensible answer from the machine evidence is:

- proven imported or written back: patient, appointment, and emergency-contact-related pathways
- likely supported and possibly exchanged depending on workflow: insurance, responsible party, dentist or provider, location, ADA or reference data, and possibly notes
- configured but specifically not proven active in the inspected live path: transaction

## Important Limitations

- this evidence does not prove every configured entity was actively downloaded
- this evidence does not prove every inbound file came from a vendor cloud command rather than a local integration workflow
- this evidence does not prove which exact fields inside each entity were transferred without deeper payload inspection
- this evidence does not by itself determine legality or contractual authorization

## Latest Notes Check

Latest local check result: `Pnotes` appears in both the Sensei extractor and injector config files, but no actual patient-note download/import artifact was found in the inspected local paths.

Checked paths:

- `C:\ProgramData\Sensei Gateway Client\DataSync\0000950863`
- `C:\SoftDent\DataSync\SDInjector_JSON\ImportedFiles\0000950863`
- `C:\ProgramData\Sensei Gateway Client\DataAdapters\SoftDent`
- `C:\ProgramData\Sensei Gateway Client\Logs`

Current conclusion: patient notes are configured as a supported pathway, but active note download/import was not proven.

## Latest Imported Field Check

Latest sampled imported JSON field names showed these higher-sensitivity fields:

- `PatientInfo.MedicalHistory`
- `PatientInfo.EthnicityType`
- `PatientInfo.BirthDate`
- `PatientInfo.ResponsibleParties`
- `PatientInfo.SoftDentEmergencyContactPhoneValue`
- `PatientInfo.SoftDentEmergencyContactTextBoxValue`
- `AppointmentInfo.ConfirmationNote`

Current conclusion: no single field is automatically illegal to transfer if it is authorized, covered by the BAA, and needed for the enabled workflow. However, `MedicalHistory`, ethnicity, emergency-contact fields, responsible-party data, and appointment confirmation notes are harder to justify as strictly necessary for basic reminders or ordinary Patient Manager unless the vendor can identify the exact Patient Manager feature that requires them.

## Practical Use

Use this inventory when asking the vendor, counsel, or compliance staff:

1. which of these categories are actually transferred in this deployment
2. which are read-only versus writable
3. which are covered by the signed agreement and BAA
4. which can be disabled without breaking required reporting
