# Sensei Patient Manager Legal Findings

## Purpose

This memo answers the practical question: did the observed Sensei or Patient Manager pathway break laws?

This is an evidence-based compliance finding, not a legal opinion from counsel.

## Current Finding

The current evidence does not prove that Sensei or Patient Manager broke the law.

The current evidence does prove enough risk to treat the deployment as under-documented and potentially non-compliant until the vendor provides the signed agreement, BAA, data-flow description, enabled-module list, and writeback authorization.

## Why It Is Not Proven Illegal Yet

The missing piece is authorization.

The workspace search found no signed Sensei or Carestream agreement and no signed BAA. Without those documents, there is no way to compare the observed machine behavior against the actual permissions, safeguards, and scope the practice agreed to.

## Why It Is Still A Serious Compliance Concern

The local machine evidence shows behavior broader than an ordinary Patient Manager-only expectation:

- cloud-connected SyncAgent and Ingress endpoints
- patient and appointment import evidence
- emergency-contact writeback surface
- staged or configured insurance, provider, location, ADA, and reference entities
- `Pnotes` capability in config
- `Transaction` capability in config
- inbound import and writeback surfaces

Public Sensei materials describe Patient Manager mostly as patient engagement: scheduling, reminders, recalls, online booking, patient communication, forms, check-in, reviews, follow-ups, and treatment-plan outreach.

Public Sensei materials also describe broader modules outside Patient Manager, including Business Health, Payment Manager, Insights Manager, eClaims, eVerifications, Patient Care, Rx Manager, Imaging, Cloud Apps, and enterprise workflows.

That means the machine behavior may fit the broader Sensei Cloud platform, but it is not fully explained by Patient Manager alone.

## HIPAA Analysis

HHS business-associate guidance says a covered entity may disclose PHI to a business associate only when the business associate uses the information for the purposes for which it was engaged, safeguards it from misuse, and gives satisfactory written assurances through a contract or other written agreement.

HHS also states that a business associate contract must describe permitted and required PHI uses, prohibit other uses or disclosures except as permitted by the contract or law, and require safeguards.

HHS minimum-necessary guidance says PHI should not be used or disclosed when it is not necessary to satisfy a particular purpose or carry out a function. It also says covered entities generally must take reasonable steps to limit PHI use, disclosure, and requests to the minimum necessary to accomplish the intended purpose.

Applied here:

- Patient Manager can likely justify patient and appointment data if it is properly contracted and limited.
- Broader handling of insurance, responsible-party, notes, transaction, provider, location, medical history, ethnicity, emergency-contact data, appointment confirmation notes, and writeback behavior needs explicit coverage and minimum-necessary justification.
- If there is no BAA, or if the BAA does not cover the actual data categories and bidirectional/writeback behavior, the deployment may be a HIPAA compliance problem.
- If the vendor used PHI for its own independent purpose outside the practice's authorized healthcare operations, that would be a major HIPAA red flag.

## Field-Level Minimum-Necessary Finding

The sampled imported JSON field names that are hardest to justify for basic Patient Manager are:

- `PatientInfo.MedicalHistory`
- `PatientInfo.EthnicityType`
- `PatientInfo.ResponsibleParties`
- `PatientInfo.SoftDentEmergencyContactPhoneValue`
- `PatientInfo.SoftDentEmergencyContactTextBoxValue`
- `AppointmentInfo.ConfirmationNote`

These fields are not automatically illegal. They become legally problematic if the vendor cannot show that each field was necessary for an enabled, authorized workflow and covered by the agreement and BAA.

## Kansas Analysis

Kansas law at K.S.A. 50-6,139b requires holders of personal information to use reasonable procedures and practices appropriate to the nature of the information and to exercise reasonable care to protect it from unauthorized access, use, modification, or disclosure.

Applied here:

- If the Sensei pathway is authorized, documented, safeguarded, and limited to agreed practice operations, Kansas law does not automatically prohibit it.
- If the pathway allows unauthorized use, modification, disclosure, or poorly controlled writeback, the Kansas risk increases.
- If HIPAA or another federal/state security obligation applies and is violated, Kansas law treats that failure as important evidence under its own personal-information protection framework.

## Georgia Analysis

Georgia-specific public pages were not retrievable through the available web-fetch tool during this review, so this memo does not make a Georgia-specific statutory conclusion.

The practical Georgia risk still follows the same core pattern: unauthorized access, use, disclosure, weak safeguards, or breach-notice failures would be the likely legal problem, not the mere existence of Patient Manager.

Georgia review should be completed by counsel using the signed agreement, BAA, and Georgia breach/privacy statutes.

## Decision Matrix

### Likely compliant if all are true

- Patient Manager or broader Sensei modules were actually licensed and enabled knowingly.
- A signed agreement covers cloud-connected operation.
- A BAA covers the actual PHI categories involved.
- The agreement and BAA cover bidirectional import and writeback if enabled.
- The practice approved writeback behavior.
- The vendor can document minimum-necessary data handling.
- Safeguards, auditability, and rollback are documented.

### Potentially non-compliant if any are true

- No signed BAA exists for PHI handled through this pathway.
- The BAA only covers narrow Patient Manager behavior but the machine shows broader Sensei Cloud behavior.
- The vendor cannot explain why `Transaction`, `Pnotes`, insurance, provider, location, ADA, or reference entities are present.
- The vendor cannot identify which modules are enabled.
- Writeback was enabled without written practice approval.
- The vendor cannot provide data-flow, retention, hosting, and sub-processor documentation.
- PHI was used for vendor purposes outside the practice's authorized healthcare operations.

## Best Current Answer

Did they break laws with Patient Manager?

Not proven.

Could they have broken HIPAA, Kansas, contract, or related privacy obligations if the broader behavior was not authorized and covered by a BAA?

Yes.

Is the current evidence strong enough to require vendor escalation and document review?

Yes.

## Required Next Evidence

To move from risk finding to legal conclusion, collect:

1. the signed Sensei or Carestream agreement
2. the signed BAA
3. the enabled module list for this tenant
4. the data-flow diagram or narrative
5. the list of writable entities
6. the writeback approval record
7. the vendor's explanation for `Transaction` and `Pnotes` in config
