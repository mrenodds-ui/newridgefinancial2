from __future__ import annotations


def _collect_journal_amounts(*, lines: list[dict[str, object]], field: str) -> tuple[list[float], list[str]]:
    values: list[float] = []
    invalid_fields: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        raw_value = line.get(field, 0)
        if raw_value in (None, ""):
            raw_value = 0
        try:
            values.append(float(raw_value))
        except (TypeError, ValueError):
            values.append(0.0)
            invalid_fields.append(f"line {line_number} {field}")
    return values, invalid_fields


def build_journal_validation(*, lines: list[dict[str, object]], chart_of_accounts: dict[str, str], open_period: bool) -> dict[str, object]:
    debit_values, invalid_debit_fields = _collect_journal_amounts(lines=lines, field="debit")
    credit_values, invalid_credit_fields = _collect_journal_amounts(lines=lines, field="credit")
    invalid_amount_fields = invalid_debit_fields + invalid_credit_fields
    debit_total = round(sum(debit_values), 2)
    credit_total = round(sum(credit_values), 2)
    balanced = debit_total == credit_total and not invalid_amount_fields
    missing_accounts = [str(line.get("account_code") or "") for line in lines if str(line.get("account_code") or "") not in chart_of_accounts]
    has_negative_amounts = any(value < 0 for value in debit_values + credit_values)
    issues: list[str] = []
    if not balanced:
        issues.append("Journal entry is not balanced.")
    if not open_period:
        issues.append("Accounting period is closed.")
    if missing_accounts:
        issues.append(f"Unknown account codes: {', '.join(missing_accounts)}")
    if invalid_amount_fields:
        issues.append(f"Journal line amounts must be numeric: {', '.join(invalid_amount_fields)}")
    if has_negative_amounts:
        issues.append("Journal line amounts must be non-negative.")
    return {
        "balanced": balanced,
        "debit_total": debit_total,
        "credit_total": credit_total,
        "open_period": open_period,
        "account_validation_passed": not missing_accounts,
        "amount_validation_passed": not has_negative_amounts and not invalid_amount_fields,
        "issues": issues,
    }