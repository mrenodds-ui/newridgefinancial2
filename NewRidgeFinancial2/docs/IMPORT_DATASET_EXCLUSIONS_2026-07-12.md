# Import Dataset Exclusions — 2026-07-12

**Context:** Moonshot Import Dataset Hygiene after ERA honesty browser smoke  
**Build:** hal-10571 (+ watcher fix `2439197`)  
**Honesty:** empty ≠ $0 — no invented QuickBooks wages or AP balances

## The 2 missing datasets (identified)

| datasetKey | Severity | Upstream search | Disposition |
|------------|----------|-----------------|-------------|
| `quickbooks.payroll` | optional | No payroll CSV/XLS under `document_inbox/quickbooks`, SoftDent export roots, or QB-named folders | **Empty-batch honesty marker** written |
| `quickbooks.ap` | optional | No AP / unpaid-bills CSV under the same roots | **Empty-batch honesty marker** written |

Critical money-read completeness was already **100%** (4/4). These two were the ticker’s “IMPORTS 17/19 · 2 missing” optional gaps — not July SoftDent Register.

## What was written (not invented dollars)

Via `apex_qb_export_inbox_pack.write_qb_payroll_ap_exports(empty_payroll=True, empty_ap=True, period="2026-07")`:

| File | Role |
|------|------|
| `app_data/nr2/document_inbox/quickbooks/quickbooks_payroll_detail.csv` | Header-only |
| `app_data/nr2/document_inbox/quickbooks/quickbooks_payroll.batch_empty.json` | `honesty=empty_not_zero` |
| `app_data/nr2/document_inbox/quickbooks/quickbooks_ap_aging.csv` | Header-only |
| `app_data/nr2/document_inbox/quickbooks/quickbooks_ap.batch_empty.json` | `honesty=empty_not_zero` |

## Deliberate exclusion rationale

Staff have not dropped a current QuickBooks Payroll Detail or Unpaid Bills / AP aging export into the NR2 QB inbox. Until a real export arrives:

- Do **not** invent wage or vendor-balance rows.
- Keep `batchEmpty=true` sidecars so HAL/payroll gap widgets treat the datasets as **present-but-empty**.
- Replace markers automatically when real CSVs land (`write_payroll_export` / `write_ap_export` clear the sidecar).

## Not excluded

- July SoftDent Register (Ins Plan $0 SoftDent truth) — untouched; do not re-export hoping Ins Plan > 0.
- SoftDent critical datasets (dashboard, AR, etc.) — already connected after watcher hotfix.

## Quarantine hygiene

Purged **2568** leftover quarantine items whose only failure was  
`load_import_bundle() got an unexpected keyword argument 'read_only'`  
(fixed in `2439197`). Inbox already held live copies; no SoftDent write-back.
