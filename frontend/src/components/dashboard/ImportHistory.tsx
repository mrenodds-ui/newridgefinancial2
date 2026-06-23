import type { ImportRecord } from "../../types/dashboard";

export default function ImportHistory({ history }: { history: ImportRecord[] }) {
  if (!history.length) {
    return <div className="import-history-empty">No import history yet.</div>;
  }
  return (
    <section className="dashboard-import-history-card">
      <div className="dashboard-import-history-title">Import History</div>
      <div className="dashboard-import-table-scroll">
        <table className="dashboard-import-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Report Type</th>
              <th>File Name</th>
              <th>Imported At</th>
              <th>Rows</th>
              <th>Status</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {history.map((rec) => (
              <tr key={rec.id}>
                <td>{rec.source}</td>
                <td>{rec.reportType}</td>
                <td>{rec.fileName}</td>
                <td>{new Date(rec.importedAt).toLocaleString()}</td>
                <td>{rec.rowCount}</td>
                <td>
                  {rec.status === "success" && <span className="dashboard-import-status-badge">Success</span>}
                  {rec.status === "error" && (
                    <span className="dashboard-import-status-badge dashboard-import-status-badge--error">Error</span>
                  )}
                  {rec.status === "pending" && (
                    <span className="dashboard-import-status-badge dashboard-import-status-badge--pending">Pending</span>
                  )}
                </td>
                <td>{rec.errorMessage ? rec.errorMessage : <span className="empty-cell">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
