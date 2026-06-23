import type { FinancialHealthFlag } from "../../api/client";

function formatToken(value: string) {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}

function statusBadgeClass(status: string) {
  return status === "warning"
    ? "dashboard-import-status-badge dashboard-import-status-badge--pending"
    : status === "error"
      ? "dashboard-import-status-badge dashboard-import-status-badge--error"
      : "dashboard-import-status-badge";
}

type TransactionFeedStatusNoticeProps = {
  healthFlags?: FinancialHealthFlag[] | null;
};

export function TransactionFeedStatusNotice({ healthFlags }: TransactionFeedStatusNoticeProps) {
  const relevantFlags = (healthFlags ?? []).filter(
    (flag) => ["softdent_transaction_feed", "softdent_page_coverage"].includes(flag.key) && flag.status !== "ok",
  );

  if (!relevantFlags.length) {
    return null;
  }

  return (
    <div className="admin-audit-list admin-audit-list--spaced">
      {relevantFlags.map((flag) => (
        <div key={flag.key} className="admin-audit-item">
          <div className="admin-audit-item__header">
            <strong>{flag.key === "softdent_page_coverage" ? "Page coverage gaps" : "Transaction-backed coverage"}</strong>
            <span className={statusBadgeClass(flag.status)}>{flag.status}</span>
          </div>
          <div className="admin-audit-item__summary">{flag.message}</div>
          <div className="admin-audit-item__summary">
            {flag.sourceMode ? (
              <span className="dashboard-import-status-badge dashboard-import-status-badge--pending dashboard-import-status-badge--spaced">
                source mode: {formatToken(flag.sourceMode)}
              </span>
            ) : null}
            {flag.validationStatus ? (
              <span className="dashboard-import-status-badge dashboard-import-status-badge--pending dashboard-import-status-badge--spaced">
                validation: {formatToken(flag.validationStatus)}
              </span>
            ) : null}
          </div>
          {flag.key === "softdent_transaction_feed" ? (
            <div className="admin-audit-item__summary">SQLite transaction rows: {flag.sqliteTransactionRows ?? 0}</div>
          ) : null}
          {flag.action ? <div className="admin-audit-item__summary">Next step: {flag.action}</div> : null}
        </div>
      ))}
    </div>
  );
}
