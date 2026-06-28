# Broad Page Work — Uncommitted Safety Patch

This note documents the untracked file `BROAD_PAGE_WORK_UNCOMMITTED_SAFETY_PATCH.diff`. It is **not** part of the current HAL baseline and should not be treated as active work.

## What this patch contains

Earlier **broad page conversion work** from the "do all pages" pass — converting mockup-image pages to functional component-based renderers across multiple dashboards. It was saved as a safety patch before the repo was cleaned back to the HAL baseline.

**Files included in the patch:**

- `site/page-sample-data.js` — seed data updates for financial, SoftDent, QuickBooks, A/R, and related pages
- `site/page-views.js` — functional page renderers and removal of mock-image routing for non-HAL pages
- `site/styles.css` — broad `pv-*` layout/style hunks (financial, SoftDent, A/R, Claims, documents, etc.)
- `validate-pages.mjs` — functional-page validation assertions

The patch does **not** include HAL Step 4 work or the AI readiness display patch. Those are committed separately.

## Current clean HAL baseline

The active, committed baseline is:

- **`8802979`** — HAL display local AI readiness
- Parent: **`d5c6e94`** — HAL command center manager signals

`main` should be checked out at `8802979` with a clean tracked working tree. Only this README and the patch file itself should appear as untracked.

## How to use this patch

- **Review later** — open or diff the patch when you are ready to evaluate or split the broad page work into reviewable commits.
- **Do not apply automatically** — do not run `git apply` as part of builds, CI, or routine setup.
- **Do not commit unless explicitly approved** — the patch file and this README are documentation/safety artifacts until you decide otherwise.

## What not to do

- Do not mistake this patch for the current app state.
- Do not apply it on top of HAL work without reviewing conflicts.
- Do not delete it without confirming the broad page changes are captured elsewhere.

## Restoring the broad page work (manual, when approved)

From a clean `8802979` checkout:

```bash
git apply --recount BROAD_PAGE_WORK_UNCOMMITTED_SAFETY_PATCH.diff
```

Review the result, run validators, and commit only after explicit approval.
