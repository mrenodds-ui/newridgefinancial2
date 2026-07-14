"""HAL-10591 / HON-001 — Empty ≠ $0 programmatic UI honesty policy.

Guarantees null/missing financial values never render as ``$0.00``, and that
Print Preview visual-audit aggregates are not conflated with gold payment lines.
No SoftDent write-back. empty != $0.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

DEF_ID = "HAL-10591"
PACKAGE_BUILD_ID = "hal-10591"

EMPTY_DISPLAY = "—"
NO_DATA_DISPLAY = "No data"
UNKNOWN_DISPLAY = "unknown"


class HonestyPolicy(str, Enum):
    EMPTY_IS_NOT_ZERO = "EMPTY_IS_NOT_ZERO"
    VISUAL_AUDIT_IS_NOT_GOLD = "VISUAL_AUDIT_IS_NOT_GOLD"
    NULL_DISPLAYS_AS_NULL = "NULL_DISPLAYS_AS_NULL"


# Source tags for display discrimination
SOURCE_GOLD_CSV = "gold_csv"
SOURCE_GOLD_PAYMENT_LINES = "gold_payment_lines"
SOURCE_INSURANCE_PAYMENT_LINES = "insurance_payment_lines"
SOURCE_PRINT_PREVIEW_VISUAL = "print_preview_visual"
SOURCE_LEDGER_SPINE = "ledger_episode_5yr"
SOURCE_CATALOG = "catalog"
SOURCE_KPI = "kpi"
SOURCE_UNKNOWN = "unknown"

GOLD_LIKE_SOURCES = frozenset(
    {
        SOURCE_GOLD_CSV,
        SOURCE_GOLD_PAYMENT_LINES,
        SOURCE_INSURANCE_PAYMENT_LINES,
    }
)

_EMPTY_SENTINELS = (None, "", "null", "none", "n/a", "na", "missing", "—", "-", "–")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_empty_money(value: Any) -> bool:
    """True when value is missing/null — NOT when value is a real 0.0."""
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip().lower()
        if s in _EMPTY_SENTINELS or s in {"unknown", "no data"}:
            return True
        if s in {"$0", "$0.00", "0", "0.0", "0.00"}:
            # Ambiguous string zero — treat as empty unless caller passes float 0.0
            return True
        return False
    return False


def parse_money_or_empty(value: Any) -> float | None:
    """Parse money; return None for empty/missing (never coerce empty → 0.0)."""
    if is_empty_money(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def enforce_empty_not_zero(
    value: Any,
    *,
    source_tag: str = SOURCE_UNKNOWN,
    empty_display: str = EMPTY_DISPLAY,
) -> dict[str, Any]:
    """Return display payload that never renders empty as ``$0.00``.

    Explicit float ``0.0`` is allowed (operator-observed zero). Missing/null → ``—``.
    Visual-audit sources get a distinct badge (not gold).
    """
    tag = str(source_tag or SOURCE_UNKNOWN).strip() or SOURCE_UNKNOWN
    out: dict[str, Any] = {
        "ok": True,
        "def": DEF_ID,
        "sourceTag": tag,
        "emptyIsNotZero": True,
        "showDollars": False,
        "display": empty_display,
        "value": None,
        "badge": None,
        "tone": "muted",
        "tooltip": None,
        "policies": [HonestyPolicy.EMPTY_IS_NOT_ZERO.value, HonestyPolicy.NULL_DISPLAYS_AS_NULL.value],
    }

    if is_empty_money(value):
        if tag in GOLD_LIKE_SOURCES:
            out["display"] = empty_display
            out["tooltip"] = "No gold payment-line data — empty != $0 (not $0.00)."
        elif tag == SOURCE_PRINT_PREVIEW_VISUAL:
            out["display"] = empty_display
            out["tooltip"] = "No Print Preview visual audit recorded yet — empty != $0."
        else:
            out["display"] = empty_display
            out["tooltip"] = "No data — empty != $0 (not $0.00)."
        out["isEmpty"] = True
        return out

    amount = parse_money_or_empty(value)
    if amount is None:
        # Non-empty but unparseable
        out["display"] = UNKNOWN_DISPLAY
        out["tooltip"] = "Unrecognized amount — empty != $0."
        out["isEmpty"] = True
        return out

    out["value"] = amount
    out["showDollars"] = True
    out["isEmpty"] = False
    out["display"] = f"${amount:,.2f}"
    out["tone"] = "ok"

    if tag == SOURCE_PRINT_PREVIEW_VISUAL:
        out["badge"] = "visual"
        out["label"] = "Visual audit"
        out["tone"] = "warn"
        out["tooltip"] = (
            "Visual audit aggregate from SoftDent Print Preview — not a gold payment line."
        )
        out["policies"].append(HonestyPolicy.VISUAL_AUDIT_IS_NOT_GOLD.value)
    elif tag in GOLD_LIKE_SOURCES:
        out["badge"] = "gold"
        out["label"] = "Payment lines"
        out["tooltip"] = "From SoftDent insurance payment lines (gold)."
    elif tag in {SOURCE_LEDGER_SPINE, SOURCE_CATALOG}:
        out["badge"] = "spine"
        out["label"] = "Ledger estimate"
        out["tooltip"] = "Ledger/spine estimate — not SoftDent gold payment lines."
    return out


def format_display_money(
    value: Any,
    *,
    source_tag: str = SOURCE_UNKNOWN,
    empty_display: str = EMPTY_DISPLAY,
) -> str:
    """Convenience: display string only (never ``$0.00`` for empty)."""
    return str(
        enforce_empty_not_zero(value, source_tag=source_tag, empty_display=empty_display).get(
            "display"
        )
        or empty_display
    )


def decorate_money_field(
    payload: dict[str, Any],
    field: str,
    *,
    source_tag: str,
    display_key: str | None = None,
) -> dict[str, Any]:
    """Attach honesty display for a money field onto a widget/payload dict."""
    out = dict(payload)
    enforced = enforce_empty_not_zero(out.get(field), source_tag=source_tag)
    key = display_key or f"{field}Display"
    out[key] = enforced.get("display")
    out[f"{field}Honesty"] = enforced
    out.setdefault("emptyIsNotZero", True)
    out.setdefault("honestyDef", DEF_ID)
    return out


def assert_display_not_fake_zero(display: str, *, context: str = "") -> None:
    """Raise if a display string is the forbidden empty→$0.00 lie."""
    # Real $0.00 is allowed only when value was explicitly 0.0; callers must not
    # pass empty through format that yields $0.00. This helper flags literal
    # misuse in audits when paired with is_empty_money True.
    d = str(display or "").strip()
    if d in {"$0", "$0.00"} and context.endswith(":empty"):
        raise AssertionError(f"HON-001 violation: empty rendered as {d!r} ({context})")


def audit_ui_honesty_surfaces() -> dict[str, Any]:
    """Scan key SoftDent/Apex honesty surfaces for empty≠$0 compliance markers."""
    findings: list[dict[str, Any]] = []
    ok_count = 0
    fail_count = 0

    def _check(name: str, cond: bool, detail: str) -> None:
        nonlocal ok_count, fail_count
        findings.append({"surface": name, "ok": cond, "detail": detail})
        if cond:
            ok_count += 1
        else:
            fail_count += 1

    # Core policy unit checks
    empty = enforce_empty_not_zero(None, source_tag=SOURCE_GOLD_PAYMENT_LINES)
    _check(
        "gold_null",
        empty.get("display") == EMPTY_DISPLAY and empty.get("display") != "$0.00",
        f"display={empty.get('display')!r}",
    )
    empty_str = enforce_empty_not_zero("", source_tag=SOURCE_GOLD_CSV)
    _check("gold_empty_str", empty_str.get("display") == EMPTY_DISPLAY, str(empty_str.get("display")))
    zero = enforce_empty_not_zero(0.0, source_tag=SOURCE_KPI)
    _check(
        "explicit_zero_allowed",
        zero.get("display") == "$0.00" and zero.get("showDollars") is True,
        str(zero.get("display")),
    )
    visual = enforce_empty_not_zero(1.0, source_tag=SOURCE_PRINT_PREVIEW_VISUAL)
    _check(
        "visual_not_gold",
        visual.get("badge") == "visual" and visual.get("showDollars") is True,
        f"badge={visual.get('badge')}",
    )
    visual_empty = enforce_empty_not_zero(None, source_tag=SOURCE_PRINT_PREVIEW_VISUAL)
    _check(
        "visual_null",
        visual_empty.get("display") == EMPTY_DISPLAY,
        str(visual_empty.get("display")),
    )

    # Live SoftDent widgets
    try:
        from softdent_print_preview_audit import print_preview_audit_widget

        w = print_preview_audit_widget()
        _check(
            "print_preview_widget_honesty",
            bool(w.get("emptyIsNotZero")) and w.get("triggersGoldIngest") is False,
            f"emptyIsNotZero={w.get('emptyIsNotZero')} badge={w.get('visualBadge')}",
        )
        msg = str(w.get("message") or "")
        # Gold gap must not be phrased as $0.00 when lines empty
        if int(w.get("paymentLines") or 0) == 0:
            _check(
                "print_preview_no_fake_gold_zero",
                "$0.00" not in msg or "visual" in msg.lower(),
                msg[:120],
            )
    except Exception as exc:  # noqa: BLE001
        _check("print_preview_widget", False, f"{type(exc).__name__}:{exc}")

    try:
        from softdent_treatment_planning import build_tp_estimate_chip

        chip = build_tp_estimate_chip(
            {
                "ok": True,
                "found": False,
                "sufficient": False,
                "credibility": "insufficient",
                "sampleSize": 0,
                "source": SOURCE_GOLD_PAYMENT_LINES,
                "payer": "DELTA",
                "adaCode": "D1110",
            }
        )
        _check(
            "tp_chip_insufficient",
            chip.get("showDollars") is False
            and chip.get("emptyIsNotZero") is True
            and "$0.00" not in str(chip.get("display") or ""),
            str(chip.get("display"))[:120],
        )
    except Exception as exc:  # noqa: BLE001
        _check("tp_chip", False, f"{type(exc).__name__}:{exc}")

    try:
        from apex_backend import _money_kpi

        kpi = _money_kpi("t", "Test", None, hint="x")
        _check(
            "apex_money_kpi_null",
            kpi.get("value") is None and kpi.get("status") == "empty",
            str(kpi.get("status")),
        )
    except Exception as exc:  # noqa: BLE001
        _check("apex_money_kpi", False, f"{type(exc).__name__}:{exc}")

    result = {
        "ok": fail_count == 0,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "checkedAt": _utc_now(),
        "passCount": ok_count,
        "failCount": fail_count,
        "findings": findings,
        "policies": [p.value for p in HonestyPolicy],
        "honesty": "empty != $0; visual audit != gold; explicit 0.0 allowed",
    }
    try:
        from softdent_treatment_planning import resolve_exports_dir

        dest = resolve_exports_dir()
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"ui_honesty_audit_{datetime.now(timezone.utc).date().isoformat()}.json"
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["jsonPath"] = str(path)
    except Exception as exc:  # noqa: BLE001
        result["exportError"] = f"{type(exc).__name__}:{exc}"
    return result


def format_honesty_audit_reply(result: dict[str, Any] | None = None) -> str:
    r = result if isinstance(result, dict) else audit_ui_honesty_surfaces()
    return (
        f"UI honesty ({DEF_ID}): pass={r.get('passCount')} fail={r.get('failCount')}; "
        f"ok={r.get('ok')}. empty != $0; visual audit != gold."
    )


def ui_honesty_widget() -> dict[str, Any]:
    r = audit_ui_honesty_surfaces()
    ok = bool(r.get("ok"))
    return {
        "id": "softdent-ui-honesty",
        "type": "status",
        "label": "UI Honesty Empty≠$0 (HAL-10591)",
        "size": "full",
        "status": "ok" if ok else "warn",
        "tone": "ok" if ok else "danger",
        "message": (
            f"Honesty audit pass={r.get('passCount')} fail={r.get('failCount')}"
            if ok
            else f"Honesty audit FAILED fail={r.get('failCount')} — empty must not render as $0.00"
        ),
        "hint": "Null/missing money → — ; Print Preview visual totals badge≠gold; explicit $0.00 only when truly zero.",
        "passCount": r.get("passCount"),
        "failCount": r.get("failCount"),
        "findings": r.get("findings"),
        "halChips": [
            {"label": "UI honesty status", "query": "empty not zero honesty audit"},
            {"label": "What is empty vs $0?", "query": "What does empty != $0 mean for SoftDent widgets?"},
        ],
        "honesty": r.get("honesty"),
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "emptyIsNotZero": True,
    }


if __name__ == "__main__":
    print(json.dumps(audit_ui_honesty_surfaces(), indent=2)[:5000])
