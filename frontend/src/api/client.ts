import { ZodError, z } from "zod";
import { config } from "../config";
import type { PostingQueueEnqueueMode } from "../utils/postingQueueLineage";
import type { PostingQueueReviewAction, PostingQueueStatus } from "../utils/postingQueueStatus";
import { getApiAuthenticatedUsername, getApiAuthorizationHeader, notifyApiAuthRequired, setApiAuthenticatedUsername } from "./basicAuth";
import type { components } from "./generated/backend-openapi";
import {
  type AccountingPolicyAnswerResponse,
  type AccountingPostingQueueActivityListResponse,
  type AccountingPostingQueueEntry,
  type AccountingPostingQueueListResponse,
  type AccountingPostingQueueMetricsResponse,
  type AdminSummaryResponse,
  type DocumentRagAskResponse,
  type DocumentRagDocumentListResponse,
  type DocumentRagUploadResponse,
  type HalAskResponse,
  type HalAuditListResponse,
  type HalChartPlanApprovalResponse,
  type HalChartPlanListResponse,
  type HalChartPlanResponse,
  type HalInsuranceNarrativeResponse,
  type HalPatientDossierResponse,
  type HalStatusResponse,
  type HealthResponse,
  type JournalDraftResponse,
  type KpiResponse,
  type LocalAccountingDocumentListResponse,
  type MonitorMutationExecutionResult,
  authSessionSchema,
  accountingPolicyAnswerResponseSchema,
  accountingPostingQueueActivityListSchema,
  accountingPostingQueueEntrySchema,
  accountingPostingQueueListSchema,
  accountingPostingQueueMetricsSchema,
  adminSummarySchema,
  documentRagAskResponseSchema,
  documentRagDocumentListSchema,
  documentRagUploadResponseSchema,
  halAskResponseSchema,
  halAuditListSchema,
  halChartPlanApprovalResponseSchema,
  halChartPlanListResponseSchema,
  halChartPlanResponseSchema,
  halInsuranceNarrativeSchema,
  halPatientDossierSchema,
  halStatusSchema,
  healthSchema,
  journalDraftResponseSchema,
  kpiResponseSchema,
  localAccountingDocumentListSchema,
  monitorMutationExecutionResultSchema,
  insuranceNarrativeWorkflowResultSchema,
  officeManagerAttentionResponseSchema,
  officeManagerTaskListResponseSchema,
  officeManagerTaskMetricsResponseSchema,
  officeManagerTaskResponseSchema,
  claimPacketReadinessResponseSchema,
  softDentEndOfDayArSchema,
  softDentDraftArtifactSchema,
  softDentLocalPacketArtifactSchema,
  type SoftDentDraftArtifact,
  type SoftDentDraftRequest,
  type SoftDentEndOfDayAr,
  type SoftDentLocalPacketArtifact,
  type SoftDentLocalPacketRequest,
  type OfficeManagerAttentionResponse,
  type OfficeManagerTaskCreateRequest,
  type OfficeManagerTaskListResponse,
  type OfficeManagerTaskMetricsResponse,
  type OfficeManagerTaskResponse,
  type OfficeManagerTaskUpdateRequest,
  type OfficeManagerTaskCategory,
  type OfficeManagerTaskPriority,
  type OfficeManagerTaskStatus,
  type ClaimPacketReadinessResponse,
  type InsuranceNarrativeCasePacket,
  type InsuranceNarrativeDraft,
  type InsuranceNarrativeWorkflowResult,
} from "./schemas";

type BackendSchemas = components["schemas"];

export type FinancialSummaryWidgetFeed = {
  manager?: string | null;
  run_id?: string | null;
  generated_at?: string | null;
  received_at?: string | null;
  widgets?: Record<string, unknown> | null;
  sources?: Record<string, unknown> | null;
  jobs?: Record<string, unknown> | null;
};

export type AuthSessionResponse = BackendSchemas["AuthSessionResponse"];

function buildApiHeaders(initHeaders?: HeadersInit): Headers {
  const headers = new Headers(initHeaders);
  const authorization = getApiAuthorizationHeader();
  if (authorization && !headers.has("Authorization")) {
    headers.set("Authorization", authorization);
  }
  return headers;
}

async function apiFetch(pathOrUrl: string, init?: RequestInit, options?: { absoluteUrl?: boolean }): Promise<Response> {
  const hadAuthorization = Boolean(getApiAuthorizationHeader()) || Boolean(getApiAuthenticatedUsername());
  const response = await fetch(options?.absoluteUrl ? pathOrUrl : `${config.apiBaseUrl}${pathOrUrl}`, {
    ...init,
    credentials: init?.credentials ?? "include",
    headers: buildApiHeaders(init?.headers),
  });
  if (response.status === 401) {
    notifyApiAuthRequired(hadAuthorization);
  }
  return response;
}

// --- QuickBooks ODBC integration ---
export async function fetchQuickBooksOdbc(sql: string): Promise<Record<string, unknown>[]> {
  const response = await apiFetch("/quickbooks/odbc", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ sql }),
  });
  if (!response.ok) {
    throw new Error(`QuickBooks ODBC request failed: ${response.status}`);
  }
  const data = (await response.json()) as {
    error?: string;
    results: Record<string, unknown>[];
  };
  if (data.error) throw new Error(data.error);
  return data.results;
}

