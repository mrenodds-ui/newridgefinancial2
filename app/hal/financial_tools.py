from __future__ import annotations

from datetime import datetime, timezone
import re

from pydantic import BaseModel, Field

from app.config_runtime import get_env_setting
from app.services import build_softdent_snapshot, fetch_quickbooks_sdk_summary, fetch_softdent_dashboard_aggregate, get_quickbooks_sdk_status, get_quickbooks_source_status, get_softdent_data_coverage, get_softdent_source_status, load_softdent_claim_rows, load_softdent_clinical_note_rows, get_softdent_claim_source_status, get_softdent_clinical_note_source_status

from .sanitization import sanitize_hal_text


QUICKBOOKS_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "revenue": ("quickbooks", "revenue", "income", "deposit", "sales"),
    "expenses": ("quickbooks", "expense", "expenses", "cost", "vendor"),
    "ar": ("quickbooks", "a/r", "accounts receivable", "receivable", "invoice"),
}

QUICKBOOKS_INFERRED_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "revenue": ("revenue", "income", "sales", "deposit", "deposits", "profit and loss", "p&l", "income statement"),
    "expenses": ("expense", "expenses", "cost", "costs", "vendor", "overhead", "profit and loss", "p&l", "income statement"),
    "ar": (
        "a/r",
        "ar",
        "accounts receivable",
        "receivable",
        "receivables",
        "invoice",
        "invoices",
        "outstanding balance",
        "outstanding balances",
        "aging",
    ),
}


def _coerce_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


QUICKBOOKS_DEFAULT_QUERIES: dict[str, tuple[str, ...]] = {
    "revenue": (
        "SELECT TOP 1 TotalIncome, ReportPeriod FROM ProfitAndLossSummary ORDER BY ReportPeriod DESC",
        "SELECT TOP 1 Amount AS TotalIncome, TxnDate AS ReportDate FROM Deposit ORDER BY TxnDate DESC",
    ),
    "expenses": (
        "SELECT TOP 1 TotalExpense, ReportPeriod FROM ProfitAndLossSummary ORDER BY ReportPeriod DESC",
        "SELECT TOP 1 Amount AS TotalExpense, TxnDate AS ReportDate FROM Bill ORDER BY TxnDate DESC",
    ),
    "ar": (
        "SELECT TOP 1 BalanceRemaining AS OutstandingAR, TxnDate AS ReportDate, RefNumber FROM Invoice ORDER BY TxnDate DESC",
        "SELECT TOP 1 OpenBalance AS OutstandingAR, TxnDate AS ReportDate, RefNumber FROM Invoice ORDER BY TxnDate DESC",
    ),
}

