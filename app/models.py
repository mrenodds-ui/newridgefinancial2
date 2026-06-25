from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.hal.posting_queue import JournalDraftStatus, PostingQueueEnqueueMode, PostingQueueReviewAction, PostingQueueStatus


class KPIResponse(BaseModel):
    kpis: list[str]


class MessageResponse(BaseModel):
    message: str


class StatusResponse(BaseModel):
    status: str


class PullSectionResponse(BaseModel):
    enabled: bool
    status: str
    summary: str
    source_dir: str = ""
    import_dir: str = ""
    scanned: int = 0
    copied: int = 0
    files: list[str] = Field(default_factory=list)
    last_refresh_utc: str = ""
    last_error: str = ""


class ReportPullStatusResponse(BaseModel):
    daily_refresh_enabled: bool
    last_refresh_date: str = ""
    status: dict[str, PullSectionResponse] = Field(default_factory=dict)


class PhasesResponse(BaseModel):
    phases: list[str] = Field(default_factory=list)


class DeltaResponse(BaseModel):
    delta: str


class HalCapabilityTierRule(BaseModel):
    tier: str
    priority: str
    label: str
    scope: str
    execution_policy: str
    escalation_rule: str


class HalAccessPolicy(BaseModel):
    mode: str
    auth_requirement: str
    network_boundary: str
    audited: bool
    workspace_root: str = ""
    activity_log_path: str = ""
    review_plan_directory: str = ""
    allowed_sources: list[str]
    disallowed_actions: list[str]
    capability_hierarchy: list[HalCapabilityTierRule] = Field(default_factory=list)


class HalContextSnippet(BaseModel):
    source_id: str
    title: str
    category: str
    excerpt: str


class HalSanitizationFinding(BaseModel):
    label: str
    replacement: str


class HalAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    summary: dict[str, object] | None = None
    session_id: str | None = Field(default=None, min_length=1, max_length=128)


class HalReviewAction(BaseModel):
    action_id: str
    action_type: str
    target_device: str
    target_value: int | float
    human_review_required: bool = True
    status: str
    title: str
    confirmation_message: str


class HalResponseVoiceProfile(BaseModel):
    lane: str
    label: str
    tone: str
    style_notes: list[str] = Field(default_factory=list)


class HalGovernanceNote(BaseModel):
    label: str
    detail: str


class HalAskResponse(BaseModel):
    mode: str
    answer: str
    sanitized_question: str
    sanitization_findings: list[HalSanitizationFinding] = Field(default_factory=list)
    retrieved_context: list[HalContextSnippet] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    audit_id: str
    access_policy: HalAccessPolicy
    review_actions: list[HalReviewAction] = Field(default_factory=list)
    voice_profile: HalResponseVoiceProfile
    governance_notes: list[HalGovernanceNote] = Field(default_factory=list)
    local_ai_unavailable: str | None = None


class HalInsuranceNarrativeRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class HalInsuranceNarrativeResponse(BaseModel):
    mode: str
    matched: bool
    narrative: str
    sanitized_question: str
    sanitization_findings: list[HalSanitizationFinding] = Field(default_factory=list)
    supporting_context: list[HalContextSnippet] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    audit_id: str
    access_policy: HalAccessPolicy
    voice_profile: HalResponseVoiceProfile
    governance_notes: list[HalGovernanceNote] = Field(default_factory=list)


class HalFastReviewCheckRequest(BaseModel):
    source_text: str = Field(min_length=10, max_length=32000)
    review_task: str = Field(default="insurance_narrative_review", min_length=3, max_length=200)
    packet_id: str | None = Field(default=None, max_length=128)


class HalFastReviewStructuredReview(BaseModel):
    missing_data: list[str] = Field(default_factory=list)
    citation_issues: list[str] = Field(default_factory=list)
    possible_invented_facts: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    recommended_action: str
    ready_for_human_review: bool


class HalFastReviewCheckResponse(BaseModel):
    status: Literal["ok", "lane_unavailable", "parse_error", "error"]
    profile: str
    model: str
    base_url: str
    review: HalFastReviewStructuredReview | None = None
    raw_output: str | None = None
    latency_seconds: float | None = None
    parse_error: str | None = None
    error: str | None = None
    audit_id: str
    guardrails: list[str] = Field(default_factory=list)
    packet_id: str | None = None


class HalPatientDossierRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class HalPatientDossierResponse(BaseModel):
    mode: str
    matched: bool
    summary: str
    sanitized_question: str
    sanitization_findings: list[HalSanitizationFinding] = Field(default_factory=list)
    supporting_context: list[HalContextSnippet] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    audit_id: str
    access_policy: HalAccessPolicy
    voice_profile: HalResponseVoiceProfile
    governance_notes: list[HalGovernanceNote] = Field(default_factory=list)


class HalChartPlanRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class HalChartPlanResponse(BaseModel):
    mode: str
    status: Literal["pending_human_review"]
    question: str
    request_json: dict[str, object] = Field(default_factory=dict)
    request_file_path: str
    planned_output_path: str
    review_plan_path: str
    preview_summary: str
    flag_for_review: bool = False
    review_reason: str | None = None
    alert_reason: str | None = None
    guardrails: list[str] = Field(default_factory=list)
    audit_id: str
    access_policy: HalAccessPolicy


class HalChartPlanApprovalRequest(BaseModel):
    review_plan_path: str = Field(min_length=3, max_length=2000)


class HalChartPlanApprovalResponse(BaseModel):
    mode: str
    status: Literal["approved_and_rendered"]
    review_plan_path: str
    request_json: dict[str, object] = Field(default_factory=dict)
    rendered_output_path: str
    flag_for_review: bool = False
    review_reason: str | None = None
    alert_reason: str | None = None
    guardrails: list[str] = Field(default_factory=list)
    audit_id: str
    access_policy: HalAccessPolicy


class HalChartPlanListItemResponse(BaseModel):
    review_plan_path: str
    created_at_utc: str
    status: str
    question: str
    title: str
    chart_type: str
    planned_output_path: str
    rendered_output_path: str | None = None
    audit_id: str


class HalChartPlanListResponse(BaseModel):
    count: int
    limit: int
    status: str | None = None
    items: list[HalChartPlanListItemResponse] = Field(default_factory=list)


class JournalLine(BaseModel):
    account_code: str
    account_name: str
    debit: float = Field(default=0, ge=0)
    credit: float = Field(default=0, ge=0)
    memo: str | None = None


class JournalDraftRequest(BaseModel):
    description: str = Field(min_length=3, max_length=2000)
    transaction_date: date
    accounting_period: str = Field(min_length=7, max_length=7)
    amount: float = Field(gt=0)
    context: dict[str, object] = Field(default_factory=dict)


class JournalDraftValidation(BaseModel):
    balanced: bool
    debit_total: float
    credit_total: float
    open_period: bool
    account_validation_passed: bool
    amount_validation_passed: bool = True
    issues: list[str] = Field(default_factory=list)


class JournalDraftResponse(BaseModel):
    mode: str
    summary: str
    lines: list[JournalLine] = Field(default_factory=list)
    validation: JournalDraftValidation
    supporting_context: list[HalContextSnippet] = Field(default_factory=list)
    review_required: bool = True
    review_plan_path: str | None = None
    draft_status: JournalDraftStatus = "draft_only"
    queue_id: str | None = None
    queue_status: PostingQueueStatus | None = None
    enqueue_error: str | None = None
    local_ai_unavailable: str | None = None
    audit_id: str
    access_policy: HalAccessPolicy


class AccountingPostingQueueRequest(BaseModel):
    description: str = Field(min_length=3, max_length=2000)
    transaction_date: date
    accounting_period: str = Field(min_length=7, max_length=7)
    amount: float = Field(gt=0)
    transaction_type: str | None = None
    lines: list[JournalLine] = Field(default_factory=list)
    source_audit_id: str = Field(min_length=4, max_length=100)
    enqueue_mode: PostingQueueEnqueueMode | None = None


class AccountingPostingQueueEntryResponse(BaseModel):
    queue_id: str
    created_at_utc: str
    actor: str
    target_system: str
    status: PostingQueueStatus
    description: str
    transaction_date: str
    accounting_period: str
    amount: float
    transaction_type: str | None = None
    source_audit_id: str
    enqueue_mode: PostingQueueEnqueueMode | None = None
    lines: list[JournalLine] = Field(default_factory=list)
    validation: JournalDraftValidation
    reviewer_actor: str | None = None
    reviewed_at_utc: str | None = None
    review_note: str | None = None
    review_required: bool = True
    review_plan_path: str | None = None
    audit_id: str | None = None