export async function fetchQuickBooksOdbcCsv(sql: string): Promise<Blob> {
  const response = await apiFetch("/quickbooks/odbc/csv", {
    method: "POST",
    headers: {
      Accept: "text/csv",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ sql }),
  });
  if (!response.ok) throw new Error("CSV export failed");
  return response.blob();
}

async function getJson(path: string): Promise<unknown> {
  const { response, payload } = await requestJson(path, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw buildRequestError(path, response, payload);
  }
  return payload;
}

async function requestJson(path: string, init?: RequestInit): Promise<{ response: Response; payload: unknown }> {
  const response = await apiFetch(path, init);
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  return { response, payload };
}

function extractErrorDetail(payload: unknown): string | null {
  if (typeof payload === "string" && payload.trim()) {
    return payload.trim();
  }
  if (payload && typeof payload === "object") {
    const detail = "detail" in payload ? (payload as { detail?: unknown }).detail : null;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
    const message = "message" in payload ? (payload as { message?: unknown }).message : null;
    if (typeof message === "string" && message.trim()) {
      return message.trim();
    }
  }
  return null;
}

function buildRequestError(path: string, response: Response, payload: unknown): Error {
  const detail = extractErrorDetail(payload);
  const message = detail || `Request failed for ${path}: ${response.status}`;
  console.error(`Request failed for ${path}`, {
    status: response.status,
    statusText: response.statusText,
    detail,
    payload,
  });
  return Object.assign(new Error(message), {
    path,
    status: response.status,
  });
}

const HAL_SCHEMA_ERROR_MESSAGE = "HAL returned an unexpected response shape. Reference: hal-schema.";

function parseHalAskResponse(payload: unknown): HalAskResponse {
  try {
    return halAskResponseSchema.parse(payload);
  } catch (error) {
    if (import.meta.env.DEV && error instanceof ZodError) {
      console.error("HAL ask response failed schema validation", error);
    }
    throw new Error(HAL_SCHEMA_ERROR_MESSAGE);
  }
}

const numberLikeSchema = z.union([z.number(), z.string()]);

const financialSummaryLatestArSchema = z
  .object({
    as_of_date: z.string(),
    total_ar: z.number(),
    insurance_ar: z.number(),
    patient_ar: z.number(),
    current_balance: z.number(),
    balance_30: z.number(),
    balance_60: z.number(),
    balance_90: z.number(),
    credit_balance: z.number(),
    source: z.string(),
    available: z.boolean(),
  })
  .passthrough();

const financialSummaryMonthlyKpiSchema = z
  .object({
    month: z.string().optional(),
    year_month: z.string().optional(),
    gross_production: z.number().optional(),
    net_production: z.number().optional(),
    collections: z.number().optional(),
    production_adjustments: z.number().optional(),
    collection_adjustments: z.number().optional(),
    receivables_change: z.number().optional(),
    deposit_total: z.number().optional(),
    new_patients_seen: z.number().optional(),
    existing_patients_seen: z.number().optional(),
    collection_rate: z.number().optional(),
    calendar_year: z.number().optional(),
    calendar_month: z.number().optional(),
  })
  .passthrough();

const financialSummaryLatestDailyKpiSchema = z
  .object({
    production: z.number().optional(),
    collections: z.number().optional(),
  })
  .passthrough();

const financialSummaryQuickBooksStatusSchema = z
  .object({
    status: z.string().nullable().optional(),
    message: z.string().nullable().optional(),
    lastCheckedAtUtc: z.string().nullable().optional(),
    lastImportedAtUtc: z.string().nullable().optional(),
    lastError: z.string().nullable().optional(),
    rowCounts: z.record(z.number()).nullable().optional(),
  })
  .passthrough();

const financialSummaryQuickBooksExpenseCategorySchema = z
  .object({
    expense_category: z.string().nullable().optional(),
    account_name: z.string().nullable().optional(),
    total_amount: numberLikeSchema.nullable().optional(),
    transaction_count: numberLikeSchema.nullable().optional(),
    first_transaction_date: z.string().nullable().optional(),
    last_transaction_date: z.string().nullable().optional(),
    last_imported_at_utc: z.string().nullable().optional(),
  })
  .passthrough();

const financialSummaryQuickBooksMonthlyExpenseSchema = z
  .object({
    year_month: z.string().nullable().optional(),
    expense_total: numberLikeSchema.nullable().optional(),
    transaction_count: numberLikeSchema.nullable().optional(),
    last_imported_at_utc: z.string().nullable().optional(),
  })
  .passthrough();

const financialSummaryQuickBooksProfitLossSchema = z
  .object({
    year_month: z.string().nullable().optional(),
    period_start: z.string().nullable().optional(),
    period_end: z.string().nullable().optional(),
    income_total: numberLikeSchema.nullable().optional(),
    expense_total: numberLikeSchema.nullable().optional(),
    net_income: numberLikeSchema.nullable().optional(),
    cogs_total: numberLikeSchema.nullable().optional(),
    payroll_total: numberLikeSchema.nullable().optional(),
    rent_total: numberLikeSchema.nullable().optional(),
    supplies_total: numberLikeSchema.nullable().optional(),
    lab_total: numberLikeSchema.nullable().optional(),
    merchant_fees_total: numberLikeSchema.nullable().optional(),
    utilities_total: numberLikeSchema.nullable().optional(),
    depreciation: numberLikeSchema.nullable().optional(),
    amortization: numberLikeSchema.nullable().optional(),
    interest: numberLikeSchema.nullable().optional(),
    taxes: numberLikeSchema.nullable().optional(),
    base_ebitda_candidate: numberLikeSchema.nullable().optional(),
    last_imported_at_utc: z.string().nullable().optional(),
  })
  .passthrough();

