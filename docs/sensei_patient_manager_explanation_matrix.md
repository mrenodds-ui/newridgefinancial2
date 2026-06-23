# Sensei Patient Manager Explanation Matrix

This document maps the observed Sensei Gateway behavior against a simple question:

Would this make technical sense if the practice had a broader Patient Manager style workflow enabled?

The goal is not to prove that Patient Manager is definitely the cause. The goal is to separate:

- behavior that Patient Manager could plausibly explain
- behavior that still needs explicit vendor confirmation
- behavior that remains a red flag even if Patient Manager exists

## Bottom Line

Patient Manager could plausibly explain why the installed Sensei pathway is broader than a read-only reporting tool.

In particular, it could explain:

- patient imports
- appointment imports
- cloud-connected sync coordination
- some writeback behavior tied to patient workflow

It does not automatically explain or excuse everything. Contract scope, BAA scope, minimum necessary use, and writeback governance would still need to match the actual behavior.

## Matrix

### Patient import activity

- Observed behavior: imported patient JSON files were present and patient-related writeback or import success was logged.
- Likely explained by Patient Manager: yes.
- Why: a patient-management workflow often needs patient record synchronization, patient status updates, or cloud-coordinated record refresh.
- Still needs vendor proof: yes.
- Remaining concern: whether the exact patient fields transferred were disclosed and authorized.

### Appointment import activity

- Observed behavior: imported appointment JSON files were present.
- Likely explained by Patient Manager: yes.
- Why: appointment management, reminders, scheduling workflows, and status synchronization commonly require appointment data exchange.
- Still needs vendor proof: yes.
- Remaining concern: whether appointment writeback is enabled by design in this deployment and who approved it.

### Emergency-contact pathway and writeback surface

- Observed behavior: writeback template targeted `PatientEmergencyContact`, and extractor activity touched that table.
- Likely explained by Patient Manager: possibly.
- Why: some patient-management workflows may maintain contact and responsible-party information as part of communication or demographic upkeep.
- Still needs vendor proof: yes.
- Remaining concern: this is more sensitive because it reflects a direct writeback-capable path into SoftDent tables.

### Cloud connectivity to vendor Azure endpoints

- Observed behavior: live outbound HTTPS sessions and Azure-hosted `SyncAgentApi` and `IngressApi` endpoints were configured.
- Likely explained by Patient Manager: yes.
- Why: cloud-managed patient communication and workflow products often coordinate sync jobs, commands, and status through vendor services.
- Still needs vendor proof: yes.
- Remaining concern: cloud connectivity must be disclosed in the agreement, BAA, and patient-facing privacy posture.

### Insurance or responsible-party related activity

- Observed behavior: staged `insco` data and injector log references involving insurance policies and responsible parties.
- Likely explained by Patient Manager: maybe.
- Why: some patient-management and collections workflows use insurance or responsible-party context.
- Still needs vendor proof: yes.
- Remaining concern: this is broader than a narrow scheduling-only explanation and may exceed what staff assumed was being synced.

### Dentist, provider, location, ADA, and reference data

- Observed behavior: staged folders and config showed these entities.
- Likely explained by Patient Manager: maybe.
- Why: some workflow products need provider, office, code, or reference context to render schedules and patient interactions correctly.
- Still needs vendor proof: yes.
- Remaining concern: these categories suggest a broad integration surface, not a narrow patient-messaging feature alone.

### Notes or `Pnotes`

- Observed behavior: `Pnotes` was enabled in config.
- Likely explained by Patient Manager: maybe, but weakly.
- Why: notes could support patient communication history or workflow context, but that is more invasive than basic scheduling sync.
- Still needs vendor proof: yes.
- Remaining concern: notes can contain highly sensitive content, so this requires especially clear contractual and privacy coverage.

### Transaction capability

- Observed behavior: `Transaction` was enabled in config, but live transaction movement was not observed in the inspected path.
- Likely explained by Patient Manager: maybe, but not by a narrow patient-engagement story alone.
- Why: transaction data would make more sense for billing, collections, analytics, or broader revenue-cycle workflows than simple patient scheduling.
- Still needs vendor proof: yes.
- Remaining concern: if Patient Manager is the only claimed justification, transaction capability may still be under-explained.

## Best Current Interpretation

If Patient Manager is part of this deployment, it could reasonably explain the existence of:

- patient imports
- appointment imports
- cloud-connected sync infrastructure
- some demographic or contact writeback surfaces

It does not by itself fully explain or justify:

- broad insurance or responsible-party handling
- notes handling
- transaction capability
- any writeback scope that was not explicitly disclosed and approved

## What Still Needs Direct Vendor Confirmation

Ask the vendor to answer all of these in writing:

1. Is Patient Manager enabled in this exact tenant or deployment?
2. Which observed entities are required specifically for Patient Manager?
3. Which observed entities are unrelated to Patient Manager and belong to other Sensei modules?
4. Which entities are read-only versus writable?
5. Which writeback workflows are expected for patient, appointment, and emergency-contact data?
6. Why is `Transaction` enabled if live transaction emission is not currently visible?
7. Does `Pnotes` transfer occur, and if so, what exact fields are included?

## Compliance Meaning

Even if Patient Manager explains the behavior technically, the setup still needs:

- agreement language covering cloud-connected and bidirectional behavior
- a BAA covering the actual data categories handled
- minimum-necessary justification for each data category
- documented approval for any writeback behavior

Patient Manager is a plausible technical explanation. It is not a substitute for authorization, disclosure, or compliance.
