import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { formatCurrency } from "../../utils/formatting";
import {
  fetchAccountingPostingQueueActivity,
  fetchAccountingPostingQueueMetrics,
  fetchAdminSummary,
  fetchFinancialSummary,
  fetchHalAudits,
  fetchHalFieldTimeframes,
  fetchHalStatus,
  refreshHalFinancialSources,
} from "../api/client";
import { SoftDentCoveragePanel } from "../components/dashboard/SoftDentCoveragePanel";
import { TransactionDiagnosticsCard } from "../components/dashboard/TransactionDiagnosticsCard";
import { TransactionFeedStatusNotice } from "../components/dashboard/TransactionFeedStatusNotice";
import { PageSurfaceHeader, PageSurfaceShell } from "../components/PageSurfaceHeader";
import { useAuthSession } from "../hooks/useAuthSession";
import { queryClient, queryKeys } from "../queryClient";
import { getPostingQueueActivityLineageLabel, getPostingQueueHandoffModeLabel } from "../utils/postingQueueLineage";

function confidenceBadgeClass(label: string, reviewRequired: boolean) {
  if (label === "manual review") {
    return "dashboard-import-status-badge dashboard-import-status-badge--error";
  }
  if (reviewRequired || label === "review suggested") {
    return "dashboard-import-status-badge dashboard-import-status-badge--pending";
  }
  return "dashboard-import-status-badge";
}

function landingWindowBadgeClass(withinWindow: boolean, observedAgeMinutes: number | null, maxLandingMinutes: number) {
  if (withinWindow) {
    return "dashboard-import-status-badge";
  }
  if (observedAgeMinutes !== null && observedAgeMinutes <= maxLandingMinutes * 1.5) {
    return "dashboard-import-status-badge dashboard-import-status-badge--pending";
  }
  return "dashboard-import-status-badge dashboard-import-status-badge--error";
}