const financialSourceReviewItemSchema = z
  .object({
    sourceSystem: z.string(),
    status: z.string(),
    summary: z.string(),
    confidenceLabel: z.string(),
    reviewRequired: z.boolean(),
    reviewFlags: z.array(z.string()).default([]),
    lastVerifiedAt: z.string().nullable().optional(),
    metrics: z.record(z.union([z.string(), z.number(), z.boolean(), z.null()])).optional(),
  })
  .passthrough();

const financialSummarySourceReviewSchema = z
  .object({
    quickBooks: financialSourceReviewItemSchema.nullable().optional(),
    softDent: financialSourceReviewItemSchema.nullable().optional(),
    softDentClaims: financialSourceReviewItemSchema.nullable().optional(),
  })
  .passthrough();

const softDentCoverageCountsSchema = z
  .object({
    missing: z.number(),
    limited: z.number(),
    available: z.number(),
  })
  .passthrough();

const softDentCoverageRowSchema = z
  .object({
    key: z.string(),
    label: z.string(),
    status: z.enum(["missing", "limited", "available"]),
    summary: z.string(),
    requiredReport: z.string(),
    action: z.string(),
    sourceFile: z.string(),
    sourceBackend: z.string(),
    modifiedAtUtc: z.string(),
    rowCount: z.number(),
    lastPeriod: z.string(),
  })
  .passthrough();

const softDentCoverageSummarySchema = z
  .object({
    summary: z.string(),
    counts: softDentCoverageCountsSchema,
    rows: z.array(softDentCoverageRowSchema).default([]),
  })
  .passthrough();

const softDentCoverageMetricBreakdownRowSchema = z
  .object({
    label: z.string(),
    amount: z.number(),
    count: z.number(),
  })
  .passthrough();

const softDentCoverageMetricSchema = z
  .object({
    label: z.string(),
    available: z.boolean(),
    sourceFile: z.string(),
    sourceBackend: z.string(),
    modifiedAtUtc: z.string(),
    rowCount: z.number(),
    itemCount: z.number(),
    totalAmount: z.number(),
    lastPeriod: z.string(),
    summary: z.string(),
    breakdown: z.array(softDentCoverageMetricBreakdownRowSchema).default([]),
  })
  .passthrough();

const softDentCoverageMetricsSchema = z
  .object({
    trueOutstandingClaims: softDentCoverageMetricSchema.nullable().optional(),
    unsubmittedClaims: softDentCoverageMetricSchema.nullable().optional(),
    insuranceIncome: softDentCoverageMetricSchema.nullable().optional(),
    insurancePaymentDistribution: softDentCoverageMetricSchema.nullable().optional(),
    insuranceCheckDistribution: softDentCoverageMetricSchema.nullable().optional(),
    treatmentPlans: softDentCoverageMetricSchema.nullable().optional(),
    paymentPlans: softDentCoverageMetricSchema.nullable().optional(),
  })
  .passthrough();

const claimsSummarySchema = z
  .object({
    available: z.boolean(),
    true_outstanding_claims_amount: z.number(),
    true_outstanding_claims_count: z.number(),
    unsubmitted_claims_amount: z.number(),
    unsubmitted_claims_count: z.number(),
    top_outstanding_payers: z.array(softDentCoverageMetricBreakdownRowSchema).default([]),
    top_unsubmitted_payers: z.array(softDentCoverageMetricBreakdownRowSchema).default([]),
  })
  .passthrough();

const financialHealthFlagSchema = z
  .object({
    key: z.string(),
    code: z.string(),
    status: z.string(),
    sourceSystem: z.string(),
    message: z.string(),
    action: z.string().nullable().optional(),
    configured: z.boolean().nullable().optional(),
    emitted: z.boolean().nullable().optional(),
    configuredEntity: z.string().nullable().optional(),
    dataSyncEvidencePath: z.string().nullable().optional(),
    sqliteTransactionRows: numberLikeSchema.nullable().optional(),
    sourceMode: z.string().nullable().optional(),
    validationStatus: z.string().nullable().optional(),
  })
  .passthrough();

const financialTransactionDiagnosticsSchema = z
  .object({
    transactionConfigured: z.boolean(),
    dataSyncTransactionEmitted: z.boolean(),
    dataSyncEvidencePath: z.string().nullable().optional(),
    sqliteTransactionRows: z.number(),
    sourceMode: z.string().nullable().optional(),
    validationStatus: z.string().nullable().optional(),
    dataExtractorBinaryPath: z.string().nullable().optional(),
    dataExtractorBinaryModifiedAt: z.string().nullable().optional(),
    dataExtractorBinaryExists: z.boolean().nullable().optional(),
    dataExtractorSemaphorePath: z.string().nullable().optional(),
    dataExtractorSemaphoreModifiedAt: z.string().nullable().optional(),
    dataExtractorSemaphoreExists: z.boolean().nullable().optional(),
    latestExtractorLogPath: z.string().nullable().optional(),
    latestExtractorLogModifiedAt: z.string().nullable().optional(),
    latestExtractorLogExists: z.boolean().nullable().optional(),
    hasPostUpdateExtractorLog: z.boolean().nullable().optional(),
    extractorRunEvidenceStatus: z.string().nullable().optional(),
    summary: z.string().nullable().optional(),
  })
  .passthrough();

