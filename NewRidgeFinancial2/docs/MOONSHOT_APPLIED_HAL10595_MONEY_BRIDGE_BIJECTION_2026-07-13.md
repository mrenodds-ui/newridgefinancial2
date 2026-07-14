# HAL-10595 / money-bridge-bijection (applied)

**Date:** 2026-07-13  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10594_2026-07-13.md`  
**Operator:** `proceed`  
**BUILD_ID:** `hal-10595`

## What shipped

| Piece | Location |
|-------|----------|
| Bijective API | `money_cents.money_to_api_bijective` (`cents_int` / `string_decimal`) |
| Legacy float | `money_to_api` kept + DeprecationWarning |
| Schema dual-write | `*_cents` + `money_cents_exact` INTEGER; REAL retained |
| SQL notes | `docs/m_10595_money_exact.sql` |
| History / widget / API | `totalCents` + `*Cents` alongside deprecated floats |
| Migration | `scripts/migrate_history_to_exact.py` (recompute from source, never REAL) |
| Tests | `test_hal10595_money_bridge_bijection.py` |

## Behavior

- New history rows dual-write integer cents; float columns remain for compat.
- Fingerprint visual/ledger use exact string decimals (not IEEE-754 floats).
- `money_cents_exact` = ledger total cents (`totalCents`).
- Flag only — no SoftDent write-back, no gold invent. empty != $0.

## Honesty

Closes the HIGH IEEE-754 float-bridge gap after HAL-10594 SQL null honesty.
