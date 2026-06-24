import { http, HttpResponse } from "msw";
import { getApiAuthenticatedUsername } from "../api/basicAuth";
import { DRAFT_STATUS_DRAFT_ONLY, DRAFT_STATUS_ENQUEUED, type JournalDraftStatus } from "../utils/journalDraftStatus";
import {
  ENQUEUE_MODE_AUTO_VALIDATED_AI,
  ENQUEUE_MODE_MANUAL_REVIEW_QUEUE,
  type PostingQueueEnqueueMode,
} from "../utils/postingQueueLineage";
import {
  POSTING_QUEUE_STATUS_APPROVED,
  POSTING_QUEUE_STATUS_PENDING_REVIEW,
  POSTING_QUEUE_STATUS_REJECTED,
  type PostingQueueReviewAction,
  type PostingQueueStatus,
} from "../utils/postingQueueStatus";

type PostingQueueItem = {
  queue_id: string;
  created_at_utc: string;
  actor: string;
  target_system: string;
  status: PostingQueueStatus;
  description: string;
  transaction_date: string;
  accounting_period: string;
  amount: number;
  transaction_type: string | null;
  source_audit_id: string;
  enqueue_mode: PostingQueueEnqueueMode | null;
  lines: Array<{
    account_code: string;
    account_name: string;
    debit: number;
    credit: number;
    memo: string;
  }>;
  validation: {
    balanced: boolean;
    debit_total: number;
    credit_total: number;
    open_period: boolean;
    account_validation_passed: boolean;
    issues: string[];
  };
  reviewer_actor: string | null;
  reviewed_at_utc: string | null;
  review_note: string | null;
  review_required: boolean;
};

let postingQueueItems: PostingQueueItem[] = [
  {
    queue_id: "qbd-queue-1001",
    created_at_utc: "2026-06-15T12:30:00Z",
    actor: "hal_operator",
    target_system: "quickbooks_desktop",
    status: POSTING_QUEUE_STATUS_PENDING_REVIEW,
    description: "Queue prepaid insurance entry for QuickBooks Desktop review.",
    transaction_date: "2026-06-15",
    accounting_period: "2026-06",
    amount: 1200,
    transaction_type: "prepaid_insurance",
    source_audit_id: "hal-journal-1",
    enqueue_mode: ENQUEUE_MODE_AUTO_VALIDATED_AI,
    lines: [
      {
        account_code: "1310",
        account_name: "Prepaid Insurance",
        debit: 1200,
        credit: 0,
        memo: "Queue prepaid insurance entry for QuickBooks Desktop review.",
      },
      {
        account_code: "1010",
        account_name: "Cash",
        debit: 0,
        credit: 1200,
        memo: "Queue prepaid insurance entry for QuickBooks Desktop review.",
      },
    ],
    validation: {
      balanced: true,
      debit_total: 1200,
      credit_total: 1200,
      open_period: true,
      account_validation_passed: true,
      issues: [],
    },
    reviewer_actor: null,
    reviewed_at_utc: null,
    review_note: null,
    review_required: true,
  },
  {
    queue_id: "qbd-queue-1002",
    created_at_utc: "2026-06-15T12:20:00Z",
    actor: "hal_operator",
    target_system: "quickbooks_desktop",
    status: POSTING_QUEUE_STATUS_APPROVED,
    description: "Queue vendor bill for QuickBooks Desktop review.",
    transaction_date: "2026-06-14",
    accounting_period: "2026-06",
    amount: 700,
    transaction_type: "vendor_bill",
    source_audit_id: "hal-source-125",
    enqueue_mode: ENQUEUE_MODE_MANUAL_REVIEW_QUEUE,
    lines: [
      {
        account_code: "5200",
        account_name: "Dental Supplies Expense",
        debit: 700,
        credit: 0,
        memo: "Queue vendor bill for QuickBooks Desktop review.",
      },
      {
        account_code: "2100",
        account_name: "Accounts Payable",
        debit: 0,
        credit: 700,
        memo: "Queue vendor bill for QuickBooks Desktop review.",
      },
    ],
    validation: {
      balanced: true,
      debit_total: 700,
      credit_total: 700,
      open_period: true,
      account_validation_passed: true,
      issues: [],
    },
    reviewer_actor: "hal_operator",
    reviewed_at_utc: "2026-06-15T12:25:00Z",
    review_note: "Validated against June vendor support.",
    review_required: false,
  },
];

function buildMockAuthSession(username: string) {
  if (username === "viewer") {
    return {
      username: "viewer",
      display_name: "Viewer",
      roles: ["dashboard:read"],
    };
  }

  return {
    username: "admin",
    display_name: "Administrator",
    roles: ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
  };
}