const widgetMetricSchema = z.union([z.string(), z.number(), z.boolean(), z.null()]);

const financialWidgetSchema = z
  .object({
    status: z.string().optional(),
    title: z.string().optional(),
    summary: z.string().optional(),
    metrics: z.record(widgetMetricSchema).default({}),
  })
  .passthrough();

const financialSummaryWidgetFeedSchema = z.object({
  manager: z.string().optional(),
  run_id: z.string().nullable().optional(),
  generated_at: z.string().nullable().optional(),
  received_at: z.string().nullable().optional(),
  widgets: z.record(financialWidgetSchema).default({}),
  sources: z.record(z.unknown()).default({}),
  jobs: z.record(z.unknown()).default({}),
});

const financialSummarySchema = z
  .object({
    generatedAt: z.string().nullable().optional(),
    latestSoftDentRefreshAt: z.string().nullable().optional(),
    dataFreshnessStatus: z.string().nullable().optional(),
    healthFlags: z.array(financialHealthFlagSchema).optional().default([]),
    transactionDiagnostics: financialTransactionDiagnosticsSchema.nullable().optional().default(null),
    sourceReview: financialSummarySourceReviewSchema.nullable().optional().default(null),
    softDentCoverage: softDentCoverageSummarySchema.nullable().optional().default(null),
    softDentCoverageMetrics: softDentCoverageMetricsSchema.nullable().optional().default(null),
    claimsSummary: claimsSummarySchema.nullable().optional().default(null),
    lastRefreshed: z.string().nullable().optional(),
    latestDailyKpi: financialSummaryLatestDailyKpiSchema.nullable().optional().default(null),
    latestAr: financialSummaryLatestArSchema.nullable().optional().default(null),
    monthlyKpis: z.array(financialSummaryMonthlyKpiSchema).default([]),
    trailing12Months: z.array(financialSummaryMonthlyKpiSchema).default([]),
    calendarYearKpis: z.array(financialSummaryMonthlyKpiSchema).default([]),
    fourYearMonthlyKpis: z.array(financialSummaryMonthlyKpiSchema).default([]),
    providerProduction: z.array(z.record(z.unknown())).default([]),
    topAdaCodes: z.array(z.record(z.unknown())).default([]),
    quickBooksStatus: financialSummaryQuickBooksStatusSchema.nullable().optional().default(null),
    quickBooksExpenseCategories: z.array(financialSummaryQuickBooksExpenseCategorySchema).optional().default([]),
    quickBooksMonthlyExpenses: z.array(financialSummaryQuickBooksMonthlyExpenseSchema).optional().default([]),
    quickBooksProfitLossSummary: z.array(financialSummaryQuickBooksProfitLossSchema).optional().default([]),
    quickBooksEbitdaCandidates: z.array(financialSummaryQuickBooksProfitLossSchema).optional().default([]),
    dataFreshnessWarnings: z.unknown().optional(),
    currentMonthProduction: z.record(z.unknown()).nullable().optional(),
    currentYearProduction: z.record(z.unknown()).nullable().optional(),
    widgetFeed: financialSummaryWidgetFeedSchema.nullable().optional().default(null),
  })
  .passthrough();

const halFinancialRefreshResponseSchema = z
  .object({
    message: z.string(),
    actor: z.string(),
    refreshed_at_utc: z.string(),
    refresh_report: z.unknown(),
    financial_summary: financialSummarySchema,
    hal_status: halStatusSchema,
    admin_summary: adminSummarySchema,
  })
  .passthrough();

export async function fetchHealth(): Promise<HealthResponse> {
  const payload = await getJson("/health");
  return healthSchema.parse(payload);
}

