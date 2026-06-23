import type { FinancialTransactionDiagnostics } from "../../api/client";

function badgeClass(active: boolean) {
  return active ? "dashboard-import-status-badge" : "dashboard-import-status-badge dashboard-import-status-badge--pending";
}

function formatToken(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ").replaceAll("-", " ") : "unknown";
}

type TransactionDiagnosticsCardProps = {
  diagnostics?: FinancialTransactionDiagnostics | null;
};

export function TransactionDiagnosticsCard({ diagnostics }: TransactionDiagnosticsCardProps) {
  if (!diagnostics) {
    return <div className="admin-audit-item">Transaction diagnostics are unavailable.</div>;
  }

  return (
    <div className="admin-audit-item">
      <div className="admin-audit-item__header">
        <strong>SoftDent Transaction Diagnostics</strong>
        <span className={badgeClass(Boolean(diagnostics.dataSyncTransactionEmitted))}>
          {diagnostics.dataSyncTransactionEmitted ? "live DataSync transaction" : "live DataSync missing"}
        </span>
      </div>
      <div className="admin-audit-item__summary">{diagnostics.summary}</div>
      <div className="admin-audit-item__summary">
        <span className={badgeClass(Boolean(diagnostics.transactionConfigured))}>
          configured: {diagnostics.transactionConfigured ? "yes" : "no"}
        </span>{" "}
        <span className={badgeClass(Boolean(diagnostics.dataSyncTransactionEmitted))}>
          datasync emitted: {diagnostics.dataSyncTransactionEmitted ? "yes" : "no"}
        </span>{" "}
        <span className={badgeClass((diagnostics.sqliteTransactionRows ?? 0) > 0)}>
          sqlite rows: {diagnostics.sqliteTransactionRows ?? 0}
        </span>
      </div>
      <div className="admin-audit-item__summary">
        Source mode: {formatToken(diagnostics.sourceMode)} · validation: {formatToken(diagnostics.validationStatus)}
      </div>
      <div className="admin-audit-item__summary">Latest extractor log: {diagnostics.latestExtractorLogModifiedAt ?? "missing"}</div>
      <div className="admin-audit-item__summary">DataExtractor updated: {diagnostics.dataExtractorBinaryModifiedAt ?? "missing"}</div>
      <div className="admin-audit-item__summary">DIRun semaphore updated: {diagnostics.dataExtractorSemaphoreModifiedAt ?? "missing"}</div>
      <div className="admin-audit-item__summary">Extractor run evidence: {formatToken(diagnostics.extractorRunEvidenceStatus)}</div>
    </div>
  );
}