export const handlers = [
  http.get("/api/health", () =>
    HttpResponse.json({
      status: "ok",
      service: "New Ridge Family Financial",
    }),
  ),
  http.post("/api/auth/login", async ({ request }) => {
    const payload = (await request.json()) as { username?: string; password?: string };
    const username = String(payload?.username || "").trim();
    const password = String(payload?.password || "");

    if (username === "admin" && password === "password") {
      return HttpResponse.json(buildMockAuthSession("admin"));
    }
    if (username === "viewer" && password === "viewer-password") {
      return HttpResponse.json(buildMockAuthSession("viewer"));
    }
    return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
  }),
  http.post("/api/auth/logout", () => HttpResponse.json({ message: "Signed out" })),
  http.get("/api/auth/session", () => {
    const username = getApiAuthenticatedUsername();
    if (!username) {
      return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
    }
    return HttpResponse.json(buildMockAuthSession(username));
  }),
  http.get("/api/kpis", () =>
    HttpResponse.json({
      items: [
        {
          period: "2026-04",
          production: 120000,
          collections: 112000,
          overhead_percentage: 28,
        },
        {
          period: "2026-05",
          production: 135000,
          collections: 126500,
          overhead_percentage: 26,
        },
      ],
    }),
  ),
  http.get("/api/hal9000/admin-summary", () =>
    HttpResponse.json({
      last_refresh_date: "2026-05-23",
      report_pull_status: {
        softdent: { scanned: 2, copied: 1, updated: 0, skipped: 1 },
      },
      kpis: [
        {
          period: "2026-04",
          production: 120000,
          collections: 112000,
          overhead_percentage: 28,
        },
        {
          period: "2026-05",
          production: 135000,
          collections: 126500,
          overhead_percentage: 26,
        },
      ],
      kpi_thresholds: {
        overhead_percentage: { target: 60, comparator: "lte" },
        collections_ratio: { target: 0.92, comparator: "gte" },
      },
      priority_summary: "SoftDent page coverage gaps remain visible to HAL: 2 missing, 1 limited, 4 available.",
      priority_actions: [
        "SoftDent page coverage remains constrained: 2 missing, 1 limited. Resolve Treatment Plans, Payment Plans, Unsubmitted Claims first.",
        "Claims aging: Escalate payer responses older than 30 days.",
        "Collections ratio: Review payment plans before day-close.",
      ],
      report_summary: {
        softdent_coverage: {
          summary: "Missing aggregate claim and plan exports explain why some HAL-owned page lanes are still partial.",
          counts: { missing: 2, limited: 1, available: 4 },
          rows: [
            {
              key: "unsubmittedClaims",
              label: "Unsubmitted Claims",
              status: "missing",
              summary: "Unsubmitted claim exposure is not available until the approved aggregate export lands.",
              requiredReport: "unsubmitted_claims.csv",
              action: "Stage the unsubmitted claims export into the canonical SoftDent import lane.",
              sourceFile: "",
              sourceBackend: "missing",
              modifiedAtUtc: "",
              rowCount: 0,
              lastPeriod: "",
            },
            {
              key: "treatmentPlans",
              label: "Treatment Plans",
              status: "missing",
              summary: "Treatment plan case value is still unavailable.",
              requiredReport: "treatment_plan_summary.csv",
              action: "Export the treatment plan summary and re-import through HAL.",
              sourceFile: "",
              sourceBackend: "missing",
              modifiedAtUtc: "",
              rowCount: 0,
              lastPeriod: "",
            },
            {
              key: "paymentPlans",
              label: "Payment Plans",
              status: "limited",
              summary: "Payment plan coverage is partial and not period-complete.",
              requiredReport: "payment_plans.csv",
              action: "Refresh the payment plan export for the current operating period.",
              sourceFile: "payment_plans.csv",
              sourceBackend: "csv",
              modifiedAtUtc: "2026-06-16T11:40:00Z",
              rowCount: 4,
              lastPeriod: "2026-05",
            },
          ],
        },
      },
      dso_summary: {},
      claims_summary: {
        available: true,
        true_outstanding_claims_amount: 12401,
        true_outstanding_claims_count: 9,
        unsubmitted_claims_amount: 3840,
        unsubmitted_claims_count: 4,
        top_outstanding_payers: [
          { label: "Delta Dental", amount: 7100, count: 4 },
          { label: "MetLife", amount: 3801, count: 3 },
        ],
        top_unsubmitted_payers: [
          { label: "Delta Dental", amount: 2200, count: 2 },
          { label: "Cigna", amount: 1640, count: 2 },
        ],
      },
      practice_central_delta: {
        delta: {
          outstanding_amount: -1200,
          claim_count: -2,
          high_risk_count: -1,
          average_age_days: -3,
          coverage_ratio: 0.9,
        },
      },
      softdent_insights: {
        coverage: {
          summary: "Missing aggregate claim and plan exports explain why some HAL-owned page lanes are still partial.",
          counts: { missing: 2, limited: 1, available: 4 },
          rows: [],
        },
        coverage_metrics: {
          trueOutstandingClaims: {
            label: "True Outstanding Claims",
            available: true,
            sourceFile: "outstanding_claims_by_company.csv",
            sourceBackend: "csv",
            modifiedAtUtc: "2026-06-16T11:42:00Z",
            rowCount: 3,
            itemCount: 9,
            totalAmount: 12401,
            lastPeriod: "2026-05",
            summary: "True outstanding claim exposure is available.",
            breakdown: [
              { label: "Delta Dental", amount: 7100, count: 4 },
              { label: "MetLife", amount: 3801, count: 3 },
            ],
          },
        },
        providers: [{ provider: "Entire Practice", production: 135000, collections: 126500 }],
      },
      owner_financial: {
        business_date: "2026-05-23",
        trend_limit: 5,
        trend_points: 2,
        available_windows: [5, 10],
        status_label: "Ready",
        summary: "Latest QuickBooks and SoftDent exports are available for owner review.",
        ebitda: 99900,
        revenue: 135000,
        operating_expenses: 35100,
        ebitda_margin_percent: 74,
        quickbooks_rows: 126,
        softdent_rows: 135,
        quickbooks_file: {
          name: "quickbooks_may_2026.xlsx",
          modified_at: "2026-05-23 06:00",
        },
        softdent_file: {
          name: "softdent_may_2026.xlsx",
          modified_at: "2026-05-23 06:03",
        },
        trend_summary: {
          ready_windows: 2,
          attention_windows: 0,
          average_ebitda: 93200,
          average_margin_percent: 72,
        },
        financial_operating_areas: [
          {
            title: "Production",
            status: "Ready",
            metric: "135 row(s)",
            detail: "SoftDent production exports feed the daily owner view.",
          },
          {
            title: "Collections",
            status: "Ready",
            metric: "126 row(s)",
            detail: "QuickBooks collections exports anchor the revenue side.",
          },
          {
            title: "AR Aging",
            status: "Ready",
            metric: "2 window(s)",
            detail: "Track the freshest window set before expanding into aging buckets.",
          },
          {
            title: "Insurance",
            status: "Ready",
            metric: "2 ready window(s)",
            detail: "Use ready source windows to spot claim workflow gaps.",
          },
        ],
        trend_with_deltas: [
          {
            business_date: "2026-04",
            ebitda: 86400,
            delta_vs_prior: null,
            revenue: 120000,
            operating_expenses: 33600,
            quickbooks_rows: 112,
            softdent_rows: 120,
            status_label: "Ready",
            quickbooks_file: { name: "quickbooks_apr_2026.xlsx" },
            softdent_file: { name: "softdent_apr_2026.xlsx" },
          },
          {
            business_date: "2026-05",
            ebitda: 99900,
            delta_vs_prior: 13500,
            revenue: 135000,
            operating_expenses: 35100,
            quickbooks_rows: 126,
            softdent_rows: 135,
            status_label: "Ready",
            quickbooks_file: { name: "quickbooks_may_2026.xlsx" },
            softdent_file: { name: "softdent_may_2026.xlsx" },
          },
        ],
      },
      owner_financial_detail: {
        section: "ar",
        section_title: "AR aging detail",
        alert_level: "warning",
        priority_summary: {
          critical_count: 0,
          warning_count: 1,
          triggered_count: 1,
        },
        priority_actions: [
          {
            label: "Over 90 days share",
            severity: "warning",
            gap_percent: 4,
            recommended_action: "Prioritize collection calls for 90+ day balances and verify aging workflow ownership.",
          },
        ],
        kpi_thresholds: [
          {
            id: "ar_over_90_share",
            label: "Over 90 days share",
            description: "Portion of AR in 90+ aging bucket should stay at or below 25%.",
            value_percent: 29,
            threshold_percent: 25,
            comparison: "lte",
            triggered: true,
            severity: "warning",
            recommended_action: "Prioritize collection calls for 90+ day balances and verify aging workflow ownership.",
          },
        ],
      },
    }),
  ),
  http.get("/api/hal9000/page-summary", () =>
    HttpResponse.json({
      generatedAt: "2026-06-16T12:00:00Z",
      lastRefreshed: "2026-06-16T12:00:00Z",
      latestSoftDentRefreshAt: "2026-06-16T11:58:00Z",
      dataFreshnessStatus: "fresh",
      healthFlags: [
        {
          key: "softdent_page_coverage",
          code: "SOFTDENT_PAGE_COVERAGE_GAPS",
          status: "warning",
          sourceSystem: "SoftDent",
          message: "SoftDent page coverage has 2 missing and 1 limited report lane(s): Unsubmitted Claims, Treatment Plans, Payment Plans.",
          action:
            "Review the SoftDent coverage table and stage the missing aggregate-only exports before treating blocked dashboard tiles as generic source failures.",
        },
      ],
      transactionDiagnostics: {
        transactionConfigured: true,
        dataSyncTransactionEmitted: true,
        sqliteTransactionRows: 12,
        sourceMode: "softdent+quickbooks",
        validationStatus: "warning",
        summary: "Mock financial source data is available, but SoftDent still has 2 missing and 1 limited dashboard coverage lanes.",
      },
      sourceReview: {
        softDent: {
          sourceSystem: "SoftDent",
          status: "ready",
          summary: "Mock SoftDent snapshot is available.",
          confidenceLabel: "high confidence",
          reviewRequired: false,
          reviewFlags: [],
          lastVerifiedAt: "2026-06-16T12:00:00Z",
          metrics: { providerCount: 1, period: "2026-05" },
        },
        quickBooks: {
          sourceSystem: "QuickBooks",
          status: "ready",
          summary: "Mock QuickBooks summary is available.",
          confidenceLabel: "high confidence",
          reviewRequired: false,
          reviewFlags: [],
          lastVerifiedAt: "2026-06-16T12:00:00Z",
          metrics: { revenueRows: 1, expenseRows: 1, arRows: 3 },
        },
      },
      softDentCoverage: {
        summary: "Missing aggregate claim and plan exports explain why some HAL-owned page lanes are still partial.",
        counts: { missing: 2, limited: 1, available: 4 },
        rows: [
          {
            key: "trueOutstandingClaims",
            label: "True Outstanding Claims",
            status: "available",
            summary: "Approved outstanding-claims aggregate export is available.",
            requiredReport: "outstanding_claims_by_company.csv",
            action: "Continue refreshing this aggregate as part of the monthly claim pack.",
            sourceFile: "outstanding_claims_by_company.csv",
            sourceBackend: "csv",
            modifiedAtUtc: "2026-06-16T11:42:00Z",
            rowCount: 3,
            lastPeriod: "2026-05",
          },
          {
            key: "unsubmittedClaims",
            label: "Unsubmitted Claims",
            status: "missing",
            summary: "Unsubmitted claim exposure is not available until the approved aggregate export lands.",
            requiredReport: "unsubmitted_claims.csv",
            action: "Stage the unsubmitted claims export into the canonical SoftDent import lane.",
            sourceFile: "",
            sourceBackend: "missing",
            modifiedAtUtc: "",
            rowCount: 0,
            lastPeriod: "",
          },
          {
            key: "treatmentPlans",
            label: "Treatment Plans",
            status: "missing",
            summary: "Treatment plan case value is still unavailable.",
            requiredReport: "treatment_plan_summary.csv",
            action: "Export the treatment plan summary and re-import through HAL.",
            sourceFile: "",
            sourceBackend: "missing",
            modifiedAtUtc: "",
            rowCount: 0,
            lastPeriod: "",
          },
          {
            key: "paymentPlans",
            label: "Payment Plans",
            status: "limited",
            summary: "Payment plan coverage is partial and not period-complete.",
            requiredReport: "payment_plans.csv",
            action: "Refresh the payment plan export for the current operating period.",
            sourceFile: "payment_plans.csv",
            sourceBackend: "csv",
            modifiedAtUtc: "2026-06-16T11:40:00Z",
            rowCount: 4,
            lastPeriod: "2026-05",
          },
        ],
      },
      softDentCoverageMetrics: {
        trueOutstandingClaims: {
          label: "True Outstanding Claims",
          available: true,
          sourceFile: "outstanding_claims_by_company.csv",
          sourceBackend: "csv",
          modifiedAtUtc: "2026-06-16T11:42:00Z",
          rowCount: 3,
          itemCount: 9,
          totalAmount: 12401,
          lastPeriod: "2026-05",
          summary: "True outstanding claim exposure is available.",
          breakdown: [
            { label: "Delta Dental", amount: 7100, count: 4 },
            { label: "MetLife", amount: 3801, count: 3 },
          ],
        },
        unsubmittedClaims: {
          label: "Unsubmitted Claims",
          available: true,
          sourceFile: "unsubmitted_claims.csv",
          sourceBackend: "csv",
          modifiedAtUtc: "2026-06-16T11:44:00Z",
          rowCount: 2,
          itemCount: 4,
          totalAmount: 3840,
          lastPeriod: "2026-05",
          summary: "Unsubmitted claim exposure is available.",
          breakdown: [
            { label: "Delta Dental", amount: 2200, count: 2 },
            { label: "Cigna", amount: 1640, count: 2 },
          ],
        },
      },
      claimsSummary: {
        available: true,
        true_outstanding_claims_amount: 12401,
        true_outstanding_claims_count: 9,
        unsubmitted_claims_amount: 3840,
        unsubmitted_claims_count: 4,
        top_outstanding_payers: [
          { label: "Delta Dental", amount: 7100, count: 4 },
          { label: "MetLife", amount: 3801, count: 3 },
        ],
        top_unsubmitted_payers: [
          { label: "Delta Dental", amount: 2200, count: 2 },
          { label: "Cigna", amount: 1640, count: 2 },
        ],
      },
      latestDailyKpi: { production: 4500, collections: 4200 },
      latestAr: {
        as_of_date: "2026-05-31",
        total_ar: 12500,
        insurance_ar: 7200,
        patient_ar: 5300,
        current_balance: 6800,
        balance_30: 2500,
        balance_60: 1900,
        balance_90: 1300,
        credit_balance: 0,
      },
      monthlyKpis: [
        {
          year_month: "2026-04",
          gross_production: 120000,
          net_production: 118000,
          collections: 112000,
          collection_rate: 93.33,
        },
        {
          year_month: "2026-05",
          gross_production: 135000,
          net_production: 132000,
          collections: 126500,
          collection_rate: 93.7,
        },
      ],
      trailing12Months: [
        {
          year_month: "2026-04",
          gross_production: 120000,
          net_production: 118000,
          collections: 112000,
          collection_rate: 93.33,
        },
        {
          year_month: "2026-05",
          gross_production: 135000,
          net_production: 132000,
          collections: 126500,
          collection_rate: 93.7,
        },
      ],
      calendarYearKpis: [],
      fourYearMonthlyKpis: [],
      providerProduction: [
        {
          provider: "Entire Practice",
          production: 135000,
          collections: 126500,
          insurance: 74500,
          patient: 52000,
          period: "2026-05",
        },
      ],
      topAdaCodes: [],
      quickBooksStatus: {
        status: "ready",
        message: "Mock QuickBooks summary loaded",
        lastCheckedAtUtc: "2026-06-16T12:00:00Z",
        lastImportedAtUtc: "2026-06-16T12:00:00Z",
        rowCounts: { revenue: 1, expenses: 1, ar: 3 },
      },
      quickBooksExpenseCategories: [
        { expense_category: "Payroll", total_amount: 23000 },
        { expense_category: "Supplies", total_amount: 6400 },
      ],
      quickBooksMonthlyExpenses: [
        { year_month: "2026-04", expense_total: 33600 },
        { year_month: "2026-05", expense_total: 35100 },
      ],
      quickBooksProfitLossSummary: [
        {
          year_month: "2026-05",
          income_total: 135000,
          expense_total: 35100,
          net_income: 99900,
          last_imported_at_utc: "2026-06-16T12:00:00Z",
        },
      ],
      quickBooksEbitdaCandidates: [
        {
          year_month: "2026-05",
          income_total: 135000,
          expense_total: 35100,
          net_income: 99900,
          base_ebitda_candidate: 99900,
          last_imported_at_utc: "2026-06-16T12:00:00Z",
        },
      ],
      dataFreshnessWarnings: [],
      currentMonthProduction: {
        year_month: "2026-05",
        gross_production: 135000,
        collections: 126500,
      },
      currentYearProduction: {
        year_month: "2026",
        gross_production: 255000,
        collections: 238500,
      },
    }),
  ),
  http.post("/api/hal9000/refresh-financial-sources", () =>
    HttpResponse.json({
      message: "HAL refreshed SoftDent and QuickBooks financial sources.",
      actor: "hal_operator",
      refreshed_at_utc: "2026-06-16T12:00:00Z",
      refresh_report: {
        refresh: {
          daily_refresh_enabled: true,
          last_refresh_date: "2026-06-16",
        },
      },
      financial_summary: {},
      hal_status: {},
      admin_summary: {},
    }),
  ),
  http.get("/api/hal9000/field-timeframes", () =>
    HttpResponse.json({
      mode: "local-rag-phase-1",
      registry: {
        evaluated_at_utc: "2026-06-16T12:00:00Z",
        tracked_field_count: 6,
        within_window_field_count: 4,
        compliance_percent: 66.67,
        pages: [
          {
            page_id: "dashboard",
            page_label: "Financial Dashboard",
            field_count: 2,
            within_window_count: 2,
            fields: [
              {
                field_key: "summary.production_collections",
                data_path: "financial_summary.monthlyKpis[0]",
                source_key: "softdent.snapshot",
                max_landing_minutes: 30,
                observed_source_timestamp_utc: "2026-06-16T11:50:00Z",
                observed_age_minutes: 10,
                within_landing_window: true,
              },
              {
                field_key: "summary.expenses_net_income",
                data_path: "financial_summary.quickBooksProfitLossSummary[0]",
                source_key: "quickbooks.revenue",
                max_landing_minutes: 30,
                observed_source_timestamp_utc: "2026-06-16T11:48:00Z",
                observed_age_minutes: 12,
                within_landing_window: true,
              },
            ],
          },
          {
            page_id: "admin",
            page_label: "Owner Admin",
            field_count: 4,
            within_window_count: 2,
            fields: [
              {
                field_key: "admin.report_pull_status.softdent",
                data_path: "admin_summary.report_pull_status.softdent",
                source_key: "softdent.snapshot",
                max_landing_minutes: 30,
                observed_source_timestamp_utc: "2026-06-16T11:45:00Z",
                observed_age_minutes: 15,
                within_landing_window: true,
              },
              {
                field_key: "admin.report_pull_status.quickbooks",
                data_path: "admin_summary.report_pull_status.quickbooks",
                source_key: "quickbooks.revenue",
                max_landing_minutes: 30,
                observed_source_timestamp_utc: "2026-06-16T11:20:00Z",
                observed_age_minutes: 40,
                within_landing_window: false,
              },
              {
                field_key: "admin.hal_source_review",
                data_path: "hal_status.financial_sources",
                source_key: "softdent.snapshot",
                max_landing_minutes: 30,
                observed_source_timestamp_utc: "2026-06-16T11:45:00Z",
                observed_age_minutes: 15,
                within_landing_window: true,
              },
              {
                field_key: "claims.patient_claim_rows",
                data_path: "financial_sources.softdent.live_claims",
                source_key: "softdent.claims",
                max_landing_minutes: 30,
                observed_source_timestamp_utc: "2026-06-16T10:50:00Z",
                observed_age_minutes: 70,
                within_landing_window: false,
              },
            ],
          },
        ],
      },
    }),
  ),
  http.get("/api/hal9000/status", () =>
    HttpResponse.json({
      mode: "local-rag-phase-1",
      document_count: 19,
      storage_path: "hal_local.sqlite3",
      vector_path: "hal_chroma",
      backend: "chroma",
      embedding_provider: "onnx-minilm",
      financial_sources: {
        softdent: {
          available: true,
          period: "2026-05",
          provider_count: 1,
          live_snapshot: {
            available: true,
            health: "ok",
            source_backend: "json",
            source_file: "softdent_dashboard_data.json",
            modified_at_utc: "2026-06-15T11:45:00+00:00",
            excerpt:
              "SoftDent live snapshot for 2026-05 from json source softdent_dashboard_data.json: production 135000.0, collections 126500.0, insurance 74500.0, patient 52000.0, collection ratio 0.937.",
            checked_at_utc: "2026-06-15T12:00:00+00:00",
            confidence_label: "high confidence",
            review_required: false,
            review_flags: [],
          },
          live_provider_ranking: {
            available: true,
            health: "ok",
            source_backend: "json",
            source_file: "softdent_dashboard_data.json",
            modified_at_utc: "2026-06-15T11:45:00+00:00",
            excerpt:
              "SoftDent practice production for 2026-05: production 135000.0, collections 126500.0, insurance 74500.0, patient 52000.0.",
            checked_at_utc: "2026-06-15T12:00:00+00:00",
            confidence_label: "high confidence",
            review_required: false,
            review_flags: [],
          },
          live_payer_mix: {
            available: true,
            health: "ok",
            source_backend: "json",
            source_file: "softdent_dashboard_data.json",
            modified_at_utc: "2026-06-15T11:45:00+00:00",
            excerpt:
              "SoftDent payer mix for 2026-05: insurance collections share 0.5889, patient collections share 0.4111, insurance 74500.0, patient 52000.0.",
            checked_at_utc: "2026-06-15T12:00:00+00:00",
            confidence_label: "high confidence",
            review_required: false,
            review_flags: [],
          },
          live_collection_delta: {
            available: true,
            health: "ok",
            source_backend: "json",
            source_file: "softdent_dashboard_data.json",
            modified_at_utc: "2026-06-15T11:45:00+00:00",
            excerpt:
              "SoftDent collections delta for 2026-05: production 135000.0, collections 126500.0, delta 8500.0, collection ratio 0.937.",
            checked_at_utc: "2026-06-15T12:00:00+00:00",
            confidence_label: "high confidence",
            review_required: false,
            review_flags: [],
          },
          live_claims: {
            available: true,
            health: "ok",
            source_backend: "csv",
            source_file: "softdent_claims_export.csv",
            modified_at_utc: "2026-06-15T11:47:00+00:00",
            excerpt:
              "SoftDent claims export is available with 14 row(s). Sample fields: ClaimId=1001; ClaimStatus=Denied; Payer=Delta Dental; AgingDays=42.",
            checked_at_utc: "2026-06-15T12:00:00+00:00",
            confidence_label: "high confidence",
            review_required: false,
            review_flags: [],
          },
          live_clinical_notes: {
            available: true,
            health: "ok",
            source_backend: "json",
            source_file: "softdent_clinical_notes_data.json",
            modified_at_utc: "2026-06-15T11:48:00+00:00",
            excerpt:
              "SoftDent clinical notes export is available with 8 row(s). Sample fields: NoteDate=2026-06-15; Provider=Entire Practice; Procedure=Crown prep; ClinicalNote=PATIENT_REDACTED sensitivity persists.",
            checked_at_utc: "2026-06-15T12:00:00+00:00",
            confidence_label: "review suggested",
            review_required: true,
            review_flags: ["contains clinical-note source"],
          },
        },
        quickbooks: {
          live_revenue: {
            topic: "revenue",
            available: true,
            health: "ok",
            source_backend: "sdk",
            source_id: "quickbooks-revenue-summary",
            excerpt:
              "QuickBooks approved revenue summary from sdk read-only query: ReportTitle=Profit & Loss, ReportPeriod=June 1 - 15, 2026, ReportBasis=Cash, TotalIncome=60040.78",
            checked_at_utc: "2026-06-15T12:00:00+00:00",
            confidence_label: "high confidence",
            review_required: false,
            review_flags: [],
          },
          live_expenses: {
            topic: "expenses",
            available: true,
            health: "ok",
            source_backend: "sdk",
            source_id: "quickbooks-expenses-summary",
            excerpt:
              "QuickBooks approved expenses summary from sdk read-only query: ReportTitle=Profit & Loss, ReportPeriod=June 1 - 15, 2026, ReportBasis=Cash, TotalExpense=25333.48",
            checked_at_utc: "2026-06-15T12:00:00+00:00",
            confidence_label: "high confidence",
            review_required: false,
            review_flags: [],
          },
          live_ar: {
            topic: "ar",
            available: false,
            health: "warning",
            source_backend: "unavailable",
            source_id: "quickbooks-ar-unavailable",
            excerpt: "QuickBooks ar summary tool could not run: no approved live report is configured yet.",
            checked_at_utc: "2026-06-15T12:00:00+00:00",
            confidence_label: "manual review",
            review_required: true,
            review_flags: ["live quickbooks summary missing", "source export missing"],
          },
          topics: [
            {
              topic: "revenue",
              configured: true,
              query_source: "sdk-only",
              fallback_count: 0,
            },
            {
              topic: "expenses",
              configured: false,
              query_source: "sdk-only",
              fallback_count: 0,
            },
            {
              topic: "ar",
              configured: false,
              query_source: "sdk-only",
              fallback_count: 0,
            },
          ],
        },
      },
    }),
  ),
  http.get("/api/hal9000/audits", () =>
    HttpResponse.json({
      count: 4,
      items: [
        {
          audit_id: "hal-1",
          created_at_utc: "2026-06-15T12:00:00Z",
          actor: "hal_operator",
          mode: "local-rag-phase-1",
          sanitized_question: "PATIENT_REDACTED claims review",
          retrieval_ids: ["kpi-current-summary"],
          response_summary: "Reviewed KPI summary and claims context from the local Chroma index.",
        },
        {
          audit_id: "hal-2",
          created_at_utc: "2026-06-15T11:40:00Z",
          actor: "admin",
          mode: "local-rag-phase-1",
          sanitized_question: "collections summary",
          retrieval_ids: ["README-1"],
          response_summary: "Summarized collections guidance from approved local context.",
        },
        {
          audit_id: "hal-policy-1",
          created_at_utc: "2026-06-15T12:15:00Z",
          actor: "hal_operator",
          mode: "local-rag-phase-1:accounting-policy",
          sanitized_question: "How should prepaid insurance be treated at period end?",
          retrieval_ids: ["accounting_policy_playbook-1", "month_end_close_checklist-3"],
          response_summary: "Returned draft accounting guidance with citations for prepaid insurance treatment.",
        },
        {
          audit_id: "hal-journal-1",
          created_at_utc: "2026-06-15T12:16:00Z",
          actor: "hal_operator",
          mode: "local-rag-phase-1:journal-draft",
          sanitized_question: "Record prepaid insurance for June coverage.",
          retrieval_ids: ["hal_phi_rag_architecture-24"],
          response_summary: "Drafted a balanced two-line journal entry for prepaid insurance review.",
        },
      ],
    }),
  ),
  http.post("/api/hal9000/insurance-narrative", async ({ request }) => {
    const payload = (await request.json()) as { question?: string };
    const question = payload.question || "";
    return HttpResponse.json({
      mode: "local-rag-phase-1",
      matched: true,
      narrative:
        "Insurance narrative for John Doe. The claim concerns Crown buildup performed or documented on 2026-06-01. The current claim status is Denied with payer Delta Dental. Clinical documentation notes: ClinicalNote Patient has fractured cusp with recurrent decay and documented cold sensitivity.",
      sanitized_question: question.replace("John Doe", "PATIENT_REDACTED").replace("778899", "MRN_REDACTED"),
      sanitization_findings: [
        { label: "patient_name", replacement: "PATIENT_REDACTED" },
        { label: "mrn", replacement: "MRN_REDACTED" },
      ],
      supporting_context: [
        {
          source_id: "softdent-patient-claims-dossier",
          title: "SoftDent patient claims dossier",
          category: "softdent_tool",
          excerpt:
            "SoftDent claims dossier matched rows: PatientName=PATIENT_REDACTED; MRN=MRN_REDACTED; ClaimId=CLM-1001; ClaimStatus=Denied; Payer=Delta Dental; Procedure=Crown buildup; ServiceDate=2026-06-01; DenialReason=Additional narrative requested by payer",
        },
        {
          source_id: "softdent-patient-clinical-dossier",
          title: "SoftDent patient clinical dossier",
          category: "softdent_tool",
          excerpt:
            "SoftDent clinical dossier matched rows: PatientName=PATIENT_REDACTED; MRN=MRN_REDACTED; NoteDate=2026-06-01; Procedure=Crown buildup; ClinicalNote=Patient has fractured cusp with recurrent decay and documented cold sensitivity.",
        },
      ],
      guardrails: [
        "approved local read-only scope",
        "patient-specific local tool only",
        "raw identifiers processed only in local patient tool",
        "sanitized audit trail",
        "review before submission",
      ],
      audit_id: "hal-narrative-1",
      access_policy: {
        mode: "local-rag-phase-1",
        auth_requirement: "Per-user HTTP Basic credentials loaded from deployment configuration with HAL-specific roles are required.",
        network_boundary: "Local-only backend mediation; no direct browser-to-model access.",
        audited: true,
        allowed_sources: ["reviewed_patient_specific_softdent_exports"],
        disallowed_actions: ["raw_phi_prompting", "arbitrary_sql"],
      },
      voice_profile: {
        lane: "patient_workflow",
        label: "Patient workflow",
        tone: "careful and case-focused",
        style_notes: ["Stay specific to the matched patient context."],
      },
      governance_notes: [
        {
          label: "Patient identifiers",
          detail: "Raw identifiers stay inside the reviewed local patient tool and the audit trail stores the sanitized request.",
        },
      ],
    });
  }),
  http.post("/api/hal9000", async ({ request }) => {
    const payload = (await request.json()) as { question?: string };
    const question = payload.question || "";
    return HttpResponse.json({
      mode: "local-rag-phase-1",
      answer: "I can help with that. I found the current monitor settings, but I won't send a brightness change until you approve it here.",
      sanitized_question: question,
      sanitization_findings: [],
      retrieved_context: [
        {
          source_id: "physical_monitor_primary",
          title: "Verified Physical Monitor Parameters (DDC/CI)",
          category: "hardware_status",
          excerpt: "Panel: Brightness=42% | Contrast=68% | Active Input=HDMI-1 (Raw Code=17).",
        },
      ],
      guardrails: ["approved local read-only scope", "deterministic server facts first", "hardware mutations require human confirmation"],
      audit_id: "hal-ask-1",
      access_policy: {
        mode: "local-rag-phase-1",
        auth_requirement: "Per-user HTTP Basic credentials loaded from deployment configuration with HAL-specific roles are required.",
        network_boundary: "Local-only backend mediation; no direct browser-to-model access.",
        audited: true,
        allowed_sources: ["approved_local_read_only_scope"],
        disallowed_actions: ["direct_hardware_writes"],
      },
      voice_profile: {
        lane: "primary",
        label: "Primary response",
        tone: "direct and grounded",
        style_notes: ["Lead with the answer.", "Use verified facts before interpretation."],
      },
      governance_notes: [
        {
          label: "Data boundary",
          detail: "HAL stays inside approved local read-only sources and sanitized retrieval.",
        },
        {
          label: "Human approval",
          detail: "Requested device or state changes stay pending until a human explicitly approves them.",
        },
      ],
      review_actions: [
        {
          action_id: "monitor-set-luminance-30",
          action_type: "SET_LUMINANCE",
          target_device: "primary_monitor",
          target_value: 30,
          human_review_required: true,
          status: "pending_confirmation",
          title: "Set monitor brightness to 30%",
          confirmation_message: "Review before sending a DDC/CI brightness change to 30%.",
        },
      ],
    });
  }),
  http.get("/api/hal9000/accounting-documents", ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") || "8");
    const search = url.searchParams.get("search");
    const documentType = url.searchParams.get("document_type");
    const reviewOnly = url.searchParams.get("review_only") === "true";
    const items = [
      {
        id: 1,
        source_path: "AI_Workspace/invoice-4881.pdf",
        source_name: "invoice-4881.pdf",
        sha256: "mock-sha-1",
        processed_at_utc: "2026-06-15T11:20:00Z",
        extractor: "local_ocr",
        document_type: "invoice",
        vendor_name: "Dental Supply Co.",
        invoice_number: "4881",
        document_date: "2026-06-14",
        total_amount: 700,
        subtotal_amount: 650,
        tax_amount: 50,
        currency: "USD",
        text_preview: "Invoice 4881 from Dental Supply Co. for gloves, bibs, and trays.",
        raw_text: "Invoice 4881 from Dental Supply Co. Items: gloves, bibs, trays. Total due 700 dollars.",
        correction_flags: ["invoice_corrected"],
        confidence_label: "review suggested",
        review_required: true,
      },
      {
        id: 2,
        source_path: "AI_Workspace/receipt-102.pdf",
        source_name: "receipt-102.pdf",
        sha256: "mock-sha-2",
        processed_at_utc: "2026-06-15T11:25:00Z",
        extractor: "local_ocr",
        document_type: "receipt",
        vendor_name: "Midwest Office Depot",
        invoice_number: null,
        document_date: "2026-06-13",
        total_amount: 82.14,
        subtotal_amount: 76.0,
        tax_amount: 6.14,
        currency: "USD",
        text_preview: "Receipt for front office labels and toner.",
        raw_text: "Midwest Office Depot receipt. Labels, toner, shipping.",
        correction_flags: [],
        confidence_label: "high confidence",
        review_required: false,
      },
    ];

    const filteredItems = items.filter((item) => {
      if (documentType && item.document_type !== documentType) {
        return false;
      }
      if (reviewOnly && !item.review_required) {
        return false;
      }
      if (!search) {
        return true;
      }
      const haystack = [item.vendor_name, item.invoice_number, item.source_name, item.raw_text].filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(search.toLowerCase());
    });

    return HttpResponse.json({
      count: filteredItems.length,
      limit,
      document_type: documentType,
      search,
      review_only: reviewOnly,
      items: filteredItems.slice(0, limit),
    });
  }),
  http.get("/api/hal9000/document-rag/documents", ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") || "25");
    const search = url.searchParams.get("search");
    const items = [
      {
        document_id: "doc-mock-001",
        source_name: "q2-earnings-notes.md",
        stored_path: "document_rag/uploads/doc-mock-001-q2-earnings-notes.md",
        mime_type: "text/markdown",
        sha256: "mock-doc-sha-1",
        uploaded_at_utc: "2026-06-21T14:10:00Z",
        uploaded_by: "hal_operator",
        page_count: 1,
        chunk_count: 2,
        content_char_count: 284,
      },
    ].filter((item) => !search || item.source_name.toLowerCase().includes(search.toLowerCase()));

    return HttpResponse.json({
      count: items.length,
      limit,
      search,
      items: items.slice(0, limit),
    });
  }),
  http.post("/api/hal9000/document-rag/documents", async () => {
    return HttpResponse.json({
      message: "Indexed q2-earnings-notes.md for grounded document Q&A.",
      document: {
        document_id: "doc-mock-001",
        source_name: "q2-earnings-notes.md",
        stored_path: "document_rag/uploads/doc-mock-001-q2-earnings-notes.md",
        mime_type: "text/markdown",
        sha256: "mock-doc-sha-1",
        uploaded_at_utc: "2026-06-21T14:10:00Z",
        uploaded_by: "hal_operator",
        page_count: 1,
        chunk_count: 2,
        content_char_count: 284,
      },
    });
  }),
  http.post("/api/hal9000/document-rag/ask", async ({ request }) => {
    const payload = (await request.json()) as { question?: string };
    return HttpResponse.json({
      mode: "langchain-document-rag-v1",
      answer: payload.question?.toLowerCase().includes("revenue")
        ? "Revenue increased by 12% year over year in Q2 2026."
        : "I do not have enough grounded context in the uploaded files to answer that.",
      sanitized_question: payload.question || "",
      sanitization_findings: [],
      retrieved_context: [
        {
          source_id: "doc-mock-001:chunk:1",
          title: "q2-earnings-notes.md",
          category: "uploaded_document",
          excerpt: "Page 1, chunk 1: Revenue increased 12% year over year. Operating margin improved 180 basis points.",
        },
      ],
      guardrails: ["uploaded files only", "grounded answer only", "insufficient context fallback", "audit log recorded"],
      audit_id: "hal-document-rag-1",
      document_count: 1,
      grounded: true,
    });
  }),
  http.post("/api/hardware/monitor-actions", async ({ request }) => {
    const payload = (await request.json()) as {
      action_type?: string;
      target_value?: number;
      user_confirmed?: boolean;
    };
    return HttpResponse.json({
      status: payload.user_confirmed ? "executed" : "rejected",
      action_type: payload.action_type || null,
      requested_value: typeof payload.target_value === "number" ? payload.target_value : null,
      applied_value: payload.user_confirmed && typeof payload.target_value === "number" ? payload.target_value : null,
      error: payload.user_confirmed ? null : "Human-in-the-loop confirmation flag was false.",
      source_backend: "ddc_ci",
    });
  }),
  http.post("/api/hal9000/patient-dossier", async ({ request }) => {
    const payload = (await request.json()) as { question?: string };
    const question = payload.question || "";
    return HttpResponse.json({
      mode: "local-rag-phase-1",
      matched: true,
      summary: "Patient-specific SoftDent claim and/or clinical-note context matched in the approved local exports.",
      sanitized_question: question.replace("John Doe", "PATIENT_REDACTED").replace("778899", "MRN_REDACTED"),
      sanitization_findings: [
        { label: "patient_name", replacement: "PATIENT_REDACTED" },
        { label: "mrn", replacement: "MRN_REDACTED" },
      ],
      supporting_context: [
        {
          source_id: "softdent-patient-claims-dossier",
          title: "SoftDent patient claims dossier",
          category: "softdent_tool",
          excerpt:
            "SoftDent claims dossier matched rows: PatientName=PATIENT_REDACTED; MRN=MRN_REDACTED; ClaimId=CLM-1001; ClaimStatus=Denied; Payer=Delta Dental",
        },
        {
          source_id: "softdent-patient-clinical-dossier",
          title: "SoftDent patient clinical dossier",
          category: "softdent_tool",
          excerpt:
            "SoftDent clinical dossier matched rows: PatientName=PATIENT_REDACTED; MRN=MRN_REDACTED; Procedure=Crown buildup; ClinicalNote=Patient has fractured cusp.",
        },
      ],
      guardrails: [
        "approved local read-only scope",
        "patient-specific local tool only",
        "raw identifiers processed only in local patient tool",
        "sanitized audit trail",
      ],
      audit_id: "hal-dossier-1",
      access_policy: {
        mode: "local-rag-phase-1",
        auth_requirement: "Per-user HTTP Basic credentials loaded from deployment configuration with HAL-specific roles are required.",
        network_boundary: "Local-only backend mediation; no direct browser-to-model access.",
        audited: true,
        allowed_sources: ["reviewed_patient_specific_softdent_exports"],
        disallowed_actions: ["raw_phi_prompting", "arbitrary_sql"],
      },
      voice_profile: {
        lane: "patient_workflow",
        label: "Patient workflow",
        tone: "careful and case-focused",
        style_notes: ["Stay specific to the matched patient context."],
      },
      governance_notes: [
        {
          label: "Patient identifiers",
          detail: "Raw identifiers stay inside the reviewed local patient tool and the audit trail stores the sanitized request.",
        },
      ],
    });
  }),
  http.post("/api/hal9000/chart-plan", async ({ request }) => {
    const payload = (await request.json()) as { question?: string };
    const question = payload.question || "";
    return HttpResponse.json({
      mode: "local-rag-phase-1",
      status: "pending_human_review",
      question,
      request_json: {
        chart_config: {
          chart_type: "bar",
          title: "June Overhead Variance",
          x_axis_label: "Category",
          y_axis_label: "Amount",
          value_format: "currency",
        },
        chart_data: [
          { label: "Software", value: 540.0 },
          { label: "Rent", value: 1200.0 },
        ],
        flag_for_review: true,
        review_reason: "Generated from narrative prompt; confirm values before rendering.",
        alert_reason: "Potential discrepancy: narrative prompt did not cite a source file.",
      },
      request_file_path: "2026-06-16-june-overhead-variance-generated-chart-request.json",
      planned_output_path: "2026-06-16-june-overhead-variance.png",
      review_plan_path: "review_plans/20260616T120000Z-hal-chart-render.json",
      preview_summary:
        "Chart preview: June Overhead Variance\nType: bar\nPoints: 2\nX axis: Category\nY axis: Amount\nPlanned output: 2026-06-16-june-overhead-variance.png\nReview required: Generated from narrative prompt; confirm values before rendering.\n[ALERT] Potential discrepancy: narrative prompt did not cite a source file.",
      flag_for_review: true,
      review_reason: "Generated from narrative prompt; confirm values before rendering.",
      alert_reason: "Potential discrepancy: narrative prompt did not cite a source file.",
      guardrails: [
        "structured chart JSON only",
        "pending human review before PNG render",
        "sandboxed artifact staging inside AI_Workspace",
      ],
      audit_id: "hal-chart-1",
      access_policy: {
        mode: "local-rag-phase-1",
        auth_requirement: "Per-user HTTP Basic credentials loaded from deployment configuration with HAL-specific roles are required.",
        network_boundary: "Local-only backend mediation; no direct browser-to-model access.",
        audited: true,
        workspace_root: "AI_Workspace",
        activity_log_path: "AI_Workspace/ai_activity.log",
        review_plan_directory: "AI_Workspace/review_plans",
        allowed_sources: ["approved_local_read_only_scope"],
        disallowed_actions: ["direct_hardware_writes"],
        capability_hierarchy: [],
      },
    });
  }),
  http.post("/api/hal9000/chart-plan/approve", async ({ request }) => {
    const payload = (await request.json()) as { review_plan_path?: string };
    return HttpResponse.json({
      mode: "local-rag-phase-1",
      status: "approved_and_rendered",
      review_plan_path: payload.review_plan_path || "review_plans/20260616T120000Z-hal-chart-render.json",
      request_json: {
        chart_config: {
          chart_type: "bar",
          title: "June Overhead Variance",
          x_axis_label: "Category",
          y_axis_label: "Amount",
          value_format: "currency",
        },
        chart_data: [
          { label: "Software", value: 540.0 },
          { label: "Rent", value: 1200.0 },
        ],
        flag_for_review: true,
        review_reason: "Generated from narrative prompt; confirm values before rendering.",
        alert_reason: "Potential discrepancy: narrative prompt did not cite a source file.",
      },
      rendered_output_path: "2026-06-16-june-overhead-variance.png",
      flag_for_review: true,
      review_reason: "Generated from narrative prompt; confirm values before rendering.",
      alert_reason: "Potential discrepancy: narrative prompt did not cite a source file.",
      guardrails: [
        "human approval recorded before PNG render",
        "sandboxed artifact write inside AI_Workspace",
        "structured chart JSON validated before render",
      ],
      audit_id: "hal-chart-1",
      access_policy: {
        mode: "local-rag-phase-1",
        auth_requirement: "Per-user HTTP Basic credentials loaded from deployment configuration with HAL-specific roles are required.",
        network_boundary: "Local-only backend mediation; no direct browser-to-model access.",
        audited: true,
        workspace_root: "AI_Workspace",
        activity_log_path: "AI_Workspace/ai_activity.log",
        review_plan_directory: "AI_Workspace/review_plans",
        allowed_sources: ["approved_local_read_only_scope"],
        disallowed_actions: ["direct_hardware_writes"],
        capability_hierarchy: [],
      },
    });
  }),
  http.get("/api/hal9000/chart-plans", ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") || "8");
    const status = url.searchParams.get("status");
    const items = [
      {
        review_plan_path: "review_plans/20260616T120500Z-hal-chart-render.json",
        created_at_utc: "2026-06-16T12:05:00+00:00",
        status: "approved_and_rendered",
        question: "Create a bar chart showing June overhead variance by category.",
        title: "June Overhead Variance",
        chart_type: "bar",
        planned_output_path: "2026-06-16-june-overhead-variance.png",
        rendered_output_path: "2026-06-16-june-overhead-variance.png",
        audit_id: "hal-chart-1",
      },
      {
        review_plan_path: "review_plans/20260616T121000Z-hal-chart-render.json",
        created_at_utc: "2026-06-16T12:10:00+00:00",
        status: "pending_human_approval",
        question: "Create a line chart showing collections trend by week.",
        title: "Collections Trend",
        chart_type: "line",
        planned_output_path: "2026-06-16-collections-trend.png",
        rendered_output_path: null,
        audit_id: "hal-chart-2",
      },
    ].filter((item) => !status || item.status === status);
    return HttpResponse.json({
      count: items.length,
      limit,
      status,
      items,
    });
  }),
  http.get("/api/hal9000/chart-files", ({ request }) => {
    const url = new URL(request.url);
    const path = url.searchParams.get("path");
    if (!path) {
      return HttpResponse.json({ detail: "path query parameter is required" }, { status: 422 });
    }
    const mockPng = Uint8Array.from([
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00,
      0x00, 0x01, 0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00, 0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63,
      0x00, 0x01, 0x00, 0x00, 0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60,
      0x82,
    ]);
    return new HttpResponse(mockPng, {
      status: 200,
      headers: { "Content-Type": "image/png" },
    });
  }),
  http.post("/api/hal9000/accounting/journal-draft", async ({ request }) => {
    const payload = (await request.json()) as {
      description?: string;
      accounting_period?: string;
      amount?: number;
      context?: {
        use_local_ai_workflow?: boolean;
        auto_enqueue_validated_draft?: boolean;
        source_text?: string;
      };
    };
    const description = payload.description || "";
    const period = payload.accounting_period || "2026-06";
    const amount = payload.amount || 0;
    const openPeriod = period !== "2024-12";
    const autoEnqueue = Boolean(
      payload.context?.use_local_ai_workflow &&
        payload.context?.auto_enqueue_validated_draft &&
        payload.context?.source_text?.trim() &&
        openPeriod,
    );
    return HttpResponse.json({
      mode: "local-rag-phase-1",
      summary: autoEnqueue
        ? "AI-assisted draft validated and pushed to the posting queue for human review."
        : `Drafted 2 journal line(s) for review from sanitized accounting input. Balanced=true. Open period=${openPeriod}.`,
      lines: [
        {
          account_code: "1310",
          account_name: "Prepaid Insurance",
          debit: amount,
          credit: 0,
          memo: description,
        },
        {
          account_code: "1010",
          account_name: "Cash",
          debit: 0,
          credit: amount,
          memo: description,
        },
      ],
      validation: {
        balanced: true,
        debit_total: amount,
        credit_total: amount,
        open_period: openPeriod,
        account_validation_passed: true,
        issues: openPeriod ? [] : ["Accounting period is closed."],
      },
      supporting_context: [
        {
          source_id: "hal_phi_rag_architecture-1",
          title: "HAL PHI-Safe Local AI Architecture",
          category: "documentation",
          excerpt: "Use backend-owned tool functions and keep outputs aggregated whenever possible.",
        },
      ],
      review_required: true,
      draft_status: (autoEnqueue ? DRAFT_STATUS_ENQUEUED : DRAFT_STATUS_DRAFT_ONLY) as JournalDraftStatus,
      queue_id: autoEnqueue ? "qbd-queue-mock-001" : null,
      queue_status: autoEnqueue ? POSTING_QUEUE_STATUS_PENDING_REVIEW : null,
      enqueue_error: null,
      audit_id: "hal-journal-1",
      access_policy: {
        mode: "local-rag-phase-1",
        auth_requirement: "Per-user HTTP Basic credentials loaded from deployment configuration with HAL-specific roles are required.",
        network_boundary: "Local-only backend mediation; no direct browser-to-model access.",
        audited: true,
        allowed_sources: ["calculated_kpis", "approved_quickbooks_summary_queries", "internal_policy_docs"],
        disallowed_actions: ["raw_phi_prompting", "arbitrary_sql", "production_writes"],
      },
    });
  }),
  http.post("/api/hal9000/accounting/policy-answer", async ({ request }) => {
    const payload = (await request.json()) as {
      question?: string;
      topic?: string;
      accounting_standard?: string;
    };
    return HttpResponse.json({
      mode: "local-rag-phase-1",
      answer: `For this request, HAL found relevant guidance from approved local policy sources. Treat this as draft guidance under ${payload.accounting_standard || "internal reviewed guidance"}. A human reviewer should confirm the final accounting treatment before anything reaches the ledger.`,
      accounting_standard: payload.accounting_standard || null,
      citations: [
        {
          source_id: "hal_phi_rag_architecture-24",
          title: "hal_phi_rag_architecture chunk 24",
          excerpt: "Use backend-owned tool functions such as get_monthly_kpi(period) and get_ar_aging_snapshot(period).",
        },
        {
          source_id: "API-1",
          title: "API chunk 1",
          excerpt: "HAL reads indexed local documentation, KPI summaries, and sanitized SoftDent aggregate snapshots.",
        },
      ],
      confidence: "medium",
      review_required: true,
      audit_id: "hal-policy-1",
      access_policy: {
        mode: "local-rag-phase-1",
        auth_requirement: "Per-user HTTP Basic credentials loaded from deployment configuration with HAL-specific roles are required.",
        network_boundary: "Local-only backend mediation; no direct browser-to-model access.",
        audited: true,
        allowed_sources: ["calculated_kpis", "internal_policy_docs"],
        disallowed_actions: ["raw_phi_prompting", "arbitrary_sql", "production_writes"],
      },
      voice_profile: {
        lane: "policy",
        label: "Policy guidance",
        tone: "measured and review-oriented",
        style_notes: ["Frame the answer as draft guidance.", "Ground the answer in approved citations."],
      },
      governance_notes: [
        {
          label: "Draft-only guidance",
          detail: "Accounting policy answers are advisory and require human accounting review before operational use.",
        },
        {
          label: "Approved sources",
          detail: "This answer was grounded in approved local citations.",
        },
      ],
    });
  }),
  http.post("/api/hal9000/accounting/posting-queue", async ({ request }) => {
    const payload = (await request.json()) as {
      description?: string;
      transaction_date?: string;
      accounting_period?: string;
      amount?: number;
      transaction_type?: string;
      source_audit_id?: string;
      enqueue_mode?: PostingQueueEnqueueMode;
      lines?: PostingQueueItem["lines"];
    };
    const nextItem: PostingQueueItem = {
      queue_id: `qbd-queue-${1000 + postingQueueItems.length + 1}`,
      created_at_utc: "2026-06-15T12:35:00Z",
      actor: "hal_operator",
      target_system: "quickbooks_desktop",
      status: POSTING_QUEUE_STATUS_PENDING_REVIEW,
      description: payload.description || "Queued accounting draft",
      transaction_date: payload.transaction_date || "2026-06-15",
      accounting_period: payload.accounting_period || "2026-06",
      amount: payload.amount || 0,
      transaction_type: payload.transaction_type || null,
      source_audit_id: payload.source_audit_id || "hal-audit-missing",
      enqueue_mode: payload.enqueue_mode || ENQUEUE_MODE_MANUAL_REVIEW_QUEUE,
      lines: payload.lines || [],
      validation: {
        balanced: true,
        debit_total: payload.amount || 0,
        credit_total: payload.amount || 0,
        open_period: true,
        account_validation_passed: true,
        issues: [],
      },
      reviewer_actor: null,
      reviewed_at_utc: null,
      review_note: null,
      review_required: true,
    };
    postingQueueItems = [nextItem, ...postingQueueItems];
    return HttpResponse.json(nextItem);
  }),
  http.get("/api/hal9000/accounting/posting-queue", ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") || "10");
    const cursor = url.searchParams.get("cursor");
    const status = url.searchParams.get("status");
    const filteredItems = status ? postingQueueItems.filter((item) => item.status === status) : postingQueueItems;
    let startIndex = 0;
    if (cursor) {
      const cursorIndex = filteredItems.findIndex((item) => `${item.created_at_utc}|${item.queue_id}` === cursor);
      startIndex = cursorIndex >= 0 ? cursorIndex + 1 : filteredItems.length;
    }
    const pageItems = filteredItems.slice(startIndex, startIndex + limit);
    const nextItem = filteredItems[startIndex + limit];
    return HttpResponse.json({
      count: pageItems.length,
      total_count: filteredItems.length,
      limit,
      cursor,
      next_cursor: nextItem ? `${pageItems[pageItems.length - 1]?.created_at_utc}|${pageItems[pageItems.length - 1]?.queue_id}` : null,
      range_start: pageItems.length === 0 ? 0 : startIndex + 1,
      range_end: startIndex + pageItems.length,
      status,
      items: pageItems,
    });
  }),
  http.get("/api/hal9000/accounting/posting-queue/metrics", () =>
    HttpResponse.json({
      total_count: postingQueueItems.length,
      pending_review_count: postingQueueItems.filter((item) => item.status === POSTING_QUEUE_STATUS_PENDING_REVIEW).length,
      approved_count: postingQueueItems.filter((item) => item.status === POSTING_QUEUE_STATUS_APPROVED).length,
      rejected_count: postingQueueItems.filter((item) => item.status === POSTING_QUEUE_STATUS_REJECTED).length,
    }),
  ),
  http.get("/api/hal9000/accounting/posting-queue/activity", ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") || "10");
    const pageItems = postingQueueItems.slice(0, limit).map(({ lines, validation, ...item }) => item);
    return HttpResponse.json({
      count: pageItems.length,
      limit,
      items: pageItems,
    });
  }),
  http.post("/api/hal9000/accounting/posting-queue/:queueId/review", async ({ params, request }) => {
    const payload = (await request.json()) as {
      action?: PostingQueueReviewAction;
      review_note?: string;
    };
    const queueId = String(params.queueId || "");
    const index = postingQueueItems.findIndex((item) => item.queue_id === queueId);
    if (index < 0) {
      return HttpResponse.json({ detail: "Posting queue entry was not found." }, { status: 404 });
    }
    const currentItem = postingQueueItems[index];
    if (currentItem.status !== POSTING_QUEUE_STATUS_PENDING_REVIEW) {
      return HttpResponse.json(
        {
          detail: "Only pending review queue entries can be approved or rejected.",
        },
        { status: 400 },
      );
    }
    const nextItem: PostingQueueItem = {
      ...currentItem,
      status: payload.action === POSTING_QUEUE_STATUS_REJECTED ? POSTING_QUEUE_STATUS_REJECTED : POSTING_QUEUE_STATUS_APPROVED,
      reviewer_actor: "hal_operator",
      reviewed_at_utc: "2026-06-15T12:40:00Z",
      review_note: payload.review_note || null,
      review_required: payload.action !== POSTING_QUEUE_STATUS_APPROVED,
    };
    postingQueueItems = postingQueueItems.map((item) => (item.queue_id === queueId ? nextItem : item));
    return HttpResponse.json(nextItem);
  }),
  http.get("/api/reports/pull-status", () =>
    HttpResponse.json({
      daily_refresh_enabled: true,
      last_refresh_date: "2026-05-23",
      status: { softdent: { scanned: 2, copied: 1, updated: 0, skipped: 1 } },
    }),
  ),
];