export async function verifyApiBasicAuthCredentials(username: string, password: string): Promise<HealthResponse> {
  const response = await fetch(`${config.apiBaseUrl}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    throw buildRequestError("/auth/login", response, payload);
  }
  const session = authSessionSchema.parse(payload);
  setApiAuthenticatedUsername(session.username);
  return { status: "ok", service: "New Ridge Family Financial" };
}

export async function fetchAuthSession(): Promise<AuthSessionResponse> {
  const response = await fetch(`${config.apiBaseUrl}/auth/session`, {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    if (response.status === 401) {
      setApiAuthenticatedUsername(null);
    }
    throw buildRequestError("/auth/session", response, payload);
  }
  const session = authSessionSchema.parse(payload);
  setApiAuthenticatedUsername(session.username);
  return session;
}

export async function logoutAuthSession(): Promise<void> {
  const { response, payload } = await requestJson("/auth/logout", {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw buildRequestError("/auth/logout", response, payload);
  }
  setApiAuthenticatedUsername(null);
}

export type FinancialSummaryLatestAr = BackendSchemas["FinancialSummaryLatestArResponse"];

export type FinancialSummaryMonthlyKpi = BackendSchemas["FinancialSummaryMonthlyKpiResponse"];

export type FinancialSummaryLatestDailyKpi = BackendSchemas["FinancialSummaryLatestDailyKpiResponse"];

export type FinancialSummaryQuickBooksStatus = BackendSchemas["FinancialSummaryQuickBooksStatusResponse"];

export type FinancialSummaryQuickBooksExpenseCategory = BackendSchemas["FinancialSummaryQuickBooksExpenseCategoryResponse"];

export type FinancialSummaryQuickBooksMonthlyExpense = BackendSchemas["FinancialSummaryQuickBooksMonthlyExpenseResponse"];

export type FinancialSummaryQuickBooksProfitLoss = BackendSchemas["FinancialSummaryQuickBooksProfitLossResponse"];

export type FinancialSourceReviewItem = BackendSchemas["FinancialSourceReviewItemResponse"];

export type FinancialSummarySourceReview = BackendSchemas["FinancialSummarySourceReviewResponse"];

export type SoftDentCoverageCounts = BackendSchemas["SoftDentCoverageCountsResponse"];

export type SoftDentCoverageRow = BackendSchemas["SoftDentCoverageRowResponse"];

export type SoftDentCoverageSummary = BackendSchemas["SoftDentCoverageSummaryResponse"];

export type SoftDentCoverageMetricBreakdownRow = BackendSchemas["SoftDentCoverageMetricBreakdownRowResponse"];

export type SoftDentCoverageMetric = BackendSchemas["SoftDentCoverageMetricResponse"];

export type SoftDentCoverageMetrics = BackendSchemas["SoftDentCoverageMetricsResponse"];

export type ClaimsSummary = BackendSchemas["ClaimsSummaryResponse"];

export type FinancialHealthFlag = BackendSchemas["FinancialHealthFlagResponse"];

export type FinancialTransactionDiagnostics = BackendSchemas["FinancialTransactionDiagnosticsResponse"];

export type FinancialSummaryResponse = BackendSchemas["FinancialSummaryResponse"] & {
  widgetFeed?: FinancialSummaryWidgetFeed | null;
};

export type HalStagedImportFilePayload = {
  file_name: string;
  mime_type: string;
  content: string;
};

export type HalStagedImportResponse = {
  message: string;
  actor: string;
  file_count: number;
  files: Array<{
    file_name: string;
    bytes_written: number;
    destination_path: string;
  }>;
};

export async function fetchFinancialSummary(): Promise<FinancialSummaryResponse> {
  const payload = await getJson("/hal9000/page-summary");
  return financialSummarySchema.parse(payload);
}

export async function uploadHalStagedFiles(files: HalStagedImportFilePayload[]): Promise<HalStagedImportResponse> {
  const response = await apiFetch("/hal9000/staged-imports", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ files }),
  });
  if (!response.ok) {
    throw new Error(`Request failed for /api/hal9000/staged-imports: ${response.status}`);
  }
  return response.json();
}

export async function uploadSoftDentImport(file: File): Promise<{ message: string }> {
  const formData = new FormData();
  formData.append("file", file, file.name);

  const { response, payload } = await requestJson("/softdent/import", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw buildRequestError("/softdent/import", response, payload);
  }
  return payload as { message: string };
}

export async function uploadQuickBooksImport(file: File): Promise<{ message: string }> {
  const formData = new FormData();
  formData.append("file", file, file.name);

  const { response, payload } = await requestJson("/quickbooks/import", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw buildRequestError("/quickbooks/import", response, payload);
  }
  return payload as { message: string };
}

export async function fetchAdminSummary(): Promise<AdminSummaryResponse> {
  const payload = await getJson("/hal9000/admin-summary");
  return adminSummarySchema.parse(payload);
}

export type HalFinancialRefreshResponse = {
  message: string;
  actor: string;
  refreshed_at_utc: string;
  refresh_report?: unknown;
  financial_summary: FinancialSummaryResponse;
  hal_status: HalStatusResponse;
  admin_summary: AdminSummaryResponse;
};

export async function refreshHalFinancialSources(): Promise<HalFinancialRefreshResponse> {
  const { response, payload } = await requestJson("/hal9000/refresh-financial-sources", {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw buildRequestError("/api/hal9000/refresh-financial-sources", response, payload);
  }
  return halFinancialRefreshResponseSchema.parse(payload);
}

export type HalFieldTimeframeField = {
  field_key: string;
  data_path: string;
  source_key: string;
  max_landing_minutes: number;
  observed_source_timestamp_utc: string;
  observed_age_minutes: number | null;
  within_landing_window: boolean;
};

export type HalFieldTimeframePage = {
  page_id: string;
  page_label: string;
  field_count: number;
  within_window_count: number;
  fields: HalFieldTimeframeField[];
};

export type HalFieldTimeframeRegistry = {
  evaluated_at_utc: string;
  tracked_field_count: number;
  within_window_field_count: number;
  compliance_percent: number;
  pages: HalFieldTimeframePage[];
};

export type HalFieldTimeframeResponse = {
  mode: string;
  registry: HalFieldTimeframeRegistry;
};

export async function fetchHalFieldTimeframes(): Promise<HalFieldTimeframeResponse> {
  const payload = await getJson("/hal9000/field-timeframes");
  return payload as HalFieldTimeframeResponse;
}

export async function fetchHalStatus(): Promise<HalStatusResponse> {
  const primary = await requestJson("/hal9000/status", {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/status", primary.response, primary.payload);
  }
  return halStatusSchema.parse(primary.payload);
}

export async function fetchHalAudits(limit = 5): Promise<HalAuditListResponse> {
  const payload = await getJson(`/hal9000/audits?limit=${limit}`);
  return halAuditListSchema.parse(payload);
}

export async function fetchLocalAccountingDocuments(options?: {
  limit?: number;
  search?: string;
  documentType?: string;
  reviewOnly?: boolean;
}): Promise<LocalAccountingDocumentListResponse> {
  const params = new URLSearchParams();
  if (options?.limit) {
    params.set("limit", String(options.limit));
  }
  if (options?.search) {
    params.set("search", options.search);
  }
  if (options?.documentType) {
    params.set("document_type", options.documentType);
  }
  if (options?.reviewOnly) {
    params.set("review_only", "true");
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const payload = await getJson(`/hal9000/accounting-documents${suffix}`);
  return localAccountingDocumentListSchema.parse(payload);
}

export async function fetchDocumentRagDocuments(options?: {
  limit?: number;
  search?: string;
}): Promise<DocumentRagDocumentListResponse> {
  const params = new URLSearchParams();
  if (options?.limit) {
    params.set("limit", String(options.limit));
  }
  if (options?.search) {
    params.set("search", options.search);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const payload = await getJson(`/hal9000/document-rag/documents${suffix}`);
  return documentRagDocumentListSchema.parse(payload);
}

export async function uploadDocumentRagDocument(file: File): Promise<DocumentRagUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const primary = await requestJson("/hal9000/document-rag/documents", {
    method: "POST",
    body: formData,
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/document-rag/documents", primary.response, primary.payload);
  }
  return documentRagUploadResponseSchema.parse(primary.payload);
}

export async function askDocumentRagQuestion(question: string, options?: { topK?: number }): Promise<DocumentRagAskResponse> {
  const primary = await requestJson("/hal9000/document-rag/ask", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      top_k: options?.topK ?? 4,
    }),
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/document-rag/ask", primary.response, primary.payload);
  }
  return documentRagAskResponseSchema.parse(primary.payload);
}

export function createHalConversationId(): string {
  const cryptoObject = typeof globalThis !== "undefined" ? globalThis.crypto : undefined;
  if (cryptoObject?.randomUUID) {
    return `hal-${cryptoObject.randomUUID()}`;
  }
  return `hal-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function askHalQuestion(
  question: string,
  options?: {
    conversationId?: string;
  },
): Promise<HalAskResponse> {
  const body = JSON.stringify({
    question,
    session_id: options?.conversationId ?? undefined,
  });
  const primary = await requestJson("/hal9000", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body,
  });
  if (!primary.response.ok) {
    throw buildRequestError(`/api/hal9000`, primary.response, primary.payload);
  }
  return parseHalAskResponse(primary.payload);
}

export async function generateHalChartPlan(question: string): Promise<HalChartPlanResponse> {
  const response = await apiFetch("/hal9000/chart-plan", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });
  if (!response.ok) {
    throw new Error(`Request failed for /api/hal9000/chart-plan: ${response.status}`);
  }
  const payload = await response.json();
  return halChartPlanResponseSchema.parse(payload);
}

