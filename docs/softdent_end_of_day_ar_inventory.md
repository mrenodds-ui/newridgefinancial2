# SoftDent Daily End-of-Day Report A/R Inventory

Read-only inventory for report-derived accounts receivable from the **last page** of the
SoftDent Daily End-of-Day report. This is not ledger database access and not a writeback path.

## Workspace status

No production Daily End-of-Day report file is checked into this repository. The adapter supports
inventory-only discovery until a report is staged into the canonical import lane.

## Canonical import lane

| Setting | Purpose |
| --- | --- |
| `SOFTDENT_END_OF_DAY_REPORT_PATH` | Optional explicit path to one report file |
| `SOFTDENT_END_OF_DAY_REPORT_DIR` | Optional directory containing multiple dated reports |
| Default directory | `app/data/imports/softdent/daily_end_of_day/` |
| Latest alias (after source sync) | `softdent_daily_end_of_day_latest.txt` or `.pdf` |

## Supported formats (initial)

| Extension | Handling |
| --- | --- |
| `.txt` | Plain-text export; last page via form feed (`\f`) or `Page X of Y` markers |
| `.pdf` | Final page text extraction via `pypdf` (bounded parse only; raw page text is never exposed) |
| `.csv` / `.tsv` | Structured report export only when the file is a true report summary, not a ledger dump |

Unsupported files are ignored during inventory.

## Filename date conventions (secondary evidence)

When report body text does not contain an explicit business date, the adapter may use filename patterns:

- `daily_end_of_day_YYYY-MM-DD.*`
- `softdent_eod_YYYYMMDD.*`
- `softdent_daily_end_of_day_YYYY-MM-DD.*`

If neither body nor filename yields a date, A/R is unavailable and `missing_softdent_eod_report_date` is surfaced.

## Header / footer date labels (primary evidence)

Parsed in report order of priority:

- `Report Date`
- `End of Day Date`
- `For Date`
- `Date Range` (uses end date when a range is present)
- `Business Date`

Generated / run metadata (separate from business date):

- `Generated`, `Printed`, `Run Date`

File modified time is **freshness metadata only**, not the report business date.

## Last-page A/R labels inventoried

### Standard End-of-Day A/R summary labels

- `Total A/R`, `Total AR`, `Accounts Receivable`
- `Patient A/R`, `Patient AR`, `Patient Balance`
- `Insurance A/R`, `Insurance AR`, `Insurance Balance`
- Aging: `Current`, `0-30`, `31-60`, `61-90`, `90+`, `Over 90`
- `Credits`, `Credit Balance`, `Total Credits`
- `Collections`, `Collection Totals`
- `Production`, `Production Totals`

### SoftDent DAYSHEET receivables block (observed in production UI)

SoftDent v19.x **DAYSHEET** reports use a receivables summary block rather than explicit
`Total A/R` labels. Observed labels (sanitized from office export):

| Label | Adapter use |
| --- | --- |
| `New Receivables Total` | Maps to bounded office `total_ar` when present on the final page |
| `Previous Receivables Total` | Ignored for `total_ar` (prior-day balance, not current total) |
| `Today's Receivables (including insurance payments)` | Ignored (daily activity, not ending A/R) |
| `Today's Receivables (excluding insurance)` | Ignored (daily activity, not ending A/R) |
| `Insurance plan payments` | Ignored unless a future parser review approves a separate bounded field |

Daysheet date headers may appear as `Friday, June 26, 2026` (weekday + month name + day + year).

Patient-level transaction rows on intermediate Daysheet pages are never parsed for A/R totals.

## Freshness

- `SOFTDENT_EOD_AR_MAX_AGE_DAYS` (default `2`)
- `current`: report business date within threshold
- `stale`: report parses but date or modified time exceeds threshold
- `unknown`: report exists but business date cannot be determined confidently

## Role gate

Report-derived A/R requires:

- `softdent:read`
- `softdent:ledger:read`

Patient-level `get_ledger_context()` behavior is unchanged until explicitly approved.
