"""Currency helpers for SoftDent/Apex financial honesty (cent-safe Decimal).

Use Decimal quantized to 2 places (ROUND_HALF_EVEN / banker's rounding) for
variance and ledger aggregates. Never coerce null/missing to 0.0.
empty != $0.

HAL-10595: prefer money_to_api_bijective (cents_int / string_decimal) over the
legacy IEEE-754 money_to_api float bridge for audit/history/API exactness.
"""

from __future__ import annotations

import warnings
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Any, Literal

from ui_honesty_policy import is_empty_money

TWOPLACES = Decimal("0.01")
CENT = Decimal("0.01")
HUNDRED = Decimal("100")

BijectiveFormat = Literal["cents_int", "string_decimal"]


def _normalize_money_text(text: str) -> str:
    """Strip currency chrome; convert accounting parentheses to leading minus."""
    t = text.strip().replace("$", "").replace(",", "").replace("—", "-")
    if t.startswith("(") and t.endswith(")") and len(t) > 2:
        t = "-" + t[1:-1].strip()
    return t.strip()


def to_money(value: Any) -> Decimal | None:
    """Parse money to Decimal cents scale, or None if empty/unparseable.

    Explicit numeric 0 / 0.0 is kept as Decimal('0.00').
    Null / blank / ambiguous string zeros from honesty policy stay None.
    """
    if is_empty_money(value):
        return None
    if isinstance(value, Decimal):
        try:
            if not value.is_finite():
                return None
            return value.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)
        except InvalidOperation:
            return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):  # NaN / Inf
            return None
        # Route through str to avoid binary float litter when possible
        try:
            return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)
        except (InvalidOperation, ValueError):
            return None
    text = _normalize_money_text(str(value))
    if not text or text in {"-", "N/A", "n/a"}:
        return None
    try:
        d = Decimal(text)
        if not d.is_finite():
            return None
        return d.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, ValueError):
        return None


def to_money_from_csv(value: Any) -> Decimal | None:
    """Parse CSV cell money; explicit string zeros stay Decimal('0.00').

    Differs from to_money(): UI honesty treats ambiguous '$0'/'0.00' strings as
    empty, but SoftDent Gold CSV Paid Amount of 0.00 is an observed zero line
    (denial / $0 payment), not a missing field.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, str):
        text = _normalize_money_text(value)
        if not text or text in {"-", "—", "N/A", "n/a"}:
            return None
        if text in {"0", "0.0", "0.00", "+0", "+0.0", "+0.00"}:
            return Decimal("0.00")
        try:
            d = Decimal(text)
            if not d.is_finite():
                return None
            return d.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)
        except (InvalidOperation, ValueError):
            return None
    return to_money(value)


def money_as_sqlite_real(value: Decimal | None) -> float | None:
    """Store Decimal money in SQLite REAL after cent quantization (display scale)."""
    if value is None:
        return None
    return float(value)


def money_to_api(value: Decimal | None) -> float | None:
    """JSON-friendly float after Decimal quantization (display/API only).

    Deprecated (HAL-10595): IEEE-754 cannot represent all cent values exactly.
    Prefer money_to_api_bijective(..., format='cents_int'|'string_decimal').
    Kept for backward-compatible float fields during dual-write transition.
    """
    warnings.warn(
        "money_to_api float bridge is deprecated; use money_to_api_bijective "
        "(cents_int or string_decimal) for bijective money",
        DeprecationWarning,
        stacklevel=2,
    )
    if value is None:
        return None
    return float(value)


def money_to_api_bijective(
    value: Any,
    format: BijectiveFormat | str = "cents_int",  # noqa: A002 — Moonshot API name
) -> int | str | None:
    """Bijective money serialization (ROUND_HALF_EVEN parity with to_money).

    format='cents_int' → integer cents (e.g. Decimal('12.34') → 1234)
    format='string_decimal' → exact decimal string (e.g. '12.34')

    Round-trip: Decimal(cents_int) / 100 == to_money(value)
                to_money(string_decimal) == to_money(value)
    """
    money = to_money(value)
    if money is None:
        return None
    fmt = str(format or "cents_int").strip().lower()
    if fmt in {"cents_int", "cents", "int"}:
        cents = (money * HUNDRED).to_integral_value(rounding=ROUND_HALF_EVEN)
        return int(cents)
    if fmt in {"string_decimal", "string", "decimal_str"}:
        return f"{money:f}"
    raise ValueError(
        f"money_to_api_bijective format must be 'cents_int' or 'string_decimal', got {format!r}"
    )


def cents_int_to_money(cents: int | None) -> Decimal | None:
    """Convert integer cents back to Decimal dollars (bijective inverse)."""
    if cents is None:
        return None
    return (Decimal(int(cents)) / HUNDRED).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


def money_add(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    if a is None or b is None:
        return None
    return (a + b).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


def money_sub(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    if a is None or b is None:
        return None
    return (a - b).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


def money_abs(a: Decimal | None) -> Decimal | None:
    if a is None:
        return None
    return abs(a).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)