class AccountingPostingQueueActivityResponse(BaseModel):
    queue_id: str
    created_at_utc: str
    actor: str
    target_system: str
    status: PostingQueueStatus
    description: str
    transaction_date: str
    accounting_period: str
    amount: float
    transaction_type: str | None = None
    source_audit_id: str
    enqueue_mode: PostingQueueEnqueueMode | None = None
    reviewer_actor: str | None = None
    reviewed_at_utc: str | None = None
    review_note: str | None = None
    review_required: bool = True


class AccountingPostingQueueListResponse(BaseModel):
    count: int
    total_count: int
    limit: int
    cursor: str | None = None
    next_cursor: str | None = None
    range_start: int = 0
    range_end: int = 0
    status: PostingQueueStatus | None = None
    items: list[AccountingPostingQueueEntryResponse] = Field(default_factory=list)


class AccountingPostingQueueActivityListResponse(BaseModel):
    count: int
    limit: int
    items: list[AccountingPostingQueueActivityResponse] = Field(default_factory=list)


class AccountingPostingQueueMetricsResponse(BaseModel):
    total_count: int
    pending_review_count: int
    approved_count: int
    rejected_count: int


class AccountingPostingQueueReviewRequest(BaseModel):
    action: PostingQueueReviewAction
    review_note: str | None = Field(default=None, max_length=2000)


class AccountingPolicyAnswerRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    topic: str | None = None
    accounting_standard: str | None = None


class AccountingPolicyCitation(BaseModel):
    source_id: str
    title: str
    excerpt: str


class AccountingPolicyAnswerResponse(BaseModel):
    mode: str
    answer: str
    accounting_standard: str | None = None
    citations: list[AccountingPolicyCitation] = Field(default_factory=list)
    confidence: str
    review_required: bool = True
    audit_id: str
    access_policy: HalAccessPolicy
    voice_profile: HalResponseVoiceProfile
    governance_notes: list[HalGovernanceNote] = Field(default_factory=list)


class HalPageResponse(BaseModel):
    message: str
    mode: str
    access_policy: HalAccessPolicy


class HalIndexRefreshResponse(BaseModel):
    message: str
    document_count: int
    source_count: int
    refreshed_at_utc: str
    storage_path: str
    vector_path: str
    backend: str
    embedding_provider: str
    mode: str


class LocalAccountingDocumentResponse(BaseModel):
    id: int
    source_path: str
    source_name: str
    sha256: str
    processed_at_utc: str
    extractor: str
    document_type: str
    vendor_name: str | None = None
    invoice_number: str | None = None
    document_date: str | None = None
    total_amount: float | None = None
    subtotal_amount: float | None = None
    tax_amount: float | None = None
    currency: str
    text_preview: str
    raw_text: str = ""
    correction_flags: list[str] = Field(default_factory=list)
    confidence_label: str = "manual review"
    review_required: bool = False


class LocalAccountingDocumentListResponse(BaseModel):
    count: int
    limit: int
    document_type: str | None = None
    search: str | None = None
    review_only: bool = False
    items: list[LocalAccountingDocumentResponse] = Field(default_factory=list)


class HalDocumentRagDocumentResponse(BaseModel):
    document_id: str
    source_name: str
    stored_path: str
    mime_type: str
    sha256: str
    uploaded_at_utc: str
    uploaded_by: str
    page_count: int = 0
    chunk_count: int = 0
    content_char_count: int = 0


class HalDocumentRagDocumentListResponse(BaseModel):
    count: int
    limit: int
    search: str | None = None
    items: list[HalDocumentRagDocumentResponse] = Field(default_factory=list)


class HalDocumentRagUploadResponse(BaseModel):
    message: str
    document: HalDocumentRagDocumentResponse


class HalDocumentRagAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=8)


class HalDocumentRagAskResponse(BaseModel):
    mode: str
    answer: str
    sanitized_question: str
    sanitization_findings: list[HalSanitizationFinding] = Field(default_factory=list)
    retrieved_context: list[HalContextSnippet] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    audit_id: str
    document_count: int = 0
    grounded: bool = False


