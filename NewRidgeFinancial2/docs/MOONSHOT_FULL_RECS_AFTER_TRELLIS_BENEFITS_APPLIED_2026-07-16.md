# Full recommendations after Trellis benefits — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_TRELLIS_BENEFITS_2026-07-16.md`  
**Operator:** continue with full recommendations  
**Build:** `nr2-12071-trellis-benefits-surface`

## Package 1 — Attended morning bundle (already run)

See `MOONSHOT_ATTENDED_MORNING_BUNDLE_APPLIED_2026-07-16.md`.

- Aging → register → collections navigated OK
- SoftDent **Excel greyed out** → Print Preview only
- `morningBundle.ok` still **false** (money beams need Excel enabled in SoftDent)
- empty ≠ $0 preserved

## Package 2 — Surface full benefits HTML (OM-safe)

| Piece | Status |
|-------|--------|
| `GET /api/trellis/eligibility-report` | Live — path, `reportUrl`, **patients / withBenefits / statusOnly** counts (no $) |
| `GET /api/trellis/eligibility-report.html` | Serves printable HTML for staff |
| OM button `#tr-report-link` | Wired; hint shows benefits vs status-only counts |
| Huddle list | Unchanged — initials + hash + verify status only |

Tonight’s 10:10 PM Trellis `--verify` will raise `withBenefits` as ClearCoverage scrapes land.

## Package 3 — SoftDent report-pull HAL teach harden

[`softdent_report_pull.py`](../softdent_report_pull.py):

- Minimize Claim Management / NR2 Optical Claims before unattended pulls
- Excel **greyed out** → Print Preview only; empty ≠ $0 for money until Excel enabled
- Never File; F10 when 64-bit `menu_select` fails
- Morning bundle needs Excel for money beams / otherwise attest_only

Tests: `test_softdent_report_pull` OK.

## Package 4 — Optional QB AP/payroll refresh

Attempted:

- `qb_sync` → QBO API **not configured** (IIF/export path remains)
- `scripts/ops/run_quickbooks_sdk_refresh.py` → refreshed revenue / expenses / P&L from analytics-db
- **AP + payroll** not refreshed: SDK monthly read unavailable; existing `quickbooks_ap*` / `quickbooks_payroll*` stay stale with `batch_empty` markers

Honest outcome: optional gaps remain until fresh QB AP/payroll exports are dropped into the inbox. No invented dollars.

## Explicitly not done

- Flip `forceCloseAvailable`
- Invent SoftDent Excel drops or QB AP/payroll rows
- Redo OM schedule / Trellis huddle / this-patient / PushEngage

## Operator leftovers

1. Enable SoftDent Output Options **Excel**, then say **approve** for morning-bundle money beams.
2. Restart NR2 once so OM/HAL pick up `nr2-12071` teach + `withBenefits` snapshot.
3. Drop fresh QB AP/payroll CSVs when available → SoftDent/QB Sync.
4. Tonight Trellis verify fills ClearCoverage benefits automatically.
