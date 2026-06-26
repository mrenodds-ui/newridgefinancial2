from __future__ import annotations

from datetime import datetime, timezone

from app.hal.office_manager_models import (
    OFFICE_MANAGER_SAFETY_DISCLAIMER,
    OfficeManagerAttentionItem,
    OfficeManagerAttentionResponse,
)
from app.hal.office_manager_task_service import get_office_manager_task_metrics
from app.hal.orchestrator import get_hal_operating_picture
from app.hal.storage import (
    count_recent_softdent_draft_audits,
    count_recent_softdent_packet_audits,
    get_accounting_posting_queue_metrics,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_end_of_day_ar_item(items: list[OfficeManagerAttentionItem], missing_codes: set[str]) -> None:
    """Add a report-derived A/R attention item from the Daily End-of-Day report.

    Keeps ``missing_softdent_ar`` when the report-derived A/R is unavailable or
    stale, and never fabricates a balance. Only an available, fresh, parsed report
    clears the missing-A/R notice.
    """
    from app.services import get_softdent_end_of_day_ar_source_status

    status = get_softdent_end_of_day_ar_source_status()
    available = bool(status.get("available"))
    parse_status = str(status.get("parse_status") or "missing")
    freshness_status = str(status.get("freshness_status") or "unknown")

    if available and parse_status in {"available", "limited"}:
        items.append(
            OfficeManagerAttentionItem(
                item_id="end-of-day-ar-available",
                category="accounts_receivable",
                severity="info",
                title="Daily End-of-Day report A/R is available",
                detail=(
                    f"Report-derived A/R is available from the Daily End-of-Day report "
                    f"(report date {status.get('report_date') or 'unknown'}). Values are report-derived, not patient-level ledger."
                ),
                action_hint="Use Patient Prep or Claims Follow-up drafts to review report-derived A/R before any office action.",
                source_key="dailyEndOfDayAr",
            )
        )
        return

    missing_codes.add("missing_softdent_ar")
    if parse_status == "stale" or freshness_status == "stale":
        items.append(
            OfficeManagerAttentionItem(
                item_id="end-of-day-ar-stale",
                category="accounts_receivable",
                severity="warning",
                title="Daily End-of-Day report A/R is stale",
                detail=str(status.get("stale_reason") or "The Daily End-of-Day report A/R is stale and must not be quoted as current."),
                action_hint="Refresh the Daily End-of-Day report export before relying on report-derived A/R.",
                source_key="dailyEndOfDayAr",
                missing_data_codes=["missing_softdent_ar"],
            )
        )
        return

    items.append(
        OfficeManagerAttentionItem(
            item_id="end-of-day-ar-unavailable",
            category="accounts_receivable",
            severity="info",
            title="A/R is unavailable",
            detail="No verified A/R source is available. HAL will not show an A/R balance or $0 without a verified source.",
            action_hint="Stage the approved SoftDent Daily End-of-Day report export to unlock report-derived A/R.",
            source_key="dailyEndOfDayAr",
            missing_data_codes=["missing_softdent_ar"],
        )
    )


def build_office_manager_attention(*, financial_summary: dict[str, object] | None = None) -> OfficeManagerAttentionResponse:
    summary = financial_summary if isinstance(financial_summary, dict) else {}
    items: list[OfficeManagerAttentionItem] = []
    missing_codes: set[str] = set()

    claims_summary = summary.get("claimsSummary") if isinstance(summary.get("claimsSummary"), dict) else {}
    health_flags = summary.get("healthFlags") if isinstance(summary.get("healthFlags"), list) else []
    softdent_coverage = summary.get("softDentCoverage") if isinstance(summary.get("softDentCoverage"), dict) else {}
    source_review = summary.get("sourceReview") if isinstance(summary.get("sourceReview"), dict) else {}
    softdent_review = source_review.get("softDent") if isinstance(source_review.get("softDent"), dict) else {}
    quickbooks_review = source_review.get("quickBooks") if isinstance(source_review.get("quickBooks"), dict) else {}

    unsubmitted_count = int(claims_summary.get("unsubmitted_claims_count") or 0)
    outstanding_count = int(claims_summary.get("true_outstanding_claims_count") or 0)
    if claims_summary.get("available"):
        if unsubmitted_count > 0:
            items.append(
                OfficeManagerAttentionItem(
                    item_id="claims-unsubmitted",
                    category="claims_follow_up",
                    severity="warning" if unsubmitted_count >= 3 else "info",
                    title="Unsubmitted claims need follow-up",
                    detail=f"{unsubmitted_count} unsubmitted claim(s) are visible from approved aggregate exports.",
                    action_hint="Review claims follow-up and create a draft checklist for staff review.",
                    source_key="claimsSummary.unsubmittedClaims",
                    count=unsubmitted_count,
                )
            )
        if outstanding_count > 0:
            items.append(
                OfficeManagerAttentionItem(
                    item_id="claims-outstanding",
                    category="claims_follow_up",
                    severity="warning" if outstanding_count >= 3 else "info",
                    title="Outstanding claims need payer follow-up",
                    detail=f"{outstanding_count} outstanding claim(s) are visible from approved aggregate exports.",
                    action_hint="Use Claims Follow-up to prepare a local review draft.",
                    source_key="claimsSummary.trueOutstandingClaims",
                    count=outstanding_count,
                )
            )
    else:
        missing_codes.add("missing_softdent_claims_export")
        items.append(
            OfficeManagerAttentionItem(
                item_id="claims-unavailable",
                category="claims_follow_up",
                severity="warning",
                title="Claims follow-up data is unavailable",
                detail="Approved aggregate claims exports are required before claims aging can drive office-manager attention.",
                action_hint="Stage approved outstanding and unsubmitted claims exports into the SoftDent import lane.",
                source_key="claimsSummary",
                missing_data_codes=["missing_softdent_claims_export"],
            )
        )

    coverage_counts = softdent_coverage.get("counts") if isinstance(softdent_coverage.get("counts"), dict) else {}
    missing_coverage = int(coverage_counts.get("missing") or 0)
    limited_coverage = int(coverage_counts.get("limited") or 0)
    if missing_coverage or limited_coverage:
        items.append(
            OfficeManagerAttentionItem(
                item_id="softdent-coverage-gaps",
                category="source_health",
                severity="warning" if missing_coverage else "info",
                title="SoftDent export coverage has gaps",
                detail=f"{missing_coverage} missing and {limited_coverage} limited SoftDent report lane(s) remain visible to HAL.",
                action_hint="Refresh or stage the missing SoftDent exports before relying on office-manager summaries.",
                source_key="softDentCoverage",
                count=missing_coverage + limited_coverage,
            )
        )

    softdent_status = str(softdent_review.get("status") or "").lower()
    if softdent_status in {"stale", "missing", "limited", "error"}:
        items.append(
            OfficeManagerAttentionItem(
                item_id="softdent-source-health",
                category="source_health",
                severity="warning",
                title="SoftDent source needs attention",
                detail=str(softdent_review.get("summary") or "SoftDent source health is not current."),
                action_hint="Review SoftDent export freshness before patient prep or claims follow-up.",
                source_key="sourceReview.softDent",
            )
        )

    quickbooks_status = str(quickbooks_review.get("status") or "").lower()
    if quickbooks_status in {"stale", "missing", "limited", "error"}:
        items.append(
            OfficeManagerAttentionItem(
                item_id="quickbooks-source-health",
                category="revenue",
                severity="warning",
                title="QuickBooks source needs attention",
                detail=str(quickbooks_review.get("summary") or "QuickBooks source health is not current."),
                action_hint="Review revenue and posting-queue inputs before month-end office-manager summaries.",
                source_key="sourceReview.quickBooks",
            )
        )

    for flag in health_flags:
        if not isinstance(flag, dict):
            continue
        label = str(flag.get("label") or flag.get("key") or "Health flag")
        detail = str(flag.get("detail") or flag.get("message") or flag.get("summary") or "")
        severity = str(flag.get("severity") or "warning").lower()
        mapped_severity = "critical" if severity in {"critical", "error"} else "warning" if severity == "warning" else "info"
        items.append(
            OfficeManagerAttentionItem(
                item_id=f"health-{label.lower().replace(' ', '-')[:40]}",
                category="system_health",
                severity=mapped_severity,
                title=label,
                detail=detail or "A financial health flag is active.",
                action_hint="Review the source health panel before acting on this item.",
                source_key="healthFlags",
            )
        )

    try:
        posting_metrics = get_accounting_posting_queue_metrics()
        pending_review = int(posting_metrics.get("pending_review_count") or 0)
        if pending_review > 0:
            items.append(
                OfficeManagerAttentionItem(
                    item_id="posting-queue-pending",
                    category="revenue",
                    severity="info",
                    title="Accounting posting queue needs review",
                    detail=f"{pending_review} local posting-queue item(s) remain pending human review.",
                    action_hint="Review the accounting posting queue before month-end close.",
                    source_key="posting_queue.metrics",
                    count=pending_review,
                )
            )
    except Exception:
        pass

    draft_count = count_recent_softdent_draft_audits(since_hours=168)
    if draft_count > 0:
        items.append(
            OfficeManagerAttentionItem(
                item_id="drafts-awaiting-review",
                category="drafts_review",
                severity="info",
                title="Drafts awaiting human review",
                detail=f"{draft_count} recent Phase 2 draft artifact(s) were created and still require human review.",
                action_hint="Open Drafts for Review and confirm draft-only, not_submitted status.",
                source_key="softdent_draft_audits",
                count=draft_count,
            )
        )

    packet_count = count_recent_softdent_packet_audits(since_hours=168)
    if packet_count > 0:
        items.append(
            OfficeManagerAttentionItem(
                item_id="local-packets-ready",
                category="local_packets",
                severity="info",
                title="Local packets ready for internal use",
                detail=f"{packet_count} recent Phase 3 local packet(s) are approved for internal office use only.",
                action_hint="Review approved local packets; they remain not_submitted with no external delivery.",
                source_key="softdent_packet_audits",
                count=packet_count,
            )
        )

    task_metrics = get_office_manager_task_metrics()
    open_tasks = int(task_metrics.get("open_count") or 0) + int(task_metrics.get("in_progress_count") or 0) + int(task_metrics.get("blocked_count") or 0)
    if open_tasks > 0:
        items.append(
            OfficeManagerAttentionItem(
                item_id="local-office-tasks-open",
                category="local_tasks",
                severity="warning" if int(task_metrics.get("urgent_open_count") or 0) > 0 else "info",
                title="Unresolved local office tasks",
                detail=f"{open_tasks} local office task(s) remain open, in progress, or blocked.",
                action_hint="Work local tasks inside this app only. No SoftDent writeback or external delivery.",
                source_key="office_manager_tasks",
                count=open_tasks,
            )
        )

    operating_picture = get_hal_operating_picture()
    backend_runtime = operating_picture.get("backend_runtime") if isinstance(operating_picture.get("backend_runtime"), dict) else {}
    frontend_runtime = operating_picture.get("frontend_runtime") if isinstance(operating_picture.get("frontend_runtime"), dict) else {}
    if backend_runtime.get("api_reachable") is False:
        items.append(
            OfficeManagerAttentionItem(
                item_id="backend-lane-unavailable",
                category="system_health",
                severity="warning",
                title="Backend model lane is unavailable",
                detail=str(operating_picture.get("summary") or "Backend lane health check failed."),
                action_hint="Use deterministic facts and local drafts while the backend lane is unavailable.",
                source_key="operating_picture.backend_runtime",
            )
        )
    if frontend_runtime.get("api_reachable") is False:
        items.append(
            OfficeManagerAttentionItem(
                item_id="frontend-lane-unavailable",
                category="system_health",
                severity="warning",
                title="Frontend model lane is unavailable",
                detail="Frontend lane health check failed.",
                action_hint="Primary HAL answers may still use backend-verified facts.",
                source_key="operating_picture.frontend_runtime",
            )
        )

    missing_codes.update(
        {
            "missing_treatment_plan_export",
            "missing_hygiene_recall_export",
            "missing_vendor_tracker_source",
        }
    )

    _append_end_of_day_ar_item(items, missing_codes)

    items.extend(
        [
            OfficeManagerAttentionItem(
                item_id="treatment-plan-unavailable",
                category="treatment_plan",
                severity="info",
                title="Treatment plan follow-up is limited",
                detail="No approved treatment-plan export source is available yet. HAL will not fabricate unscheduled treatment data.",
                action_hint="Use local tasks or drafts until a real treatment-plan export is approved.",
                source_key="treatment_plan",
                missing_data_codes=["missing_treatment_plan_export"],
            ),
            OfficeManagerAttentionItem(
                item_id="hygiene-recall-unavailable",
                category="hygiene_recall",
                severity="info",
                title="Hygiene and recall follow-up is limited",
                detail="No approved recall or hygiene export source is available yet. HAL will not fabricate overdue recall data.",
                action_hint="Track recall follow-up with local office tasks until a real export source exists.",
                source_key="hygiene_recall",
                missing_data_codes=["missing_hygiene_recall_export"],
            ),
            OfficeManagerAttentionItem(
                item_id="vendor-tracker-local-only",
                category="vendor",
                severity="info",
                title="Vendor and software issues are local-only",
                detail="Vendor/software issue tracking uses local records in this app only. No external ticket submission is performed.",
                action_hint="Create local vendor follow-up tasks and local review artifacts as needed.",
                source_key="vendor_tracker",
                missing_data_codes=["missing_vendor_tracker_source"],
            ),
        ]
    )

    summary_text = (
        f"{len(items)} office-manager attention item(s) are visible. "
        "All actions remain local only, not submitted, and not written to SoftDent."
    )
    return OfficeManagerAttentionResponse(
        generated_at_utc=_utc_now(),
        summary=summary_text,
        safety_disclaimer=OFFICE_MANAGER_SAFETY_DISCLAIMER,
        items=items,
        missing_data_codes=sorted(missing_codes),
    )