export async function approveHalChartPlan(reviewPlanPath: string): Promise<HalChartPlanApprovalResponse> {
  const response = await apiFetch("/hal9000/chart-plan/approve", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ review_plan_path: reviewPlanPath }),
  });
  if (!response.ok) {
    throw new Error(`Request failed for /api/hal9000/chart-plan/approve: ${response.status}`);
  }
  const payload = await response.json();
  return halChartPlanApprovalResponseSchema.parse(payload);
}

export async function fetchHalChartPlans(
  limit = 8,
  status?: "pending_human_approval" | "approved_and_rendered",
): Promise<HalChartPlanListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) {
    params.set("status", status);
  }
  const payload = await getJson(`/hal9000/chart-plans?${params.toString()}`);
  return halChartPlanListResponseSchema.parse(payload);
}

export function buildHalChartFileUrl(path: string): string {
  const params = new URLSearchParams({ path });
  return `${config.apiBaseUrl}/hal9000/chart-files?${params.toString()}`;
}

export async function fetchHalChartFileBlob(path: string): Promise<Blob> {
  const response = await apiFetch(
    buildHalChartFileUrl(path),
    {
      method: "GET",
    },
    { absoluteUrl: true },
  );
  if (!response.ok) {
    let detail: string | null = null;
    try {
      const payload = await response.json();
      if (payload && typeof payload === "object" && "detail" in payload) {
        const value = (payload as { detail?: unknown }).detail;
        if (typeof value === "string" && value.trim()) {
          detail = value.trim();
        }
      }
    } catch {
      detail = null;
    }
    throw new Error(detail || `Unable to load chart file (${response.status}).`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    throw new Error("The chart file endpoint returned JSON instead of a PNG.");
  }

  return response.blob();
}

export async function executeMonitorReviewAction(payload: {
  action_type: string;
  target_value: number;
  human_review_required: boolean;
  status: string;
  user_confirmed: boolean;
}): Promise<MonitorMutationExecutionResult> {
  const response = await apiFetch("/hardware/monitor-actions", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Request failed for /api/hardware/monitor-actions: ${response.status}`);
  }
  const responsePayload = await response.json();
  return monitorMutationExecutionResultSchema.parse(responsePayload);
}

export async function generateHalInsuranceNarrative(question: string): Promise<HalInsuranceNarrativeResponse> {
  const primary = await requestJson("/hal9000/insurance-narrative", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/insurance-narrative", primary.response, primary.payload);
  }
  return halInsuranceNarrativeSchema.parse(primary.payload);
}

export async function createSoftDentDraft(payload: SoftDentDraftRequest): Promise<SoftDentDraftArtifact> {
  const primary = await requestJson("/hal9000/softdent-drafts", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/softdent-drafts", primary.response, primary.payload);
  }
  return softDentDraftArtifactSchema.parse(primary.payload);
}

export async function createSoftDentLocalPacket(
  payload: SoftDentLocalPacketRequest,
): Promise<SoftDentLocalPacketArtifact> {
  const primary = await requestJson("/hal9000/softdent-local-packets", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/softdent-local-packets", primary.response, primary.payload);
  }
  return softDentLocalPacketArtifactSchema.parse(primary.payload);
}

export async function fetchSoftDentEndOfDayAr(): Promise<SoftDentEndOfDayAr> {
  const primary = await requestJson("/hal9000/softdent-end-of-day-ar", {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/softdent-end-of-day-ar", primary.response, primary.payload);
  }
  return softDentEndOfDayArSchema.parse(primary.payload);
}

export async function fetchOfficeManagerAttention(): Promise<OfficeManagerAttentionResponse> {
  const primary = await requestJson("/hal9000/office-manager/attention", {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/office-manager/attention", primary.response, primary.payload);
  }
  return officeManagerAttentionResponseSchema.parse(primary.payload);
}

export async function fetchClaimPacketReadiness(): Promise<ClaimPacketReadinessResponse> {
  const primary = await requestJson("/hal9000/claim-packet-readiness", {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/claim-packet-readiness", primary.response, primary.payload);
  }
  return claimPacketReadinessResponseSchema.parse(primary.payload);
}

export async function fetchOfficeManagerTasks(options?: {
  limit?: number;
  status?: string;
}): Promise<OfficeManagerTaskListResponse> {
  const params = new URLSearchParams();
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.status) params.set("status", options.status);
  const query = params.toString();
  const primary = await requestJson(`/hal9000/office-manager/tasks${query ? `?${query}` : ""}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/office-manager/tasks", primary.response, primary.payload);
  }
  return officeManagerTaskListResponseSchema.parse(primary.payload);
}

export async function createOfficeManagerTask(
  payload: OfficeManagerTaskCreateRequest,
): Promise<OfficeManagerTaskResponse> {
  const primary = await requestJson("/hal9000/office-manager/tasks", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/office-manager/tasks", primary.response, primary.payload);
  }
  return officeManagerTaskResponseSchema.parse(primary.payload);
}

export async function updateOfficeManagerTask(
  taskId: string,
  payload: OfficeManagerTaskUpdateRequest,
): Promise<OfficeManagerTaskResponse> {
  const primary = await requestJson(`/hal9000/office-manager/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!primary.response.ok) {
    throw buildRequestError(`/api/hal9000/office-manager/tasks/${taskId}`, primary.response, primary.payload);
  }
  return officeManagerTaskResponseSchema.parse(primary.payload);
}

export async function fetchOfficeManagerTaskMetrics(): Promise<OfficeManagerTaskMetricsResponse> {
  const primary = await requestJson("/hal9000/office-manager/tasks/metrics", {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/office-manager/tasks/metrics", primary.response, primary.payload);
  }
  return officeManagerTaskMetricsResponseSchema.parse(primary.payload);
}

export type {
  InsuranceNarrativeCasePacket,
  InsuranceNarrativeDraft,
  InsuranceNarrativeWorkflowResult,
  SoftDentDraftArtifact,
  SoftDentDraftRequest,
  SoftDentEndOfDayAr,
  SoftDentLocalPacketArtifact,
  SoftDentLocalPacketRequest,
  OfficeManagerAttentionResponse,
  OfficeManagerTaskCreateRequest,
  OfficeManagerTaskListResponse,
  OfficeManagerTaskMetricsResponse,
  OfficeManagerTaskResponse,
  OfficeManagerTaskUpdateRequest,
  OfficeManagerTaskCategory,
  OfficeManagerTaskPriority,
  OfficeManagerTaskStatus,
};

export async function createInsuranceNarrativeDraftWorkflow(payload: {
  patient_ref: string;
  claim_id?: string | null;
  procedure_ids?: string[] | null;
  narrative_type: string;
  run_checker?: boolean;
  adapter_mode?: "fixture" | "softdent_export_file";
}): Promise<InsuranceNarrativeWorkflowResult> {
  const { response, payload: responsePayload } = await requestJson("/insurance-narratives/draft", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      patient_ref: payload.patient_ref,
      claim_id: payload.claim_id ?? null,
      procedure_ids: payload.procedure_ids ?? null,
      narrative_type: payload.narrative_type,
      run_checker: payload.run_checker ?? false,
      adapter_mode: payload.adapter_mode ?? "fixture",
    }),
  });
  if (!response.ok) {
    throw buildRequestError("/api/insurance-narratives/draft", response, responsePayload);
  }
  return insuranceNarrativeWorkflowResultSchema.parse(responsePayload);
}

export async function approveAndExportInsuranceNarrativeWorkflow(payload: {
  packet: InsuranceNarrativeCasePacket;
  draft: InsuranceNarrativeDraft;
  reviewer: string;
  notes: string;
  approval_attestation: boolean;
  export_format?: "markdown" | "plain_text";
  checker_summary?: InsuranceNarrativeWorkflowResult["checker_summary"];
}): Promise<InsuranceNarrativeWorkflowResult> {
  const { response, payload: responsePayload } = await requestJson("/insurance-narratives/approve-export", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      packet: payload.packet,
      draft: payload.draft,
      reviewer: payload.reviewer,
      notes: payload.notes,
      approval_attestation: payload.approval_attestation,
      export_format: payload.export_format ?? "markdown",
      checker_summary: payload.checker_summary ?? null,
    }),
  });
  if (!response.ok) {
    throw buildRequestError("/api/insurance-narratives/approve-export", response, responsePayload);
  }
  return insuranceNarrativeWorkflowResultSchema.parse(responsePayload);
}

export async function fetchHalPatientDossier(question: string): Promise<HalPatientDossierResponse> {
  const primary = await requestJson("/hal9000/patient-dossier", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/patient-dossier", primary.response, primary.payload);
  }
  return halPatientDossierSchema.parse(primary.payload);
}

export async function draftJournalEntry(payload: {
  description: string;
  transaction_date: string;
  accounting_period: string;
  amount: number;
  context?: Record<string, unknown>;
}): Promise<JournalDraftResponse> {
  const response = await apiFetch("/hal9000/accounting/journal-draft", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Request failed for /api/hal9000/accounting/journal-draft: ${response.status}`);
  }
  const data = await response.json();
  return journalDraftResponseSchema.parse(data);
}

