# Sensei Patient Manager Scope Challenge Email

Subject: Written Clarification Requested: Is This Deployment Limited to Patient Manager?

Hello,

We are requesting written clarification about the currently installed Sensei Gateway and whether this deployment is limited to Patient Manager or is operating as part of the broader Sensei Cloud platform.

Public Sensei materials describe Patient Manager primarily as a patient engagement tool focused on scheduling, reminders, recalls, online booking, patient communication, check-in, reviews, follow-ups, and treatment-plan outreach.

Public Sensei materials also describe broader Sensei Cloud modules outside Patient Manager, including Business Health, Payment Manager, Insights Manager, eClaims, eVerifications, Patient Care, Rx Manager, Imaging, Sensei Cloud Apps, and enterprise workflows.

Our local inspection shows behavior that appears broader than a narrow Patient Manager-only workflow, including:

- cloud-connected SyncAgent and Ingress endpoints
- staged entities including patient, appointment, insurance, dentist, location, ADA, and reference data
- injector configuration including `Patient`, `Location`, `Appointment`, `Dentist`, `Provider`, `Pharmacy`, `User`, `Ada`, `Transaction`, and `Pnotes`
- local inbound import folders for at least patient and appointment entities
- writeback templates involving `PatientEmergencyContact`
- log evidence of patient-related writeback or import activity
- `Transaction` present in config, even though live transaction entity movement was not observed in the inspected local DataSync path

Please answer the following in writing:

1. Is this exact deployment limited to Patient Manager?
2. If yes, why are `Transaction`, `Pnotes`, insurance, provider, location, ADA, and reference-related entities present in the local integration surface?
3. If no, which broader Sensei modules are active or partially active in this deployment?
4. Is Business Health, Payment Manager, Insights Manager, eClaims, eVerifications, Cloud Apps, or any other non-Patient Manager service enabled for this practice?
5. Which observed entities are required specifically for Patient Manager?
6. Which observed entities belong to broader Sensei Cloud functionality outside Patient Manager?
7. Which entities are read-only and which can be written back into SoftDent?
8. What exact workflows trigger inbound import or writeback into SoftDent?
9. Why is `Transaction` enabled in config if live transaction emission is not visible in the inspected local DataSync path?
10. Does `Pnotes` transfer occur in this deployment, and if so, what exact fields are transferred?
11. Can writeback be disabled while preserving any Patient Manager functionality the practice actually uses?
12. Please provide the agreement, BAA, data-flow documentation, and module list that authorize the exact enabled scope.

We are not asking for a marketing summary. We need a deployment-specific written answer matching the installed configuration, local staging paths, injector behavior, cloud endpoints, and logs on this machine.

Related internal evidence summaries are available in:

- `docs/sensei_public_web_scope_research.md`
- `docs/sensei_exceeds_patient_manager_expectation_memo.md`
- `docs/sensei_download_inventory.md`
- `docs/sensei_vendor_request_packet.md`

Thank you.