class HalStatusResponse(BaseModel):
    mode: str
    document_count: int
    storage_path: str
    vector_path: str
    backend: str
    embedding_provider: str
    financial_sources: dict[str, object] = Field(default_factory=dict)
    operating_picture: dict[str, object] = Field(default_factory=dict)


class HalShellCommandEntry(BaseModel):
    command_id: str
    summary: str
    invocation_type: Literal["api_endpoint", "npm_script"]
    target: str
    working_directory: str
    category: str
    confirmation_required: bool = False


class HalShellCommandsResponse(BaseModel):
    purpose: str
    playbook_active: bool = True
    verification_endpoint: str
    blocked_actions: list[str] = Field(default_factory=list)
    confirmation_required_actions: list[str] = Field(default_factory=list)
    registered_commands: list[HalShellCommandEntry] = Field(default_factory=list)
    suggested_command_id: str | None = None
    suggestion_reason: str | None = None


class HalAutonomyProfileResponse(BaseModel):
    mode: str
    execution_loop: dict[str, object] = Field(default_factory=dict)
    function_calling: dict[str, object] = Field(default_factory=dict)
    sandbox: dict[str, object] = Field(default_factory=dict)
    state_management: dict[str, object] = Field(default_factory=dict)


class HalAutonomyRunRequest(BaseModel):
    objective: str = Field(min_length=3, max_length=2000)
    max_steps: int = Field(default=3, ge=1, le=12)


class HalAutonomyRunResponse(BaseModel):
    run_id: str
    created_at_utc: str
    updated_at_utc: str
    actor: str
    objective: str
    sanitized_objective: str
    status: Literal["queued", "running", "completed", "blocked"]
    max_steps: int
    current_step: int
    sandbox_mode: str
    working_directory: str
    loop_mode: str
    plan: list[dict[str, object]] = Field(default_factory=list)
    activity: list[dict[str, object]] = Field(default_factory=list)
    next_action: dict[str, object] = Field(default_factory=dict)
    activity_count: int = 0
    completion_summary: str | None = None


class HalAutonomyRunListResponse(BaseModel):
    count: int
    items: list[HalAutonomyRunResponse] = Field(default_factory=list)


class HalAuditEntryResponse(BaseModel):
    audit_id: str
    created_at_utc: str
    actor: str
    mode: str
    sanitized_question: str
    retrieval_ids: list[str] = Field(default_factory=list)
    response_summary: str


class HalAuditListResponse(BaseModel):
    count: int
    items: list[HalAuditEntryResponse] = Field(default_factory=list)


class HalStagedImportFileRequest(BaseModel):
    file_name: str = Field(min_length=3, max_length=120)
    mime_type: str = Field(min_length=3, max_length=120)
    content: str = Field(min_length=1, max_length=2_000_000)


class HalStagedImportRequest(BaseModel):
    files: list[HalStagedImportFileRequest] = Field(default_factory=list, min_length=1, max_length=8)


class HalStagedImportFileResponse(BaseModel):
    file_name: str
    bytes_written: int
    destination_path: str


class HalStagedImportResponse(BaseModel):
    message: str
    actor: str
    file_count: int
    files: list[HalStagedImportFileResponse] = Field(default_factory=list)


class ControlModelSummary(BaseModel):
    name: str
    family: str | None = None
    parameter_size: str | None = None
    context_length: int | None = None
    capabilities: list[str] = Field(default_factory=list)
    heuristic_tags: list[str] = Field(default_factory=list)


class ControlLaneRuntimeSummary(BaseModel):
    lane: str
    base_url: str
    model: str
    api_reachable: bool
    installed: bool = False
    running: bool = False
    model_count: int = 0
    installed_models: list[ControlModelSummary] = Field(default_factory=list)
    error: str | None = None
    warning: str | None = None


class ControlRuntimeStatusResponse(BaseModel):
    base_url: str
    api_reachable: bool
    installed: bool
    running: bool
    model_count: int
    installed_models: list[ControlModelSummary] = Field(default_factory=list)
    suggested_defaults: dict[str, str] = Field(default_factory=dict)
    warning: str | None = None
    lanes: dict[str, ControlLaneRuntimeSummary] = Field(default_factory=dict)


