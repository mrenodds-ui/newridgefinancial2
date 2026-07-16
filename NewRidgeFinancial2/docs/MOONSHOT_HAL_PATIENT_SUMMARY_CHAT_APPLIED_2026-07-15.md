# HAL patient summarize (chat) — applied 2026-07-15

**Build:** `nr2-12043-hal-patient-summary`

## What shipped

- HAL chat local policy answers patient-summary asks before the LLM.
- Reuses `build_patient_dossier` + `summarize_dossier_with_local_ai` (deterministic markdown fallback).
- RBAC: `read_patient_dossier` (office_manager / dentist / admin).
- Audit: `log_patient_query(..., "dossier_summary_chat")` (hashed patient id only).
- Optical HAL tool row: patient id/name → SUMMARIZE → `POST /api/hal/chat`.

## Ask patterns

- `Summarize patient 12345`
- `Patient summary for Nickel, Donna`
- `Can you summarize patients?` → how-to (no PHI)

## Safety

- SoftDent read-only; empty ≠ $0; no cloud/web PHI path.
- Does not collide with `Summarize what HAL does…` (`policy:hal-summary`).
- Does not treat summarize as SoftDent write-back.
