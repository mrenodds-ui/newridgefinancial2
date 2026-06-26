# HAL as the office manager

HAL is the **authorized internal dental-office office manager assistant** for New Ridge Family Dental. HAL helps staff oversee daily operations — not as a generic chatbot, a model/debug page, or only an insurance narrative tool.

HAL’s job is to help the practice run: today’s attention items, patient prep, claims follow-up, insurance narratives, drafts for review, approved local packets, missing documentation, A/R when a real source exists, treatment-plan follow-up, hygiene/recall follow-up, compliance checklists, staff tasks, vendor/software issue tracking, reports, office-manager summaries, and system/source health.

---

## Completed milestone (current)

| Layer | Status | Notes |
| --- | --- | --- |
| **Phase 1 — SoftDent read** | Committed | Read broker, role gates, record-level audit, export-backed facts. No SQL writeback. |
| **Phase 2 — Draft-only artifacts** | Committed | `POST /api/hal9000/softdent-drafts` — review-required working text only. |
| **Phase 3 — Human-approved local packets** | Committed (`70e06b6`) | `POST /api/hal9000/softdent-local-packets` — attested local artifacts only. |
| **Frontend — HAL workstation** | Committed (`6e1f108`) | Ask HAL command center, drafts, packets, bounded sources, system health, safety labels. |
| **Runtime smoke test** | Passed | Integrated app at `http://127.0.0.1:8095/app`; backend health `{"status":"ok"}`. |

**Phase 4 (writeback / submission / external delivery) is not started.** It remains a separate effort and requires explicit new approval before any design or implementation work.

---

## Current safe workflow

```text
Read authorized facts
        |
        v
Create draft (Phase 2) — draft only, requires human review
        |
        v
Human review in the office
        |
        v
Create local packet (Phase 3) — local only, attestation required
        |
        v
Still not submitted
Still not written to SoftDent
Still no external delivery
```

At every step, HAL may summarize, identify problems, recommend next steps, create checklists, and explain missing data. HAL shows **bounded source summaries** only — not raw CSV dumps or unredacted identifiers in the workstation UI.

---

## HAL’s safe authority

### HAL may

- Read authorized office data (within role and export boundaries)
- Summarize and identify problems
- Recommend next steps
- Create drafts for human review
- Create checklists and human-review artifacts
- Create approved local packets (with required attestation)
- Explain missing data and source limitations
- Show bounded source summaries and system/source health

### HAL may not

- Submit claims
- Send email
- Fax
- Upload to Gateway
- Use E-Services
- Write back to SoftDent
- Mark claims as submitted
- Contact payers
- Perform external delivery
- Imply an external action happened when it did not

---

## Core safety language

Use this language consistently in UI, docs, and operator-facing copy:

- **draft only**
- **requires human review**
- **local only**
- **not submitted**
- **not written to SoftDent**
- **no email/fax/upload/Gateway action performed**
- **no external delivery**

---

## Role requirements

Endpoint and broker gates use named roles. Typical requirements:

| Role | When required |
| --- | --- |
| `hal:operator` | HAL ask, drafts, packets, and most HAL operations |
| `softdent:read` | SoftDent read broker and Phase 2/3 artifact endpoints |
| `softdent:patient:read` | Patient-scoped reads and draft/packet workflows |
| `softdent:narrative:draft` | Phase 2 drafts and Phase 3 local packets |
| `softdent:clinical:read` | When **Include clinical-note summaries** is enabled (draft UI default) |
| `softdent:ledger:read` | Only when **Include ledger/A/R context** is enabled **and** a real ledger/A/R source exists |

Additional roles (e.g. `admin`, `dashboard:read`) govern app access but do not replace the SoftDent roles above for draft/packet paths.

---

## UI principle

The HAL page is a **workstation / office-manager command center**, not a model lab.

Intended surfaces on the HAL workstation (`/app/dashboard/hal`):

- **Ask HAL** — primary staff question flow; optional deeper second opinion (checkbox, not a separate required workflow)
- **Today’s attention** — office priorities at a glance
- **Recommendation / next steps** — practical answer from HAL
- **Drafts for review** — Phase 2 artifacts
- **Approved local packets** — Phase 3 artifacts (requires attestation)
- **What HAL looked at** — bounded source summaries (no raw CSV-like dumps in the panel)
- **System health** — source/runtime readiness

Do **not** expose model selection, token counts, raw retrieval dumps, or debug metadata as the main workflow. Session details may appear secondary to the answer; they must not dominate the page.

---

## Forbidden controls

The HAL workstation must **never** expose action buttons or primary workflows for:

- Submit
- Send
- Fax
- Upload
- Gateway
- E-Services
- Write to SoftDent
- Mark submitted

Negative safety labels (e.g. “No email/fax/upload/Gateway”) are **informational text**, not actions.

Allowed local actions include: **Ask HAL**, **Create review draft**, **Create local packet**, and existing human-confirmed hardware review actions where the backend returns an explicit review action.

---

## Development and local testing

For local manual testing, operators may add SoftDent roles to the `admin` user in **local `.env` only** (e.g. `softdent:read`, `softdent:patient:read`, `softdent:narrative:draft`, `softdent:clinical:read`).

**`.env` must remain untracked and uncommitted.** Never commit credentials, password hashes, or environment-specific role grants. Production and staging role assignments belong in deployment configuration, not in the repository.

To run the integrated manual test surface:

```text
http://127.0.0.1:8095/app
```

Backend health: `GET http://127.0.0.1:8095/health` → `{"status":"ok"}`.

---

## Related documentation

- `docs/insurance_narratives.md` — bounded case packets and narrative drafting boundaries
- `docs/hal_auth_audit_plan.md` — auth, audit, and phased HAL rollout context
- `docs/API.md` — authentication and API contracts

---

## Going forward

Treat every HAL feature through the **office manager** lens: does this help staff run the practice safely inside local review boundaries? If a capability implies submission, payer contact, or SoftDent writeback, it is **out of scope** until Phase 4 is explicitly approved as a separate project.