class ControlRouteRequest(BaseModel):
    objective: str = Field(min_length=3, max_length=2000)
    task_kind: Literal["chat", "coding", "analysis", "dashboard", "vision", "automation", "second_opinion"] = "chat"
    preferred_model: str | None = None
    candidate_models: list[str] = Field(default_factory=list)
    requires_vision: bool = False
    requires_tools: bool = False
    quality_priority: Literal["speed", "balanced", "quality"] = "balanced"
    max_context_tokens: int | None = Field(default=None, ge=1, le=500_000)


class ControlRouteAlternative(BaseModel):
    model: ControlModelSummary
    score: float
    reasons: list[str] = Field(default_factory=list)


class ControlRouteResponse(BaseModel):
    available: bool
    task_kind: str
    quality_priority: str
    selected_model: ControlModelSummary | None = None
    fallback_model: str | None = None
    litellm_model_alias: str | None = None
    litellm_proxy_base_url: str | None = None
    reasoning: list[str] = Field(default_factory=list)
    alternatives: list[ControlRouteAlternative] = Field(default_factory=list)
    runtime: ControlRuntimeStatusResponse


class ControlScoreRubric(BaseModel):
    required_terms: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    min_words: int = Field(default=0, ge=0, le=10_000)
    max_words: int | None = Field(default=None, ge=1, le=10_000)
    minimum_score: int = Field(default=70, ge=0, le=100)


class ControlScoreRequest(BaseModel):
    objective: str = Field(min_length=3, max_length=2000)
    model: str = Field(min_length=1, max_length=200)
    response_text: str = Field(min_length=1, max_length=100_000)
    rubric: ControlScoreRubric = Field(default_factory=ControlScoreRubric)


class ControlScoreResponse(BaseModel):
    passed: bool
    score: float
    word_count: int
    sentence_count: int
    required_hits: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    forbidden_hits: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ControlWorkflowPreviewRequest(ControlRouteRequest):
    score_threshold: int = Field(default=75, ge=0, le=100)
    requires_human_approval: bool = True


class ControlWorkflowStep(BaseModel):
    step_id: str
    title: str
    purpose: str
    endpoint: str
    approval_required: bool = False


class ControlWorkflowPreviewResponse(BaseModel):
    workflow_id: str
    objective: str
    task_kind: str
    recommended_model: str | None = None
    automation_ready: bool
    score_threshold: int
    blocking_issues: list[str] = Field(default_factory=list)
    steps: list[ControlWorkflowStep] = Field(default_factory=list)
    runtime: ControlRuntimeStatusResponse


class LiteLLMRouteAliasResponse(BaseModel):
    alias: str
    purpose: str
    upstream_models: list[str] = Field(default_factory=list)
    fallback_aliases: list[str] = Field(default_factory=list)


class LiteLLMProxyConfigResponse(BaseModel):
    proxy_base_url: str
    config_path: str
    routing_strategy: str
    auth_expected: bool = False
    startup_command: str
    model_aliases: list[LiteLLMRouteAliasResponse] = Field(default_factory=list)
    openai_compatible_example: dict[str, object] = Field(default_factory=dict)
    config_yaml: str


class LiteLLMProxyStatusResponse(BaseModel):
    proxy_base_url: str
    health_endpoint: str
    config_path: str
    reachable: bool
    auth_configured: bool = False
    configured_aliases: list[LiteLLMRouteAliasResponse] = Field(default_factory=list)
    exposed_models: list[str] = Field(default_factory=list)
    startup_command: str
    error: str | None = None


class FinancialSummaryLatestArResponse(BaseModel):
    as_of_date: str
    total_ar: float
    insurance_ar: float
    patient_ar: float
    current_balance: float
    balance_30: float
    balance_60: float
    balance_90: float
    credit_balance: float
    source: str = "softdent"
    available: bool = True


class FinancialSummaryMonthlyKpiResponse(BaseModel):
    month: str | None = None
    year_month: str | None = None
    gross_production: float | None = None
    net_production: float | None = None
    collections: float | None = None
    production_adjustments: float | None = None
    collection_adjustments: float | None = None
    receivables_change: float | None = None
    deposit_total: float | None = None
    new_patients_seen: float | None = None
    existing_patients_seen: float | None = None
    collection_rate: float | None = None
    calendar_year: int | None = None
    calendar_month: int | None = None


class FinancialSummaryLatestDailyKpiResponse(BaseModel):
    production: float | None = None
    collections: float | None = None


