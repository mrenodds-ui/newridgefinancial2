import type { ImportRecord } from "../../types/dashboard";
import "./importpanel.css";
import "./importhistoryvirtualized.css";

export default function ImportHistoryVirtualized({ history }: { history: ImportRecord[] }) {
  if (!history.length) {
    return <div className="import-history-empty">No import history yet.</div>;
  }

  return (
    <section className="dashboard-import-history-card">
      <div className="dashboard-import-history-title">Import History (Virtualized)</div>
      <div className="dashboard-import-table-scroll">
        {history.map((rec) => (
          <div key={rec.id} className="import-history-row">
            <span className="import-history-source">{rec.source}</span>
            <span className="import-history-type">{rec.reportType}</span>
            <span className="import-history-filename">{rec.fileName}</span>
            <span className="import-history-date">{new Date(rec.importedAt).toLocaleString()}</span>
            <span className="import-history-rows">{rec.rowCount}</span>
            <span className="import-history-status">{rec.status}</span>
            <span className="import-history-error">{rec.errorMessage ? rec.errorMessage : "—"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