PATIENT_NAME_PATTERN = re.compile(r"(?i)\bpatient\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
PATIENT_IDENTIFIER_PATTERN = re.compile(
    r"(?i)\b(?:mrn|account|acct|chart|claim(?:\s*(?:id|number|#))?)\s*[:#-]?\s*([a-z0-9-]+)\b"
)
PATIENT_TOOL_KEYWORDS = (
    "patient",
    "narrative",
    "appeal",
    "medical necessity",
    "prior auth",
    "authorization",
    "claim",
    "claims",
    "clinical note",
    "clinical notes",
    "letter",
)
QUESTION_STOPWORDS = {
    "a",
    "all",
    "an",
    "and",
    "appeal",
    "claim",
    "claims",
    "clinical",
    "for",
    "from",
    "give",
    "hal",
    "insurance",
    "narrative",
    "needs",
    "note",
    "notes",
    "patient",
    "please",
    "show",
    "the",
    "to",
    "with",
}

PATIENT_NAME_CANDIDATE_KEYS = (
    "patientname",
    "patient_name",
    "patient",
    "name",
)

_PATIENT_NAME_REGISTRY: dict[str, object] = {
    "names": set(),
    "updated_at_utc": None,
    "source_row_count": 0,
}

REPORT_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def _with_review_metadata(
    status: dict[str, object],
    *,
    review_flags: tuple[str, ...] | list[str] = (),
    preferred_confidence: str | None = None,
) -> dict[str, object]:
    flags = [str(flag).strip() for flag in review_flags if str(flag).strip()]
    available = bool(status.get("available"))
    health = str(status.get("health") or "warning").lower()

    if preferred_confidence:
        confidence_label = preferred_confidence
    elif available and health == "ok":
        confidence_label = "high confidence"
    elif available or health == "warning":
        confidence_label = "review suggested"
    else:
        confidence_label = "manual review"

    if not available and "source export missing" not in flags:
        flags.append("source export missing")
    if health == "degraded" and "source health degraded" not in flags:
        flags.append("source health degraded")
    if health == "warning" and not available and "manual review required" not in flags:
        flags.append("manual review required")

    status["confidence_label"] = confidence_label
    status["review_required"] = confidence_label != "high confidence"
    status["review_flags"] = flags
    return status


class ReportPeriod(BaseModel):
    start_date: str = Field(..., pattern=REPORT_DATE_PATTERN, description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., pattern=REPORT_DATE_PATTERN, description="End date in YYYY-MM-DD format")


class NormalizedReportOutput(BaseModel):
    source_backend: str = Field(..., description="sdk, env, unknown, unavailable, or empty")
    period: dict[str, str]
    rows: list[dict[str, object]] = Field(default_factory=list)
    summary_fields: dict[str, object] = Field(default_factory=dict)
    health: dict[str, object] = Field(default_factory=dict)


def build_financial_snapshot_documents() -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    softdent_snapshot = build_softdent_snapshot()
    if bool(softdent_snapshot.get("available")):
        totals = softdent_snapshot.get("totals") if isinstance(softdent_snapshot.get("totals"), dict) else {}
        production_total = _coerce_float(totals.get("production"))
        collections_total = _coerce_float(totals.get("collections"))
        insurance_total = _coerce_float(totals.get("insurance"))
        patient_total = _coerce_float(totals.get("patient"))
        collection_ratio = round((collections_total / production_total), 4) if production_total else 0.0
        insurance_mix = round((insurance_total / collections_total), 4) if collections_total else 0.0
        patient_mix = round((patient_total / collections_total), 4) if collections_total else 0.0
        providers = [provider for provider in list(softdent_snapshot.get("providers") or []) if isinstance(provider, dict)]
        provider_lines = [
            f"{str(provider.get('provider') or 'Unknown')}: production {_coerce_float(provider.get('production'))}, collections {_coerce_float(provider.get('collections'))}, insurance {_coerce_float(provider.get('insurance'))}, patient {_coerce_float(provider.get('patient'))}"
            for provider in providers
        ]
        period = str(softdent_snapshot.get("period") or "")
        content = (
            f"SoftDent financial snapshot for period {period}. "
            f"Total production {production_total}. "
            f"Total collections {collections_total}. "
            f"Total insurance {insurance_total}. "
            f"Total patient {patient_total}. "
            f"Collection ratio {collection_ratio}. Insurance mix {insurance_mix}. Patient mix {patient_mix}. "
            + " ".join(provider_lines)
            + " HAL may use this aggregated SoftDent summary for financial context only."
        )
        sanitized = sanitize_hal_text(content)
        documents.append(
            {
                "source_id": "softdent-financial-snapshot",
                "title": "SoftDent financial snapshot",
                "category": "softdent",
                "sanitized_content": str(sanitized["sanitized_text"]),
            }
        )

        if providers:
            ranked_providers = sorted(
                providers,
                key=lambda provider: _coerce_float(provider.get("production")),
                reverse=True,
            )
            ranking_lines = [
                f"Rank {index}: {str(provider.get('provider') or 'Unknown')} production {_coerce_float(provider.get('production'))} collections {_coerce_float(provider.get('collections'))}"
                for index, provider in enumerate(ranked_providers, start=1)
            ]
            ranking_doc = sanitize_hal_text(
                "SoftDent provider ranking summary. " + " ".join(ranking_lines) + " Use for provider-level aggregate production comparisons only."
            )
            documents.append(
                {
                    "source_id": "softdent-provider-ranking",
                    "title": "SoftDent provider ranking",
                    "category": "softdent",
                    "sanitized_content": str(ranking_doc["sanitized_text"]),
                }
            )

        mix_doc = sanitize_hal_text(
            f"SoftDent payer mix summary for period {period}. Insurance collections share {insurance_mix}. Patient collections share {patient_mix}."
        )
        documents.append(
            {
                "source_id": "softdent-payer-mix",
                "title": "SoftDent payer mix summary",
                "category": "softdent",
                "sanitized_content": str(mix_doc["sanitized_text"]),
            }
        )

    approved_topics = ", ".join(QUICKBOOKS_TOPIC_KEYWORDS)
    capability_text = (
        "QuickBooks controlled summary tool is restricted to approved read-only topics only. "
        f"Approved topics: {approved_topics}. "
        "HAL uses the QuickBooks Desktop SDK read-only summary surface for those topics and does not fall back to legacy QODBC summary templates. "
        "Balance sheet reporting remains unavailable until a verified SDK-backed surface exists. "
        "HAL cannot run arbitrary SQL."
    )
    sanitized_capability = sanitize_hal_text(capability_text)
    documents.append(
        {
            "source_id": "quickbooks-tool-policy",
            "title": "QuickBooks controlled summary policy",
            "category": "quickbooks",
            "sanitized_content": str(sanitized_capability["sanitized_text"]),
        }
    )
    return documents


def get_live_financial_context(question: str) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    lowered = question.lower()

    wants_claims = any(keyword in lowered for keyword in ("claim", "claims", "denial", "denied", "appeal", "aging", "payer response", "insurance claim"))
    wants_clinical_notes = any(keyword in lowered for keyword in ("clinical note", "clinical notes", "progress note", "soap", "chart note", "treatment note", "doctor note"))

    if wants_claims:
        snippets.append(run_softdent_claims_tool(question))

    if wants_clinical_notes:
        snippets.append(run_softdent_clinical_notes_tool(question))

    quickbooks_topic = detect_quickbooks_topic(question)
    if quickbooks_topic:
        snippets.append(run_quickbooks_summary_tool(quickbooks_topic))

    return snippets


def get_controlled_patient_context(question: str) -> dict[str, object]:
    lowered = question.lower()
    if not any(keyword in lowered for keyword in PATIENT_TOOL_KEYWORDS):
        return {"matched": False, "snippets": [], "narrative": "", "summary_fields": {}}

    claim_rows = load_softdent_claim_rows()
    note_rows = load_softdent_clinical_note_rows()
    known_patient_names = _refresh_patient_name_registry(claim_rows=claim_rows, note_rows=note_rows)

    signals = _extract_patient_query_signals(question, known_patient_names=known_patient_names)
    if not signals["exact_terms"] and not signals["meaningful_tokens"]:
        return {"matched": False, "snippets": [], "narrative": "", "summary_fields": {}}

    matched_claims = _find_matching_rows(claim_rows, signals)
    matched_notes = _find_matching_rows(note_rows, signals)

    if not matched_claims and not matched_notes:
        return {"matched": False, "snippets": [], "narrative": "", "summary_fields": {}}

    snippets: list[dict[str, str]] = []
    if matched_claims:
        snippets.append(
            _make_snippet(
                "softdent-patient-claims-dossier",
                "SoftDent patient claims dossier",
                "softdent_tool",
                _build_patient_row_excerpt(rows=matched_claims, label="claims dossier"),
            )
        )
    if matched_notes:
        snippets.append(
            _make_snippet(
                "softdent-patient-clinical-dossier",
                "SoftDent patient clinical dossier",
                "softdent_tool",
                _build_patient_row_excerpt(rows=matched_notes, label="clinical dossier"),
            )
        )

    narrative = _build_insurance_narrative(
        question=question,
        matched_claims=matched_claims,
        matched_notes=matched_notes,
        signals=signals,
    )
    snippets.append(
        _make_snippet(
            "softdent-insurance-narrative-support",
            "SoftDent insurance narrative support",
            "softdent_tool",
            narrative,
        )
    )
    patient_name = _pick_first_field_value(matched_claims + matched_notes, ("patientname", "patient_name", "patient", "name"))
    primary_status = _pick_first_field_value(matched_claims, ("claimstatus", "status"))
    total_claim_amount = round(sum(_coerce_numeric(row.get("ClaimAmount") or row.get("amount") or row.get("balance")) for row in matched_claims), 2)
    summary_fields = {
        "patient_name": patient_name,
        "claim_count": len(matched_claims),
        "note_count": len(matched_notes),
        "total_claim_amount": total_claim_amount,
        "primary_claim_status": primary_status,
    }
    return {"matched": True, "snippets": snippets, "narrative": narrative, "summary_fields": summary_fields}


def detect_quickbooks_topic(question: str) -> str | None:
    lowered = question.lower()

    # Direct vendor mention keeps routing explicit.
    if "quickbooks" in lowered:
        for topic, keywords in QUICKBOOKS_TOPIC_KEYWORDS.items():
            if any(_contains_keyword(lowered, keyword) for keyword in keywords[1:]):
                return topic

    # Fallback inference supports natural accounting phrasing even without vendor name.
    for topic in ("ar", "revenue", "expenses"):
        inferred_keywords = QUICKBOOKS_INFERRED_TOPIC_KEYWORDS[topic]
        if any(_contains_keyword(lowered, keyword) for keyword in inferred_keywords):
            return topic
    return None


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized_keyword = keyword.strip().lower()
    if not normalized_keyword:
        return False
    if " " in normalized_keyword or "/" in normalized_keyword:
        return normalized_keyword in text
    return re.search(rf"\b{re.escape(normalized_keyword)}\b", text) is not None


def get_quickbooks_topic_query(topic: str) -> str:
    env_name = f"HAL_QB_{topic.upper()}_SQL"
    return get_env_setting(env_name, "").strip()


def get_quickbooks_topic_status() -> list[dict[str, object]]:
    sdk_status = get_quickbooks_sdk_status()
    sdk_available = bool(sdk_status.get("com_available"))
    sdk_company_file_exists = bool(sdk_status.get("company_file_exists"))
    sdk_company_file = str(sdk_status.get("company_file") or "")
    sdk_ready = sdk_available and sdk_company_file_exists
    statuses: list[dict[str, object]] = []
    for topic in QUICKBOOKS_TOPIC_KEYWORDS:
        statuses.append(
            {
                "topic": topic,
                "configured": False,
                "query_source": "sdk" if sdk_ready else "sdk-only",
                "fallback_count": 0,
                "sdk_available": sdk_available,
                "sdk_company_file": sdk_company_file,
            }
        )
    return statuses


def build_quickbooks_profit_loss_queries(period: ReportPeriod) -> dict[str, tuple[str, ...]]:
    _validate_report_period(period)
    return {
        "revenue": QUICKBOOKS_DEFAULT_QUERIES["revenue"],
        "expenses": QUICKBOOKS_DEFAULT_QUERIES["expenses"],
    }


def build_quickbooks_balance_sheet_query(period: ReportPeriod) -> str:
    _validate_report_period(period)
    return get_quickbooks_topic_query("balance_sheet")


def build_quickbooks_ar_aging_queries(period: ReportPeriod) -> tuple[str, ...]:
    _validate_report_period(period)
    return QUICKBOOKS_DEFAULT_QUERIES["ar"]


def get_profit_loss_report(period: ReportPeriod) -> dict[str, object]:
    validated_period = _validate_report_period(period)
    period_dict = _period_payload(validated_period)

    revenue_result = _fetch_quickbooks_topic_rows("revenue", period_dict=period_dict)
    expense_result = _fetch_quickbooks_topic_rows("expenses", period_dict=period_dict)

    period_bound = str(revenue_result["source_backend"]) == "sdk" and str(expense_result["source_backend"]) == "sdk"
    warning = (
        "Period-bounded QuickBooks SDK report rows were returned for the requested profit-and-loss window."
        if period_bound
        else "Verified QuickBooks SDK profit-and-loss rows were partial or unavailable for the requested window."
    )

    normalized_rows = _normalize_profit_loss_rows(revenue_result["rows"], expense_result["rows"])
    if normalized_rows:
        total_revenue = sum(_coerce_numeric(row.get("Amount")) for row in normalized_rows if row.get("AccountType") == "Income")
        total_expense = sum(_coerce_numeric(row.get("Amount")) for row in normalized_rows if row.get("AccountType") == "Expense")
        return NormalizedReportOutput(
            source_backend=_combine_source_backends((str(revenue_result["source_backend"]), str(expense_result["source_backend"]))),
            period=_period_payload(validated_period),
            rows=normalized_rows,
            summary_fields={
                "total_revenue": total_revenue,
                "total_expense": total_expense,
                "net_income": total_revenue - total_expense,
            },
            health={
                "data_complete": bool(revenue_result["rows"]) and bool(expense_result["rows"]),
                "period_bound": period_bound,
                "warning": warning,
                "error": _combine_errors((revenue_result["error"], expense_result["error"])),
            },
        ).model_dump()

    return NormalizedReportOutput(
        source_backend="empty",
        period=_period_payload(validated_period),
        rows=[],
        summary_fields={},
        health={
            "data_complete": False,
            "period_bound": period_bound,
            "warning": "No verified SDK profit-and-loss rows were returned for the requested QuickBooks period.",
            "error": _combine_errors((revenue_result["error"], expense_result["error"])),
        },
    ).model_dump()


def get_balance_sheet_report(period: ReportPeriod) -> dict[str, object]:
    validated_period = _validate_report_period(period)
    configured_query = build_quickbooks_balance_sheet_query(validated_period)
    error_message = (
        "No approved balance sheet query is configured."
        if not configured_query
        else "Balance sheet reports require a verified SDK-backed implementation before they can be used in production."
    )
    return NormalizedReportOutput(
        source_backend="empty",
        period=_period_payload(validated_period),
        rows=[],
        summary_fields={},
        health={
            "data_complete": False,
            "period_bound": False,
            "warning": "No verified QuickBooks balance-sheet SDK surface is available in this repo yet.",
            "error": error_message,
        },
    ).model_dump()


def get_ar_aging_report(period: ReportPeriod) -> dict[str, object]:
    validated_period = _validate_report_period(period)
    result = _fetch_quickbooks_topic_rows("ar", period_dict=_period_payload(validated_period))
    normalized_rows = _normalize_ar_rows(result["rows"])
    source_backend = str(result["source_backend"])
    period_bound = source_backend == "sdk"
    if normalized_rows:
        total_outstanding = sum(_coerce_numeric(row.get("OutstandingAR")) for row in normalized_rows)
        warning = (
            "QuickBooks SDK A/R aging summary rows are sourced from the verified period-bounded ARAgingSummary report surface."
            if period_bound
            else "Approved accounts-receivable sources currently expose the latest available invoice summary rows, not a true aging bucket report."
        )
        return NormalizedReportOutput(
            source_backend=source_backend,
            period=_period_payload(validated_period),
            rows=normalized_rows,
            summary_fields={"total_outstanding_ar": total_outstanding},
            health={
                "data_complete": True,
                "period_bound": period_bound,
                "warning": warning,
                "error": result["error"],
            },
        ).model_dump()

    return NormalizedReportOutput(
        source_backend="empty",
        period=_period_payload(validated_period),
        rows=[],
        summary_fields={},
        health={
            "data_complete": False,
            "period_bound": period_bound,
            "warning": "No verified SDK accounts-receivable rows were returned for the requested QuickBooks period.",
            "error": result["error"],
        },
    ).model_dump()


def get_financial_source_status() -> dict[str, object]:
    softdent_snapshot = build_softdent_snapshot()
    softdent_available = bool(softdent_snapshot.get("available"))
    softdent_period = str(softdent_snapshot.get("period") or "")
    softdent_provider_count = int(softdent_snapshot.get("provider_count") or 0)
    return {
        "softdent": {
            "available": softdent_available,
            "period": softdent_period,
            "provider_count": softdent_provider_count,
            "coverage": get_softdent_data_coverage(),
            "live_snapshot": get_softdent_live_status(),
            "live_provider_ranking": get_softdent_provider_ranking_status(),
            "live_payer_mix": get_softdent_payer_mix_status(),
            "live_collection_delta": get_softdent_collection_delta_status(),
            "live_claims": get_softdent_claims_status(),
            "live_clinical_notes": get_softdent_clinical_notes_status(),
        },
        "quickbooks": {
            "sdk": get_quickbooks_sdk_status(),
            "topics": get_quickbooks_topic_status(),
            "live_revenue": get_quickbooks_live_status("revenue"),
            "live_expenses": get_quickbooks_live_status("expenses"),
            "live_ar": get_quickbooks_live_status("ar"),
        },
    }


def get_softdent_live_status() -> dict[str, object]:
    snapshot = build_softdent_snapshot()
    source_status = get_softdent_source_status()
    checked_at_utc = datetime.now(timezone.utc).isoformat()
    source_available = bool(source_status.get("available"))
    source_backend = str(source_status.get("source_backend") or "missing")
    source_file = str(source_status.get("source_file") or "")
    modified_at_utc = str(source_status.get("modified_at_utc") or "")

    if not bool(snapshot.get("available")):
        return _with_review_metadata({
            "available": False,
            "health": "warning" if source_available else "degraded",
            "source_backend": source_backend,
            "source_file": source_file,
            "modified_at_utc": modified_at_utc,
            "excerpt": "SoftDent live snapshot is not available from the approved local export files.",
            "checked_at_utc": checked_at_utc,
        }, review_flags=["live snapshot missing"])

    totals = snapshot.get("totals") if isinstance(snapshot.get("totals"), dict) else {}
    production_total = _coerce_float(totals.get("production"))
    collections_total = _coerce_float(totals.get("collections"))
    insurance_total = _coerce_float(totals.get("insurance"))
    patient_total = _coerce_float(totals.get("patient"))
    collection_ratio = round((collections_total / production_total), 4) if production_total else 0.0
    period = str(snapshot.get("period") or "current period")
    excerpt = (
        f"SoftDent live snapshot for {period} from {source_backend} source {source_file or 'unknown file'}: "
        f"production {production_total}, collections {collections_total}, insurance {insurance_total}, patient {patient_total}, collection ratio {collection_ratio}."
    )
    return _with_review_metadata({
        "available": True,
        "health": "ok",
        "source_backend": source_backend,
        "source_file": source_file,
        "modified_at_utc": modified_at_utc,
        "excerpt": sanitize_hal_text(excerpt)["sanitized_text"],
        "checked_at_utc": checked_at_utc,
    }, review_flags=[])


def get_softdent_provider_ranking_status() -> dict[str, object]:
    snapshot = fetch_softdent_dashboard_aggregate()
    source_status = get_softdent_source_status()
    checked_at_utc = datetime.now(timezone.utc).isoformat()

    raw_provider_rows = snapshot.get("provider_rows") if isinstance(snapshot.get("provider_rows"), list) else []
    provider_rows = [provider for provider in raw_provider_rows if isinstance(provider, dict)]
    if not provider_rows:
        return _make_softdent_unavailable_status(
            source_status=source_status,
            checked_at_utc=checked_at_utc,
            message="SoftDent provider ranking is not available from the approved local export files.",
        )

    ranked_providers = sorted(provider_rows, key=lambda provider: float(provider.get("production_amount") or 0.0), reverse=True)
    ranking_lines = [
        f"Rank {index}: {str(provider.get('provider_name') or 'Unknown')} production {_coerce_float(provider.get('production_amount'))} collections {_coerce_float(provider.get('collection_amount'))}"
        for index, provider in enumerate(ranked_providers[:3], start=1)
    ]
    excerpt = f"SoftDent provider ranking for {_softdent_period_label(snapshot)}: {'; '.join(ranking_lines)}."
    return _make_softdent_status(
        source_status=source_status,
        checked_at_utc=checked_at_utc,
        excerpt=excerpt,
    )


def get_softdent_payer_mix_status() -> dict[str, object]:
    snapshot = fetch_softdent_dashboard_aggregate()
    source_status = get_softdent_source_status()
    checked_at_utc = datetime.now(timezone.utc).isoformat()

    totals = snapshot.get("totals") if isinstance(snapshot.get("totals"), dict) else {}
    provider_rows = snapshot.get("provider_rows") if isinstance(snapshot.get("provider_rows"), list) else []
    if not provider_rows:
        return _make_softdent_unavailable_status(
            source_status=source_status,
            checked_at_utc=checked_at_utc,
            message="SoftDent payer mix is not available from the approved local export files.",
        )

    collections_total = _coerce_float(totals.get("collections"))
    insurance_total = _coerce_float(totals.get("insurance"))
    patient_total = _coerce_float(totals.get("patient"))
    insurance_mix = round((insurance_total / collections_total), 4) if collections_total else 0.0
    patient_mix = round((patient_total / collections_total), 4) if collections_total else 0.0
    excerpt = (
        f"SoftDent payer mix for {_softdent_period_label(snapshot)}: insurance collections share {insurance_mix}, "
        f"direct-pay collections share {patient_mix}, insurance {insurance_total}, direct-pay {patient_total}."
    )
    return _make_softdent_status(
        source_status=source_status,
        checked_at_utc=checked_at_utc,
        excerpt=excerpt,
    )


def get_softdent_collection_delta_status() -> dict[str, object]:
    snapshot = fetch_softdent_dashboard_aggregate()
    source_status = get_softdent_source_status()
    checked_at_utc = datetime.now(timezone.utc).isoformat()

    totals = snapshot.get("totals") if isinstance(snapshot.get("totals"), dict) else {}
    provider_rows = snapshot.get("provider_rows") if isinstance(snapshot.get("provider_rows"), list) else []
    if not provider_rows:
        return _make_softdent_unavailable_status(
            source_status=source_status,
            checked_at_utc=checked_at_utc,
            message="SoftDent collections delta is not available from the approved local export files.",
        )

    production_total = _coerce_float(totals.get("production"))
    collections_total = _coerce_float(totals.get("collections"))
    delta = round(production_total - collections_total, 2)
    collection_ratio = round((collections_total / production_total), 4) if production_total else 0.0
    excerpt = (
        f"SoftDent collections delta for {_softdent_period_label(snapshot)}: production {production_total}, "
        f"collections {collections_total}, delta {delta}, collection ratio {collection_ratio}."
    )
    return _make_softdent_status(
        source_status=source_status,
        checked_at_utc=checked_at_utc,
        excerpt=excerpt,
    )


def _softdent_period_label(snapshot: dict[str, object]) -> str:
    period_start = str(snapshot.get("period_start") or "").strip()
    return period_start[:7] if len(period_start) >= 7 else "current period"


def _make_softdent_status(*, source_status: dict[str, object], checked_at_utc: str, excerpt: str) -> dict[str, object]:
    source_backend = str(source_status.get("source_backend") or "missing")
    source_file = str(source_status.get("source_file") or "")
    modified_at_utc = str(source_status.get("modified_at_utc") or "")
    return _with_review_metadata({
        "available": True,
        "health": "ok",
        "source_backend": source_backend,
        "source_file": source_file,
        "modified_at_utc": modified_at_utc,
        "excerpt": sanitize_hal_text(excerpt)["sanitized_text"],
        "checked_at_utc": checked_at_utc,
    })


def _make_softdent_unavailable_status(*, source_status: dict[str, object], checked_at_utc: str, message: str) -> dict[str, object]:
    source_available = bool(source_status.get("available"))
    source_backend = str(source_status.get("source_backend") or "missing")
    source_file = str(source_status.get("source_file") or "")
    modified_at_utc = str(source_status.get("modified_at_utc") or "")
    return _with_review_metadata({
        "available": False,
        "health": "warning" if source_available else "degraded",
        "source_backend": source_backend,
        "source_file": source_file,
        "modified_at_utc": modified_at_utc,
        "excerpt": message,
        "checked_at_utc": checked_at_utc,
    })


def run_softdent_claims_tool(question: str) -> dict[str, str]:
    rows = load_softdent_claim_rows()
    if not rows:
        source_status = get_softdent_claim_source_status()
        return _make_snippet(
            "softdent-claims-unavailable",
            "SoftDent claims retrieval",
            "softdent_tool",
            _build_missing_source_message(
                label="claims",
                source_status=source_status,
                missing_message="SoftDent claims export is not available in the approved local import set.",
            ),
        )
    return _make_snippet(
        "softdent-claims-summary",
        "SoftDent claims retrieval",
        "softdent_tool",
        _build_softdent_row_excerpt(question=question, rows=rows, label="claims"),
    )


def get_softdent_claims_status() -> dict[str, object]:
    rows = load_softdent_claim_rows()
    source_status = get_softdent_claim_source_status()
    checked_at_utc = datetime.now(timezone.utc).isoformat()

    if not rows:
        return _make_softdent_unavailable_status(
            source_status=source_status,
            checked_at_utc=checked_at_utc,
            message="SoftDent claims export is not available from the approved local export files.",
        )

    excerpt = _build_softdent_export_status_excerpt(rows=rows, label="claims")
    return _make_softdent_status(
        source_status=source_status,
        checked_at_utc=checked_at_utc,
        excerpt=excerpt,
    )


def run_softdent_clinical_notes_tool(question: str) -> dict[str, str]:
    rows = load_softdent_clinical_note_rows()
    if not rows:
        source_status = get_softdent_clinical_note_source_status()
        return _make_snippet(
            "softdent-clinical-notes-unavailable",
            "SoftDent clinical notes retrieval",
            "softdent_tool",
            _build_missing_source_message(
                label="clinical notes",
                source_status=source_status,
                missing_message="SoftDent clinical notes export is not available in the approved local import set.",
            ),
        )
    return _make_snippet(
        "softdent-clinical-notes-summary",
        "SoftDent clinical notes retrieval",
        "softdent_tool",
        _build_softdent_row_excerpt(question=question, rows=rows, label="clinical notes"),
    )


def get_softdent_clinical_notes_status() -> dict[str, object]:
    rows = load_softdent_clinical_note_rows()
    source_status = get_softdent_clinical_note_source_status()
    checked_at_utc = datetime.now(timezone.utc).isoformat()

    if not rows:
        return _make_softdent_unavailable_status(
            source_status=source_status,
            checked_at_utc=checked_at_utc,
            message="SoftDent clinical notes export is not available from the approved local export files.",
        )

    excerpt = _build_softdent_export_status_excerpt(rows=rows, label="clinical notes")
    return _make_softdent_status(
        source_status=source_status,
        checked_at_utc=checked_at_utc,
        excerpt=excerpt,
    )


def _build_softdent_row_excerpt(*, question: str, rows: list[dict], label: str) -> str:
    query_tokens = _tokenize(question)
    scored_rows = []
    for row in rows:
        row_text = _row_to_text(row)
        row_tokens = _tokenize(row_text)
        score = len(query_tokens & row_tokens)
        scored_rows.append((score, row))
    scored_rows.sort(key=lambda item: item[0], reverse=True)
    top_rows = [row for score, row in scored_rows if score > 0][:3]
    if not top_rows:
        top_rows = [row for _, row in scored_rows[:2]]

    row_summaries = []
    for row in top_rows:
        fields = []
        for key, value in list(row.items())[:6]:
            if value in (None, ""):
                continue
            fields.append(f"{key}={value}")
        if fields:
            row_summaries.append("; ".join(fields))
    if not row_summaries:
        return f"SoftDent {label} export is available but did not contain readable rows for this query."
    return f"SoftDent {label} matches from approved local export: {' | '.join(row_summaries)}"


def _build_missing_source_message(*, label: str, source_status: dict[str, object], missing_message: str) -> str:
    if bool(source_status.get("available")):
        return (
            f"SoftDent {label} export exists in {str(source_status.get('source_backend') or 'missing')} source {str(source_status.get('source_file') or 'unknown file')} "
            "but no readable rows were available."
        )
    return missing_message


def _build_softdent_export_status_excerpt(*, rows: list[dict], label: str) -> str:
    sample = rows[0] if rows else {}
    sample_fields = []
    for key, value in list(sample.items())[:4]:
        if value in (None, ""):
            continue
        sample_fields.append(f"{key}={value}")
    field_summary = "; ".join(sample_fields) if sample_fields else "no sample fields"
    return f"SoftDent {label} export is available with {len(rows)} row(s). Sample fields: {field_summary}."


def _row_to_text(row: dict) -> str:
    return " ".join(f"{key} {value}" for key, value in row.items() if value not in (None, ""))


def _tokenize(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", text.lower()) if token}


def _normalize_patient_name_for_matching(raw_value: object) -> str:
    value = str(raw_value or "").strip().lower()
    if not value:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", " ", value).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if len(normalized) < 3:
        return ""
    if not re.search(r"[a-z]", normalized):
        return ""
    return normalized


def _extract_patient_name_from_row(row: dict) -> str:
    for key, value in row.items():
        if _normalize_key(str(key)) in {_normalize_key(candidate) for candidate in PATIENT_NAME_CANDIDATE_KEYS}:
            normalized = _normalize_patient_name_for_matching(value)
            if normalized:
                return normalized
    return ""


def _refresh_patient_name_registry(*, claim_rows: list[dict], note_rows: list[dict]) -> set[str]:
    names: set[str] = set()
    for row in [*claim_rows, *note_rows]:
        extracted = _extract_patient_name_from_row(row)
        if extracted:
            names.add(extracted)

    _PATIENT_NAME_REGISTRY["names"] = names
    _PATIENT_NAME_REGISTRY["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _PATIENT_NAME_REGISTRY["source_row_count"] = len(claim_rows) + len(note_rows)
    return names


def _extract_patient_query_signals(question: str, *, known_patient_names: set[str] | None = None) -> dict[str, object]:
    exact_terms: list[str] = []
    name_match = PATIENT_NAME_PATTERN.search(question)
    if name_match:
        extracted_name = _normalize_patient_name_for_matching(name_match.group(1).strip().lower())
        extracted_name_tokens = [token for token in extracted_name.split() if token not in {"mrn", "account", "acct", "chart", "claim", "id", "number"}]
        extracted_name = " ".join(extracted_name_tokens)
        if extracted_name:
            exact_terms.append(extracted_name)
    exact_terms.extend(match.group(1).strip().lower() for match in PATIENT_IDENTIFIER_PATTERN.finditer(question))

    normalized_question = _normalize_patient_name_for_matching(question)
    padded_question = f" {normalized_question} " if normalized_question else ""
    if padded_question:
        for known_name in sorted((known_patient_names or set()), key=len, reverse=True):
            if f" {known_name} " in padded_question:
                exact_terms.append(known_name)

    deduped_exact_terms: list[str] = []
    seen_terms: set[str] = set()
    for term in exact_terms:
        normalized_term = _normalize_patient_name_for_matching(term)
        if normalized_term and normalized_term not in seen_terms:
            deduped_exact_terms.append(normalized_term)
            seen_terms.add(normalized_term)

    tokens = _tokenize(question)
    meaningful_tokens = {token for token in tokens if token not in QUESTION_STOPWORDS and len(token) >= 3}
    return {
        "exact_terms": deduped_exact_terms,
        "meaningful_tokens": meaningful_tokens,
    }


def _find_matching_rows(rows: list[dict], signals: dict[str, object]) -> list[dict]:
    exact_terms = list(signals.get("exact_terms", []))
    meaningful_tokens = set(signals.get("meaningful_tokens", set()))
    exact_match_rows: list[tuple[int, dict]] = []
    token_match_rows: list[tuple[int, dict]] = []
    for row in rows:
        row_text = _row_to_text(row)
        lowered = row_text.lower()
        row_tokens = _tokenize(lowered)
        exact_score = 0
        for exact_term in exact_terms:
            if exact_term and exact_term in lowered:
                exact_score += 10
        token_score = len(meaningful_tokens & row_tokens)
        total_score = exact_score + token_score
        if total_score <= 0:
            continue
        if exact_score > 0:
            exact_match_rows.append((total_score, row))
        else:
            token_match_rows.append((total_score, row))

    ranked_rows = exact_match_rows if exact_match_rows else token_match_rows
    ranked_rows.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in ranked_rows[:3]]


def _build_patient_row_excerpt(*, rows: list[dict], label: str) -> str:
    summaries = []
    for row in rows[:3]:
        fields = []
        for key, value in list(row.items())[:8]:
            if value in (None, ""):
                continue
            fields.append(f"{key}={value}")
        if fields:
            summaries.append("; ".join(fields))
    if not summaries:
        return f"SoftDent {label} matched rows were found but contained no readable fields."
    return f"SoftDent {label} matched rows: {' | '.join(summaries)}"


def _build_insurance_narrative(*, question: str, matched_claims: list[dict], matched_notes: list[dict], signals: dict[str, object]) -> str:
    patient_name = _pick_first_field_value(matched_claims + matched_notes, ("patientname", "patient_name", "patient", "name"))
    if not patient_name:
        patient_name = next(iter(signals.get("exact_terms", [])), "the patient")
    procedure = _pick_first_field_value(matched_claims + matched_notes, ("procedure", "procdesc", "description", "servicedescription", "treatment"))
    payer = _pick_first_field_value(matched_claims, ("payer", "carrier", "insurance", "insurancename", "plan"))
    claim_status = _pick_first_field_value(matched_claims, ("claimstatus", "status"))
    service_date = _pick_first_field_value(matched_claims + matched_notes, ("servicedate", "dateofservice", "notedate", "date", "dos"))
    denial_reason = _pick_first_field_value(matched_claims, ("denialreason", "reason", "remark", "claimnote", "note"))
    note_points = _collect_field_values(matched_notes, ("clinicalnote", "note", "narrative", "assessment"), limit=2)
    claim_points = _collect_field_values(matched_claims, ("claimamount", "balance", "agingdays", "tooth", "surface", "code"), limit=4)

    sentences = [f"Insurance narrative for {patient_name}."]
    if procedure or service_date:
        procedure_text = procedure or "the documented procedure"
        if service_date:
            sentences.append(f"The claim concerns {procedure_text} performed or documented on {service_date}.")
        else:
            sentences.append(f"The claim concerns {procedure_text}.")
    if claim_status or payer:
        status_text = claim_status or "under review"
        if payer:
            sentences.append(f"The current claim status is {status_text} with payer {payer}.")
        else:
            sentences.append(f"The current claim status is {status_text}.")
    if denial_reason:
        sentences.append(f"Claim-side support details include: {denial_reason}.")
    if note_points:
        sentences.append(f"Clinical documentation notes: {' '.join(note_points)}")
    if claim_points:
        sentences.append(f"Additional claim facts: {', '.join(claim_points)}.")
    sentences.append("This narrative was prepared from local read-only SoftDent claims and clinical-note exports and should be reviewed before submission.")
    return " ".join(sentences)


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", key.lower())


def _pick_first_field_value(rows: list[dict], candidate_keys: tuple[str, ...]) -> str:
    normalized_keys = {_normalize_key(key) for key in candidate_keys}
    for row in rows:
        for key, value in row.items():
            if _normalize_key(str(key)) in normalized_keys and value not in (None, ""):
                return str(value)
    return ""


def _collect_field_values(rows: list[dict], candidate_keys: tuple[str, ...], *, limit: int) -> list[str]:
    normalized_keys = {_normalize_key(key) for key in candidate_keys}
    values: list[str] = []
    for row in rows:
        for key, value in row.items():
            if _normalize_key(str(key)) in normalized_keys and value not in (None, ""):
                values.append(f"{key} {value}")
                if len(values) >= limit:
                    return values
    return values


def get_quickbooks_live_status(topic: str) -> dict[str, object]:
    snippet = run_quickbooks_summary_tool(topic)
    source_status = get_quickbooks_source_status(topic)
    source_id = str(snippet.get("source_id") or f"quickbooks-{topic}-unavailable")
    available = source_id.endswith("-summary")
    excerpt = str(snippet.get("excerpt") or f"QuickBooks {topic} summary is unavailable from the approved local sources.")
    if available:
        if "sdk read-only query" in excerpt:
            source_backend = "sdk"
        elif "env read-only query" in excerpt:
            source_backend = "env"
        elif "fallback read-only query" in excerpt:
            source_backend = "unknown"
        else:
            source_backend = "unknown"
        health = "ok"
    else:
        source_backend = "unavailable"
        health = "degraded" if source_id.endswith(("-sdk-blocked", "-unavailable", "-empty")) else "warning"

    review_flags: list[str] = []
    preferred_confidence: str | None = None
    if available and source_backend != "sdk":
        review_flags.append("using non-sdk read-only source")
        preferred_confidence = "review suggested"
    if not available:
        review_flags.append("live quickbooks summary missing")

    return _with_review_metadata({
        "topic": topic,
        "available": available,
        "health": health,
        "source_backend": source_backend,
        "source_id": source_id,
        "source_file": source_status.get("source_file") or "",
        "modified_at_utc": source_status.get("modified_at_utc") or "",
        "excerpt": excerpt,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }, review_flags=review_flags, preferred_confidence=preferred_confidence)


def run_quickbooks_summary_tool(topic: str) -> dict[str, str]:
    sdk_error: Exception | None = None
    try:
        sdk_rows = fetch_quickbooks_sdk_summary(topic)
        if sdk_rows:
            first_row = sdk_rows[0]
            summary_fields = ", ".join(f"{key}={value}" for key, value in list(first_row.items())[:6])
            return _make_snippet(
                f"quickbooks-{topic}-summary",
                f"QuickBooks {topic} summary",
                "quickbooks_tool",
                f"QuickBooks approved {topic} summary from sdk read-only query: {summary_fields}",
            )

        # A/R can legitimately have no open balances; keep the SDK lane healthy instead of treating empty results as a failure.
        if topic == "ar":
            return _make_snippet(
                "quickbooks-ar-summary",
                "QuickBooks ar summary",
                "quickbooks_tool",
                "QuickBooks approved ar summary from sdk read-only query: no outstanding accounts receivable rows were returned.",
            )
    except Exception as exc:
        sdk_error = exc

    blocked_sdk_error = sdk_error is not None and any(
        marker in str(sdk_error).lower()
        for marker in ("timed out", "blocked by the quickbooks ui")
    )

    if sdk_error is not None:
        return _make_snippet(
            f"quickbooks-{topic}-sdk-blocked",
            f"QuickBooks {topic} summary",
            "quickbooks_tool",
            f"QuickBooks {topic} SDK summary is currently unavailable: {sdk_error}",
        )

    return _make_snippet(
        f"quickbooks-{topic}-empty",
        f"QuickBooks {topic} summary",
        "quickbooks_tool",
        f"QuickBooks approved {topic} summary from sdk read-only query returned no rows.",
    )


def _validate_report_period(period: ReportPeriod) -> ReportPeriod:
    start = datetime.strptime(period.start_date, "%Y-%m-%d")
    end = datetime.strptime(period.end_date, "%Y-%m-%d")
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    return period


def _period_payload(period: ReportPeriod) -> dict[str, str]:
    return {
        "start_date": period.start_date,
        "end_date": period.end_date,
    }


def _fetch_quickbooks_topic_rows(
    topic: str,
    *,
    allow_sdk: bool = True,
    period_dict: dict[str, str] | None = None,
) -> dict[str, object]:
    sdk_error: Exception | None = None
    if allow_sdk:
        try:
            sdk_rows = fetch_quickbooks_sdk_summary(topic, period_dict=period_dict)
            if sdk_rows:
                return {"source_backend": "sdk", "rows": sdk_rows, "error": None}

            # A/R SDK report can be empty when there are no open receivables.
            if topic == "ar":
                return {"source_backend": "sdk", "rows": [], "error": None}
        except Exception as exc:
            sdk_error = exc

    return {
        "source_backend": "empty",
        "rows": [],
        "error": _error_text(sdk_error),
    }


def _normalize_profit_loss_rows(revenue_rows: list[dict], expense_rows: list[dict]) -> list[dict[str, object]]:
    normalized_rows: list[dict[str, object]] = []
    for row in revenue_rows:
        normalized_rows.append(
            {
                "AccountType": "Income",
                "Amount": _coerce_numeric(row.get("TotalIncome") or row.get("Amount")),
                "ReportPeriod": str(row.get("ReportPeriod") or row.get("ReportDate") or row.get("TxnDate") or ""),
                "SourceTopic": "revenue",
            }
        )
    for row in expense_rows:
        normalized_rows.append(
            {
                "AccountType": "Expense",
                "Amount": _coerce_numeric(row.get("TotalExpense") or row.get("Amount")),
                "ReportPeriod": str(row.get("ReportPeriod") or row.get("ReportDate") or row.get("TxnDate") or ""),
                "SourceTopic": "expenses",
            }
        )
    return normalized_rows


def _normalize_ar_rows(rows: list[dict]) -> list[dict[str, object]]:
    normalized_rows: list[dict[str, object]] = []
    for row in rows:
        normalized_rows.append(
            {
                "CustomerRef": str(row.get("CustomerRef") or row.get("CustomerName") or ""),
                "OutstandingAR": _coerce_numeric(row.get("OutstandingAR") or row.get("BalanceRemaining") or row.get("OpenBalance")),
                "ReportDate": str(row.get("ReportDate") or row.get("TxnDate") or ""),
                "RefNumber": str(row.get("RefNumber") or ""),
            }
        )
    return normalized_rows


def _coerce_numeric(value: object) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _combine_source_backends(source_backends: tuple[str, ...]) -> str:
    unique = {backend for backend in source_backends if backend and backend != "empty"}
    if not unique:
        return "empty"
    if unique <= {"env", "fallback"}:
        return "env" if "env" in unique else "fallback"
    if len(unique) == 1:
        return unique.pop()
    return "mixed"


def _error_text(error: Exception | None) -> str | None:
    if error is None:
        return None
    return str(error)


def _combine_errors(errors: tuple[str | None, ...]) -> str | None:
    messages = [message for message in errors if message]
    if not messages:
        return None
    return " | ".join(messages)


def _make_snippet(source_id: str, title: str, category: str, content: str) -> dict[str, str]:
    sanitized = sanitize_hal_text(content)
    return {
        "source_id": source_id,
        "title": title,
        "category": category,
        "excerpt": str(sanitized["sanitized_text"]),
    }