export async function fetchAccountingPolicyAnswer(payload: {
  question: string;
  topic?: string;
  accounting_standard?: string;
}): Promise<AccountingPolicyAnswerResponse> {
  const primary = await requestJson("/hal9000/accounting/policy-answer", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!primary.response.ok) {
    throw buildRequestError("/api/hal9000/accounting/policy-answer", primary.response, primary.payload);
  }
  return accountingPolicyAnswerResponseSchema.parse(primary.payload);
}

export async function fetchAccountingPostingQueue(
  payload: {
    limit?: number;
    cursor?: string;
    status?: PostingQueueStatus;
  } = {},
): Promise<AccountingPostingQueueListResponse> {
  const params = new URLSearchParams();
  params.set("limit", String(payload.limit ?? 10));
  if (payload.cursor) {
    params.set("cursor", payload.cursor);
  }
  if (payload.status) {
    params.set("status", payload.status);
  }
  const responsePayload = await getJson(`/hal9000/accounting/posting-queue?${params.toString()}`);
  return accountingPostingQueueListSchema.parse(responsePayload);
}

export async function fetchAccountingPostingQueueMetrics(): Promise<AccountingPostingQueueMetricsResponse> {
  const payload = await getJson("/hal9000/accounting/posting-queue/metrics");
  return accountingPostingQueueMetricsSchema.parse(payload);
}