class FinancialSummaryQuickBooksStatusResponse(BaseModel):
    status: str | None = None
    message: str | None = None
    lastCheckedAtUtc: str | None = None
    lastImportedAtUtc: str | None = None
    lastError: str | None = None
    rowCounts: dict[str, int] | None = None


class FinancialSummaryQuickBooksExpenseCategoryResponse(BaseModel):
    expense_category: str | None = None
    account_name: str | None = None
    total_amount: float | str | None = None
    transaction_count: float | str | None = None
    first_transaction_date: str | None = None
    last_transaction_date: str | None = None
    last_imported_at_utc: str | None = None


class FinancialSummaryQuickBooksMonthlyExpenseResponse(BaseModel):
    year_month: str | None = None
    expense_total: float | str | None = None
    transaction_count: float | str | None = None
    last_imported_at_utc: str | None = None


class FinancialSummaryQuickBooksProfitLossResponse(BaseModel):
    year_month: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    income_total: float | str | None = None
    expense_total: float | str | None = None
    net_income: float | str | None = None
    cogs_total: float | str | None = None
    payroll_total: float | str | None = None
    rent_total: float | str | None = None
    supplies_total: float | str | None = None
    lab_total: float | str | None = None
    merchant_fees_total: float | str | None = None
    utilities_total: float | str | None = None
    depreciation: float | str | None = None
    amortization: float | str | None = None
    interest: float | str | None = None
    taxes: float | str | None = None
    base_ebitda_candidate: float | str | None = None
    last_imported_at_utc: str | None = None


class FinancialSourceReviewItemResponse(BaseModel):
    sourceSystem: str
    status: str
    summary: str
    confidenceLabel: str
    reviewRequired: bool
    reviewFlags: list[str] = Field(default_factory=list)
    lastVerifiedAt: str | None = None
    metrics: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class FinancialSummarySourceReviewResponse(BaseModel):
    quickBooks: FinancialSourceReviewItemResponse | None = None
    softDent: FinancialSourceReviewItemResponse | None = None
    softDentClaims: FinancialSourceReviewItemResponse | None = None


class SoftDentCoverageCountsResponse(BaseModel):
    missing: int
    limited: int
    available: int


class SoftDentCoverageRowResponse(BaseModel):
    key: str
    label: str
    status: Literal["missing", "limited", "available"]
    summary: str
    requiredReport: str
    action: str
    sourceFile: str
    sourceBackend: str
    modifiedAtUtc: str
    rowCount: int
    lastPeriod: str


class SoftDentCoverageSummaryResponse(BaseModel):
    summary: str
    counts: SoftDentCoverageCountsResponse
    rows: list[SoftDentCoverageRowResponse] = Field(default_factory=list)


class SoftDentCoverageMetricBreakdownRowResponse(BaseModel):
    label: str
    amount: float
    count: int


class SoftDentCoverageMetricResponse(BaseModel):
    label: str = ""
    available: bool = False
    sourceFile: str = ""
    sourceBackend: str = ""
    modifiedAtUtc: str = ""
    rowCount: int = 0
    itemCount: int = 0
    totalAmount: float = 0
    lastPeriod: str = ""
    summary: str = ""
    breakdown: list[SoftDentCoverageMetricBreakdownRowResponse] = Field(default_factory=list)


class SoftDentCoverageMetricsResponse(BaseModel):
    trueOutstandingClaims: SoftDentCoverageMetricResponse | None = None
    unsubmittedClaims: SoftDentCoverageMetricResponse | None = None
    insuranceIncome: SoftDentCoverageMetricResponse | None = None
    insurancePaymentDistribution: SoftDentCoverageMetricResponse | None = None
    insuranceCheckDistribution: SoftDentCoverageMetricResponse | None = None
    treatmentPlans: SoftDentCoverageMetricResponse | None = None
    paymentPlans: SoftDentCoverageMetricResponse | None = None


class ClaimsSummaryResponse(BaseModel):
    available: bool
    true_outstanding_claims_amount: float
    true_outstanding_claims_count: int
    unsubmitted_claims_amount: float
    unsubmitted_claims_count: int
    top_outstanding_payers: list[SoftDentCoverageMetricBreakdownRowResponse] = Field(default_factory=list)
    top_unsubmitted_payers: list[SoftDentCoverageMetricBreakdownRowResponse] = Field(default_factory=list)


