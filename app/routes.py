from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
import io
import json
import logging
import os
import secrets
from typing import Mapping, Optional
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, ValidationError
from .auth import (
    APP_SESSION_COOKIE_NAME,
    AuthenticatedUser,
    authenticate,
    authenticate_credentials,
    build_auth_session_cookie_options,
    clear_auth_session_cookie,
    create_auth_session_token,
    require_roles,
)
from .data_pipeline import get_pull_status_payload, import_uploaded_file
from .services import fetch_quickbooks_data
from .hal import advance_hal_autonomy_run, answer_accounting_policy_question, answer_hal_question, answer_hal_second_opinion_question, answer_insurance_narrative_request, answer_patient_dossier_request, approve_hal_chart_plan, create_hal_autonomy_run, create_hal_chart_plan, draft_accounting_journal_entry, get_accounting_posting_queue_summary, get_hal_access_policy, get_hal_autonomy_profile, get_hal_autonomy_run_status, get_hal_index_status, get_hal_phases, get_hal_shell_commands, list_accounting_posting_queue, list_hal_audit_events, list_hal_autonomy_runs, list_hal_chart_plans, list_recent_accounting_posting_queue_activity, queue_accounting_posting_draft, refresh_local_hal_index, review_accounting_posting_queue_entry
from .hal import answer_document_rag_question, ingest_document_rag_upload, list_document_rag_documents
from .hal.orchestrator import get_hal_operating_picture
from .hal.financial_tools import get_financial_source_status
from .hal.widget_feed import get_widget_feed, record_widget_feed
from .hal.safety import append_ai_activity_log, create_ai_workspace_handle, ensure_within_ai_workspace, resolve_ai_workspace_handle
from .hal.posting_queue import PostingQueueStatus

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_IMPORT_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_RAG_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_WIDGET_UPDATE_BYTES = 512 * 1024
LOCAL_WIDGET_UPDATE_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
LOCAL_WIDGET_UPDATE_ENVIRONMENTS = {"development", "dev", "test", "testing", "local"}
PRODUCTION_WIDGET_UPDATE_ENVIRONMENTS = {"production", "prod", "staging"}


class QuickBooksDiagnosticRequest(BaseModel):
    sql: str


class AuthSessionResponse(BaseModel):
    username: str
    display_name: str
    roles: list[str]


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthLogoutResponse(BaseModel):
    message: str


async def _read_upload_with_limit(file: UploadFile, *, limit_bytes: int = MAX_IMPORT_UPLOAD_BYTES) -> bytes:
    content = await file.read(limit_bytes + 1)
    if len(content) > limit_bytes:
        raise HTTPException(status_code=413, detail=f"Uploaded file exceeds {limit_bytes} byte limit")
    return content


def _build_redacted_hal_http_exception(*, operation: str, actor: str, exc: Exception) -> HTTPException:
    error_id = f"hal-{uuid4().hex[:12]}"
    logger.exception("%s failed for actor %s [error_id=%s]", operation, actor, error_id)
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action=f"{operation}-error",
        detail=f"{operation} failed. Review server logs with error_id={error_id}.",
    )
    return HTTPException(status_code=503, detail=f"{operation.replace('-', ' ').capitalize()} failed. Reference ID: {error_id}")


def _raise_not_implemented_surface(surface_name: str) -> None:
    raise HTTPException(status_code=501, detail=f"{surface_name} is not implemented in this service.")


def _quickbooks_odbc_unavailable_response() -> HTTPException:
    return HTTPException(status_code=503, detail="QuickBooks ODBC diagnostic is unavailable.")


def _quickbooks_odbc_unavailable_csv_response() -> StreamingResponse:
    return StreamingResponse(
        io.StringIO("Error: QuickBooks ODBC diagnostic is unavailable.\n"),
        status_code=503,
        media_type="text/csv",
    )


def _widget_update_api_key_header_name() -> str:
    header_name = str(os.getenv("WIDGET_API_KEY_HEADER") or "X-API-Key").strip()
    return header_name or "X-API-Key"