export async function fetchAccountingPostingQueueActivity(limit = 10): Promise<AccountingPostingQueueActivityListResponse> {
  const payload = await getJson(`/hal9000/accounting/posting-queue/activity?limit=${limit}`);
  return accountingPostingQueueActivityListSchema.parse(payload);
}

export async function queueAccountingPostingDraft(payload: {
  description: string;
  transaction_date: string;
  accounting_period: string;
  amount: number;
  transaction_type?: string;
  source_audit_id: string;
  enqueue_mode?: PostingQueueEnqueueMode;
  lines: Array<{
    account_code: string;
    account_name: string;
    debit: number;
    credit: number;
    memo?: string | null;
  }>;
}): Promise<AccountingPostingQueueEntry> {
  const response = await apiFetch("/hal9000/accounting/posting-queue", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Request failed for /api/hal9000/accounting/posting-queue: ${response.status}`);
  }
  const data = await response.json();
  return accountingPostingQueueEntrySchema.parse(data);
}

export async function reviewAccountingPostingQueueEntry(payload: {
  queueId: string;
  action: PostingQueueReviewAction;
  review_note?: string;
}): Promise<AccountingPostingQueueEntry> {
  const response = await apiFetch(`/hal9000/accounting/posting-queue/${payload.queueId}/review`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      action: payload.action,
      review_note: payload.review_note,
    }),
  });
  if (!response.ok) {
    throw new Error(`Request failed for /api/hal9000/accounting/posting-queue/${payload.queueId}/review: ${response.status}`);
  }
  const data = await response.json();
  return accountingPostingQueueEntrySchema.parse(data);
}
