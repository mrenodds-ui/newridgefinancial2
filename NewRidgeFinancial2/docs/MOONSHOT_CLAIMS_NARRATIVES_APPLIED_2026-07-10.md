# Claims 30/60/90 Tiles + Narratives Insurance HAL — Applied

**Date:** 2026-07-10  
**Build:** **hal-10350**  
**Consult:** `MOONSHOT_CLAIMS_NARRATIVES_CONSULT_2026-07-10.md`  
**Status:** C1–C7 + MUST/SHOULD recommendations applied after operator “proceed with all recommendations”

## C1 — Backend aging buckets

- `apex_claims_narratives_pack.py` — normalize claim rows, 30/60/90 buckets, claim detail, narrative context, insurance generate, aging alert config, narrative audit
- `_claims_summary_from_bundle` returns `agingBuckets` / `agingCounts` / `agingMeta`
- APIs:
  - `GET /api/apex/claims-aging`
  - `GET /api/apex/claims/<claim_id>`
  - `GET|POST /api/apex/claims-aging/alerts`
  - `POST /api/apex/narratives/context`
  - `POST /api/apex/hal/narrative-generate`
  - `GET /api/apex/narratives/audit`

## C2 — Tile shelf widgets

- Widget type `claim-shelf` on Claims page: `claims-aging-30`, `claims-aging-60`, `claims-aging-90`
- Each tile: Claim ID, Patient Name, Date (+ age when present)
- Horizontal scroll shelf with accent colors (cyan / amber / rose)

## C3 — Claim detail drawer

- Click tile → slide-out drawer with import-backed claim fields
- **Draft Narrative** seeds Narratives page with claim/payer context

## C4 — HAL control

- Focus rules for 30/60/90 shelves
- Actions: `focus_claim_tile`, `open_claim_detail`, `focus_claims_bucket`
- Claims import status banner; Ask HAL chips for aging shelves
- HAL page chips: Focus 90-day claims, Claims aging status

## C5 — Narratives context panel

- Selectors for clinical notes, claims, insurance/payers from SoftDent import
- **Lock Context** → session `contextId`
- Insurance Narrative section added to scrubber

## C6 — Insurance narratives

- Types: appeal, medical-necessity, attachment-cover, prior-auth
- Consent checkbox required; source attribution footer; always `requiresHumanReview`
- Audit via `nr2:v2:narratives:audit` (+ CPA audit when store available)

## C7 — Thresholds + bulk

- Aging alert thresholds on 60/90 shelves (configurable)
- Bulk select checkboxes + **Bulk appeal** → Narratives seed with claim ID list
- CI fixture enriched with Age + 30/60/90 sample rows

## Honesty

- Never invents claim IDs, patient names, dates, or dollars
- Empty shelves use honest empty messages (not fake zeros)
- Age from Age/Days fields or computed from ServiceDate when parseable

## Files

- `apex_claims_narratives_pack.py` (new)
- `apex_backend.py` — widgets, routes, HAL board-actions, narrative structure
- `nr2_browser_security.py` — claims API prefixes
- `site/apex-core.js` — claim-shelf, drawer, HAL actions
- `site/apex-narratives.js` — context panel + payer generate
- `site/apex-bridge.css` — shelf/drawer/context styles
- `site/index.html`, `nr2-build.json` — **hal-10350**
- `ci-fixtures/imports/softdent/softdent_claims_export.csv`
