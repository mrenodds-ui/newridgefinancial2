# HAL Auth And Audit Plan

This plan defines the controls that should be in place before HAL is allowed to call a real model with production-adjacent data.

## Current state

- HAL now runs as a local Phase 1 backend flow.
- Questions are sanitized before retrieval.
- Retrieval is limited to approved local context.
- Audit metadata is recorded for each HAL request.
- Authentication is still shared HTTP Basic auth and is not sufficient for production AI access.

## Required auth upgrades

Before any real model integration:

1. Replace shared Basic Auth with unique user identities.
2. Require role checks for HAL access separately from dashboard read access.
3. Restrict HAL to named operator roles such as practice owner, office manager, and approved finance users.
4. Add short session lifetime and explicit reauthentication for privileged HAL actions.
5. Keep HAL on localhost or a tightly controlled internal network boundary.

## Required audit upgrades

Audit events should capture:

- authenticated user id
- request timestamp
- HAL mode and model id
- sanitized question text or hashed raw prompt reference
- retrieval document ids
- tool invocation ids
- response status and latency

Audit events should not store raw PHI unless there is an explicit retention decision and access policy for that log store.

## Operational controls

- Keep model serving local or within an approved private boundary.
- Block arbitrary SQL and direct database credentials from the model runtime.
- Review imported documents for prompt injection and untrusted content.
- Apply retention limits to HAL audit records.
- Review HAL access and audit logs regularly.

## Rollout sequence

1. Phase 1: local mocked/sanitized retrieval only.
2. Phase 2: read-only backend tools over aggregated data.
3. Phase 3: real model calls only after auth, audit, retention, and privacy review are signed off.
