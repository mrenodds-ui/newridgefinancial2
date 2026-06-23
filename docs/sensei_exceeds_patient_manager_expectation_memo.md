# Sensei Behavior Exceeds Ordinary Patient Manager Expectation

## Purpose

This memo states a narrow, evidence-based conclusion for internal review or vendor escalation:

The currently observed Sensei Gateway behavior appears broader than what a normal practice would ordinarily expect from a product described only as Patient Manager.

## Core Conclusion

Patient Manager may explain part of what was observed, but it does not fully explain the full integration surface currently visible on the machine.

Specifically:

- patient import activity is plausibly consistent with Patient Manager
- appointment import activity is plausibly consistent with Patient Manager
- cloud-connected sync infrastructure is plausibly consistent with Patient Manager
- some demographic or emergency-contact related workflow behavior may be consistent with Patient Manager

However, the observed system also shows signs of a broader integration footprint, including:

- insurance or responsible-party related handling
- provider, location, ADA, and reference entity scope
- `Pnotes` capability in config
- `Transaction` capability in config
- inbound import and writeback surfaces that go beyond a simple read-only patient engagement tool

## Why This Matters

The practical issue is not whether the product can technically do these things. The issue is whether the practice was clearly told that it does these things, approved that scope, and has the right contract and privacy coverage for it.

If staff were led to believe this was only a narrow Patient Manager or reminder-style workflow, the current observed behavior appears broader than that ordinary expectation.

## Evidence Supporting This Conclusion

- imported patient JSON files were observed locally
- imported appointment JSON files were observed locally
- local writeback pathways targeted SoftDent tables such as `PatientEmergencyContact`
- injector logs showed patient-related writeback or import success
- staged folders and config referenced insurance, provider, location, ADA, and reference entities
- `Pnotes` and `Transaction` appeared in config even though live transaction movement was not observed in the inspected path
- the client maintained cloud-connected communication with vendor Azure endpoints

## What Patient Manager Plausibly Explains

- patient synchronization
- appointment synchronization
- cloud-coordinated workflow activity
- some contact or demographic update behavior

## What Still Looks Broader Than Ordinary Patient Manager Expectation

- broad insurance or responsible-party handling
- notes capability
- transaction capability
- any undisclosed writeback scope
- any entity set that is materially wider than patient scheduling and communication workflows

## Compliance Meaning

This memo does not claim the behavior is illegal.

It does support these narrower conclusions:

- the observed behavior is broader than a minimal Patient Manager expectation
- the actual enabled scope should be confirmed directly with the vendor in writing
- the signed agreement and BAA should be checked against the real observed behavior, not just the product name

## Requested Vendor Response

If the vendor claims the observed behavior is explained by Patient Manager, ask them to confirm in writing:

1. whether Patient Manager is enabled in this exact deployment
2. which observed entities are required for Patient Manager
3. which observed entities belong to other modules or services
4. which observed entities are read-only versus writable
5. why `Pnotes` and `Transaction` are enabled or present in config
6. whether the practice explicitly approved any writeback behavior

## Practical Bottom Line

The best current evidence-based statement is:

Sensei may partly be behaving this way because of Patient Manager, but the visible integration surface still appears broader than what an ordinary practice would usually expect from Patient Manager alone.