def _widget_update_allows_local_fallback(request: Request) -> bool:
    environment = str(os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()
    if environment in PRODUCTION_WIDGET_UPDATE_ENVIRONMENTS:
        return False
    if environment in LOCAL_WIDGET_UPDATE_ENVIRONMENTS:
        return True
    client_host = request.client.host if request.client is not None else ""
    return client_host == "testclient"


def _authorize_widget_update_request(request: Request) -> str:
    expected_api_key = str(os.getenv("WIDGET_API_KEY") or "").strip()
    header_name = _widget_update_api_key_header_name()
    if expected_api_key:
        provided_api_key = str(request.headers.get(header_name) or "").strip()
        if not provided_api_key or not secrets.compare_digest(provided_api_key, expected_api_key):
            raise HTTPException(status_code=401, detail=f"Missing or invalid {header_name} for widget updates")
        return "api-key"

    if not _widget_update_allows_local_fallback(request):
        raise HTTPException(
            status_code=403,
            detail="Widget updates require WIDGET_API_KEY in this environment",
        )

    client_host = request.client.host if request.client is not None else ""
    if client_host in LOCAL_WIDGET_UPDATE_HOSTS:
        return "local"

    raise HTTPException(
        status_code=403,
        detail="Widget update route only accepts local requests unless WIDGET_API_KEY is configured",
    )


def _serialize_chart_artifact_handle(value: object) -> object:
    if isinstance(value, str) and value.strip():
        return create_ai_workspace_handle(value)
    return value


def _serialize_public_hal_access_policy(access_policy: object) -> object:
    if not isinstance(access_policy, dict):
        return access_policy
    serialized = dict(access_policy)
    serialized["workspace_root"] = ""
    serialized["activity_log_path"] = ""
    serialized["review_plan_directory"] = ""
    return serialized


def _serialize_public_hal_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    if "access_policy" in serialized:
        serialized["access_policy"] = _serialize_public_hal_access_policy(serialized.get("access_policy"))
    return serialized


def _serialize_chart_plan_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = _serialize_public_hal_payload(payload)
    for field_name in ("request_file_path", "planned_output_path", "review_plan_path", "rendered_output_path"):
        if field_name in serialized:
            serialized[field_name] = _serialize_chart_artifact_handle(serialized.get(field_name))
    return serialized


def _serialize_chart_plan_list_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    serialized["items"] = [
        _serialize_chart_plan_payload(item)
        for item in raw_items
        if isinstance(item, dict)
    ]
    return serialized


def _serialize_local_accounting_document_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    serialized["source_path"] = ""
    return serialized


def _serialize_local_accounting_document_list_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    serialized["items"] = [
        _serialize_local_accounting_document_payload(item)
        for item in raw_items
        if isinstance(item, dict)
    ]
    return serialized


def _build_auth_session_response(user: AuthenticatedUser) -> AuthSessionResponse:
    return AuthSessionResponse(
        username=user.username,
        display_name=user.display_name,
        roles=sorted(user.roles),
    )


def _serialize_document_rag_document_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    serialized["stored_path"] = ""
    return serialized


def _serialize_document_rag_document_list_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    serialized["items"] = [
        _serialize_document_rag_document_payload(item)
        for item in raw_items
        if isinstance(item, dict)
    ]
    return serialized


def _serialize_document_rag_upload_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    document_payload = payload.get("document")
    if isinstance(document_payload, dict):
        serialized["document"] = _serialize_document_rag_document_payload(document_payload)
    return serialized


def _serialize_journal_draft_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = _serialize_public_hal_payload(payload)
    serialized["review_plan_path"] = None
    return serialized


def _serialize_posting_queue_entry_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    serialized["review_plan_path"] = None
    return serialized


def _serialize_posting_queue_list_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    serialized["items"] = [
        _serialize_posting_queue_entry_payload(item)
        for item in raw_items
        if isinstance(item, dict)
    ]
    return serialized


def _run_quickbooks_odbc_query(sql: str) -> list[dict[str, object]]:
    return fetch_quickbooks_data(validate_quickbooks_diagnostic_sql(sql))


def _render_quickbooks_odbc_csv(results: list[dict[str, object]]) -> StreamingResponse:
    if not results:
        return StreamingResponse(io.StringIO("No data found\n"), media_type="text/csv")
    output = io.StringIO()
    import csv
    writer = csv.DictWriter(output, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=quickbooks_export.csv"})

# CSV export for QuickBooks ODBC
@router.get("/api/quickbooks/odbc/csv", tags=["QuickBooks"], include_in_schema=False)
@router.get("/quickbooks/odbc/csv", tags=["QuickBooks"])
def get_quickbooks_odbc_csv(
    sql: str = Query(..., description="SQL query to run against QuickBooks via QODBC"),
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """
    Run a SQL query against QuickBooks via QODBC and return the results as CSV.
    """
    del user
    try:
        results = _run_quickbooks_odbc_query(sql)
        return _render_quickbooks_odbc_csv(results)
    except ValueError as exc:
        return StreamingResponse(io.StringIO(f"Error: {str(exc)}\n"), status_code=400, media_type="text/csv")
    except Exception as e:
        logger.exception("QuickBooks ODBC CSV diagnostic failed")
        return _quickbooks_odbc_unavailable_csv_response()


@router.post("/api/quickbooks/odbc/csv", tags=["QuickBooks"], include_in_schema=False)
@router.post("/quickbooks/odbc/csv", tags=["QuickBooks"])
def post_quickbooks_odbc_csv(
    payload: QuickBooksDiagnosticRequest = Body(...),
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    del user
    try:
        results = _run_quickbooks_odbc_query(payload.sql)
        return _render_quickbooks_odbc_csv(results)
    except ValueError as exc:
        return StreamingResponse(io.StringIO(f"Error: {str(exc)}\n"), status_code=400, media_type="text/csv")
    except Exception as e:
        logger.exception("QuickBooks ODBC CSV diagnostic failed")
        return _quickbooks_odbc_unavailable_csv_response()

@router.get("/api/quickbooks/odbc", tags=["QuickBooks"], include_in_schema=False)
@router.get("/quickbooks/odbc", tags=["QuickBooks"])
def get_quickbooks_odbc(
    sql: str = Query(..., description="SQL query to run against QuickBooks via QODBC"),
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """
    Run a SQL query against QuickBooks via QODBC and return the results.
    """
    del user
    try:
        results = _run_quickbooks_odbc_query(sql)
        return {"results": results}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        logger.exception("QuickBooks ODBC diagnostic failed")
        raise _quickbooks_odbc_unavailable_response() from e


@router.post("/api/quickbooks/odbc", tags=["QuickBooks"], include_in_schema=False)
@router.post("/quickbooks/odbc", tags=["QuickBooks"])
def post_quickbooks_odbc(
    payload: QuickBooksDiagnosticRequest = Body(...),
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    del user
    try:
        results = _run_quickbooks_odbc_query(payload.sql)
        return {"results": results}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        logger.exception("QuickBooks ODBC diagnostic failed")
        raise _quickbooks_odbc_unavailable_response() from e


@router.get("/api/auth/session", response_model=AuthSessionResponse, tags=["Auth"])
@router.get("/auth/session", response_model=AuthSessionResponse, tags=["Auth"])
def get_auth_session(user: AuthenticatedUser = Depends(authenticate)):
    return _build_auth_session_response(user)


@router.post("/api/auth/login", response_model=AuthSessionResponse, tags=["Auth"])
@router.post("/auth/login", response_model=AuthSessionResponse, tags=["Auth"])
def login_auth_session(payload: AuthLoginRequest, request: Request, response: Response):
    normalized_username = payload.username.strip()
    if not normalized_username or not payload.password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    user = authenticate_credentials(normalized_username, payload.password)
    response.set_cookie(
        APP_SESSION_COOKIE_NAME,
        create_auth_session_token(user),
        **build_auth_session_cookie_options(request),
    )
    return _build_auth_session_response(user)


@router.post("/api/auth/logout", response_model=AuthLogoutResponse, tags=["Auth"])
@router.post("/auth/logout", response_model=AuthLogoutResponse, tags=["Auth"])
def logout_auth_session(response: Response):
    clear_auth_session_cookie(response)
    return AuthLogoutResponse(message="Signed out")

from .models import (
    AccountingPostingQueueActivityListResponse,
    AccountingPostingQueueEntryResponse,
    AccountingPostingQueueListResponse,
    AccountingPostingQueueMetricsResponse,
    AccountingPostingQueueReviewRequest,
    AccountingPostingQueueRequest,
    AccountingPolicyAnswerRequest,
    AccountingPolicyAnswerResponse,
    DeltaResponse,
    FinancialSummaryResponse,
    HalAuditListResponse,
    HalAutonomyProfileResponse,
    HalAutonomyRunListResponse,
    HalAutonomyRunRequest,
    HalAutonomyRunResponse,
    HalChartPlanApprovalRequest,
    HalChartPlanApprovalResponse,
    HalChartPlanListResponse,
    HalChartPlanRequest,
    HalChartPlanResponse,
    HalAskRequest,
    HalAskResponse,
    HalInsuranceNarrativeRequest,
    HalInsuranceNarrativeResponse,
    HalPatientDossierRequest,
    HalPatientDossierResponse,
    JournalDraftRequest,
    JournalDraftResponse,
    LocalAccountingDocumentListResponse,
    HalIndexRefreshResponse,
    HalPageResponse,
    ReportPullStatusResponse,
    HalStagedImportRequest,
    HalStagedImportResponse,
    HalShellCommandsResponse,
    HalStatusResponse,
    KPIResponse,
    MessageResponse,
    PhasesResponse,
    StatusResponse,
    WidgetUpdateRequest,
    WidgetUpdateResponse,
)
from .models import HalDocumentRagAskRequest, HalDocumentRagAskResponse, HalDocumentRagDocumentListResponse, HalDocumentRagUploadResponse
from .services import (
    build_softdent_snapshot,
    fetch_quickbooks_sdk_summary,
    get_quickbooks_sdk_status,
    get_softdent_claim_source_status,
    get_softdent_clinical_note_source_status,
    get_softdent_coverage_metrics,
    get_softdent_source_status,
    load_quickbooks_export_rows,
    load_softdent_dashboard_rows,
    load_softdent_ar_rows,
    get_kpi_data,
    list_local_accounting_documents,
    stage_hal_import_files,
    run_rebuild_receipt,
    run_refresh_and_verify,
    run_ci_gates,
    run_smoke_tests,
    validate_quickbooks_diagnostic_sql,
)


HAL_SESSION_COOKIE_NAME = "hal_session_id"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return 0.0
    return 0.0


def _as_optional_iso(value: object) -> str | None:
    rendered = str(value or "").strip()
    return rendered or None


def _build_review_item(*, source_system: str, status: str, summary: str, confidence_label: str, review_required: bool, review_flags: list[str], last_verified_at: str | None, metrics: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "sourceSystem": source_system,
        "status": status,
        "summary": summary,
        "confidenceLabel": confidence_label,
        "reviewRequired": review_required,
        "reviewFlags": review_flags,
        "lastVerifiedAt": last_verified_at,
        "metrics": metrics or {},
    }


def _softdent_coverage_counts(coverage: object) -> tuple[int, int, int]:
    coverage_dict = coverage if isinstance(coverage, dict) else {}
    counts = coverage_dict.get("counts") if isinstance(coverage_dict.get("counts"), dict) else {}
    return (
        int(counts.get("missing") or 0),
        int(counts.get("limited") or 0),
        int(counts.get("available") or 0),
    )


def _softdent_coverage_actionable_labels(coverage: object, *, max_items: int = 3) -> list[str]:
    coverage_dict = coverage if isinstance(coverage, dict) else {}
    rows = coverage_dict.get("rows") if isinstance(coverage_dict.get("rows"), list) else []
    return [
        str(row.get("label") or "")
        for row in rows
        if isinstance(row, dict) and str(row.get("status") or "") in {"missing", "limited"}
    ][:max_items]


def _build_softdent_claims_summary(metrics: object) -> dict[str, object]:
    metrics_dict = metrics if isinstance(metrics, dict) else {}
    outstanding = metrics_dict.get("trueOutstandingClaims") if isinstance(metrics_dict.get("trueOutstandingClaims"), dict) else {}
    unsubmitted = metrics_dict.get("unsubmittedClaims") if isinstance(metrics_dict.get("unsubmittedClaims"), dict) else {}
    return {
        "available": bool(outstanding.get("available")) or bool(unsubmitted.get("available")),
        "true_outstanding_claims_amount": _coerce_float(outstanding.get("totalAmount")),
        "true_outstanding_claims_count": int(outstanding.get("itemCount") or 0),
        "unsubmitted_claims_amount": _coerce_float(unsubmitted.get("totalAmount")),
        "unsubmitted_claims_count": int(unsubmitted.get("itemCount") or 0),
        "top_outstanding_payers": outstanding.get("breakdown") if isinstance(outstanding.get("breakdown"), list) else [],
        "top_unsubmitted_payers": unsubmitted.get("breakdown") if isinstance(unsubmitted.get("breakdown"), list) else [],
    }


def _first_non_empty(row: dict[str, object], *aliases: str) -> str:
    normalized_aliases = {
        "".join(character for character in alias.lower() if character.isalnum())
        for alias in aliases
    }
    for key, value in row.items():
        if value in (None, ""):
            continue
        normalized_key = "".join(character for character in str(key).lower() if character.isalnum())
        if normalized_key in normalized_aliases:
            return str(value).strip()
    return ""


def _normalize_year_month(value: object) -> str:
    rendered = str(value or "").strip()
    if not rendered:
        return ""
    if len(rendered) >= 7 and rendered[4] == "-":
        return rendered[:7]
    if rendered.lower().startswith("as of "):
        rendered = rendered[6:].strip()
    for pattern in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(rendered, pattern).strftime("%Y-%m")
        except ValueError:
            continue
    return ""


def _normalize_iso_date(value: object) -> str | None:
    rendered = str(value or "").strip()
    if not rendered:
        return None
    if len(rendered) >= 10 and rendered[4] == "-":
        return rendered[:10]
    if rendered.lower().startswith("as of "):
        rendered = rendered[6:].strip()
    for pattern in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(rendered, pattern).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _build_monthly_kpis(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        year_month = _normalize_year_month(row.get("period") or row.get("Period") or row.get("year_month") or row.get("month"))
        if not year_month:
            continue
        metric = grouped.setdefault(
            year_month,
            {
                "year_month": year_month,
                "month": year_month,
                "gross_production": 0.0,
                "net_production": 0.0,
                "collections": 0.0,
                "collection_rate": 0.0,
            },
        )
        metric["gross_production"] = round(float(metric["gross_production"]) + _coerce_float(row.get("production") or row.get("Production")), 2)
        metric["collections"] = round(float(metric["collections"]) + _coerce_float(row.get("collections") or row.get("Collections")), 2)

    monthly_kpis = [grouped[key] for key in sorted(grouped.keys())]
    for metric in monthly_kpis:
        gross_production = _coerce_float(metric.get("gross_production"))
        collections = _coerce_float(metric.get("collections"))
        metric["net_production"] = gross_production
        metric["collection_rate"] = round((collections / gross_production) * 100, 2) if gross_production else 0.0
    return monthly_kpis


def _build_current_year_production(monthly_kpis: list[dict[str, object]]) -> dict[str, object]:
    latest_monthly = monthly_kpis[-1] if monthly_kpis else None
    latest_year = str((latest_monthly or {}).get("year_month") or "")[:4]
    if not latest_year:
        return {}

    year_rows = [row for row in monthly_kpis if str(row.get("year_month") or "").startswith(latest_year)]
    gross_production = round(sum(_coerce_float(row.get("gross_production")) for row in year_rows), 2)
    collections = round(sum(_coerce_float(row.get("collections")) for row in year_rows), 2)
    return {
        "year_month": latest_year,
        "month": latest_year,
        "gross_production": gross_production,
        "net_production": gross_production,
        "collections": collections,
        "collection_rate": round((collections / gross_production) * 100, 2) if gross_production else 0.0,
        "calendar_year": int(latest_year) if latest_year.isdigit() else latest_year,
    }


def _build_quickbooks_expense_summaries(*, expense_rows: list[dict[str, object]], quickbooks_imported_at: str, fallback_expense_total: float, generated_at: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    categories: dict[tuple[str, str], dict[str, object]] = {}
    monthly: dict[str, dict[str, object]] = {}

    for row in expense_rows:
        amount = _coerce_float(
            _first_non_empty(
                row,
                "amount",
                "expense_total",
                "total_amount",
                "totalexpense",
                "expense",
                "total",
            )
        )
        category = _first_non_empty(row, "expense_category", "category", "type", "account_type") or "Uncategorized"
        account_name = _first_non_empty(row, "account_name", "account", "name") or category
        year_month = _normalize_year_month(
            _first_non_empty(row, "year_month", "month", "period", "date", "transaction_date", "txn_date", "report_period", "reportdate")
        )
        transaction_date = _normalize_iso_date(
            _first_non_empty(row, "date", "transaction_date", "txn_date", "last_transaction_date", "reportdate")
        )

        if amount == 0.0 and not year_month and not transaction_date:
            continue

        category_key = (category, account_name)
        category_entry = categories.setdefault(
            category_key,
            {
                "expense_category": category,
                "account_name": account_name,
                "total_amount": 0.0,
                "transaction_count": 0,
                "first_transaction_date": None,
                "last_transaction_date": None,
                "last_imported_at_utc": quickbooks_imported_at,
            },
        )
        category_entry["total_amount"] = round(float(category_entry["total_amount"]) + amount, 2)
        category_entry["transaction_count"] = int(category_entry["transaction_count"]) + 1
        if transaction_date:
            first_transaction_date = category_entry.get("first_transaction_date")
            last_transaction_date = category_entry.get("last_transaction_date")
            category_entry["first_transaction_date"] = transaction_date if not first_transaction_date else min(str(first_transaction_date), transaction_date)
            category_entry["last_transaction_date"] = transaction_date if not last_transaction_date else max(str(last_transaction_date), transaction_date)

        if year_month:
            monthly_entry = monthly.setdefault(
                year_month,
                {
                    "year_month": year_month,
                    "expense_total": 0.0,
                    "transaction_count": 0,
                    "last_imported_at_utc": quickbooks_imported_at,
                },
            )
            monthly_entry["expense_total"] = round(float(monthly_entry["expense_total"]) + amount, 2)
            monthly_entry["transaction_count"] = int(monthly_entry["transaction_count"]) + 1

    category_items = sorted(categories.values(), key=lambda item: (-_coerce_float(item.get("total_amount")), str(item.get("account_name") or "")))
    monthly_items = [monthly[key] for key in sorted(monthly.keys())]
    if not monthly_items and fallback_expense_total > 0:
        monthly_items = [
            {
                "year_month": generated_at[:7],
                "expense_total": fallback_expense_total,
                "transaction_count": 1,
                "last_imported_at_utc": quickbooks_imported_at,
            }
        ]
    return category_items, monthly_items


def _build_latest_ar_snapshot(*, ar_rows: list[dict[str, object]], fallback_as_of_date: str) -> dict[str, object]:
    snapshot = {
        "as_of_date": fallback_as_of_date,
        "total_ar": 0.0,
        "insurance_ar": 0.0,
        "patient_ar": 0.0,
        "current_balance": 0.0,
        "balance_30": 0.0,
        "balance_60": 0.0,
        "balance_90": 0.0,
        "credit_balance": 0.0,
    }
    explicit_buckets = False

    for row in ar_rows:
        row_as_of_date = _normalize_iso_date(_first_non_empty(row, "as_of_date", "report_date", "reportdate", "date"))
        if row_as_of_date:
            snapshot["as_of_date"] = row_as_of_date

        current_balance = _coerce_float(_first_non_empty(row, "current_balance", "current"))
        balance_30 = _coerce_float(_first_non_empty(row, "balance_30", "30_day", "30days", "30day"))
        balance_60 = _coerce_float(_first_non_empty(row, "balance_60", "60_day", "60days", "60day"))
        balance_90 = _coerce_float(_first_non_empty(row, "balance_90", "90_day", "90days", "90day", "balance_over_90", "over_90"))
        credit_balance = _coerce_float(_first_non_empty(row, "credit_balance", "credit"))
        insurance_ar = _coerce_float(_first_non_empty(row, "insurance_ar", "insurance_balance", "insurance"))
        patient_ar = _coerce_float(_first_non_empty(row, "patient_ar", "patient_balance", "patient"))
        total_ar = _coerce_float(_first_non_empty(row, "total_ar", "outstanding_ar", "accounts_receivable", "open_balance", "balance_remaining", "amount", "balance"))

        row_has_explicit_buckets = any(
            value > 0
            for value in (current_balance, balance_30, balance_60, balance_90, credit_balance, insurance_ar, patient_ar)
        )
        explicit_buckets = explicit_buckets or row_has_explicit_buckets

        snapshot["insurance_ar"] = round(_coerce_float(snapshot.get("insurance_ar")) + insurance_ar, 2)
        snapshot["patient_ar"] = round(_coerce_float(snapshot.get("patient_ar")) + patient_ar, 2)
        snapshot["credit_balance"] = round(_coerce_float(snapshot.get("credit_balance")) + credit_balance, 2)
        if row_has_explicit_buckets:
            snapshot["current_balance"] = round(_coerce_float(snapshot.get("current_balance")) + current_balance, 2)
            snapshot["balance_30"] = round(_coerce_float(snapshot.get("balance_30")) + balance_30, 2)
            snapshot["balance_60"] = round(_coerce_float(snapshot.get("balance_60")) + balance_60, 2)
            snapshot["balance_90"] = round(_coerce_float(snapshot.get("balance_90")) + balance_90, 2)

        snapshot["total_ar"] = round(_coerce_float(snapshot.get("total_ar")) + total_ar, 2)

    if explicit_buckets and _coerce_float(snapshot.get("total_ar")) == 0.0:
        snapshot["total_ar"] = round(
            _coerce_float(snapshot.get("current_balance"))
            + _coerce_float(snapshot.get("balance_30"))
            + _coerce_float(snapshot.get("balance_60"))
            + _coerce_float(snapshot.get("balance_90")),
            2,
        )

    return snapshot


def _softdent_ar_snapshot_is_available(snapshot: Mapping[str, object]) -> bool:
    return snapshot.get("available") is True and str(snapshot.get("source") or "") == "softdent"


def _build_softdent_latest_ar_snapshot(*, softdent_ar_rows: list[dict[str, object]], fallback_as_of_date: str) -> dict[str, object]:
    snapshot = {
        "as_of_date": fallback_as_of_date,
        "total_ar": 0.0,
        "insurance_ar": 0.0,
        "patient_ar": 0.0,
        "current_balance": 0.0,
        "balance_30": 0.0,
        "balance_60": 0.0,
        "balance_90": 0.0,
        "credit_balance": 0.0,
    }
    explicit_ar_values_present = False

    for row in softdent_ar_rows:
        row_as_of_date = (
            _normalize_iso_date(_first_non_empty(row, "as_of_date", "report_date", "reportdate", "date"))
            or _normalize_year_month(_first_non_empty(row, "period", "year_month", "month", "report_period"))
        )
        if row_as_of_date:
            snapshot["as_of_date"] = row_as_of_date

        current_balance = _coerce_float(_first_non_empty(row, "current_balance", "current"))
        balance_30 = _coerce_float(_first_non_empty(row, "balance_30", "30_day", "30days", "30day"))
        balance_60 = _coerce_float(_first_non_empty(row, "balance_60", "60_day", "60days", "60day"))
        balance_90 = _coerce_float(_first_non_empty(row, "balance_90", "90_day", "90days", "90day", "balance_over_90", "over_90"))
        credit_balance = _coerce_float(_first_non_empty(row, "credit_balance", "credit"))
        insurance_ar = _coerce_float(_first_non_empty(row, "insurance_ar", "insurance_balance"))
        patient_ar = _coerce_float(_first_non_empty(row, "patient_ar", "patient_balance"))
        total_ar = _coerce_float(_first_non_empty(row, "total_ar", "outstanding_ar", "accounts_receivable", "open_balance", "balance_remaining", "amount", "balance"))

        row_has_explicit_ar_values = any(
            value > 0
            for value in (
                total_ar,
                insurance_ar,
                patient_ar,
                current_balance,
                balance_30,
                balance_60,
                balance_90,
                credit_balance,
            )
        )
        if not row_has_explicit_ar_values:
            continue

        explicit_ar_values_present = True
        snapshot["insurance_ar"] = round(_coerce_float(snapshot.get("insurance_ar")) + insurance_ar, 2)
        snapshot["patient_ar"] = round(_coerce_float(snapshot.get("patient_ar")) + patient_ar, 2)
        snapshot["current_balance"] = round(_coerce_float(snapshot.get("current_balance")) + current_balance, 2)
        snapshot["balance_30"] = round(_coerce_float(snapshot.get("balance_30")) + balance_30, 2)
        snapshot["balance_60"] = round(_coerce_float(snapshot.get("balance_60")) + balance_60, 2)
        snapshot["balance_90"] = round(_coerce_float(snapshot.get("balance_90")) + balance_90, 2)
        snapshot["credit_balance"] = round(_coerce_float(snapshot.get("credit_balance")) + credit_balance, 2)
        snapshot["total_ar"] = round(_coerce_float(snapshot.get("total_ar")) + total_ar, 2)

    if explicit_ar_values_present:
        if _coerce_float(snapshot.get("total_ar")) == 0.0:
            snapshot["total_ar"] = round(
                _coerce_float(snapshot.get("current_balance"))
                + _coerce_float(snapshot.get("balance_30"))
                + _coerce_float(snapshot.get("balance_60"))
                + _coerce_float(snapshot.get("balance_90")),
                2,
            )
        snapshot["available"] = True
        snapshot["source"] = "softdent"
        return snapshot

    return {
        "available": False,
        "source": "softdent",
        "as_of_date": fallback_as_of_date,
        "total_ar": 0.0,
        "insurance_ar": 0.0,
        "patient_ar": 0.0,
        "current_balance": 0.0,
        "balance_30": 0.0,
        "balance_60": 0.0,
        "balance_90": 0.0,
        "credit_balance": 0.0,
    }


def _resolve_hal_session_id(request: Request, payload_session_id: str | None) -> str:
    cookie_session_id = str(request.cookies.get(HAL_SESSION_COOKIE_NAME) or "").strip()
    if cookie_session_id:
        return cookie_session_id
    explicit_session_id = str(payload_session_id or "").strip()
    if explicit_session_id:
        return explicit_session_id
    return f"hal-session-{uuid4().hex}"


def _should_honor_explicit_hal_session_id(*, question: str, payload_session_id: str | None, request: Request) -> bool:
    explicit_session_id = str(payload_session_id or "").strip()
    if not explicit_session_id:
        return False

    cookie_session_id = str(request.cookies.get(HAL_SESSION_COOKIE_NAME) or "").strip()
    if not cookie_session_id:
        return True

    lowered_question = str(question or "").lower()
    patient_workflow_keywords = (
        "patient",
        "mrn",
        "claim",
        "narrative",
        "clinical note",
        "clinical notes",
        "follow-up plan",
        "follow up plan",
    )
    if any(keyword in lowered_question for keyword in patient_workflow_keywords):
        return True

    return False


def _resolve_effective_hal_session_id(request: Request, payload_session_id: str | None, *, question: str) -> str:
    if _should_honor_explicit_hal_session_id(question=question, payload_session_id=payload_session_id, request=request):
        return str(payload_session_id or "").strip()
    return _resolve_hal_session_id(request, payload_session_id)


def _hal_session_cookie_options(request: Request) -> dict[str, object]:
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": request.url.scheme == "https" or forwarded_proto == "https",
    }


def _build_financial_summary_payload() -> dict[str, object]:
    generated_at = _utc_now_iso()
    softdent_rows = load_softdent_dashboard_rows()
    softdent_snapshot = build_softdent_snapshot()
    softdent_source = get_softdent_source_status()
    softdent_claim_source = get_softdent_claim_source_status()
    financial_sources = get_financial_source_status()

    monthly_kpis = _build_monthly_kpis(softdent_rows)

    trailing_12 = monthly_kpis[-12:] if len(monthly_kpis) > 12 else monthly_kpis
    latest_monthly = monthly_kpis[-1] if monthly_kpis else None

    quickbooks_status = get_quickbooks_sdk_status()
    quickbooks_errors: dict[str, str] = {}

    def _fetch_quickbooks_topic(topic: str) -> list[dict]:
        try:
            return fetch_quickbooks_sdk_summary(topic)
        except Exception as exc:
            quickbooks_errors[topic] = str(exc)
            return []

    quickbooks_revenue_rows = _fetch_quickbooks_topic("revenue")
    quickbooks_expense_rows = _fetch_quickbooks_topic("expenses")
    quickbooks_ar_rows = _fetch_quickbooks_topic("ar")
    quickbooks_error = "; ".join(f"{topic}: {detail}" for topic, detail in quickbooks_errors.items()) or None
    quickbooks_partial_success = any((quickbooks_revenue_rows, quickbooks_expense_rows, quickbooks_ar_rows))

    quickbooks_live = financial_sources.get("quickbooks") if isinstance(financial_sources.get("quickbooks"), dict) else {}
    softdent_live = financial_sources.get("softdent") if isinstance(financial_sources.get("softdent"), dict) else {}
    softdent_coverage = softdent_live.get("coverage") if isinstance(softdent_live.get("coverage"), dict) else None
    softdent_coverage_metrics = get_softdent_coverage_metrics()
    softdent_claims_summary = _build_softdent_claims_summary(softdent_coverage_metrics)
    softdent_live_snapshot = softdent_live.get("live_snapshot") if isinstance(softdent_live.get("live_snapshot"), dict) else {}
    softdent_live_claims = softdent_live.get("live_claims") if isinstance(softdent_live.get("live_claims"), dict) else {}
    quickbooks_live_revenue = quickbooks_live.get("live_revenue") if isinstance(quickbooks_live.get("live_revenue"), dict) else {}
    quickbooks_live_expenses = quickbooks_live.get("live_expenses") if isinstance(quickbooks_live.get("live_expenses"), dict) else {}
    quickbooks_live_ar = quickbooks_live.get("live_ar") if isinstance(quickbooks_live.get("live_ar"), dict) else {}
    quickbooks_imported_at = (
        _as_optional_iso(quickbooks_live_revenue.get("modified_at_utc"))
        or _as_optional_iso(quickbooks_live_expenses.get("modified_at_utc"))
        or _as_optional_iso(quickbooks_live_ar.get("modified_at_utc"))
        or generated_at
    )

    revenue_total = _coerce_float((quickbooks_revenue_rows[0] if quickbooks_revenue_rows else {}).get("TotalIncome"))
    expense_total = _coerce_float((quickbooks_expense_rows[0] if quickbooks_expense_rows else {}).get("TotalExpense"))
    net_income = revenue_total - expense_total
    detailed_quickbooks_expense_rows = load_quickbooks_export_rows("expenses")
    quickbooks_expense_categories, quickbooks_monthly_expenses = _build_quickbooks_expense_summaries(
        expense_rows=detailed_quickbooks_expense_rows,
        quickbooks_imported_at=quickbooks_imported_at,
        fallback_expense_total=expense_total,
        generated_at=generated_at,
    )
    latest_ar_snapshot = _build_softdent_latest_ar_snapshot(
        softdent_ar_rows=load_softdent_ar_rows(),
        fallback_as_of_date=str(latest_monthly.get("year_month") if isinstance(latest_monthly, dict) else "") or generated_at[:10],
    )
    latest_ar = latest_ar_snapshot if _softdent_ar_snapshot_is_available(latest_ar_snapshot) else None
    quickbooks_profit_loss = []
    if quickbooks_revenue_rows and quickbooks_expense_rows:
        quickbooks_profit_loss.append(
            {
                "year_month": generated_at[:7],
                "period_start": f"{generated_at[:7]}-01",
                "period_end": generated_at[:10],
                "income_total": revenue_total,
                "expense_total": expense_total,
                "net_income": net_income,
                "base_ebitda_candidate": net_income,
                "last_imported_at_utc": quickbooks_imported_at,
            }
        )

    expense_detail_available = bool(detailed_quickbooks_expense_rows)
    quickbooks_status_message = (
        "QuickBooks SDK summaries retrieved."
        if not quickbooks_errors
        else "QuickBooks SDK partial read completed; one or more approved topics are unavailable."
        if quickbooks_partial_success
        else "QuickBooks SDK summaries are currently unavailable."
    )
    quickbooks_review_flags = [str(flag) for flag in list(quickbooks_live_revenue.get("review_flags") or [])]
    quickbooks_review_flags.extend(str(flag) for flag in list(quickbooks_live_expenses.get("review_flags") or []))
    quickbooks_review_flags.extend(str(flag) for flag in list(quickbooks_live_ar.get("review_flags") or []))
    quickbooks_review_flags.extend(f"{topic} sdk read failed" for topic in quickbooks_errors)
    if expense_total > 0 and not expense_detail_available:
        quickbooks_review_flags.append("expense detail export missing")
    quickbooks_review_flags = list(dict.fromkeys(quickbooks_review_flags))
    quickbooks_review_required = (
        bool(quickbooks_live_revenue.get("review_required"))
        or bool(quickbooks_live_expenses.get("review_required"))
        or bool(quickbooks_live_ar.get("review_required"))
        or bool(quickbooks_review_flags)
    )
    quickbooks_confidence_label = str(
        quickbooks_live_revenue.get("confidence_label")
        or quickbooks_live_expenses.get("confidence_label")
        or quickbooks_live_ar.get("confidence_label")
        or ("manual review" if quickbooks_error else "review suggested")
    )
    if quickbooks_review_required and quickbooks_confidence_label == "high confidence":
        quickbooks_confidence_label = "review suggested"

    quickbooks_review_summary_parts = [
        str(
            quickbooks_live_revenue.get("excerpt")
            if not quickbooks_error and quickbooks_live_revenue.get("excerpt")
            else quickbooks_status_message if not quickbooks_error or quickbooks_partial_success
            else quickbooks_error
        )
    ]
    if expense_total > 0 and not expense_detail_available:
        quickbooks_review_summary_parts.append(
            "Expense category detail export is unavailable, so category breakdowns stay blank and the monthly expense chart falls back to the current SDK summary total."
        )

    softdent_modified = _as_optional_iso(softdent_source.get("modified_at_utc"))
    latest_softdent_refresh_at = softdent_modified or _as_optional_iso(softdent_live_snapshot.get("checked_at_utc")) or generated_at

    health_flags = []
    if not bool(softdent_source.get("available")):
        health_flags.append(
            {
                "key": "softdent_source",
                "code": "SOFTDENT_SOURCE_MISSING",
                "status": "warning",
                "sourceSystem": "SoftDent",
                "message": "SoftDent export source file is not currently available.",
                "action": "Confirm bridge export staging and rerun refresh.",
            }
        )
    softdent_missing_count, softdent_limited_count, softdent_available_count = _softdent_coverage_counts(softdent_coverage)
    if softdent_missing_count or softdent_limited_count:
        coverage_labels = ", ".join(_softdent_coverage_actionable_labels(softdent_coverage)) or "coverage rows"
        health_flags.append(
            {
                "key": "softdent_page_coverage",
                "code": "SOFTDENT_PAGE_COVERAGE_GAPS",
                "status": "warning" if softdent_missing_count else "info",
                "sourceSystem": "SoftDent",
                "message": f"SoftDent page coverage has {softdent_missing_count} missing and {softdent_limited_count} limited report lane(s): {coverage_labels}.",
                "action": "Review the SoftDent coverage table and stage the missing aggregate-only exports before treating blocked dashboard tiles as generic source failures.",
            }
        )
    for topic, detail in quickbooks_errors.items():
        health_flags.append(
            {
                "key": f"quickbooks_{topic}_sdk",
                "code": f"QUICKBOOKS_{topic.upper()}_READ_ERROR",
                "status": "warning",
                "sourceSystem": "QuickBooks",
                "message": f"{topic} summary failed: {detail}",
                "action": "Verify QuickBooks Desktop is open and SDK permissions are granted.",
            }
        )

    source_review = {
        "softDent": _build_review_item(
            source_system="SoftDent",
            status="ready" if bool(softdent_source.get("available")) else "missing",
            summary=str(softdent_live_snapshot.get("excerpt") or "SoftDent summary source status is available."),
            confidence_label=str(softdent_live_snapshot.get("confidence_label") or "manual review"),
            review_required=bool(softdent_live_snapshot.get("review_required", True)),
            review_flags=list(softdent_live_snapshot.get("review_flags") or []),
            last_verified_at=_as_optional_iso(softdent_live_snapshot.get("checked_at_utc")) or latest_softdent_refresh_at,
            metrics={
                "providerCount": softdent_snapshot.get("provider_count", 0),
                "period": softdent_snapshot.get("period", ""),
                "missingReports": softdent_missing_count,
                "limitedReports": softdent_limited_count,
                "availableReports": softdent_available_count,
            },
        ),
        "softDentClaims": _build_review_item(
            source_system="SoftDent Claims",
            status="ready" if bool(softdent_claim_source.get("available")) else "missing",
            summary=str(softdent_live_claims.get("excerpt") or "SoftDent claims source status is available."),
            confidence_label=str(softdent_live_claims.get("confidence_label") or "manual review"),
            review_required=bool(softdent_live_claims.get("review_required", True)),
            review_flags=list(softdent_live_claims.get("review_flags") or []),
            last_verified_at=_as_optional_iso(softdent_live_claims.get("checked_at_utc")) or generated_at,
            metrics={
                "sourceFile": softdent_claim_source.get("source_file") or "",
                "sourceBackend": softdent_claim_source.get("source_backend") or "missing",
            },
        ),
        "quickBooks": _build_review_item(
            source_system="QuickBooks",
            status="ready" if not quickbooks_error and not quickbooks_review_required else "warning",
            summary=" ".join(part for part in quickbooks_review_summary_parts if part),
            confidence_label=quickbooks_confidence_label,
            review_required=quickbooks_review_required,
            review_flags=quickbooks_review_flags or (["sdk read failed"] if quickbooks_error else []),
            last_verified_at=_as_optional_iso(quickbooks_live_revenue.get("checked_at_utc")) or generated_at,
            metrics={
                "revenueRows": len(quickbooks_revenue_rows),
                "expenseRows": len(quickbooks_expense_rows),
                "arRows": len(quickbooks_ar_rows),
            },
        ),
    }

    return {
        "generatedAt": generated_at,
        "lastRefreshed": generated_at,
        "latestSoftDentRefreshAt": latest_softdent_refresh_at,
        "dataFreshnessStatus": "fresh" if bool(softdent_source.get("available")) else "stale",
        "healthFlags": health_flags,
        "transactionDiagnostics": {
            "transactionConfigured": bool(softdent_source.get("available")) and bool(quickbooks_status.get("com_available")),
            "dataSyncTransactionEmitted": bool(softdent_source.get("available")),
            "sqliteTransactionRows": len(monthly_kpis),
            "sourceMode": "softdent+quickbooks",
            "validationStatus": "ok" if not quickbooks_error else "warning",
            "summary": (
                f"HAL can read current SoftDent and QuickBooks financial source surfaces, but SoftDent still has {softdent_missing_count} missing and {softdent_limited_count} limited dashboard coverage lanes."
                if softdent_missing_count or softdent_limited_count
                else "HAL can read current SoftDent and QuickBooks financial source surfaces."
            ),
        },
        "sourceReview": source_review,
        "softDentCoverage": softdent_coverage,
        "softDentCoverageMetrics": softdent_coverage_metrics,
        "claimsSummary": softdent_claims_summary,
        "latestDailyKpi": {
            "production": _coerce_float((latest_monthly or {}).get("gross_production")),
            "collections": _coerce_float((latest_monthly or {}).get("collections")),
        },
        "latestAr": latest_ar,
        "monthlyKpis": monthly_kpis,
        "trailing12Months": trailing_12,
        "calendarYearKpis": monthly_kpis,
        "fourYearMonthlyKpis": monthly_kpis,
        "providerProduction": softdent_snapshot.get("providers") or [],
        "topAdaCodes": [],
        "quickBooksStatus": {
            "status": "ready" if not quickbooks_error else "warning",
            "message": quickbooks_status_message,
            "lastCheckedAtUtc": generated_at,
            "lastImportedAtUtc": quickbooks_imported_at,
            "lastError": quickbooks_error,
            "rowCounts": {
                "revenue": len(quickbooks_revenue_rows),
                "expenses": len(quickbooks_expense_rows),
                "ar": len(quickbooks_ar_rows),
            },
        },
        "quickBooksExpenseCategories": quickbooks_expense_categories,
        "quickBooksMonthlyExpenses": quickbooks_monthly_expenses,
        "quickBooksProfitLossSummary": quickbooks_profit_loss,
        "quickBooksEbitdaCandidates": quickbooks_profit_loss,
        "dataFreshnessWarnings": [] if not health_flags else health_flags,
        "currentMonthProduction": latest_monthly or {},
        "currentYearProduction": _build_current_year_production(monthly_kpis),
    }


def _build_public_financial_summary_payload() -> dict[str, object]:
    payload = _build_financial_summary_payload()
    widget_feed = get_widget_feed()
    if widget_feed is None:
        return payload

    public_payload = dict(payload)
    public_payload["widgetFeed"] = widget_feed
    return public_payload


def _build_admin_summary_payload() -> dict[str, object]:
    financial_summary = _build_financial_summary_payload()
    source_review = financial_summary.get("sourceReview") if isinstance(financial_summary.get("sourceReview"), dict) else {}
    softdent_review = source_review.get("softDent") if isinstance(source_review.get("softDent"), dict) else {}
    quickbooks_review = source_review.get("quickBooks") if isinstance(source_review.get("quickBooks"), dict) else {}
    softdent_coverage = financial_summary.get("softDentCoverage") if isinstance(financial_summary.get("softDentCoverage"), dict) else {}
    softdent_coverage_metrics = financial_summary.get("softDentCoverageMetrics") if isinstance(financial_summary.get("softDentCoverageMetrics"), dict) else {}
    claims_summary = financial_summary.get("claimsSummary") if isinstance(financial_summary.get("claimsSummary"), dict) else {}
    latest_refresh = str(financial_summary.get("latestSoftDentRefreshAt") or financial_summary.get("generatedAt") or "")
    monthly_kpis = financial_summary.get("monthlyKpis") if isinstance(financial_summary.get("monthlyKpis"), list) else []
    softdent_missing_count, softdent_limited_count, softdent_available_count = _softdent_coverage_counts(softdent_coverage)
    softdent_actionable_labels = _softdent_coverage_actionable_labels(softdent_coverage)

    admin_kpis = [
        {
            "period": str(item.get("year_month") or item.get("month") or ""),
            "production": _coerce_float(item.get("gross_production")),
            "collections": _coerce_float(item.get("collections")),
            "overhead_percentage": 0,
        }
        for item in monthly_kpis
        if isinstance(item, dict)
    ]

    priority_actions = [
        "Refresh both SoftDent and QuickBooks data sources before owner review.",
        "Review source confidence flags before approving downstream actions.",
    ]
    if softdent_missing_count or softdent_limited_count:
        priority_actions.insert(
            0,
            (
                f"SoftDent page coverage remains constrained: {softdent_missing_count} missing, {softdent_limited_count} limited. "
                f"Resolve {', '.join(softdent_actionable_labels) or 'the missing coverage rows'} first."
            ),
        )

    return {
        "last_refresh_date": latest_refresh,
        "report_pull_status": {
            "softdent": {
                "status": softdent_review.get("status") or "unknown",
                "summary": softdent_review.get("summary") or "",
            },
            "quickbooks": {
                "status": quickbooks_review.get("status") or "unknown",
                "summary": quickbooks_review.get("summary") or "",
            },
        },
        "kpis": admin_kpis,
        "report_summary": {
            "financial_generated_at": financial_summary.get("generatedAt"),
            "health_flags": financial_summary.get("healthFlags"),
            "softdent_coverage": softdent_coverage,
        },
        "dso_summary": {},
        "claims_summary": claims_summary,
        "practice_central_delta": {},
        "softdent_insights": {
            "summary": softdent_review.get("summary") or "",
            "coverage": softdent_coverage,
            "coverage_metrics": softdent_coverage_metrics,
        },
        "priority_actions": priority_actions,
        "priority_summary": (
            f"SoftDent page coverage gaps remain visible to HAL: {softdent_missing_count} missing, {softdent_limited_count} limited, {softdent_available_count} available."
            if softdent_missing_count or softdent_limited_count
            else "HAL source refresh is available for all financial pages."
        ),
    }

@router.get("/api/kpis", response_model=KPIResponse, include_in_schema=False)
@router.get("/kpis", response_model=KPIResponse)
def get_kpis(user: AuthenticatedUser = Depends(authenticate)):
    del user
    kpis = [kpi["name"] for kpi in get_kpi_data()]
    return KPIResponse(kpis=kpis)


# --- Script migration endpoints ---

@router.post("/api/rebuild", include_in_schema=False)
@router.post("/rebuild")
def api_rebuild(user: AuthenticatedUser = Depends(require_roles("admin"))):
    """Trigger rebuild receipt logic (from write_rebuild_receipt.py)."""
    del user
    return run_rebuild_receipt()

@router.post("/api/refresh", include_in_schema=False)
@router.post("/refresh")
def api_refresh(user: AuthenticatedUser = Depends(require_roles("admin"))):
    """Trigger refresh and verification (from refresh_from_softdent_and_verify.py)."""
    del user
    return run_refresh_and_verify()

@router.post("/api/ci-gates", include_in_schema=False)
@router.post("/ci-gates")
def api_ci_gates(user: AuthenticatedUser = Depends(require_roles("admin"))):
    """Run CI gates (from run_ci_gates.py)."""
    del user
    return run_ci_gates()

@router.post("/api/smoke", include_in_schema=False)
@router.post("/smoke")
def api_smoke(user: AuthenticatedUser = Depends(require_roles("admin"))):
    """Run smoke tests (from smoke_all_routes.py)."""
    del user
    return run_smoke_tests()


@router.post("/api/widgets/update", response_model=WidgetUpdateResponse, status_code=202)
@router.post("/widgets/update", response_model=WidgetUpdateResponse, status_code=202, include_in_schema=False)
async def api_widget_update(request: Request):
    auth_mode = _authorize_widget_update_request(request)
    body = await request.body()
    if len(body) > MAX_WIDGET_UPDATE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Widget update payload exceeds {MAX_WIDGET_UPDATE_BYTES} byte limit",
        )
    if not body:
        raise HTTPException(status_code=400, detail="Widget update payload is required")
    try:
        raw_payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Widget update payload must be valid JSON") from exc
    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=422, detail="Widget update payload must be a JSON object")
    try:
        validated = WidgetUpdateRequest.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc
    try:
        widget_feed = record_widget_feed(validated.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    widgets = widget_feed.get("widgets") if isinstance(widget_feed.get("widgets"), dict) else {}
    sources = widget_feed.get("sources") if isinstance(widget_feed.get("sources"), dict) else {}
    jobs = widget_feed.get("jobs") if isinstance(widget_feed.get("jobs"), dict) else {}
    return {
        "accepted": True,
        "manager": str(widget_feed.get("manager") or ""),
        "run_id": widget_feed.get("run_id"),
        "received_at": str(widget_feed.get("received_at") or _utc_now_iso()),
        "widget_count": len(widgets),
        "source_count": len(sources),
        "job_count": len(jobs),
        "auth_mode": auth_mode,
        "message": "HAL widget update accepted.",
    }

@router.get("/api/hal9000/page-summary", response_model=FinancialSummaryResponse, response_model_exclude_none=True)
def hal9000_page_summary(user: AuthenticatedUser = Depends(require_roles("dashboard:read"))):
    del user
    return _build_public_financial_summary_payload()


@router.get("/api/hal9000/admin-summary")
def hal9000_admin_summary(user: AuthenticatedUser = Depends(require_roles("admin"))):
    del user
    return _build_admin_summary_payload()

@router.get("/api/softdent", response_model=MessageResponse, include_in_schema=False)
@router.get("/softdent", response_model=MessageResponse)
def softdent_page(user: AuthenticatedUser = Depends(require_roles("dashboard:read"))):
    del user
    _raise_not_implemented_surface("SoftDent page")

@router.get("/api/quickbooks", response_model=MessageResponse, include_in_schema=False)
@router.get("/quickbooks", response_model=MessageResponse)
def quickbooks_page(user: AuthenticatedUser = Depends(require_roles("dashboard:read"))):
    del user
    _raise_not_implemented_surface("QuickBooks page")

@router.get("/api/accounts-receivable", response_model=MessageResponse, include_in_schema=False)
@router.get("/accounts-receivable", response_model=MessageResponse)
def ar_page(user: AuthenticatedUser = Depends(require_roles("dashboard:read"))):
    del user
    _raise_not_implemented_surface("Accounts Receivable page")

@router.get("/reconciliation", response_model=MessageResponse)
def reconciliation_page(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    _raise_not_implemented_surface("Reconciliation page")

@router.get("/api/trends", response_model=MessageResponse, include_in_schema=False)
@router.get("/trends", response_model=MessageResponse)
def trends_page(user: AuthenticatedUser = Depends(require_roles("dashboard:read"))):
    del user
    _raise_not_implemented_surface("Trends page")

@router.get("/api/ebitda", response_model=MessageResponse, include_in_schema=False)
@router.get("/ebitda", response_model=MessageResponse)
def ebitda_page(user: AuthenticatedUser = Depends(require_roles("dashboard:read"))):
    del user
    _raise_not_implemented_surface("EBITDA page")

@router.get("/api/claims", response_model=MessageResponse, include_in_schema=False)
@router.get("/claims", response_model=MessageResponse)
def claims_page(user: AuthenticatedUser = Depends(require_roles("hal:operator", "dashboard:read"))):
    del user
    _raise_not_implemented_surface("Claims page")

@router.get("/api/hal9000", response_model=HalPageResponse, include_in_schema=False)
@router.get("/hal9000", response_model=HalPageResponse)
def hal9000_page(request: Request, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del request
    del user
    return _serialize_public_hal_payload({
        "message": "HAL9000 local Phase 1 endpoint is active with sanitized retrieval and audit logging.",
        "mode": "local-rag-phase-1",
        "access_policy": get_hal_access_policy(),
    })

@router.get("/admin", response_model=MessageResponse)
def admin_page(user: AuthenticatedUser = Depends(require_roles("admin"))):
    del user
    _raise_not_implemented_surface("Admin page")

@router.get("/api/reports", response_model=MessageResponse, include_in_schema=False)
@router.get("/reports", response_model=MessageResponse)
def reports_page(user: AuthenticatedUser = Depends(require_roles("admin"))):
    del user
    _raise_not_implemented_surface("Reports page")

@router.get("/api/health", response_model=StatusResponse)
def api_health(user: AuthenticatedUser = Depends(authenticate)):
    del user
    return {"status": "ok"}

@router.get("/api/admin", response_model=MessageResponse)
def api_admin(user: AuthenticatedUser = Depends(require_roles("admin"))):
    del user
    _raise_not_implemented_surface("Admin API")

@router.get("/api/reconciliation", response_model=MessageResponse)
def api_reconciliation(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    _raise_not_implemented_surface("Reconciliation API")

@router.get("/api/hal9000/phases", response_model=PhasesResponse)
def api_hal9000_phases(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    return {"phases": get_hal_phases()}


@router.post("/api/hal9000/refresh-index", response_model=HalIndexRefreshResponse)
def api_hal9000_refresh_index(user: AuthenticatedUser = Depends(require_roles("hal:index:refresh"))):
    return refresh_local_hal_index(actor=user.username)


@router.get("/api/hal9000/status", response_model=HalStatusResponse)
async def api_hal9000_status(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    return get_hal_index_status()


@router.get("/api/hal9000/field-timeframes")
async def api_hal9000_field_timeframes(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    operating_picture = get_hal_operating_picture()
    registry = operating_picture.get("page_field_timeframe_registry") if isinstance(operating_picture.get("page_field_timeframe_registry"), dict) else {}
    return {
        "mode": "local-rag-phase-1",
        "registry": registry,
    }


@router.post("/api/hal9000/refresh-financial-sources")
async def api_hal9000_refresh_financial_sources(user: AuthenticatedUser = Depends(require_roles("admin"))):
    refresh_report = run_refresh_and_verify()
    return {
        "message": "HAL refreshed SoftDent and QuickBooks financial sources.",
        "actor": user.username,
        "refreshed_at_utc": _utc_now_iso(),
        "refresh_report": refresh_report,
        "financial_summary": _build_public_financial_summary_payload(),
        "hal_status": get_hal_index_status(),
        "admin_summary": _build_admin_summary_payload(),
    }


@router.post("/api/hal9000/staged-imports", response_model=HalStagedImportResponse)
async def api_hal9000_staged_imports(
    payload: HalStagedImportRequest,
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    try:
        return stage_hal_import_files(
            [file.model_dump() for file in payload.files],
            actor=user.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/hal9000/accounting-documents", response_model=LocalAccountingDocumentListResponse)
async def api_hal9000_accounting_documents(
    limit: int = Query(20, ge=1, le=100),
    document_type: str | None = Query(None, min_length=1, max_length=80),
    search: str | None = Query(None, min_length=1, max_length=200),
    review_only: bool = Query(False),
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    del user
    return _serialize_local_accounting_document_list_payload(
        list_local_accounting_documents(limit=limit, document_type=document_type, search=search, review_only=review_only)
    )


@router.get("/api/hal9000/document-rag/documents", response_model=HalDocumentRagDocumentListResponse)
async def api_hal9000_document_rag_documents(
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, min_length=1, max_length=200),
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    del user
    return _serialize_document_rag_document_list_payload(list_document_rag_documents(limit=limit, search=search))


@router.post("/api/hal9000/document-rag/documents", response_model=HalDocumentRagUploadResponse)
async def api_hal9000_document_rag_upload(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    try:
        return _serialize_document_rag_upload_payload(ingest_document_rag_upload(
            file_name=file.filename or "document.txt",
            content=await _read_upload_with_limit(file, limit_bytes=MAX_DOCUMENT_RAG_UPLOAD_BYTES),
            content_type=file.content_type or "application/octet-stream",
            actor=user.username,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/hal9000/document-rag/ask", response_model=HalDocumentRagAskResponse)
async def api_hal9000_document_rag_ask(
    payload: HalDocumentRagAskRequest,
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    try:
        return answer_document_rag_question(question=payload.question, actor=user.username, top_k=payload.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise _build_redacted_hal_http_exception(operation="document-rag-ask", actor=user.username, exc=exc) from exc


@router.get("/api/hal/shell/commands", response_model=HalShellCommandsResponse)
async def api_hal_shell_commands(
    command_hint: str | None = Query(None, min_length=1, max_length=120),
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    del user
    return get_hal_shell_commands(command_hint=command_hint)


@router.get("/api/hal9000/autonomy/profile", response_model=HalAutonomyProfileResponse)
async def api_hal9000_autonomy_profile(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    return get_hal_autonomy_profile()


@router.post("/api/hal9000/autonomy/runs", response_model=HalAutonomyRunResponse)
def api_hal9000_autonomy_runs_create(payload: HalAutonomyRunRequest, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    return create_hal_autonomy_run(objective=payload.objective, actor=user.username, max_steps=payload.max_steps)


@router.get("/api/hal9000/autonomy/runs", response_model=HalAutonomyRunListResponse)
def api_hal9000_autonomy_runs_list(
    limit: int = Query(10, ge=1, le=50),
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    del user
    return list_hal_autonomy_runs(limit=limit)


@router.get("/api/hal9000/autonomy/runs/{run_id}", response_model=HalAutonomyRunResponse)
def api_hal9000_autonomy_runs_get(run_id: str, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    try:
        return get_hal_autonomy_run_status(run_id=run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/hal9000/autonomy/runs/{run_id}/advance", response_model=HalAutonomyRunResponse)
def api_hal9000_autonomy_runs_advance(
    run_id: str,
    cycles: int = Query(1, ge=1, le=5),
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    try:
        return advance_hal_autonomy_run(run_id=run_id, actor=user.username, cycles=cycles)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/hal9000/audits", response_model=HalAuditListResponse)
def api_hal9000_audits(limit: int = Query(10, ge=1, le=100), user: AuthenticatedUser = Depends(require_roles("admin"))):
    del user
    return list_hal_audit_events(limit=limit)

@router.get("/api/reports/pull-status", response_model=ReportPullStatusResponse)
def api_reports_pull_status(request: Request, user: AuthenticatedUser = Depends(require_roles("admin"))):
    del user
    return get_pull_status_payload(request.app)

@router.get("/api/reports/practice-central-delta", response_model=DeltaResponse)
def api_reports_practice_central_delta(user: AuthenticatedUser = Depends(require_roles("admin"))):
    del user
    _raise_not_implemented_surface("Practice Central delta report")

@router.post("/api/softdent/import", response_model=MessageResponse, include_in_schema=False)
@router.post("/softdent/import", response_model=MessageResponse)
async def softdent_import(request: Request, file: UploadFile = File(...), user: AuthenticatedUser = Depends(require_roles("admin"))):
    del user
    try:
        result = import_uploaded_file(
            app=request.app,
            source="softdent",
            file_name=file.filename or "softdent_import.csv",
            content=await _read_upload_with_limit(file),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": f"SoftDent import completed with {len(result['files_written'])} canonical file(s)."}

@router.post("/api/quickbooks/import", response_model=MessageResponse, include_in_schema=False)
@router.post("/quickbooks/import", response_model=MessageResponse)
async def quickbooks_import(request: Request, file: UploadFile = File(...), user: AuthenticatedUser = Depends(require_roles("admin"))):
    del user
    try:
        result = import_uploaded_file(
            app=request.app,
            source="quickbooks",
            file_name=file.filename or "quickbooks_import.csv",
            content=await _read_upload_with_limit(file),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": f"QuickBooks import completed with {len(result['files_written'])} canonical file(s)."}

@router.post("/api/hal9000", response_model=HalAskResponse, include_in_schema=False)
@router.post("/hal9000", response_model=HalAskResponse)
async def hal9000_post(payload: HalAskRequest, request: Request, response: Response, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    session_id = _resolve_effective_hal_session_id(request, payload.session_id, question=payload.question)
    try:
        result = answer_hal_question(
            question=payload.question,
            actor=user.username,
            summary=payload.summary,
            session_id=session_id,
        )
        response.set_cookie(HAL_SESSION_COOKIE_NAME, session_id, **_hal_session_cookie_options(request))
        return _serialize_public_hal_payload(result)
    except Exception as exc:
        raise _build_redacted_hal_http_exception(operation="hal-question", actor=user.username, exc=exc) from exc


@router.post("/api/hal9000/second-opinion", response_model=HalAskResponse, include_in_schema=False)
@router.post("/hal9000/second-opinion", response_model=HalAskResponse)
async def hal9000_second_opinion_post(payload: HalAskRequest, request: Request, response: Response, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    session_id = _resolve_effective_hal_session_id(request, payload.session_id, question=payload.question)
    try:
        result = answer_hal_second_opinion_question(
            question=payload.question,
            actor=user.username,
            summary=payload.summary,
            session_id=session_id,
        )
        response.set_cookie(HAL_SESSION_COOKIE_NAME, session_id, **_hal_session_cookie_options(request))
        return _serialize_public_hal_payload(result)
    except Exception as exc:
        raise _build_redacted_hal_http_exception(operation="hal-second-opinion", actor=user.username, exc=exc) from exc


@router.post("/api/hal9000/insurance-narrative", response_model=HalInsuranceNarrativeResponse)
async def api_hal9000_insurance_narrative(payload: HalInsuranceNarrativeRequest, request: Request, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del request
    return _serialize_public_hal_payload(answer_insurance_narrative_request(question=payload.question, actor=user.username))


@router.post("/api/hal9000/patient-dossier", response_model=HalPatientDossierResponse)
async def api_hal9000_patient_dossier(payload: HalPatientDossierRequest, request: Request, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del request
    return _serialize_public_hal_payload(answer_patient_dossier_request(question=payload.question, actor=user.username))


@router.post("/api/hal9000/chart-plan", response_model=HalChartPlanResponse)
async def api_hal9000_chart_plan(payload: HalChartPlanRequest, request: Request, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del request
    try:
        return _serialize_chart_plan_payload(create_hal_chart_plan(question=payload.question, actor=user.username))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/hal9000/chart-plans", response_model=HalChartPlanListResponse)
async def api_hal9000_chart_plans(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(pending_human_approval|approved_and_rendered)$"),
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    del user
    return _serialize_chart_plan_list_payload(list_hal_chart_plans(limit=limit, status=status))


@router.post("/api/hal9000/chart-plan/approve", response_model=HalChartPlanApprovalResponse)
async def api_hal9000_chart_plan_approve(payload: HalChartPlanApprovalRequest, request: Request, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del request
    try:
        resolved_review_plan_path = resolve_ai_workspace_handle(payload.review_plan_path, label="Review plan handle")
        return _serialize_chart_plan_payload(approve_hal_chart_plan(review_plan_path=str(resolved_review_plan_path), actor=user.username))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/hal9000/chart-files")
async def api_hal9000_chart_file(
    path: str = Query(..., min_length=3, max_length=2000),
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    del user
    try:
        file_path = resolve_ai_workspace_handle(path, label="Chart file handle")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Chart file not found.")
    return FileResponse(file_path)


@router.post("/api/hal9000/accounting/policy-answer", response_model=AccountingPolicyAnswerResponse)
async def api_hal9000_accounting_policy_answer(payload: AccountingPolicyAnswerRequest, request: Request, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del request
    return _serialize_public_hal_payload(answer_accounting_policy_question(
        question=payload.question,
        topic=payload.topic,
        accounting_standard=payload.accounting_standard,
        actor=user.username,
    ))


@router.post("/api/hal9000/accounting/journal-draft", response_model=JournalDraftResponse)
async def api_hal9000_journal_draft(payload: JournalDraftRequest, request: Request, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del request
    return _serialize_journal_draft_payload(draft_accounting_journal_entry(
        description=payload.description,
        transaction_date=payload.transaction_date.isoformat(),
        accounting_period=payload.accounting_period,
        amount=payload.amount,
        context=payload.context,
        actor=user.username,
    ))


@router.post("/api/hal9000/accounting/posting-queue", response_model=AccountingPostingQueueEntryResponse)
async def api_hal9000_accounting_posting_queue(payload: AccountingPostingQueueRequest, request: Request, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del request
    try:
        return _serialize_posting_queue_entry_payload(queue_accounting_posting_draft(
            description=payload.description,
            transaction_date=payload.transaction_date.isoformat(),
            accounting_period=payload.accounting_period,
            amount=payload.amount,
            transaction_type=payload.transaction_type,
            lines=[line.model_dump() for line in payload.lines],
            source_audit_id=payload.source_audit_id,
            enqueue_mode=payload.enqueue_mode,
            actor=user.username,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/hal9000/accounting/posting-queue", response_model=AccountingPostingQueueListResponse)
async def api_hal9000_accounting_posting_queue_list(
    limit: int = Query(10, ge=1, le=100),
    cursor: str | None = Query(None),
    status: PostingQueueStatus | None = Query(None),
    user: AuthenticatedUser = Depends(require_roles("hal:operator")),
):
    del user
    try:
        return _serialize_posting_queue_list_payload(list_accounting_posting_queue(limit=limit, cursor=cursor, status=status))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/hal9000/accounting/posting-queue/metrics", response_model=AccountingPostingQueueMetricsResponse)
async def api_hal9000_accounting_posting_queue_metrics(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    return get_accounting_posting_queue_summary()


@router.get("/api/hal9000/accounting/posting-queue/activity", response_model=AccountingPostingQueueActivityListResponse)
async def api_hal9000_accounting_posting_queue_activity(limit: int = Query(10, ge=1, le=25), user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    return list_recent_accounting_posting_queue_activity(limit)


@router.post("/api/hal9000/accounting/posting-queue/{queue_id}/review", response_model=AccountingPostingQueueEntryResponse)
async def api_hal9000_accounting_posting_queue_review(queue_id: str, payload: AccountingPostingQueueReviewRequest, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    try:
        return _serialize_posting_queue_entry_payload(review_accounting_posting_queue_entry(
            queue_id=queue_id,
            action=payload.action,
            review_note=payload.review_note,
            actor=user.username,
        ))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
