# HAL-10591 / HON-001 — Empty≠$0 Programmatic UI Enforcement (applied)

**Date:** 2026-07-13  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10590_2026-07-13.md`  
**Operator:** `proceed`  
**BUILD_ID:** `hal-10591`

## What shipped

| Piece | Location |
|-------|----------|
| Policy module | `ui_honesty_policy.py` — `HonestyPolicy`, `enforce_empty_not_zero`, surface audit |
| CLI audit | `scripts/audit_ui_honesty.py` |
| Widget | `softdent-ui-honesty` |
| API | `GET /api/apex/ui-honesty/status` |
| HAL | `policy:empty-not-zero` |
| Sync | `import_sync.py` → `softdent.uiHonesty` snapshot |
| Wire-ins | Print Preview audit display (`[visual]` badge), gold pipeline `—`, TP `_fmt_money` / chips, Apex `_money_kpi` |
| Tests | `test_hon_001_empty_not_zero_hal10591.py` |

## Behavior

- Null/missing money → display `—` / `No data` / `unknown` — **never** `$0.00`.
- Explicit float `0.0` may still show `$0.00` (true zero).
- `source_tag=print_preview_visual` → badge `visual` + tooltip “not a gold payment line.”
- Gold gap with `paymentLines=0` → `goldPaymentLinesDisplay=—` (not `$0.00`).
- No SoftDent write-back; visual audit still does not create gold lines.

## Honesty

empty ≠ $0. Visual audit ≠ gold. BUILD_ID coupled to `hal-10591`.
