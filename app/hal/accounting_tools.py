from __future__ import annotations

from typing import Any


CHART_OF_ACCOUNTS: dict[str, str] = {
    "1010": "Cash",
    "1100": "Accounts Receivable",
    "1310": "Prepaid Insurance",
    "1500": "Equipment",
    "2100": "Accounts Payable",
    "2200": "Accrued Expenses",
    "4000": "Patient Service Revenue",
    "5050": "Insurance Expense",
    "5200": "Dental Supplies Expense",
    "6200": "Payroll Expense",
    "6100": "Depreciation Expense",
    "1590": "Accumulated Depreciation",
}

TRANSACTION_TYPE_ALIASES: dict[str, str] = {
    "prepaid": "prepaid_insurance",
    "prepaid_insurance": "prepaid_insurance",
    "depreciation": "depreciation",
    "cash_receipt": "patient_cash_receipt",
    "patient_cash_receipt": "patient_cash_receipt",
    "equipment_purchase": "equipment_purchase",
    "vendor_bill": "vendor_bill",
    "payroll_accrual": "payroll_accrual",
    "supplies_accrual": "supplies_accrual",
    "patient_service_revenue": "patient_service_revenue",
}

TRANSACTION_TYPE_RULES: list[tuple[tuple[str, ...], str]] = [
    (("prepaid", "insurance"), "prepaid_insurance"),
    (("depreciation",), "depreciation"),
    (("payroll", "accrual"), "payroll_accrual"),
    (("supplies", "accrual"), "supplies_accrual"),
    (("supply", "accrual"), "supplies_accrual"),
    (("vendor", "bill"), "vendor_bill"),
    (("cash", "collection"), "patient_cash_receipt"),
    (("patient", "payment"), "patient_cash_receipt"),
    (("equipment", "purchase"), "equipment_purchase"),
]

TRANSACTION_TYPE_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "prepaid_insurance": [
        {"account_code": "1310", "account_name": "Prepaid Insurance", "debit": "amount", "credit": 0},
        {"account_code": "1010", "account_name": "Cash", "debit": 0, "credit": "amount"},
    ],
    "depreciation": [
        {"account_code": "6100", "account_name": "Depreciation Expense", "debit": "amount", "credit": 0},
        {"account_code": "1590", "account_name": "Accumulated Depreciation", "debit": 0, "credit": "amount"},
    ],
    "patient_cash_receipt": [
        {"account_code": "1010", "account_name": "Cash", "debit": "amount", "credit": 0},
        {"account_code": "1100", "account_name": "Accounts Receivable", "debit": 0, "credit": "amount"},
    ],
    "equipment_purchase": [
        {"account_code": "1500", "account_name": "Equipment", "debit": "amount", "credit": 0},
        {"account_code": "1010", "account_name": "Cash", "debit": 0, "credit": "amount"},
    ],
    "vendor_bill": [
        {"account_code": "5200", "account_name": "Dental Supplies Expense", "debit": "amount", "credit": 0},
        {"account_code": "2100", "account_name": "Accounts Payable", "debit": 0, "credit": "amount"},
    ],
    "payroll_accrual": [
        {"account_code": "6200", "account_name": "Payroll Expense", "debit": "amount", "credit": 0},
        {"account_code": "2200", "account_name": "Accrued Expenses", "debit": 0, "credit": "amount"},
    ],
    "supplies_accrual": [
        {"account_code": "5200", "account_name": "Dental Supplies Expense", "debit": "amount", "credit": 0},
        {"account_code": "2200", "account_name": "Accrued Expenses", "debit": 0, "credit": "amount"},
    ],
    "patient_service_revenue": [
        {"account_code": "1100", "account_name": "Accounts Receivable", "debit": "amount", "credit": 0},
        {"account_code": "4000", "account_name": "Patient Service Revenue", "debit": 0, "credit": "amount"},
    ],
}

CLOSED_PERIODS = {"2024-12", "2025-01"}


def get_chart_of_accounts() -> dict[str, str]:
    return CHART_OF_ACCOUNTS.copy()


def is_period_open(period: str) -> bool:
    return period not in CLOSED_PERIODS


def _normalize_transaction_type(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    return TRANSACTION_TYPE_ALIASES.get(normalized)


def _infer_transaction_type(description: str, context: dict[str, object]) -> str:
    explicit_type = _normalize_transaction_type(context.get("transaction_type"))
    if explicit_type is not None:
        return explicit_type

    lower_description = description.lower()
    for keywords, transaction_type in TRANSACTION_TYPE_RULES:
        if all(keyword in lower_description for keyword in keywords):
            return transaction_type
    return "patient_service_revenue"


def draft_journal_entry_for_common_case(
    *,
    description: str,
    accounting_period: str,
    amount: float,
    context: dict[str, object],
) -> list[dict[str, object]]:
    del accounting_period
    transaction_type = _infer_transaction_type(description, context)
    matched_template = TRANSACTION_TYPE_TEMPLATES[transaction_type]

    lines: list[dict[str, object]] = []
    for template_line in matched_template:
        debit = amount if template_line["debit"] == "amount" else float(template_line["debit"])
        credit = amount if template_line["credit"] == "amount" else float(template_line["credit"])
        lines.append(
            {
                "account_code": template_line["account_code"],
                "account_name": template_line["account_name"],
                "debit": round(debit, 2),
                "credit": round(credit, 2),
                "memo": description,
            }
        )
    return lines