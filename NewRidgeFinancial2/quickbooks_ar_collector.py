"""Build QuickBooks A/R aging rows from SDK probe summary (read-only, local cache)."""

from __future__ import annotations

from typing import Any


def build_quickbooks_ar_rows_from_sdk(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return standard aging rows when SDK summary includes A/R totals or buckets."""
    if not isinstance(payload, dict):
        return []
    aging = payload.get("ar_aging") or payload.get("accounts_receivable_aging") or payload.get("arAging")
    if isinstance(aging, list) and aging:
        rows: list[dict[str, Any]] = []
        for item in aging:
            if not isinstance(item, dict):
                continue
            balance = item.get("balance")
            if balance is None:
                balance = item.get("Balance") or item.get("amount") or item.get("Amount")
            if balance in (None, ""):
                continue
            rows.append(
                {
                    "Bucket": str(item.get("bucket") or item.get("Bucket") or item.get("range") or "Unknown"),
                    "Balance": balance,
                }
            )
        return rows

    total = payload.get("accounts_receivable")
    if total in (None, ""):
        total = payload.get("total_accounts_receivable") or payload.get("AccountsReceivable") or payload.get("ar_total")
    if total in (None, ""):
        return []
    return [{"Bucket": "Total A/R", "Balance": total, "AccountsReceivable": total}]


def write_quickbooks_ar_csv(destination, rows: list[dict[str, Any]], write_csv) -> str | None:
    if not rows:
        return None
    path = destination / "quickbooks_ar.csv"
    write_csv(path, rows, ["Bucket", "Balance", "AccountsReceivable"])
    return path.name