export default function AdminPage() {
  const {
    isAuthenticated,
    isAdmin,
    isLoading: isAuthSessionLoading,
    isError: isAuthSessionError,
    isRoleKnown,
    error: authSessionError,
    retry: retryAuthSession,
  } = useAuthSession();
  const canLoadAdminData = isAuthenticated && isRoleKnown && isAdmin;
  const adminSummaryQuery = useQuery({
    queryKey: queryKeys.adminSummary,
    queryFn: fetchAdminSummary,
    enabled: canLoadAdminData,
  });
  const halStatusQuery = useQuery({
    queryKey: queryKeys.halStatus,
    queryFn: fetchHalStatus,
    enabled: canLoadAdminData,
  });
  const halFieldTimeframesQuery = useQuery({
    queryKey: ["hal-field-timeframes"],
    queryFn: fetchHalFieldTimeframes,
    enabled: canLoadAdminData,
  });
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
    enabled: canLoadAdminData,
  });
  const halAuditQuery = useQuery({
    queryKey: queryKeys.halAudits,
    queryFn: () => fetchHalAudits(5),
    enabled: canLoadAdminData,
  });
  const postingQueueQuery = useQuery({
    queryKey: ["accounting-posting-queue-activity-admin"],
    queryFn: () => fetchAccountingPostingQueueActivity(10),
    enabled: canLoadAdminData,
  });
  const postingQueueMetricsQuery = useQuery({
    queryKey: ["accounting-posting-queue-metrics"],
    queryFn: fetchAccountingPostingQueueMetrics,
    enabled: canLoadAdminData,
  });
  const refreshMutation = useMutation({
    mutationFn: refreshHalFinancialSources,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["financial-summary"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.adminSummary });
      queryClient.invalidateQueries({ queryKey: queryKeys.halStatus });
      queryClient.invalidateQueries({ queryKey: queryKeys.halAudits });
      queryClient.invalidateQueries({ queryKey: ["hal-field-timeframes"] });
    },
  });

  const summary = adminSummaryQuery.data;
  const halStatus = halStatusQuery.data;
  const healthFlags = financialSummaryQuery.data?.healthFlags ?? [];
  const transactionDiagnostics = financialSummaryQuery.data?.transactionDiagnostics ?? null;
  const halAudits = halAuditQuery.data?.items ?? [];
  const accountingAudits = halAudits.filter((item) => item.mode.includes("accounting") || item.mode.includes("journal-draft"));
  const postingQueueItems = postingQueueQuery.data?.items ?? [];
  const postingQueueItemsBySourceAudit = new Map<string, typeof postingQueueItems>();
  for (const item of postingQueueItems) {
    const existingItems = postingQueueItemsBySourceAudit.get(item.source_audit_id) ?? [];
    postingQueueItemsBySourceAudit.set(item.source_audit_id, [...existingItems, item]);
  }
  const postingQueueMetrics = postingQueueMetricsQuery.data;
  const pendingPostingQueueCount = postingQueueMetrics?.pending_review_count ?? 0;
  const approvedPostingQueueCount = postingQueueMetrics?.approved_count ?? 0;
  const rejectedPostingQueueCount = postingQueueMetrics?.rejected_count ?? 0;
  const totalPostingQueueCount = postingQueueMetrics?.total_count ?? 0;
  const financialSources = halStatus?.financial_sources;
  const softdentFinancialSource = financialSources?.softdent;
  const quickbooksFinancialSource = financialSources?.quickbooks;
  const softdentLiveSnapshot = softdentFinancialSource?.live_snapshot;
  const softdentLivePracticeProduction = softdentFinancialSource?.live_provider_ranking;
  const softdentLivePayerMix = softdentFinancialSource?.live_payer_mix;
  const softdentLiveCollectionDelta = softdentFinancialSource?.live_collection_delta;
  const softdentLiveTransactionFeed = softdentFinancialSource?.live_transaction_feed;
  const softdentLiveClaims = softdentFinancialSource?.live_claims;
  const softdentLiveClinicalNotes = softdentFinancialSource?.live_clinical_notes;
  const softdentLiveStatuses = [
    { label: "SOFTDENT SNAPSHOT", item: softdentLiveSnapshot },
    { label: "SOFTDENT PRACTICE PRODUCTION", item: softdentLivePracticeProduction },
    { label: "SOFTDENT PAYER MIX", item: softdentLivePayerMix },
    { label: "SOFTDENT COLLECTIONS DELTA", item: softdentLiveCollectionDelta },
    { label: "SOFTDENT TRANSACTION FEED", item: softdentLiveTransactionFeed },
    { label: "SOFTDENT CLAIMS", item: softdentLiveClaims },
    { label: "SOFTDENT CLINICAL NOTES", item: softdentLiveClinicalNotes },
  ].filter((entry) => Boolean(entry.item));
  const quickbooksTopics = quickbooksFinancialSource?.topics ?? [];
  const quickbooksLiveRevenue = quickbooksFinancialSource?.live_revenue;
  const quickbooksLiveExpenses = quickbooksFinancialSource?.live_expenses;
  const quickbooksLiveAr = quickbooksFinancialSource?.live_ar;
  const quickbooksLiveStatuses = [quickbooksLiveRevenue, quickbooksLiveExpenses, quickbooksLiveAr].filter(
    (item): item is NonNullable<typeof quickbooksLiveRevenue> => Boolean(item),
  );
  const fieldRegistry = halFieldTimeframesQuery.data?.registry;
  const fieldRegistryPages = fieldRegistry?.pages ?? [];
  const softDentCoverage = financialSummaryQuery.data?.softDentCoverage ?? null;
  const claimsSummary = financialSummaryQuery.data?.claimsSummary ?? null;
  const topOutstandingPayers = claimsSummary?.top_outstanding_payers ?? [];
  const topUnsubmittedPayers = claimsSummary?.top_unsubmitted_payers ?? [];

  if (isAuthenticated && isAuthSessionLoading) {
    return (
      <div className="dashboard-page admin-page">
        <header className="admin-hero">
          <p className="admin-eyebrow">Operations Console</p>
          <h1>Owner Financial Dashboard</h1>
          <p className="admin-subtitle">Checking admin access for the authenticated API session.</p>
        </header>
      </div>
    );
  }

  if (isAuthenticated && isAuthSessionError) {
    return (
      <div className="dashboard-page admin-page">
        <header className="admin-hero">
          <p className="admin-eyebrow">Operations Console</p>
          <h1>Owner Financial Dashboard</h1>
          <p className="admin-subtitle">The API session is connected, but admin access could not be verified yet.</p>
        </header>

        <section className="admin-grid">
          <article className="admin-card admin-card--highlight">
            <h2>Admin Session Check Failed</h2>
            <p>{authSessionError?.message || "Unable to verify admin access for the current API session."}</p>
            <div className="hal-form__actions">
              <button type="button" className="refresh-button" onClick={() => void retryAuthSession()}>
                Retry admin check
              </button>
              <Link to="/">Return to the dashboard</Link>
            </div>
          </article>
        </section>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="dashboard-page admin-page">
        <header className="admin-hero">
          <p className="admin-eyebrow">Operations Console</p>
          <h1>Owner Financial Dashboard</h1>
          <p className="admin-subtitle">Sign in with an admin account to load HAL refresh controls, audit review, and owner-only financial operations.</p>
        </header>

        <section className="admin-grid">
          <article className="admin-card admin-card--highlight">
            <h2>Sign-In Required</h2>
            <p>Use the dashboard sign-in banner to connect an admin account before opening the owner console.</p>
            <Link to="/">Return to the dashboard</Link>
          </article>
        </section>
      </div>
    );
  }

  if (isAuthenticated && isRoleKnown && !isAdmin) {
    return (
      <div className="dashboard-page admin-page">
        <header className="admin-hero">
          <p className="admin-eyebrow">Operations Console</p>
          <h1>Owner Financial Dashboard</h1>
          <p className="admin-subtitle">Admin access is required for HAL refreshes, audit review, and owner-only financial operations.</p>
        </header>

        <section className="admin-grid">
          <article className="admin-card admin-card--highlight">
            <h2>Admin Access Required</h2>
            <p>Signed-in viewer accounts can continue using the reporting pages, but this console is limited to admin users.</p>
            <Link to="/">Return to the dashboard</Link>
          </article>
        </section>
      </div>
    );
  }

  return (
    <PageSurfaceShell className="admin-page">
      <PageSurfaceHeader
        breadcrumbs="Owner / Operations console"
        eyebrow="Operations console"
        title="Owner financial dashboard"
        titleId="admin-page-title"
        description="SoftDent-fed financial dashboard with HAL retrieval visibility, audit checkpoints, and local vector index health."
        badges={[
          { label: "Owner Access" },
          { label: "Local Audit Trail" },
          { label: "Read-Only Sources" },
        ]}
        statusItems={[
          { label: "Last refresh", value: summary?.last_refresh_date || "Not available" },
          { label: "HAL mode", value: halStatusQuery.data?.mode ?? "Unknown" },
          { label: "Posting queue", value: String(postingQueueQuery.data?.items?.length ?? 0) },
        ]}
      />

      <section className="admin-toolbar">
        <button type="button" className="admin-button" onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending}>
          HAL Refresh SoftDent + QuickBooks
        </button>
        <div className="admin-toolbar__meta">Last refresh: {summary?.last_refresh_date || "not available"}</div>
      </section>

      {refreshMutation.isError ? (
        <section className="admin-grid">
          <article className="admin-card admin-card--highlight">
            <h2>Refresh failed</h2>
            <p>{refreshMutation.error instanceof Error ? refreshMutation.error.message : "Unable to refresh HAL financial sources."}</p>
          </article>
        </section>
      ) : null}

      <section className="admin-grid">
        <article className="admin-card">
          <h2>SoftDent-fed financial dashboard</h2>
          <p>{summary?.priority_summary || "Waiting for owner summary data."}</p>
          <ul className="admin-list">
            {(summary?.priority_actions || []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="admin-card admin-card--highlight">
          <h2>HAL Retrieval Status</h2>
          <dl className="admin-kv">
            <div>
              <dt>Backend</dt>
              <dd>{halStatus?.backend || "loading"}</dd>
            </div>
            <div>
              <dt>Embedding model</dt>
              <dd>{halStatus?.embedding_provider || "loading"}</dd>
            </div>
            <div>
              <dt>Indexed documents</dt>
              <dd>{halStatus?.document_count ?? "loading"}</dd>
            </div>
            <div>
              <dt>SoftDent snapshot</dt>
              <dd>
                {softdentFinancialSource?.available
                  ? `${softdentFinancialSource.period || "current"} · practice-wide`
                  : "not available"}
              </dd>
            </div>
          </dl>
          <div className="admin-audit-list">
            {softdentLiveStatuses.map(({ label, item }) => (
              <div key={label} className="admin-audit-item">
                <div className="admin-audit-item__header">
                  <strong>{label}</strong>
                  <span>
                    {item?.health?.toUpperCase() || "LOADING"} · {item?.source_backend || "missing"} ·{" "}
                    <span className={confidenceBadgeClass(item?.confidence_label || "manual review", item?.review_required ?? true)}>
                      {item?.confidence_label || "manual review"}
                    </span>
                  </span>
                </div>
                <div className="admin-audit-item__summary">{item?.excerpt || "SoftDent live status is not available yet."}</div>
                <div className="admin-audit-item__summary">Source file: {item?.source_file || "unknown"}</div>
                <div className="admin-audit-item__summary">Source modified: {item?.modified_at_utc || "unknown"}</div>
                <div className="admin-audit-item__summary">Last checked: {item?.checked_at_utc || "unknown"}</div>
                <div className="admin-audit-item__summary">
                  {(item?.review_flags?.length ?? 0) > 0 ? (
                    item?.review_flags?.map((flag) => (
                      <span
                        key={`${label}-${flag}`}
                        className="dashboard-import-status-badge dashboard-import-status-badge--pending dashboard-import-status-badge--spaced"
                      >
                        {flag}
                      </span>
                    ))
                  ) : (
                    <span className="dashboard-import-status-badge">no review flags</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="admin-card">
          <h2>Transaction Feed Status</h2>
          <TransactionFeedStatusNotice healthFlags={healthFlags} />
          <div className="admin-audit-list admin-audit-list--spaced">
            <TransactionDiagnosticsCard diagnostics={transactionDiagnostics} />
          </div>
        </article>

        <article className="admin-card admin-card--wide">
          <h2>SoftDent Coverage Accountability</h2>
          <p className="admin-card__summary">
            HAL now treats missing page report lanes as operator-visible issues instead of generic freshness drift.
          </p>
          <SoftDentCoveragePanel
            coverage={softDentCoverage}
            emptyMessage="SoftDent coverage details are unavailable in the admin console."
          />
          <div className="admin-audit-list admin-audit-list--spaced">
            <div className="admin-audit-item">
              <div className="admin-audit-item__header">
                <strong>Claims aggregate snapshot</strong>
                <span>{claimsSummary?.available ? "live aggregate exports" : "waiting on approved exports"}</span>
              </div>
              <div className="admin-audit-item__summary">
                True outstanding: {formatCurrency(claimsSummary?.true_outstanding_claims_amount ?? 0)} across{" "}
                {claimsSummary?.true_outstanding_claims_count ?? 0} claim(s)
              </div>
              <div className="admin-audit-item__summary">
                Unsubmitted: {formatCurrency(claimsSummary?.unsubmitted_claims_amount ?? 0)} across{" "}
                {claimsSummary?.unsubmitted_claims_count ?? 0} claim(s)
              </div>
              <div className="admin-audit-item__summary">
                Top outstanding payers:{" "}
                {topOutstandingPayers.length
                  ? topOutstandingPayers.map((item) => `${item.label} ${formatCurrency(item.amount)}`).join(" · ")
                  : "not available yet"}
              </div>
              <div className="admin-audit-item__summary">
                Top unsubmitted payers:{" "}
                {topUnsubmittedPayers.length
                  ? topUnsubmittedPayers.map((item) => `${item.label} ${formatCurrency(item.amount)}`).join(" · ")
                  : "not available yet"}
              </div>
            </div>
          </div>
        </article>

        <article className="admin-card">
          <h2>QuickBooks HAL Tool Readiness</h2>
          <p className="admin-card__summary">
            {quickbooksLiveRevenue?.available
              ? quickbooksLiveRevenue.excerpt
              : quickbooksLiveRevenue?.excerpt || "Live QuickBooks revenue summary is not available yet."}
          </p>
          <div className="admin-audit-list">
            {quickbooksLiveStatuses.map((item) => (
              <div key={item.topic} className="admin-audit-item">
                <div className="admin-audit-item__header">
                  <strong>{item.topic.toUpperCase()}</strong>
                  <span>
                    {item.health.toUpperCase()} · {item.source_backend} ·{" "}
                    <span className={confidenceBadgeClass(item.confidence_label, item.review_required)}>{item.confidence_label}</span>
                  </span>
                </div>
                <div className="admin-audit-item__summary">{item.excerpt}</div>
                <div className="admin-audit-item__summary">Last checked: {item.checked_at_utc || "unknown"}</div>
                <div className="admin-audit-item__summary">
                  {item.review_flags.length > 0 ? (
                    item.review_flags.map((flag) => (
                      <span
                        key={`${item.topic}-${flag}`}
                        className="dashboard-import-status-badge dashboard-import-status-badge--pending dashboard-import-status-badge--spaced"
                      >
                        {flag}
                      </span>
                    ))
                  ) : (
                    <span className="dashboard-import-status-badge">no review flags</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="admin-audit-list">
            {quickbooksTopics.map((item) => (
              <div key={item.topic} className="admin-audit-item">
                <div className="admin-audit-item__header">
                  <strong>{item.topic.toUpperCase()}</strong>
                  <span>{item.configured ? "Configured SQL" : "SDK only"}</span>
                </div>
                <div className="admin-audit-item__summary">
                  Query source: {item.query_source}. Legacy fallback count: {item.fallback_count}.
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="admin-card">
          <h2>QuickBooks Posting Queue</h2>
          <p className="admin-card__summary">
            Local review queue for QuickBooks Desktop drafts. Approval changes queue state only and does not post entries.
          </p>
          <dl className="admin-kv">
            <div>
              <dt>Pending review</dt>
              <dd>
                <Link className="admin-inline-link" to="/posting-queue?status=pending_review">
                  {pendingPostingQueueCount}
                </Link>
              </dd>
            </div>
            <div>
              <dt>Approved</dt>
              <dd>
                <Link className="admin-inline-link" to="/posting-queue?status=approved">
                  {approvedPostingQueueCount}
                </Link>
              </dd>
            </div>
            <div>
              <dt>Rejected</dt>
              <dd>
                <Link className="admin-inline-link" to="/posting-queue?status=rejected">
                  {rejectedPostingQueueCount}
                </Link>
              </dd>
            </div>
            <div>
              <dt>Total queued</dt>
              <dd>
                <Link className="admin-inline-link" to="/posting-queue">
                  {totalPostingQueueCount}
                </Link>
              </dd>
            </div>
          </dl>
        </article>

        <article className="admin-card admin-card--wide">
          <h2>Field Landing Window Compliance</h2>
          <p className="admin-card__summary">
            Evaluated: {fieldRegistry?.evaluated_at_utc ?? "unavailable"} · Fields within window:{" "}
            {fieldRegistry?.within_window_field_count ?? 0}/{fieldRegistry?.tracked_field_count ?? 0} · Compliance:{" "}
            {fieldRegistry?.compliance_percent ?? 0}%
          </p>
          {halFieldTimeframesQuery.isPending ? <p>Loading field timeframe registry...</p> : null}
          {halFieldTimeframesQuery.isError ? <p>Unable to load field timeframe registry.</p> : null}
          <div className="admin-timeframe-table-wrap">
            <table className="import-history-table admin-timeframe-table">
              <thead>
                <tr>
                  <th>Page</th>
                  <th>Field</th>
                  <th>Source</th>
                  <th>Window</th>
                  <th>Observed Age</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {fieldRegistryPages.length === 0 ? (
                  <tr>
                    <td colSpan={6}>No field-timeframe rows available.</td>
                  </tr>
                ) : (
                  fieldRegistryPages.flatMap((page) =>
                    page.fields.map((field) => (
                      <tr key={`${page.page_id}-${field.field_key}`}>
                        <td>{page.page_label}</td>
                        <td>{field.field_key}</td>
                        <td>{field.source_key}</td>
                        <td>{field.max_landing_minutes} min</td>
                        <td>{field.observed_age_minutes === null ? "unknown" : `${field.observed_age_minutes} min`}</td>
                        <td>
                          <span
                            className={landingWindowBadgeClass(
                              field.within_landing_window,
                              field.observed_age_minutes,
                              field.max_landing_minutes,
                            )}
                          >
                            {field.within_landing_window ? "within window" : "outside window"}
                          </span>
                        </td>
                      </tr>
                    )),
                  )
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="admin-card admin-card--wide">
          <h2>Recent Accounting Copilot Audits</h2>
          <div className="admin-audit-list">
            {accountingAudits.length === 0 ? <p>No accounting copilot audit events available.</p> : null}
            {accountingAudits.map((item) => (
              <div key={item.audit_id} className="admin-audit-item">
                <div className="admin-audit-item__header">
                  <strong>{item.mode}</strong>
                  <span>{item.created_at_utc}</span>
                </div>
                <div className="admin-audit-item__summary">Actor: {item.actor}</div>
                <div className="admin-audit-item__summary">{item.response_summary}</div>
                {postingQueueItemsBySourceAudit.get(item.audit_id)?.map((queueItem) => (
                  <div key={queueItem.queue_id} className="admin-audit-item__summary">
                    Queue handoff: {queueItem.status.replace("_", " ")} · {queueItem.queue_id} ·{" "}
                    {getPostingQueueHandoffModeLabel(queueItem.enqueue_mode)}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </article>

        <article className="admin-card admin-card--wide">
          <h2>Recent Posting Queue Activity</h2>
          <div className="admin-audit-list">
            {postingQueueItems.length === 0 ? <p>No posting queue items available.</p> : null}
            {postingQueueItems.map((item) => (
              <div key={item.queue_id} className="admin-audit-item">
                <div className="admin-audit-item__header">
                  <strong>{item.description}</strong>
                  <span>{item.status.replace("_", " ")}</span>
                </div>
                <div className="admin-audit-item__summary">Queue ID: {item.queue_id}</div>
                <div className="admin-audit-item__summary">
                  Amount: {item.amount.toFixed(2)} · Period: {item.accounting_period}
                </div>
                <div className="admin-audit-item__summary">Source audit: {item.source_audit_id}</div>
                <div className="admin-audit-item__summary">Draft lineage: {getPostingQueueActivityLineageLabel(item.enqueue_mode)}</div>
                {item.reviewed_at_utc ? (
                  <div className="admin-audit-item__summary">
                    Reviewed by {item.reviewer_actor} at {item.reviewed_at_utc}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </article>

        <article className="admin-card admin-card--wide">
          <h2>Recent HAL Audit Events</h2>
          <div className="admin-audit-list">
            {halAudits.length === 0 ? <p>No HAL audit events available.</p> : null}
            {halAudits.map((item) => (
              <div key={item.audit_id} className="admin-audit-item">
                <div className="admin-audit-item__header">
                  <strong>{item.actor}</strong>
                  <span>{item.created_at_utc}</span>
                </div>
                <div className="admin-audit-item__summary">{item.response_summary}</div>
              </div>
            ))}
          </div>
        </article>
      </section>
    </PageSurfaceShell>
  );
}