class FinancialHealthFlagResponse(BaseModel):
    key: str
    code: str
    status: str
    sourceSystem: str
    message: str
    action: str | None = None
    configured: bool | None = None
    emitted: bool | None = None
    configuredEntity: str | None = None
    dataSyncEvidencePath: str | None = None
    sqliteTransactionRows: float | str | None = None
    sourceMode: str | None = None
    validationStatus: str | None = None


class FinancialTransactionDiagnosticsResponse(BaseModel):
    transactionConfigured: bool
    dataSyncTransactionEmitted: bool
    dataSyncEvidencePath: str | None = None
    sqliteTransactionRows: int
    sourceMode: str | None = None
    validationStatus: str | None = None
    dataExtractorBinaryPath: str | None = None
    dataExtractorBinaryModifiedAt: str | None = None
    dataExtractorBinaryExists: bool | None = None
    dataExtractorSemaphorePath: str | None = None
    dataExtractorSemaphoreModifiedAt: str | None = None
    dataExtractorSemaphoreExists: bool | None = None
    latestExtractorLogPath: str | None = None
    latestExtractorLogModifiedAt: str | None = None
    latestExtractorLogExists: bool | None = None
    hasPostUpdateExtractorLog: bool | None = None
    extractorRunEvidenceStatus: str | None = None
    summary: str | None = None


class WidgetUpdateResponse(BaseModel):
    accepted: bool
    manager: str
    run_id: str | None = None
    received_at: str
    widget_count: int
    source_count: int
    job_count: int
    auth_mode: str
    message: str


class WidgetDefinition(BaseModel):
    status: str | None = None
    title: str | None = None
    summary: str | None = None
    metrics: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class WidgetUpdateRequest(BaseModel):
    manager: str = Field(min_length=1)
    widgets: dict[str, WidgetDefinition] = Field(min_length=1, max_length=20)
    run_id: str | None = None
    generated_at: str | None = None
    sources: dict[str, object] = Field(default_factory=dict)
    jobs: dict[str, object] = Field(default_factory=dict)


class FinancialSummaryResponse(BaseModel):
    generatedAt: str | None = None
    latestSoftDentRefreshAt: str | None = None
    dataFreshnessStatus: str | None = None
    healthFlags: list[FinancialHealthFlagResponse] = Field(default_factory=list)
    transactionDiagnostics: FinancialTransactionDiagnosticsResponse | None = None
    sourceReview: FinancialSummarySourceReviewResponse | None = None
    softDentCoverage: SoftDentCoverageSummaryResponse | None = None
    softDentCoverageMetrics: SoftDentCoverageMetricsResponse | None = None
    claimsSummary: ClaimsSummaryResponse | None = None
    lastRefreshed: str | None = None
    latestDailyKpi: FinancialSummaryLatestDailyKpiResponse | None = None
    latestAr: FinancialSummaryLatestArResponse | None = None
    monthlyKpis: list[FinancialSummaryMonthlyKpiResponse] = Field(default_factory=list)
    trailing12Months: list[FinancialSummaryMonthlyKpiResponse] = Field(default_factory=list)
    calendarYearKpis: list[FinancialSummaryMonthlyKpiResponse] = Field(default_factory=list)
    fourYearMonthlyKpis: list[FinancialSummaryMonthlyKpiResponse] = Field(default_factory=list)
    providerProduction: list[dict[str, object]] = Field(default_factory=list)
    topAdaCodes: list[dict[str, object]] = Field(default_factory=list)
    quickBooksStatus: FinancialSummaryQuickBooksStatusResponse | None = None
    quickBooksExpenseCategories: list[FinancialSummaryQuickBooksExpenseCategoryResponse] = Field(default_factory=list)
    quickBooksMonthlyExpenses: list[FinancialSummaryQuickBooksMonthlyExpenseResponse] = Field(default_factory=list)
    quickBooksProfitLossSummary: list[FinancialSummaryQuickBooksProfitLossResponse] = Field(default_factory=list)
    quickBooksEbitdaCandidates: list[FinancialSummaryQuickBooksProfitLossResponse] = Field(default_factory=list)
    dataFreshnessWarnings: object | None = None
    currentMonthProduction: dict[str, object] | None = None
    currentYearProduction: dict[str, object] | None = None
    widgetFeed: dict[str, object] | None = None
