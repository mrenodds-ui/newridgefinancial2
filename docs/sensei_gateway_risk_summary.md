# Sensei Gateway Risk Summary

## Plain-English Bottom Line

Sensei Gateway on this machine is not acting like a simple one-way report exporter.

It appears to be a bidirectional sync client that:

- stages local SoftDent-related data for outbound sync
- keeps live encrypted connections to vendor cloud endpoints
- accepts or stages inbound JSON payloads for import into SoftDent
- has writeback templates for updating local emergency-contact records
- has evidence of at least some successful patient-related writeback activity

That does not prove anything illegal by itself. It does mean the product has a broader data and control surface than a passive reporting bridge.

## What It Appears To Access

From the local DataSync tenant tree and injector config, Sensei is associated with these data categories:

- patient data
- appointment data
- insurance/company data
- dentist and provider data
- ADA and reference data
- location data
- notes or `Pnotes`
- transaction capability in config, even though live transaction emission was not observed in the outbound DataSync tree

## What It Appears To Change

The local SoftDent injector path shows imported JSON files for at least:

- patient
- appointment

The local writeback template for emergency contacts targets the `PatientEmergencyContact` table.

The injector log on 2026-06-16 reported:

- repeated duplicate-key errors for some operations
- a successful patient-related writeback message
- updates involving patients, responsible parties, and insurance policies

So the installed product appears capable of writing data back into SoftDent, not just reading from it.

## What It Connects To

The installed Sensei client config points to Azure-hosted endpoints for:

- `SyncAgentApi`
- `IngressApi`

The running service maintained active outbound HTTPS sessions to remote IPs during inspection, and the configured hosts presented Microsoft-issued TLS certificates for the Azure Container Apps domain.

This means the product is cloud-connected and not strictly local-only.

## Operational Risks

## Data Scope Risk

If the vendor or practice believes this is only a limited export bridge, that understanding appears incomplete. The local install shows broader entity coverage and writeback capability.

## Change Risk

Because inbound/import paths exist, a bad payload, duplicate-key condition, mapping error, or vendor workflow bug could attempt to change local practice data.

## Visibility Risk

The dashboard-side refresh scripts do not appear to trigger new Sensei staging directly. That means Sensei may operate on its own cadence or remote command path, which can make it harder for local staff to understand exactly when data is being read or written.

## Reliability Risk

Current logs show extractor and connectivity problems, including:

- emergency-contact extraction failures
- earlier queue/session instability
- duplicate-key writeback/import errors

That combination increases the chance of partial sync behavior, stale data, or mixed success/failure states.

## Compliance Risk

If contracts, notices, or staff assumptions describe Sensei as a narrower tool than what is actually installed, there may be a mismatch between real data handling and documented approval.

## What Is Proven Versus Not Proven

Proven from this machine:

- Sensei stages multiple categories of local practice data
- Sensei is cloud-connected
- Sensei has inbound/import and writeback surfaces
- patient and appointment JSONs exist in injector import folders
- at least one patient writeback/import success was logged

Not proven from this machine alone:

- that Sensei is doing anything illegal
- that every configured entity is actively being written back
- that transaction writeback is currently succeeding
- that the vendor is collecting more than the contract allows

## Practical Recommendation

Treat Sensei Gateway as a bidirectional clinical/business data integration product, not as a simple export helper.

Any approval, compliance, or security review should assume:

- outbound sync of practice data
- inbound import/writeback capability
- remote cloud coordination
- the need for auditability and vendor accountability